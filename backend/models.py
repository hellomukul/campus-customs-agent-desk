"""Data types for the Campus Customs agent team.

Three groups:

* `AgentName` and `AGENT_TITLES` — who is on the team.
* `AgentReport` and its parts — the structured answer every agent must return,
  built so a reviewer can see which MCP tool backed each claim.
* `TeamDeps` and `RunLimits` — the per-run state the agents share: the audit
  trail, the delegation budget, and the registry that lets any agent hand work
  to any other.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters for typing
    from pydantic_ai import Agent

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_NAMES: tuple[AgentName, ...] = (
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
)

AGENT_TITLES: dict[AgentName, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}

AGENT_BLURBS: dict[AgentName, str] = {
    "boss": (
        "the owner — triages tickets, decides who works what, approves spending "
        "and discounts, and is the only one who signs off on money"
    ),
    "inventory": (
        "stock on hand by SKU and size, restocks, vendors and lead times, and "
        "receiving goods into inventory"
    ),
    "accounting": (
        "cash balance, vendor invoices, recording payments, and whether the shop "
        "can actually afford something"
    ),
    "facilities": (
        "the shop premises — the lease, rent amounts and due dates, and landlord "
        "correspondence"
    ),
    "customer_service": (
        "the customer's side — what we can honestly promise, substitutions, "
        "wording the reply, and quoting prices to a buyer"
    ),
}


class FactChecked(BaseModel):
    """One claim and the MCP tool call that backs it.

    Agents are told never to state a shop number without filling one of these
    in, which is what makes a run reviewable after the fact.
    """

    claim: str = Field(description="The fact, stated plainly, e.g. 'CC-TEE-WHITE size S is out of stock'.")
    mcp_tool: str = Field(description="The MCP tool that produced it, e.g. 'check_inventory'.")
    value: str = Field(description="The value the tool actually returned, e.g. 'qty=0'.")


class ActionTaken(BaseModel):
    """A change this agent made to the database through an MCP write tool."""

    description: str = Field(description="What changed, in one line.")
    mcp_tool: str = Field(description="The MCP write tool used.")
    approved_by: str = Field(description="Who authorised it.")
    result: str = Field(description="What the tool returned, e.g. 'payment_id=1, balance_after=2560.0'.")


class ApprovalNeeded(BaseModel):
    """Something the agent will not do without a human (or the Boss) saying yes."""

    what: str = Field(description="The action being held back.")
    why: str = Field(description="Why it needs approval — money, a price change, a customer promise.")
    amount: float | None = Field(default=None, description="Dollar amount at stake, if any.")


class AgentReport(BaseModel):
    """What every agent returns, whether it was asked directly or delegated to."""

    agent: str = Field(description="Which agent is reporting.")
    summary: str = Field(description="Two or three sentences: what you were asked, what you found, what you did.")
    facts: list[FactChecked] = Field(default_factory=list, description="Every shop number you used, with its MCP source.")
    actions: list[ActionTaken] = Field(default_factory=list, description="Database changes you made. Empty if none.")
    approvals_needed: list[ApprovalNeeded] = Field(default_factory=list, description="What you are holding for approval.")
    delegated_to: list[str] = Field(default_factory=list, description="Other agents you asked for help.")
    recommendation: str = Field(description="What you think should happen next, in plain language.")
    customer_message: str | None = Field(default=None, description="Draft wording for the requester, when one is needed.")


@dataclass
class RunLimits:
    """Caps that keep a five-agent mesh from running away.

    With full connectivity any agent can call any other, so without these a
    single ticket could fan out indefinitely. These are deliberately tight:
    the three open tickets each need two or three hops at most.
    """

    max_depth: int = 2           # Boss -> specialist -> one more hop, then stop.
    max_delegations: int = 6     # Total hand-offs allowed in one run.
    request_limit: int = 30      # Model requests across the whole run, all agents.
    total_tokens: int = 200_000  # Token ceiling for the whole run, all agents.


@dataclass
class TeamDeps:
    """Shared state for one run of the team.

    Carried through every delegation, so depth and the delegation budget are
    counted across the whole team rather than per agent.
    """

    run_id: str
    ticket_id: int | None = None
    limits: RunLimits = field(default_factory=RunLimits)
    depth: int = 0
    # Shared by reference with every child, so the delegation budget is spent
    # across the whole team rather than reset at each hop.
    budget: dict[str, int] = field(default_factory=lambda: {"delegations": 0})
    chain: list[str] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)
    registry: dict[str, "Agent[TeamDeps, AgentReport]"] = field(default_factory=dict)
    usage: Any = None
    usage_limits: Any = None

    def child(self, to_agent: AgentName) -> "TeamDeps":
        """A copy for the delegate: one level deeper, same shared counters."""
        return TeamDeps(
            run_id=self.run_id,
            ticket_id=self.ticket_id,
            limits=self.limits,
            depth=self.depth + 1,
            budget=self.budget,
            chain=[*self.chain, to_agent],
            seen=self.seen,
            registry=self.registry,
            usage=self.usage,
            usage_limits=self.usage_limits,
        )

    @staticmethod
    def task_key(from_agent: str, to_agent: str, task: str) -> str:
        """Fingerprint of a hand-off, used to refuse the same question twice."""
        digest = hashlib.sha1(task.strip().lower().encode()).hexdigest()[:12]
        return f"{from_agent}->{to_agent}:{digest}"
