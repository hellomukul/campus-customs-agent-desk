# Campus Customs agent team

Five PydanticAI agents that work the shop's open tickets. All shop data reaches
them through the MCP server in `../mcp_server/` — there is no second tool layer.

| Agent | Owns |
|---|---|
| **Boss** | Triage, decisions, the only one who approves money or price changes |
| **Inventory** | Stock by SKU/size, vendors, lead times, receiving goods |
| **Accounting** | Cash, invoices, recording payments, affordability |
| **Facilities** | The lease, rent amounts and dates, the landlord |
| **Customer Service** | What we can honestly promise, and the wording of the reply |

Every agent has an `ask_<other>` tool for each of the other four — 20 delegation
tools, full mesh — so any agent can hand work to any other.

## Layout

```
backend/
  main.py          FastAPI routes for the dashboard
  agents.py        the five agents, the MCP toolset, the delegation mesh
  models.py        AgentReport and its parts, TeamDeps, RunLimits
  audit.py         append-only writer for output/audit_trail.json
  run_tickets.py   work the open tickets end to end (CLI)
  check_wiring.py  no-LLM check of MCP, connectivity and the audit trail
  prompts/         one role prompt per agent + _shop_rules.md (shared)
```

## Setup

Dependencies come from the project venv at `../.venv` (see the root
`README.md`):

```bash
cd .. && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`PORTKEY_API_KEY` is read from the nearest `.env` walking up from this folder
(the project root has it). Model: `gpt-6-luna` through Portkey, for every agent.

## Running

```bash
../.venv/bin/python check_wiring.py          # no model calls, spends no tokens
../.venv/bin/python run_tickets.py           # all open tickets (CLI)
../.venv/bin/python run_tickets.py 101 103   # specific tickets
```

The API for the dashboard, from this folder:

```bash
../.venv/bin/uvicorn main:app --reload --port 8000
```

`http://localhost:8000` for the route index, `/docs` for interactive docs. See
the Problem 7 section of `../output/harness.md` for every route.

**Agents never move money.** They are given a view of the MCP toolset with
`record_payment` filtered out; a spend is queued with `propose_payment` and
only `POST /approvals/{id}/approve` — a human clicking approve — changes the
cash balance.

Writes go to `../data/campus_customs_new.db`. Reset the scenario any time:

```bash
cp ../data/campus_customs.db ../data/campus_customs_new.db
```

## Limits

`RunLimits` in `models.py` caps a run: depth 2, six delegations, 30 model
requests and 200k tokens across the whole team, with repeat hand-offs refused.
See the safety section of `../output/harness.md`.
