"""The Campus Customs agent team — five PydanticAI agents, fully connected.

Boss, Inventory, Accounting, Facilities and Customer Service. Each one gets:

* its role prompt from `prompts/<name>.md`, with the shared house rules in
  `prompts/_shop_rules.md` appended;
* the **same** MCP toolset, built from the `campus-customs` entry in the
  project-root `.mcp.json`, which is the only way any agent reaches shop data;
* an `ask_<other>` tool for each of the other four, so any agent can hand work
  to any other (5 x 4 = 20 delegation tools, full mesh);
* a structured `AgentReport` output tying every claim to the tool behind it.

Every step is appended to output/audit_trail.json as it happens.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset, StdioTransport
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

import audit
from models import (
    AGENT_BLURBS,
    AGENT_NAMES,
    AGENT_TITLES,
    AgentName,
    AgentReport,
    RunLimits,
    TeamDeps,
)

HERE = Path(__file__).resolve().parent
HW5 = HERE.parent
PROMPTS = HERE / "prompts"
MCP_SERVER_NAME = "campus-customs"


def find_mcp_config() -> Path:
    """Locate the .mcp.json that defines the campus-customs server.

    Prefers the one in this project (hw5/.mcp.json), which is what a fresh
    clone gets, then walks upward so it still works when the project sits
    inside a larger workspace that registers the server at its own root.
    """
    for candidate in (HW5, *HW5.parents):
        cfg = candidate / ".mcp.json"
        if cfg.exists():
            try:
                servers = json.loads(cfg.read_text()).get("mcpServers", {})
            except json.JSONDecodeError:
                continue
            if MCP_SERVER_NAME in servers:
                return cfg
    raise RuntimeError(
        f"No .mcp.json defining {MCP_SERVER_NAME!r} found at {HW5} or above it."
    )

# The Portkey key lives in the project-root .env. Walk upward so it is found
# whichever folder this is launched from. The value is never logged.
for _candidate in (HERE, *HERE.parents):
    if (_candidate / ".env").exists():
        load_dotenv(_candidate / ".env")
        break

# Only this model, through Portkey's OpenAI-compatible gateway.
MODEL_NAME = os.getenv("CAMPUS_CUSTOMS_MODEL", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is not set. Add it to the project-root .env "
            "(see backend/.env.example) and try again."
        )
    return key


def build_model() -> OpenAIResponsesModel:
    """`gpt-6-luna` on Portkey. The Responses endpoint is used because these
    agents call function tools."""
    client = AsyncOpenAI(api_key=require_api_key(), base_url=PORTKEY_BASE_URL)
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# Tools the agents may never call. `record_payment` is the only thing that
# moves cash, and it is reserved for the human-approval route in main.py:
# agents prepare a spend with `propose_payment` and a person approves it.
AGENT_BLOCKED_TOOLS = {"record_payment"}


def build_mcp_toolset(prepare_only: bool = True) -> MCPToolset:
    """The one door to shop data.

    Built from the same `.mcp.json` entry Claude Code uses, so the agents and
    the vibe coder are provably talking to the same server and the same
    database. There is deliberately no second, non-MCP tool layer.

    With `prepare_only` (the default) the toolset hides `record_payment`, so
    no agent can move money even if it tries — it can only queue a proposal.
    """
    config_path = find_mcp_config()
    cfg = json.loads(config_path.read_text())["mcpServers"][MCP_SERVER_NAME]

    # Script paths in the config may be relative to the config's own folder,
    # so a cloned copy of this project works without editing absolute paths.
    base = config_path.parent
    args = [
        str((base / a).resolve()) if a.endswith(".py") and not Path(a).is_absolute() else a
        for a in cfg["args"]
    ]
    command = cfg["command"]
    if command.endswith("python") or command.endswith("python3"):
        # Use the interpreter this process is running under, so the server
        # starts inside the same virtualenv that has fastmcp installed.
        command = sys.executable if Path(command).name == command else command

    toolset = MCPToolset(
        StdioTransport(command=command, args=args, keep_alive=True),
        id=MCP_SERVER_NAME,
    )
    if prepare_only:
        return toolset.filtered(lambda _ctx, tool: tool.name not in AGENT_BLOCKED_TOOLS)
    return toolset


def load_instructions(name: AgentName) -> str:
    role = (PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()
    rules = (PROMPTS / "_shop_rules.md").read_text(encoding="utf-8").strip()
    roster = "\n".join(
        f"- **{AGENT_TITLES[other]}** (`ask_{other}`) — {AGENT_BLURBS[other]}"
        for other in AGENT_NAMES
        if other != name
    )
    return (
        f"{role}\n\n{rules}\n\n"
        "## Who you can ask\n\n"
        "You can hand work to any of these, and they can hand work back to you:\n\n"
        f"{roster}\n\n"
        "Use the matching `ask_<role>` tool with one clear question and the "
        "facts they need. Their answer comes back as a structured report — "
        "carry its facts into your own `facts` list, crediting the same tool."
    )


# --------------------------------------------------------------- audit helpers


def _record_steps(run_id: str, agent_name: str, messages: list[Any], depth: int) -> None:
    """Append one audit entry per step of this agent's loop.

    Captures the model's own text, every MCP tool call with its arguments, and
    every tool result — enough to replay what the agent saw and did.
    """
    step = 0
    for message in messages:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ToolCallPart):
                    step += 1
                    audit.append({
                        "kind": "step", "run_id": run_id, "agent": agent_name,
                        "depth": depth, "step": step, "event": "tool_call",
                        "tool": part.tool_name, "arguments": part.args_as_dict(),
                        "tool_call_id": part.tool_call_id,
                    })
                elif isinstance(part, TextPart) and part.content.strip():
                    step += 1
                    audit.append({
                        "kind": "step", "run_id": run_id, "agent": agent_name,
                        "depth": depth, "step": step, "event": "model_text",
                        "text": part.content.strip()[:2000],
                    })
        elif isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolReturnPart):
                    step += 1
                    audit.append({
                        "kind": "step", "run_id": run_id, "agent": agent_name,
                        "depth": depth, "step": step, "event": "tool_result",
                        "tool": part.tool_name, "tool_call_id": part.tool_call_id,
                        "result": str(part.content)[:4000],
                    })


# ----------------------------------------------------------------- delegation


REFUSALS = {
    "depth": (
        "Refused: delegation depth limit reached. Answer with what you already "
        "have and note in your report what you could not confirm."
    ),
    "budget": (
        "Refused: this run has used its delegation budget. Finish with the "
        "facts you have."
    ),
    "repeat": (
        "Refused: that same question has already been asked of that agent in "
        "this run. Use the answer you were given."
    ),
}


async def _delegate(
    ctx: RunContext[TeamDeps],
    from_agent: AgentName,
    to_agent: AgentName,
    task: str,
    context: str,
) -> dict:
    """Run another agent as a sub-agent of this one, inside the shared budget."""
    deps = ctx.deps
    limits = deps.limits
    key = TeamDeps.task_key(from_agent, to_agent, task)

    reason = None
    if deps.depth >= limits.max_depth:
        reason = "depth"
    elif deps.budget["delegations"] >= limits.max_delegations:
        reason = "budget"
    elif key in deps.seen:
        reason = "repeat"

    if reason:
        audit.append({
            "kind": "delegation_refused", "run_id": deps.run_id, "from": from_agent,
            "to": to_agent, "reason": reason, "depth": deps.depth,
            "delegations_used": deps.budget["delegations"], "task": task[:500],
        })
        return {"delegated": False, "reason": reason, "message": REFUSALS[reason]}

    deps.seen.add(key)
    deps.budget["delegations"] += 1
    child = deps.child(to_agent)

    audit.append({
        "kind": "delegation", "run_id": deps.run_id, "from": from_agent,
        "to": to_agent, "depth": child.depth,
        "delegations_used": deps.budget["delegations"], "chain": child.chain,
        "task": task[:1000], "context": context[:1000],
    })

    prompt = f"{task}\n\nContext from {AGENT_TITLES[from_agent]}:\n{context}" if context else task
    report = await run_agent(to_agent, prompt, child)
    return {"delegated": True, "agent": to_agent, "report": report.model_dump()}


def _attach_delegation_tools(agent: Agent[TeamDeps, AgentReport], me: AgentName) -> None:
    """Give `me` an ask_<other> tool for each of the other four agents."""
    for other in AGENT_NAMES:
        if other == me:
            continue

        def make(target: AgentName = other, mine: AgentName = me):
            async def delegate(
                ctx: RunContext[TeamDeps], task: str, context: str = ""
            ) -> dict:
                return await _delegate(ctx, mine, target, task, context)

            delegate.__name__ = f"ask_{target}"
            delegate.__doc__ = (
                f"Hand work to the {AGENT_TITLES[target]} agent — {AGENT_BLURBS[target]}.\n\n"
                "Args:\n"
                f"    task: One clear question or instruction for {AGENT_TITLES[target]}.\n"
                "    context: Facts you already have so they do not re-read the same rows "
                "(ticket id, SKU, size, amounts).\n\n"
                "Returns their structured report. Ask only for what they own, one "
                "question at a time, and never the same question twice."
            )
            return delegate

        agent.tool(make())


# ---------------------------------------------------------------- team wiring


def build_team(toolset: Any | None = None) -> dict[str, Agent[TeamDeps, AgentReport]]:
    """Build all five agents sharing one model and one (prepare-only) MCP toolset."""
    model = build_model()
    toolset = toolset or build_mcp_toolset()
    team: dict[str, Agent[TeamDeps, AgentReport]] = {}

    for name in AGENT_NAMES:
        agent = Agent(
            model,
            name=f"campus-customs-{name}",
            deps_type=TeamDeps,
            output_type=AgentReport,
            instructions=load_instructions(name),
            toolsets=[toolset],
        )
        _attach_delegation_tools(agent, name)
        team[name] = agent

    return team


async def run_agent(name: AgentName, task: str, deps: TeamDeps) -> AgentReport:
    """Run one agent, auditing its start, every loop step, and its report."""
    agent = deps.registry[name]
    audit.append({
        "kind": "agent_start", "run_id": deps.run_id, "agent": name,
        "depth": deps.depth, "chain": deps.chain, "ticket_id": deps.ticket_id,
        "task": task[:1500],
    })
    try:
        result = await agent.run(
            task,
            deps=deps,
            usage=deps.usage,
            usage_limits=deps.usage_limits,
        )
    except Exception as exc:
        audit.append({
            "kind": "error", "run_id": deps.run_id, "agent": name,
            "depth": deps.depth, "error": type(exc).__name__, "detail": str(exc)[:1500],
        })
        raise

    _record_steps(deps.run_id, name, list(result.all_messages()), deps.depth)
    report = result.output
    audit.append({
        "kind": "agent_end", "run_id": deps.run_id, "agent": name,
        "depth": deps.depth, "chain": deps.chain,
        "report": report.model_dump(),
        "usage": {
            "requests": deps.usage.requests,
            "input_tokens": deps.usage.input_tokens,
            "output_tokens": deps.usage.output_tokens,
            "total_tokens": deps.usage.total_tokens,
        },
    })
    return report


def new_run(
    run_id: str,
    team: dict[str, Agent[TeamDeps, AgentReport]],
    ticket_id: int | None = None,
    limits: RunLimits | None = None,
) -> TeamDeps:
    """Fresh shared state for one top-level request, with its token budget."""
    limits = limits or RunLimits()
    return TeamDeps(
        run_id=run_id,
        ticket_id=ticket_id,
        limits=limits,
        registry=team,
        usage=RunUsage(),
        usage_limits=UsageLimits(
            request_limit=limits.request_limit,
            total_tokens_limit=limits.total_tokens,
        ),
    )
