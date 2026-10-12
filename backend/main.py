"""FastAPI backend for the Campus Customs desk dashboard.

    uvicorn main:app --reload --port 8000     (run from this folder)
    http://localhost:8000        health + route index
    http://localhost:8000/docs   interactive docs

Two rules shape this file:

* **All shop data comes through MCP.** Every route reads and writes
  `../data/campus_customs_new.db` by calling a tool on the `campus-customs`
  MCP server. There is no direct SQL here.
* **Agents prepare, humans pay.** One MCP connection is opened here. The
  agents are handed a *filtered view* of it with `record_payment` removed, so
  a run can queue a proposal with `propose_payment` but cannot move a cent.
  `POST /approvals/{id}/approve` is the only thing in the system that calls
  `record_payment`, and it runs because a person clicked approve.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import audit
from agents import (
    AGENT_BLOCKED_TOOLS,
    MODEL_NAME,
    build_mcp_toolset,
    build_team,
    new_run,
    run_agent,
)
from models import RunLimits

HERE = Path(__file__).resolve().parent
HW5 = HERE.parent
PRISTINE_DB = HW5 / "data" / "campus_customs.db"
WORKING_DB = HW5 / "data" / "campus_customs_new.db"
APPROVALS_PATH = HW5 / "output" / "pending_approvals.json"

RESOLVED_STATUSES = {"resolved", "closed"}

BRIEF = """You are working ticket {ticket_id} for Campus Customs.

Read the ticket with list_tickets(ticket_id={ticket_id}), verify the facts
through the MCP tools, pull in whichever specialists own the parts you do not,
and leave the ticket updated.

You cannot pay for anything. If money needs to move, prepare it with
propose_payment and say clearly that it is waiting on a human.

Keep it tight — a handful of tool calls and at most one or two hand-offs."""


# --------------------------------------------------------------------- state


class AppState:
    """Live objects shared by the routes."""

    def __init__(self) -> None:
        self.mcp: Any = None            # the MCP connection, all tools
        self.agent_toolset: Any = None  # filtered view: no record_payment
        self.team: dict[str, Any] = {}
        self.runs: dict[str, dict] = {}
        self.lock = asyncio.Lock()


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the MCP connection once and keep it for the server's life."""
    state.mcp = build_mcp_toolset(prepare_only=False)
    state.agent_toolset = state.mcp.filtered(
        lambda _ctx, tool: tool.name not in AGENT_BLOCKED_TOOLS
    )
    state.team = build_team(state.agent_toolset)
    async with state.mcp:
        yield


app = FastAPI(
    title="Campus Customs desk API",
    version="1.0",
    summary="Tickets, agent runs, human payment approval, cash and reset.",
    lifespan=lifespan,
)

# The React dashboard runs on its own dev port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp_call(tool: str, args: dict | None = None) -> Any:
    """Call one MCP tool on behalf of a route.

    Routes use the unfiltered connection — the restriction is on the *agents*,
    whose toolset has `record_payment` filtered out. A human clicking approve
    is exactly the authority that filter exists to require.
    """
    result = await state.mcp.client.call_tool(tool, args or {})
    if result.data is not None:
        return result.data
    return json.loads(result.content[0].text)


def read_approvals() -> list[dict]:
    if not APPROVALS_PATH.exists() or APPROVALS_PATH.stat().st_size == 0:
        return []
    try:
        data = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def write_approvals(queue: list[dict]) -> None:
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS_PATH.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")


# -------------------------------------------------------------------- models


class RunRequest(BaseModel):
    wait: bool = Field(default=False, description="Block until the run finishes instead of polling /runs.")


class ApproveRequest(BaseModel):
    approved_by: str = Field(description="Name of the person clicking approve.")
    note: str | None = None


class RejectRequest(BaseModel):
    rejected_by: str
    reason: str | None = None


# -------------------------------------------------------------------- routes


@app.get("/", summary="Health check and route index")
async def root() -> dict:
    return {
        "service": "Campus Customs desk API",
        "status": "ok",
        "model": MODEL_NAME,
        "database": str(WORKING_DB.relative_to(HW5)),
        "data_access": "all shop data via the campus-customs MCP server",
        "routes": {
            "GET /tickets": "the three tickets with open/resolved status",
            "POST /tickets/{id}/run": "run the agent team on one ticket",
            "GET /runs/{run_id}": "status and report of a run",
            "GET /events": "recent agent events for the dashboard to poll",
            "GET /approvals": "payment proposals waiting on a human",
            "POST /approvals/{id}/approve": "a person approves — this is what moves cash",
            "POST /approvals/{id}/reject": "a person rejects; no money moves",
            "GET /cash": "current checking balance",
            "POST /reset": "restore the working database from the original",
        },
    }


@app.get("/tickets", summary="The three tickets and whether each is open or resolved")
async def get_tickets() -> dict:
    tickets = await mcp_call("list_tickets")
    today = await mcp_call("get_today")
    out = []
    for t in tickets:
        out.append({
            **t,
            "is_open": t["status"] not in RESOLVED_STATUSES,
            "is_resolved": t["status"] in RESOLVED_STATUSES,
            "state": "resolved" if t["status"] in RESOLVED_STATUSES else "open",
        })
    return {
        "as_of": today.get("date_today"),
        "count": len(out),
        "open": sum(1 for t in out if t["is_open"]),
        "resolved": sum(1 for t in out if t["is_resolved"]),
        "tickets": out,
    }


@app.get("/tickets/{ticket_id}", summary="One ticket")
async def get_ticket(ticket_id: int) -> dict:
    rows = await mcp_call("list_tickets", {"ticket_id": ticket_id})
    if not rows:
        raise HTTPException(404, f"No ticket {ticket_id}.")
    t = rows[0]
    return {**t, "is_open": t["status"] not in RESOLVED_STATUSES}


async def _execute_run(run_id: str, ticket_id: int) -> None:
    """Run the team on a ticket. Everything lands in the audit trail as it goes."""
    record = state.runs[run_id]
    deps = new_run(run_id, state.team, ticket_id=ticket_id, limits=RunLimits())
    audit.append({
        "kind": "run_start", "run_id": run_id, "ticket_id": ticket_id,
        "entry_agent": "boss", "source": "api", "model": MODEL_NAME,
        "limits": vars(deps.limits),
    })
    try:
        report = await run_agent("boss", BRIEF.format(ticket_id=ticket_id), deps)
        record["status"] = "complete"
        record["report"] = report.model_dump()
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        record["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        record["delegations"] = deps.budget["delegations"]
        record["usage"] = {
            "requests": deps.usage.requests,
            "total_tokens": deps.usage.total_tokens,
        }
        audit.append({
            "kind": "run_end", "run_id": run_id, "ticket_id": ticket_id,
            "source": "api", "status": record["status"],
            "delegations": record["delegations"], "usage": record["usage"],
        })


@app.post("/tickets/{ticket_id}/run", summary="Run the agent team on one ticket")
async def run_ticket(ticket_id: int, body: RunRequest | None = None) -> dict:
    rows = await mcp_call("list_tickets", {"ticket_id": ticket_id})
    if not rows:
        raise HTTPException(404, f"No ticket {ticket_id}.")

    run_id = f"ticket-{ticket_id}-{uuid.uuid4().hex[:8]}"
    state.runs[run_id] = {
        "run_id": run_id, "ticket_id": ticket_id, "status": "running",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "since_seq": audit.entry_count(),
    }

    wait = bool(body and body.wait)
    if wait:
        await _execute_run(run_id, ticket_id)
    else:
        asyncio.create_task(_execute_run(run_id, ticket_id))
    return state.runs[run_id]


@app.get("/runs/{run_id}", summary="Status and report of one agent run")
async def get_run(run_id: str) -> dict:
    record = state.runs.get(run_id)
    if record is None:
        raise HTTPException(404, f"No run {run_id}.")
    return record


@app.get("/runs", summary="All runs this server has started")
async def list_runs() -> dict:
    return {"runs": list(state.runs.values())}


@app.get("/events", summary="Recent agent events — what each agent said and which tools it used")
async def get_events(since: int = 0, limit: int = 60, run_id: str | None = None) -> dict:
    """Reads the append-only audit trail. Poll with `since` = the last `seq`
    seen and the dashboard gets only what is new."""
    trail_path = audit.TRAIL_PATH
    trail = json.loads(trail_path.read_text()) if trail_path.exists() else []

    events = []
    for e in trail:
        if e.get("seq", 0) <= since:
            continue
        if run_id and e.get("run_id") != run_id:
            continue
        kind = e.get("kind")
        item = {
            "seq": e.get("seq"), "at": e.get("at"), "kind": kind,
            "run_id": e.get("run_id"), "agent": e.get("agent"),
            "depth": e.get("depth"),
        }
        if kind == "step" and e.get("event") == "tool_call":
            item |= {"event": "tool_call", "tool": e.get("tool"),
                     "arguments": e.get("arguments"),
                     "said": f"called {e.get('tool')}"}
        elif kind == "step" and e.get("event") == "tool_result":
            item |= {"event": "tool_result", "tool": e.get("tool"),
                     "said": str(e.get("result", ""))[:600]}
        elif kind == "step":
            item |= {"event": e.get("event"), "said": e.get("text", "")[:600]}
        elif kind == "delegation":
            item |= {"event": "delegation", "from": e.get("from"), "to": e.get("to"),
                     "said": f"{e.get('from')} asked {e.get('to')}: {e.get('task','')[:300]}"}
        elif kind == "delegation_refused":
            item |= {"event": "delegation_refused", "from": e.get("from"),
                     "to": e.get("to"), "reason": e.get("reason"),
                     "said": f"refused ({e.get('reason')})"}
        elif kind == "agent_start":
            item |= {"event": "agent_start", "said": e.get("task", "")[:300]}
        elif kind == "agent_end":
            report = e.get("report") or {}
            item |= {"event": "agent_end", "said": report.get("summary", ""),
                     "tools_used": sorted({f["mcp_tool"] for f in report.get("facts", [])}),
                     "approvals_needed": report.get("approvals_needed", [])}
        else:
            item |= {"event": kind, "said": e.get("status") or e.get("detail") or ""}
        events.append(item)

    tail = events[-limit:]
    return {
        "since": since,
        "latest_seq": trail[-1]["seq"] if trail else 0,
        "returned": len(tail),
        "events": tail,
    }


@app.get("/approvals", summary="Payment proposals waiting on a human")
async def get_approvals(status: str | None = None) -> dict:
    queue = await mcp_call("list_pending_approvals")
    if status:
        queue = [p for p in queue if p["status"] == status]
    return {
        "count": len(queue),
        "pending": sum(1 for p in queue if p["status"] == "pending"),
        "approvals": queue,
    }


@app.post("/approvals/{approval_id}/approve",
          summary="A human approves — the only route that changes the cash balance")
async def approve(approval_id: int, body: ApproveRequest) -> dict:
    """Posts the queued payment for real.

    Until this is called the proposal has moved nothing. Here the backend calls
    `record_payment` on the MCP server, which writes the ledger row, lowers the
    balance and marks the invoice paid in one transaction, stamped with the
    name of the person who clicked approve.
    """
    if not body.approved_by.strip():
        raise HTTPException(400, "approved_by must name the person approving.")

    async with state.lock:
        queue = read_approvals()
        proposal = next((p for p in queue if p["id"] == approval_id), None)
        if proposal is None:
            raise HTTPException(404, f"No approval {approval_id}.")
        if proposal["status"] != "pending":
            raise HTTPException(
                409,
                f"Approval {approval_id} is already {proposal['status']}; no money moved.",
            )

        before = await mcp_call("get_cash_balance", {"account": proposal["account"]})
        try:
            payment = await mcp_call("record_payment", {
                "kind": proposal["kind"],
                "amount": proposal["amount"],
                "approved_by": body.approved_by.strip(),
                "ref_id": proposal["ref_id"],
                "account": proposal["account"],
                "memo": body.note or proposal["reason"],
            })
        except Exception as exc:
            audit.append({
                "kind": "approval_failed", "approval_id": approval_id,
                "approved_by": body.approved_by, "error": str(exc)[:500],
            })
            raise HTTPException(400, f"Payment refused by the MCP server: {exc}") from exc

        after = await mcp_call("get_cash_balance", {"account": proposal["account"]})
        proposal |= {
            "status": "approved",
            "money_moved": True,
            "approved_by": body.approved_by.strip(),
            "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "approval_note": body.note,
            "payment": payment,
        }
        write_approvals(queue)

    audit.append({
        "kind": "approval", "approval_id": approval_id, "decision": "approved",
        "approved_by": body.approved_by.strip(), "amount": proposal["amount"],
        "payment_id": payment.get("payment_id"),
        "balance_before": before["balance"], "balance_after": after["balance"],
    })
    return {
        "ok": True, "approval": proposal, "payment": payment,
        "balance_before": before["balance"], "balance_after": after["balance"],
    }


@app.post("/approvals/{approval_id}/reject", summary="A human rejects — no money moves")
async def reject(approval_id: int, body: RejectRequest) -> dict:
    async with state.lock:
        queue = read_approvals()
        proposal = next((p for p in queue if p["id"] == approval_id), None)
        if proposal is None:
            raise HTTPException(404, f"No approval {approval_id}.")
        if proposal["status"] != "pending":
            raise HTTPException(409, f"Approval {approval_id} is already {proposal['status']}.")
        proposal |= {
            "status": "rejected", "money_moved": False,
            "rejected_by": body.rejected_by, "rejection_reason": body.reason,
            "rejected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        write_approvals(queue)
    audit.append({
        "kind": "approval", "approval_id": approval_id, "decision": "rejected",
        "rejected_by": body.rejected_by, "amount": proposal["amount"],
    })
    return {"ok": True, "approval": proposal, "money_moved": False}


@app.get("/cash", summary="Current checking balance from cash_accounts")
async def get_cash(account: str = "checking") -> dict:
    balance = await mcp_call("get_cash_balance", {"account": account})
    if not balance.get("found"):
        raise HTTPException(404, f"No cash account {account!r}.")
    queue = read_approvals()
    pending = [p for p in queue if p["status"] == "pending"]
    return {
        "account": balance["account"],
        "balance": balance["balance"],
        "as_of": balance["date"],
        "pending_approvals": len(pending),
        "pending_total": round(sum(p["amount"] for p in pending), 2),
        "balance_if_all_approved": round(
            balance["balance"] - sum(p["amount"] for p in pending), 2
        ),
        "source": "cash_accounts via MCP get_cash_balance",
    }


@app.post("/reset", summary="Restore the working database from the untouched original")
async def reset() -> dict:
    """Copies `data/campus_customs.db` over `data/campus_customs_new.db` and
    clears the approval queue. The original is only ever read, never written.
    The audit trail is deliberately left intact — it is append-only history."""
    if not PRISTINE_DB.exists():
        raise HTTPException(500, f"Original database missing at {PRISTINE_DB}.")

    async with state.lock:
        shutil.copyfile(PRISTINE_DB, WORKING_DB)
        cleared = len(read_approvals())
        write_approvals([])
        state.runs.clear()

    cash = await mcp_call("get_cash_balance", {"account": "checking"})
    tickets = await mcp_call("list_tickets")
    audit.append({
        "kind": "reset", "source": "api",
        "balance_after_reset": cash["balance"],
        "approvals_cleared": cleared,
        "note": "working copy restored from data/campus_customs.db; original untouched",
    })
    return {
        "ok": True,
        "restored": "data/campus_customs_new.db from data/campus_customs.db",
        "original_untouched": True,
        "balance": cash["balance"],
        "tickets": [{"id": t["id"], "status": t["status"]} for t in tickets],
        "approvals_cleared": cleared,
        "audit_trail": "left intact — append-only history",
    }
