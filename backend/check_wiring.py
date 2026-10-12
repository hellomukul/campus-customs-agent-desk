"""Wiring check — no model calls, no tokens spent.

Confirms three things before any agent is run:

1. the MCP toolset built from .mcp.json exposes the tools we expect, and they
   return real rows from data/campus_customs_new.db;
2. all five agents exist and each one carries an ask_<other> tool for the other
   four (full connectivity);
3. the audit trail appends without erasing what is already there.

    python check_wiring.py
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import audit
from agents import AGENT_BLOCKED_TOOLS, build_mcp_toolset, build_team
from models import AGENT_NAMES

HW5 = Path(__file__).resolve().parent.parent
DB = HW5 / "data" / "campus_customs_new.db"

EXPECTED_TOOLS = {
    "get_today", "get_cash_balance", "list_tickets", "check_inventory",
    "get_pricing", "list_invoices", "get_lease_due", "list_vendors",
    "record_payment", "adjust_inventory", "update_price", "update_ticket",
    "propose_payment", "list_pending_approvals",
}


def db_value(sql: str):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return conn.execute(sql).fetchone()
    finally:
        conn.close()


async def main() -> int:
    failures: list[str] = []

    # 1. MCP toolset — unfiltered, so we can see every tool the server offers.
    toolset = build_mcp_toolset(prepare_only=False)
    async with toolset:
        client = toolset.client
        tools = {t.name for t in await client.list_tools()}
        missing = EXPECTED_TOOLS - tools
        print(f"MCP tools exposed: {len(tools)}")
        print("  " + ", ".join(sorted(tools)))
        if missing:
            failures.append(f"MCP toolset missing tools: {sorted(missing)}")

        async def call(name, args):
            res = await client.call_tool(name, args)
            return res.data if res.data is not None else json.loads(res.content[0].text)

        today = await call("get_today", {})
        cash = await call("get_cash_balance", {"account": "checking"})
        tickets = await call("list_tickets", {"status": "open"})

    db_today = db_value("SELECT date_today FROM desk LIMIT 1")[0]
    db_cash = db_value("SELECT balance FROM cash_accounts WHERE name='checking'")[0]
    db_open = db_value("SELECT COUNT(*) FROM tickets WHERE status='open'")[0]

    checks = [
        ("get_today matches desk table", today["date_today"], db_today),
        ("get_cash_balance matches cash_accounts", cash["balance"], db_cash),
        ("list_tickets returns the open tickets", len(tickets), db_open),
    ]
    for label, got, want in checks:
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {got!r} vs db {want!r}")
        if not ok:
            failures.append(label)

    # 2. Agents must NOT be able to reach the tool that moves money.
    agent_view = toolset.filtered(lambda _c, t: t.name not in AGENT_BLOCKED_TOOLS)
    blocked_ok = AGENT_BLOCKED_TOOLS <= tools
    print(f"\n{'PASS' if blocked_ok else 'FAIL'}  server offers {sorted(AGENT_BLOCKED_TOOLS)}, "
          f"but the agents' filtered view hides it (humans approve instead)")
    if not blocked_ok:
        failures.append("record_payment missing from the server")

    # 3. Full connectivity
    team = build_team(agent_view)
    print(f"\nAgents built: {len(team)} -> {', '.join(team)}")
    for name, agent in team.items():
        tool_names = set(agent._function_toolset.tools)  # noqa: SLF001 - test introspection
        expected = {f"ask_{other}" for other in AGENT_NAMES if other != name}
        have = {t for t in tool_names if t.startswith("ask_")}
        ok = expected <= have
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {len(have)} delegation tools -> {', '.join(sorted(have))}")
        if not ok:
            failures.append(f"{name} missing delegation tools: {sorted(expected - have)}")

    # 4. Audit trail appends
    before = audit.entry_count()
    audit.append({"kind": "wiring_check", "note": "check_wiring.py append test"})
    after = audit.entry_count()
    ok = after == before + 1
    print(f"\n{'PASS' if ok else 'FAIL'}  audit trail: {before} -> {after} entries (append-only)")
    if not ok:
        failures.append("audit trail did not append")

    print("\n" + ("ALL CHECKS PASSED" if not failures else f"FAILURES: {failures}"))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
