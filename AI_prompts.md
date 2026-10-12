# AI Prompt Log — Homework 5

A record of the prompts I gave the AI while working this assignment, kept per
problem and in the order I typed them.

**How to use this file**

- One `##` section per problem, with the problem number and title.
- Prompts are kept verbatim inside the code fences — typos, shorthand and all.
  The fences keep Markdown from reformatting anything.
- **Follow-up prompts** hold any correction or refinement after the first
  result; the section is empty where there weren't any.
- **Notes** is a short record of what the step produced.

---

## Problem 1 — Set up the hw5 folder, data, and prompt log

**Prompts**

1.
```text
AI Assignment 5: /j
```

2.
```text
/folder-joke-proof hw5
```

3.
```text
create a AI_Prompts.md file and keep logging my prompts in the file. It should record problem number and title, prompts and followuup prompts if needed. Also, unzip the data file - data(1).zip and place in the data folder.
```

**Follow-up prompts**

1.
```text
This is step 1.
create a AI_Prompts.md file and keep logging my prompts in the file including this one. It should record problem number and title, prompts and followuup prompts if needed. Create the folder structure
Look at the previous hw project structure first so you don't overwrite or mess up anything that is already there. Also, unzip the data file in hw5 folder - data (1).zip and place in the data folder.
```

2.
```text
Keep it as AI_prompts.md, this is a separate assignment and hence data would be different.
```

**Notes**

- Prompt 1 was a typo (`/j` matched no skill or command), so nothing ran for it.
- `joke.txt` written into `homework/hw5/` as the folder proof.
- Checked `hw1`–`hw4` first for the existing layout before creating anything;
  `hw5/` held only `joke.txt` and `data (1).zip`, so nothing was overwritten.
- Scaffolded `data/`, `output/`, and `prompts/` to match the earlier homework
  folders (`.gitkeep` in the two empty ones).
- Extracted `data (1).zip` with `unzip -n` (never overwrite) → the archive holds
  a single file, `data/campus_customs.db`, now at `hw5/data/campus_customs.db`.
  Verified as a valid SQLite database with tables: `cash_accounts`, `desk`,
  `inventory`, `invoices`, `leases`, `payments`, `pricing`, `tickets`,
  `vendors`. It shares a filename with the hw4 database but is a different
  dataset — hw5 is a separate assignment.
- This file, named `AI_prompts.md` to match `hw1`–`hw4`.

---

## Problem 2 — Study the Campus Customs database

**Prompts**

1.
```text
Let's do problem 2, which is studying the Campus Customs database. Open data/campus_customs.db and go through every table and its fields. Make a copy of the original database called data/campus_customs_new.db, since we'll be using this copy to update the data in later steps. Keep the original database untouched so we can reset it whenever needed. Also study the three open tickets and see how they link to the other tables. Create output/harness.md and for every table, list its fields and add one short line explaining why that table matters for the agents. Make sure you cover all the tables and their fields, and that the database copy and documentation are based on what's actually in the database.
```

**Follow-up prompts**

*(none)*

**Notes**

- Read the schema and every row straight out of the database (opened read-only,
  `mode=ro`) — the documentation is from the actual data, not assumed.
- Copied with `cp -n` to `data/campus_customs_new.db`; verified identical by MD5
  and confirmed the original is still untouched afterward.
- 9 tables documented in `output/harness.md`, every field listed: `desk`,
  `cash_accounts`, `vendors`, `invoices`, `leases`, `pricing`, `inventory`,
  `payments` (empty — the agents' write/audit target), `tickets`.
- Key findings: today is `2026-08-31`; checking holds $3,400 against $3,240 of
  known obligations; invoice 501 is 3 days overdue; `CC-TEE-WHITE`/`S` and
  `CC-MUG-CREST`/`OS` are at zero stock.
- The three open tickets: #101 customer order for the out-of-stock tee, linked
  by FK to the overdue reprint invoice for that same SKU/size; #102 rent notice
  linked by FK to lease 1 ($2,400 due 2026-09-02); #103 bulk hoodie discount
  with no FK links, short 12 units in size M.
- Only `tickets.lease_id`/`invoice_id` and `invoices.vendor_id` are real foreign
  keys; `sku`/`size` and `payments.ref_id`/`account` are soft links the agents
  must validate themselves.

---

## Problem 3 — Build the MCP server

**Prompts**

1.
```text
Let's do problem 3, which is building the MCP server. Create an MCP server in the mcp_server/ folder using FastMCP and connect it to data/campus_customs_new.db. For now, build three tools that we will need to help resolve the three open tickets in the database, tickets 101, 102, and 103. Look at the actual tickets and the related tables to decide what each tool should do. Give the tools clear names and make sure they use the information in the database instead of making anything up. We don't need to connect to or run the MCP server yet, and we'll add more tools to it in later steps. In output/harness.md, list each of the three tools, which table it reads, which ticket it helps resolve (101, 102, or 103), and one sentence explaining why that tool is useful for that specific ticket. Also create a short mcp_server/README.md explaining what the MCP server is for, which database file it uses, and the three tools it has. Make sure the ticket numbers and tool explanations match the actual data in the database.
```

**Follow-up prompts**

*(none)*

**Notes**

- Created `mcp_server/server.py` (FastMCP, named `campus-customs`), pointed at
  `data/campus_customs_new.db` and opened read-only — the original database is
  still untouched. Also added `mcp_server/requirements.txt`.
- Three tools, chosen from what the open tickets actually need:
  - `check_inventory` reads `inventory` → ticket **101** (`CC-TEE-WHITE`/`S` is
    at qty 0, so the order cannot be filled).
  - `get_lease_due` reads `leases` (plus `desk.date_today` for the day count) →
    ticket **102** (lease 1, $2,400, due 2026-09-02, 2 days out).
  - `get_pricing` reads `pricing` → ticket **103** (`CC-HOOD-NAVY` cost $22 vs
    list $58, the floor for a bulk discount).
- Followed the house style of the lecture 9 FastMCP server (stdio by default,
  `--http` flag). Dates are measured against `desk.date_today`, not the system
  clock.
- Did not connect or serve it, as instructed, but did call the three functions
  directly against the database to confirm they return real rows and that all
  three register as tools. Verified: ticket 101 → `qty_on_hand 0`,
  `can_fulfill false`; ticket 102 → `days_until_due 2`; ticket 103 → cost 22.00
  / list 58.00, and `CC-HOOD-NAVY`/`M` short 12 of the 20 requested.
- Documented in `mcp_server/README.md` and in a new "MCP server — Problem 3"
  section of `output/harness.md` (tool → table → ticket → why).

---

## Problem 4 — Connect the MCP server to the vibe coder and smoke-test it

**Prompts**

1.
```text
Let's do step 4, which is connecting the MCP server to Claude Code, Codex, or Cursor so it can use the tools. Add the MCP server we built in mcp_server/ to this project and save the connection JSON in .mcp.json at the project root, or use the local MCP server configuration file that the vibe coder supports. Then test each of the three MCP tools and save the results in output/mcp_smoke.json. For every tool, include the prompt I used with the vibe coder, the tool name, and the actual tool output. Make sure the outputs match the values in data/campus_customs_new.db. Update the file with the evidence for all three tools, and make sure the MCP connection and tool calls actually work.
```

**Follow-up prompts**

*(none)*

**Notes**

- Registered the server as `campus-customs` in the project-root `.mcp.json`
  (`/Users/hellomukul/Desktop/aifoundations/.mcp.json`), matching how
  `yale-som-courses` and `outlook` are configured there.
- Created `mcp_server/.venv` with FastMCP 4.1.0 and pointed the config at that
  interpreter, so the entry does not depend on the ambient `python3`.
- Claude Code reads `.mcp.json` at session start, so `campus-customs` was not
  live in the current session. To get real evidence anyway, the server was
  launched from that exact config entry and driven over the MCP stdio protocol
  (`initialize` → `tools/list` → `tools/call`). `tools/list` returned all three
  tools.
- `output/mcp_smoke.json` records, per tool: the prompt, the tool name and
  arguments, the verbatim tool output, the SQL used to re-check it, the matching
  rows from `data/campus_customs_new.db`, and a per-field match result. 12
  assertions across the three tools, all matching; `all_calls_succeeded` and
  `all_outputs_match_database` are both true.
- Results — 101: `CC-TEE-WHITE`/`S` `qty 0`, `can_fulfill false`. 102: lease 1,
  $2,400, due 2026-09-02, `days_until_due 2` from the desk date. 103:
  `CC-HOOD-NAVY` cost $22 / list $58, a $45 offer clearing cost by $23/unit.
- Added a "MCP connection — Problem 4" section to `output/harness.md`.

---

## Problem 5 — Build the agent team and extend the MCP server

**Prompts**

1.
```text
Let's do step 5, which is building the agent team and adding more tools to the MCP server. Build five agents for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Give each agent its own prompt file in `backend/prompts/`, put the data types in `backend/models.py`, and keep the agent files under `backend/`. Make sure all five agents can delegate tasks to any of the other agents when they need help, so they have full connectivity. Use `PORTKEY_API_KEY` for AI calls and only `gpt-6-luna` through Portkey for every agent. Write detailed prompts in your own words for each role, covering the shop rules and everything that agent needs to do, rather than using short, generic prompts.

Also add any tools the agents need to resolve the open tickets to the existing MCP server in `mcp_server/`. All shop information must come through the MCP server using `data/campus_customs_new.db`. Don't create a separate layer of shop tools that bypasses MCP. Make sure the agents append information to `output/audit_trail.json` as they run, recording enough detail for each agent-loop step to be reviewed later, and never erase the existing audit trail when adding new entries.

Update `output/harness.md` to list every agent and every MCP tool, including the new ones, and mention which database table each tool uses. Add a short safety section covering the rules agents should follow when dealing with customers and money, along with limits to keep token usage under control. Update `mcp_server/README.md` so the tool list matches the tools we have now. Test that the agents can delegate work to one another and use the MCP tools to get real information from the working database.
```

**Follow-up prompts**

*(none)*

**Notes**

- **MCP server** grew from 3 tools to 12. New read tools: `get_today` (desk),
  `get_cash_balance` (cash_accounts), `list_tickets` (tickets), `list_invoices`
  (invoices), `list_vendors` (vendors). New write tools: `record_payment`
  (payments + cash_accounts + invoices, one transaction), `adjust_inventory`
  (inventory), `update_price` (pricing), `update_ticket` (tickets). Read tools
  open the database read-only; writes require a non-empty `approved_by` and
  refuse overdrafts, double payments, negative stock, below-cost prices and
  invalid ticket statuses. Guard rails were tested on a throwaway copy first.
- **Five agents** in `backend/` on PydanticAI, all on `gpt-6-luna` through
  Portkey with `PORTKEY_API_KEY` read from the project-root `.env` (never
  printed). Types in `backend/models.py`, a role prompt each in
  `backend/prompts/` plus a shared `_shop_rules.md` covering the house rules.
- **Full connectivity**: each agent gets an `ask_<other>` tool for the other
  four — 20 delegation tools. Confirmed by `backend/check_wiring.py`, which also
  verifies the 12 MCP tools and that their values match the working database
  (no model calls, so it costs nothing to run).
- **No bypass layer**: the agents' only shop tools are the MCP toolset, built
  from the same `campus-customs` entry in the project-root `.mcp.json` that
  Claude Code uses.
- **Audit trail** is append-only — `audit.append` reads the existing file, adds
  one entry and writes via a temp file; a corrupt file is moved aside, never
  replaced. Entry kinds: run_start, agent_start, step (model text / MCP tool
  call with arguments / tool result), delegation, delegation_refused, agent_end
  with the report and usage, error, run_end.
- **Token limits** in `RunLimits`, shared across the team: depth 2, 6
  delegations, 30 model requests, 200k tokens, plus a fingerprint guard that
  refuses a repeated question.
- **Live test** — reset the working copy, then ran all three tickets. Real
  delegation happened (Boss → Inventory/Accounting/Facilities/Customer Service,
  and Facilities → Accounting at depth 2) and real rows changed: invoice 501
  paid ($840) and rent paid ($2,400), balance 3,400 → 160, two `payments` rows
  signed by Boss, tickets 101 `in_progress` / 102 `resolved` / 103
  `waiting_approval` with notes appended rather than overwritten. The Boss
  refused the bulk discount on ticket 103. 236 audit entries over four runs,
  contiguous `seq`, all five agents represented. Original database untouched.
- Updated `mcp_server/README.md` to all 12 tools and added the agent roster,
  tool/table map, safety rules and token limits to `output/harness.md`.

---

## Problem 6 — Plan how the agents should resolve the three tickets

**Prompts**

1.
```text
Let's do step 6, which is planning how the agents should resolve the three open tickets before we wire the backend. Create `output/desk_tickets.html` as a page I can open by double-clicking, with one tab each for tickets 101, 102, and 103, plus empty Cash and Reflection tabs for later steps. The Cash and Reflection tabs can be blank or just have a short "coming later" note for now.

For each ticket tab, write an Expected section in my own words explaining how I think the team should handle that ticket. Include which agent the Boss should call first and why, all the agent delegations I expect to happen, and which MCP tools should be used. Don't have the Boss call every agent for every ticket. Look at the actual tickets and database information to make a sensible plan for each one, and explain why those agents and tools are needed. Leave space for an Actual section that we'll fill in after running the agents. For now, only fill in the Expected sections and leave the Actual sections empty. Make sure all three tickets have their own plans and the page is easy to read.
```

**Follow-up prompts**

1.
```text
resolve this.
```
*(asked in a forked side session, about the Step 7 caveat flagged at the end of Problem 6 — whether the Expected predictions hold against the Problem 5 run)*

**Notes**

- Created `output/desk_tickets.html` — a single self-contained file (no server,
  no external assets), black-and-pink per the project style. Five tabs: 101,
  102, 103, Cash, Reflection, switchable by click or arrow keys.
- Each ticket tab opens with a strip of the real ticket/database figures, then
  an **Expected** section: which agent the Boss should call first and why, the
  delegations I expect (with a small chain diagram), which agents should
  deliberately stay out and why, a tool → table → reason table, and how I
  expect the ticket to end.
- Deliberately different plans per ticket, not five agents on everything:
  - **101** → Inventory first (stock is the gate), then Accounting (invoice 501
    blocks the reprint), then Customer Service. Facilities excluded — rent only
    matters as a number Accounting subtracts.
  - **102** → Facilities first (the email is a claim to verify against lease 1),
    then Accounting. Inventory and Customer Service excluded — no stock angle,
    and a landlord is not a retail customer.
  - **103** → Inventory first (8 of 20 on hand makes the discount moot), then
    Customer Service; the Boss reads `get_pricing` himself rather than
    delegating a single lookup. Accounting only if a restock is actually
    ordered; Facilities not at all.
- **Actual** sections left empty on all three, each with a checklist of what to
  fill in from `output/audit_trail.json`. Cash and Reflection tabs carry a
  short "coming later" note.
- Verified in a browser: tabs switch correctly, the right panel shows, no
  console errors. (Served temporarily for the check; the file itself opens by
  double-clicking.)
- Note: the Expected sections are the plan written independently of the
  Problem 5 run, so Step 7 can compare them honestly.

---

**Follow-up resolution — Expected vs. the recorded run**

Checked the three Expected plans against `output/audit_trail.json` (the Problem 5
run). Scored on first call, delegations, tools and outcome:

- **102 — exact match**, including the hedged depth-2 `Facilities -> Accounting`
  hop. All 7 predicted tools called, none extra.
- **103 — match.** Boss called Inventory first, used `get_pricing` himself
  rather than delegating it, never called `update_price`, left it
  `waiting_approval`. Accounting and Facilities stayed out as planned.
- **101 — partly wrong, as suspected.** First call (Inventory), all 10 predicted
  tools and the outcome were right, but I predicted 3 delegations and only 2
  happened: **Customer Service was never called**. The Boss drafted the customer
  message himself. The hedged `Inventory -> Accounting` depth-2 hop also did not
  happen — Inventory read `list_invoices` directly instead.
- **Unplanned behaviour: specialists write ticket status.** Not in any Expected
  section. On ticket 102 both Accounting and Facilities set the ticket to
  `waiting_approval` before the Boss set `resolved`; on 103 Customer Service set
  `in_progress` first. Three agents wrote to one ticket in a single run. Caused
  by house rule 19 ("leave the ticket better than you found it") applying to
  everyone while `update_ticket` is the only write tool not gated on money.
- **Minor waste:** on 103 Customer Service re-ran `check_inventory`,
  `get_pricing`, `list_vendors` and `get_today` that the Boss had already passed
  it as context.

---

## Problem 7 — Backend routes for the dashboard

**Prompts**

1.
```text
Let's do step 7, which is building the backend routes for the dashboard. In `backend/main.py`, use FastAPI to add routes that return the three tickets and whether each one is open or resolved, take a ticket ID and run the agent team on that ticket, and return recent agent events showing what each agent said and which tools they used so the dashboard can refresh.

Also add a route that approves a payment or purchase after a human clicks approve. The agents should only prepare the payment or purchase, and this route should be the one that actually changes the cash balance. Add a route to return the current checking balance from the `cash_accounts` table, and a route to reset the working database to its original values so we can try a fresh run. Use `data/campus_customs_new.db` for the working database and make sure the reset restores the original values without changing `data/campus_customs.db`.

Document every backend route in `output/harness.md`, with one line explaining its URL and what it does. From the `backend/` folder, the server should run with `uvicorn main:app --reload --port 8000` and be available at `http://localhost:8000` so the React dashboard can call it. Test the routes and make sure they return the correct ticket statuses, agent events, checking balance, and approval results, and that payment approvals only change cash when a human approves them.
```

**Follow-up prompts**

*(none)*

**Notes**

- `backend/main.py` — FastAPI, 12 routes, no SQL anywhere in it: every route
  goes through the `campus-customs` MCP server on one connection held for the
  server's lifetime. CORS open to the React dev ports.
- **Human-in-the-loop.** This step reverses Problem 5's behaviour, where the
  Boss paid directly. Added an MCP tool `propose_payment` that validates a
  spend against the live tables and queues it in
  `output/pending_approvals.json` with `money_moved: false` — no cash, no
  ledger row. The agents are given a *filtered* view of the MCP toolset with
  `record_payment` removed, so they cannot pay even if they try.
  `POST /approvals/{id}/approve` is the only caller of `record_payment`.
  Added `list_pending_approvals` so nothing is queued twice, and rewrote the
  money sections of all five prompts to match.
- Routes: `/`, `/tickets`, `/tickets/{id}`, `/tickets/{id}/run` (background,
  returns a run_id), `/runs/{run_id}`, `/runs`, `/events` (polling with
  `since`), `/approvals`, `/approvals/{id}/approve`, `/approvals/{id}/reject`,
  `/cash`, `/reset`.
- **Tested live** with the documented `uvicorn main:app --reload --port 8000`.
  Key result: after a full agent run on ticket 102 the balance was still
  $3,400.00 and `payments` was empty, with two proposals queued for $3,240.
  Approving proposal 1 as "Mukul Gupta" moved the balance to $2,560.00, wrote
  payment row 1 stamped with that name and marked invoice 501 paid; approving
  it again returned 409; an unsigned approval returned 400; rejecting
  proposal 2 moved nothing. `/reset` restored everything and left the original
  database byte-identical and the audit trail intact.

---

## Problem 8 — Frontend dashboard

**Prompts**

1.
```text
Let's do step 8, which is building the frontend dashboard for the agent team. Build it in `frontend/` using React, Vite, and TypeScript, and connect it to the backend at `http://localhost:8000`. Make sure the backend allows requests from the Vite frontend origin, usually `http://localhost:5173`, so the browser can call the routes.

The dashboard should list all three tickets, let me pick one and start the agent team on it, and show what each agent is saying and doing while the ticket is being worked on. When the run finishes, mark the ticket as resolved and show a short summary of what each agent did. It should also let a human approve a payment or purchase when asked, and show the current checking balance, which should decrease after an approved payment.

Make the dashboard look good and feel like a real operations desk that someone would enjoy using. Be creative with the layout and visual design, including how the agents' activity appears, how resolved tickets are shown, and how the cash balance is displayed. Create `output/design.md` explaining the design choices you made for the dashboard, including the layout, how the agents are visually distinguished, how resolved tickets and cash are shown, and the creative details that make the dashboard feel special and enjoyable to use.

Make sure the frontend actually calls the backend routes we built in step 7, and test the main features, including selecting and running a ticket, viewing agent activity and the summary, resolving a ticket, approving a payment or purchase, and seeing the checking balance update. Start the backend from `backend/` using `uvicorn main:app --reload --port 8000` and start the dashboard with `npm run dev` from `frontend/`.
```

**Follow-up prompts**

*(none)*

**Notes**

- Scaffolded `frontend/` with Vite's `react-ts` template. Three columns in the
  order the work happens: ticket queue, run console (ticket + dispatch button +
  agent roster + live feed), and what needs a human (approvals, then summary).
  Cash balance in the top bar. Black-and-pink per the project style.
- Every panel is wired to a real Problem 7 route — nothing mocked. The live
  feed polls `GET /events?since=` every 1.2s so it only pulls what is new.
  CORS for `http://localhost:5173` was already in place from Problem 7.
- Design choices written up in `output/design.md`: the three-column layout, a
  fixed hue per agent used in the roster, every feed row and the summary, the
  counting cash meter with its "held for approval" figure, the rubber-stamp
  treatment for resolved tickets, the approvals panel styled as something you
  sign (approve stays disabled until your name is filled in), and the feed as a
  transcript of tool calls and hand-offs rather than a spinner.
- **Tested by clicking through in a browser**, both servers on the documented
  commands. Selected #102 and dispatched; the feed filled live with tool calls,
  results and 3 hand-offs (one at depth 2) while the roster lit each agent in
  turn. Run finished with a per-agent summary — and the balance was still
  $3,400.00 with $3,240 queued, proving agents cannot pay. Approving the $840
  invoice animated the balance to $2,560.00, approving the $2,400 rent took it
  to $160.00, and both `payments` rows were stamped "Mukul Gupta". Re-running
  #102 had the Boss mark it `resolved`, which rendered the stamp. No console
  errors.
- Two fixes found during testing: filtered PydanticAI's internal `final_result`
  rows out of the feed (they carry the whole report as arguments and swamped
  the view), and made the page restore the last run and its events on reload.
- Also closed out the Problem 4 follow-up: `campus-customs` is now connected in
  Claude Code, so the three original tools were re-run through the session's own
  `mcp__campus-customs__*` tools against a freshly reset database. Identical
  values; appended as `live_in_claude_code` in `output/mcp_smoke.json`.
- Left the working database reset to its opening state ($3,400, all tickets
  open) and stopped both servers.

---

## Problem 9 — Resolve all three tickets and record what happened

**Prompts**

1.
```text
Let's do step 9, which is resolving all three tickets and recording what actually happened. Before running the agents, reset `data/campus_customs_new.db` to its original values again and note the starting checking balance. Then run tickets 101, 102, and 103 on the dashboard until all three are resolved. Make sure the agents use the MCP tools and the actual database information, and that any payment or purchase is only completed after a human approves it.

Open `output/desk_tickets.html` from step 6 and fill in the Actual section for each ticket based on the real runs. Include which agents worked on it, what they delegated to each other, and which MCP tools they used. Keep the Expected section unchanged so we can compare the plan with what actually happened.

On the Cash tab of the same `output/desk_tickets.html`, itemize the money. Show the starting checking balance after the reset, how the cash changed for each ticket when it was resolved, and why, including the payment or purchase and its dollar amount. Also show the ending checking balance and make sure it matches the `cash_accounts` table in the working database. Check the calculations carefully because the cash amounts need to be correct even if all tickets are resolved.

Save `output/resolved_tickets.json` with each ticket's ID, final status, a short outcome, what each agent contributed, and any human approvals. Also create `output/resolved_board.html`, which I can open by double-clicking, with a screenshot of the React dashboard for each resolved ticket (101, 102, and 103). Append the real runs to `output/audit_trail.json` without deleting any existing entries. Finally, finish `output/harness.md` so it covers the database tables, MCP tools, all five agents, API routes, dashboard, and safety rules. Test the results against the working database and make sure the ticket statuses, outcomes, audit trail, and cash balances all match what actually happened.
```

**Follow-up prompts**

*(none)*

**Notes**

- Reset the working copy from the original first; starting balance **$3,400.00**,
  all three tickets `open`, `payments` empty.
- Worked every ticket from the dashboard (clicked through the running React app,
  backend on :8000). Five agent runs in total — 101 and 102 each needed a second
  run after their payment was approved, 103 took one.
- **All three finished `resolved`.** 101: size S confirmed at 0, blocking
  invoice 501 paid, closed with an honest 2026-09-05 *estimate* and no promised
  delivery. 102: notice verified against lease 1, rent paid, stale ticket note
  reconciled on the second run instead of queueing a duplicate payment. 103:
  8 of 20 on hand, Boss approved a customer-specific $52.00/unit offer recorded
  on the ticket rather than written into `pricing`; no money moved.
- **Human-in-the-loop held.** The balance stayed $3,400.00 through every agent
  run. Both payments were queued with `propose_payment` and only posted when a
  person clicked approve; both `payments` rows read
  `approved_by = "Mukul Gupta"`.
- Cash: 3,400.00 − 840.00 − 2,400.00 = **160.00**, which matches
  `cash_accounts.checking`.
- Filled the **Actual** section of each ticket in `output/desk_tickets.html`
  from the audit trail — agents, every hand-off with depth, tools per agent,
  database changes, and an honest plan-vs-run comparison. Expected sections left
  untouched. Wrote the itemized **Cash** tab.
- Created `output/resolved_tickets.json` (status, outcome, per-agent
  contribution, hand-offs, tools, approvals) and `output/resolved_board.html`
  with a real dashboard screenshot per resolved ticket, embedded as base64 so
  the file opens by double-clicking.
- Audit trail grew 400 → **714** entries, contiguous `seq`, nothing deleted.
  It also captured a `delegation_refused` — the depth cap firing on ticket 103
  when Customer Service escalated to the Boss and that Boss tried to delegate
  onward.
- Finished `output/harness.md`: added a table of contents, updated the tool list
  to all **14** MCP tools with who may call what, and appended the final results
  with the cash reconciliation and verification table.
- Ran a verification script over everything: ticket statuses, payments, balance,
  invoice status, untouched pricing/inventory, pristine original database, audit
  integrity, and the HTML artefacts — all pass.
- Left the database in its resolved end state as the evidence for this step.

---

## Problem 10 — Fill in the Reflection tab

**Prompts**

1.
```text
Let's do step 10, which is filling in the Reflection tab in `output/desk_tickets.html`. Use the three tickets we actually ran, along with the Expected and Actual sections and the Cash tab on the same page, to answer all the reflection questions in my own words. Be detailed and specific to what happened in this Campus Customs app, not generic answers.

Explain how the agents performed on each ticket and why, how the actual agent delegations compared with the plans we wrote earlier, and what would have been simpler if we had used one agent with tools instead of a multi-agent team. Also describe three new problems Campus Customs could face that this agent team could solve using the tools we built, and three new problems it could not solve with the current tools. For each problem the team cannot solve, explain which additional tools and agents would be needed. Use the actual ticket runs, agent activity, tool calls, outcomes, and cash changes as evidence for your answers. Make sure every question in the Reflection tab is answered thoroughly and that the answers match what is recorded in the ticket tabs and Cash tab.
```

**Follow-up prompts**

*(none)*

**Notes**

- Pulled the real figures out of `output/audit_trail.json` first rather than
  writing from memory: 5 runs, 66 model requests, 367,826 tokens, 14 hand-offs
  plus 1 refused, 91 MCP tool calls, and the per-tool histogram.
- Five sections in the Reflection tab, all grounded in the runs:
  - **Per-ticket performance.** 101 praised for a negative result — it refused
    to invent stock, and Inventory corrected my own planning assumption by
    distinguishing "a bill for a reprint" from "a reprint". 102 as the best
    verified, because Facilities caught that the ticket states no amount at all
    and the second run reconciled a stale note instead of double-paying. 103 as
    the best decision at the worst price — $52/unit kept off the `pricing`
    table, but 106k tokens because of the CS → Boss escalation.
  - **Plan vs. actual delegations** in a table. The exclusions and first-movers
    were right; every payment prediction was wrong because step 7 removed
    `record_payment` from the agents after the plan was written; 103's route was
    wrong in both order and cost.
  - **One agent vs. the team.** Used the tool histogram as evidence —
    `get_today` 16 times, one lease read 9 times, 91 calls for a database with
    one invoice — and argued a single agent would have done it in well under
    half the tokens. Also what gets *worse*: the role prompts are the safety
    boundary, and 102's verification was genuinely independent. Ended with a
    concrete recommendation to keep Boss/Accounting split and fold the other
    three into one operations agent.
  - **Three solvable problems**: a second vendor invoice (and the team would now
    refuse it at a $160 balance), the `CC-MUG-CREST` stock-out (different
    vendor, 3-day lead, 2026-09-03), and receiving the reprint with
    `adjust_inventory`, which is built and tested but was never called.
  - **Three unsolvable ones**, each with the tools and agents needed: placing
    and tracking an actual purchase order plus a frozen desk date (needs
    `purchase_orders`, `create/receive_purchase_order`, `advance_date`, and a
    Scheduler agent); actually contacting the customer (needs `contacts`,
    `send_message` behind the same propose/approve gate, and a Comms split);
    and taking money *in* (needs `orders`/`receipts`, `record_sale`,
    `list_receivables`, and a Sales/Revenue agent) — the Cash tab shows only
    outflows, and the two outstanding customer amounts, $28.00 and $1,040.00,
    are recorded nowhere.
- Verified every factual claim against the database before publishing: mug at
  qty 0 and $14.00, Elm City Gifts at 3 lead days, tee at $28.00, 52 × 20 =
  $1,040, closing balance $160.00, and `adjust_inventory` / `update_price` /
  `record_payment` all at **0 agent calls** in the step-9 runs.
- Also refreshed the page header, which still read "3 open tickets" from step 6;
  it now shows 3/3 resolved and the cash movement. The **Expected** sections
  were not touched.
- Rendered and checked in a browser: all five tabs present, Expected and Actual
  intact on each ticket, no console errors.

---
