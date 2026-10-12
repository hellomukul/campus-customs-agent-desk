# Campus Customs — a five-agent operations desk

Homework 5. A small Yale apparel shop with three open tickets, worked by five
PydanticAI agents that reach the shop's data **only** through an MCP server,
behind a FastAPI backend and a React dashboard where a human approves anything
that costs money.

- **5 agents** — Boss, Inventory, Accounting, Facilities, Customer Service, fully
  connected: any agent can hand work to any other.
- **14 MCP tools** over a SQLite database. There is no second, non-MCP data path.
- **Agents cannot spend.** `record_payment` is filtered out of their toolset;
  they queue a proposal and a person clicks approve.
- Every agent-loop step is appended to `output/audit_trail.json`.

---

## 1. Requirements

- Python 3.11+ (built on 3.13)
- Node 18+ (built on 24) and npm
- A **Portkey API key** with access to `gpt-6-luna`

## 2. Set up

```bash
cd hw5

# Python environment — one venv for the MCP server, agents and API
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Your API key
cp .env.example .env
#   then edit .env and put your real PORTKEY_API_KEY in it
#   (.env is gitignored and is never committed)

# Dashboard dependencies
npm install --prefix frontend
```

## 3. Copy the original database to the working database

Two database files ship with the repo:

| File | Role |
|---|---|
| `data/campus_customs.db` | **The original.** Never written to. The reset source. |
| `data/campus_customs_new.db` | **The working copy.** Everything reads and writes this. |

The repo ships the working copy in its *finished* state (all three tickets
resolved, balance $160.00) as the evidence for Problem 9. **For a clean run,
copy the original over it first:**

```bash
cp data/campus_customs.db data/campus_customs_new.db
rm -f output/pending_approvals.json
```

That restores the opening state: checking **$3,400.00**, all three tickets
`open`, invoice 501 unpaid, `payments` empty.

> Both lines matter. The second clears the human-approval queue. If you restore
> the database but leave an old queue behind, the agents will read "invoice 501
> was already approved" from the queue while the database still shows it unpaid,
> conclude they are about to double-pay, and correctly refuse to act — which
> looks like the app doing nothing.

You can do the same thing at any time from the running app — the **Reset day**
button on the dashboard, or `curl -X POST http://localhost:8000/reset`. Both
leave `data/campus_customs.db` untouched, so you can always get back here.

## 4. Start the MCP server

The backend launches the MCP server itself over stdio, using the
`campus-customs` entry in `.mcp.json`, so **for normal use you do not need to
start it by hand** — skip to step 5.

To run it standalone (to poke at the tools, or to use it from Claude Code,
Cursor or Codex):

```bash
.venv/bin/python mcp_server/server.py            # stdio
.venv/bin/python mcp_server/server.py --http     # http://127.0.0.1:8002/mcp
```

To register it with a vibe coder, point it at this project's `.mcp.json`, or add
the same entry to your own config with absolute paths:

```json
{
  "mcpServers": {
    "campus-customs": {
      "command": "/absolute/path/to/hw5/.venv/bin/python",
      "args": ["/absolute/path/to/hw5/mcp_server/server.py"]
    }
  }
}
```

Tools and tables: `mcp_server/README.md`.

## 5. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

- Route index: <http://localhost:8000>
- Interactive docs: <http://localhost:8000/docs>

It opens the MCP connection on startup and keeps it for the life of the server.
It already allows CORS from the Vite dev origin.

Quick check that the agents and tools are wired up — **no model calls, costs
nothing**:

```bash
cd backend && ../.venv/bin/python check_wiring.py
```

## 6. Start the React dashboard

In a second terminal:

```bash
npm run dev --prefix frontend
```

Open <http://localhost:5173>. Point it elsewhere with
`VITE_API_BASE=http://host:port`.

## 7. Reset, then run all three tickets

1. **Reset** — click **Reset day** in the top bar (or `cp data/campus_customs.db
   data/campus_customs_new.db` with the server stopped). The balance should read
   **$3,400.00** and all three tickets should be `open`.
2. Put your name in the **on duty** box. Nothing can be approved without it.
3. Pick **#101 Bulldog tee** and click **Dispatch the team**. Watch the feed:
   each agent's tool calls and hand-offs appear live.
4. When it finishes, a payment proposal appears under **Needs your signature**.
   Nothing has been paid — the balance is still $3,400.00. Click **Approve** and
   watch it count down to $2,560.00.
5. **Dispatch the team** on #101 again. With the invoice paid, the Boss closes
   it out and the ticket gets its `RESOLVED` stamp.
6. Repeat for **#102 Rent due**: dispatch → approve the $2,400 rent → dispatch
   again → resolved. Balance $160.00.
7. **#103 Bulk discount** needs one run and no payment — there is nothing to
   approve, because the team decides not to spend.

Expect roughly 60–120 seconds per run.

> **These are language models, so runs are not identical.** The decisions have
> been stable across our runs — stock is never invented, the rent is always
> verified against the lease before it is proposed, and nothing is ever paid
> without a human — but the exact wording, the number of hand-offs and
> occasionally the final status will vary. A ticket sometimes stops at
> `in_progress` or `waiting_approval` and needs one more **Dispatch the team**
> to close. That is the agents being cautious, not a failure; the note they
> append to the ticket says what they are waiting on.
>
> The run recorded in `output/` is one such pass, captured in full in
> `output/audit_trail.json` and `output/resolved_tickets.json`. You can also drive it from the command
line without the dashboard:

```bash
cd backend && ../.venv/bin/python run_tickets.py 101 102 103
```

> Tickets 101 and 102 need **two** runs each: one to investigate and queue the
> payment, then one after you approve it. That is the design — agents prepare,
> humans pay.

---

## What's in here

```
hw5/
├── AI_prompts.md        every prompt used to build this, per problem
├── requirements.txt     Python dependencies
├── .env.example         copy to .env and add your key
├── .mcp.json            the campus-customs MCP server entry
├── data/                original + working database
├── mcp_server/
│   ├── server.py        14 MCP tools over the SQLite database
│   └── README.md        tool-by-tool reference
├── backend/
│   ├── main.py          FastAPI routes for the dashboard
│   ├── agents.py        the five agents, MCP toolset, delegation mesh
│   ├── models.py        AgentReport, TeamDeps, RunLimits
│   ├── audit.py         append-only audit trail writer
│   ├── run_tickets.py   work tickets from the command line
│   ├── check_wiring.py  no-LLM connectivity check
│   └── prompts/         one prompt per agent + shared house rules
├── frontend/            React + Vite + TypeScript dashboard
└── output/
    ├── harness.md            the full reference: tables, tools, agents, routes, safety
    ├── design.md             dashboard design rationale
    ├── desk_tickets.html     plan vs. run per ticket, cash ledger, reflection
    ├── resolved_board.html   the three resolved tickets with screenshots
    ├── resolved_tickets.json machine-readable outcomes
    ├── mcp_smoke.json        MCP connection evidence
    ├── audit_trail.json      every agent-loop step, append-only
    └── github_url.txt        this repository
```

**Start with `output/harness.md`** — database tables, all 14 MCP tools and the
table each uses, the five agents, the API routes, the dashboard, the safety
rules and token limits, and the final results.

Then open `output/desk_tickets.html` and `output/resolved_board.html` in a
browser (just double-click them — no server needed).

## Safety model in one paragraph

Agents read the shop only through MCP, and every number in a report is tagged
with the tool that produced it. Write tools refuse unsafe changes: no overdraft,
no double payment, no negative stock, no price at or below cost, no unsigned
write. The one tool that moves cash is withheld from the agents entirely — they
call `propose_payment`, which validates and queues, and only
`POST /approvals/{id}/approve` posts it, stamped with the approver's name. Run
limits (depth 2, six hand-offs, 30 requests, 200k tokens, repeat-question guard)
stop a fully connected mesh from looping; the guard fired for real on ticket 103.
