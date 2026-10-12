"""Work the open tickets with the agent team.

    python run_tickets.py            # every open ticket
    python run_tickets.py 101 103    # only these

Each ticket starts as one request to the Boss, who pulls in whichever
specialists the ticket needs. Everything is appended to
output/audit_trail.json; the run prints a short summary per ticket.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import audit
from agents import build_mcp_toolset, build_team, new_run, run_agent
from models import AgentReport, RunLimits

HW5 = Path(__file__).resolve().parent.parent

BRIEF = """You are working ticket {ticket_id} for Campus Customs.

Start by reading the ticket with list_tickets(ticket_id={ticket_id}), then work
it to a conclusion: verify the facts through the MCP tools, pull in whichever
specialists own the parts you do not, make the decisions that are yours, and
leave the ticket updated.

Keep it tight — a handful of tool calls and at most one or two hand-offs."""


async def open_ticket_ids(toolset) -> list[int]:
    async with toolset:
        res = await toolset.client.call_tool("list_tickets", {"status": "open"})
        data = res.data if res.data is not None else json.loads(res.content[0].text)
    return [t["id"] for t in data]


def summarise(ticket_id: int, report: AgentReport, deps) -> None:
    print(f"\n{'=' * 72}\nTICKET {ticket_id} — {report.agent}\n{'=' * 72}")
    print(f"\n{report.summary}\n")
    if report.delegated_to:
        print(f"Delegated to: {', '.join(report.delegated_to)}")
    if report.facts:
        print("\nFacts (each from an MCP tool):")
        for f in report.facts:
            print(f"  - {f.claim}  [{f.mcp_tool}: {f.value}]")
    if report.actions:
        print("\nActions taken:")
        for a in report.actions:
            print(f"  - {a.description}  [{a.mcp_tool}, approved by {a.approved_by}] -> {a.result}")
    if report.approvals_needed:
        print("\nWaiting on approval:")
        for ap in report.approvals_needed:
            amount = f" (${ap.amount:,.2f})" if ap.amount else ""
            print(f"  - {ap.what}{amount}: {ap.why}")
    print(f"\nRecommendation: {report.recommendation}")
    if report.customer_message:
        print(f"\nDraft message:\n{report.customer_message}")
    u = deps.usage
    print(
        f"\nUsage: {u.requests} requests, {u.total_tokens} tokens, "
        f"{deps.budget['delegations']} delegations"
    )


async def main() -> int:
    wanted = [int(a) for a in sys.argv[1:]]
    toolset = build_mcp_toolset()
    team = build_team(toolset)

    ticket_ids = wanted or await open_ticket_ids(toolset)
    print(f"Working tickets: {ticket_ids}")

    failures = 0
    async with toolset:
        for ticket_id in ticket_ids:
            run_id = f"ticket-{ticket_id}-{datetime.now():%Y%m%d-%H%M%S}"
            deps = new_run(run_id, team, ticket_id=ticket_id, limits=RunLimits())
            audit.append({
                "kind": "run_start", "run_id": run_id, "ticket_id": ticket_id,
                "entry_agent": "boss", "limits": vars(deps.limits),
                "model": __import__("agents").MODEL_NAME,
            })
            try:
                report = await run_agent("boss", BRIEF.format(ticket_id=ticket_id), deps)
                summarise(ticket_id, report, deps)
                status = "ok"
            except Exception as exc:
                failures += 1
                status = f"{type(exc).__name__}: {exc}"
                print(f"\nTICKET {ticket_id} FAILED — {status}")
            audit.append({
                "kind": "run_end", "run_id": run_id, "ticket_id": ticket_id,
                "status": status, "delegations": deps.budget["delegations"],
                "usage": {
                    "requests": deps.usage.requests,
                    "input_tokens": deps.usage.input_tokens,
                    "output_tokens": deps.usage.output_tokens,
                    "total_tokens": deps.usage.total_tokens,
                },
            })

    print(f"\nAudit trail: {audit.entry_count()} entries at output/audit_trail.json")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
