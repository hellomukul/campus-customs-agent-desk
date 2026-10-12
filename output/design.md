# Dashboard design — Campus Customs Desk

`frontend/`, React + Vite + TypeScript, talking to the FastAPI backend at
`http://localhost:8000`.

The brief was to make it feel like a real operations desk. So the governing
idea was not "show the data" but **put the user in the chair**: this is a small
shop, the balance is small, and five agents are about to spend your money. The
screen should make you feel responsible for what happens next.

---

## 1. Layout — three columns, one job each

```
┌──────────────────────────────────────────────────────────────────────┐
│  brand   [ CASH METER ]              on duty: ____      Reset day    │
├──────────────┬───────────────────────────────────┬───────────────────┤
│ TICKET QUEUE │  selected ticket + Dispatch       │ NEEDS YOUR        │
│              │  ───────────────────────────────  │ SIGNATURE         │
│  #101 ▸      │  agent roster (5 chips)           │                   │
│  #102 ▸      │  ───────────────────────────────  │ ───────────────   │
│  #103 ▸      │  AGENT ACTIVITY (live feed)       │ SUMMARY           │
└──────────────┴───────────────────────────────────┴───────────────────┘
```

The columns map to the three things a person actually does here, left to
right, in the order they do them:

- **Left — what needs doing.** The ticket queue, always visible, never
  collapsing. You pick from here.
- **Centre — what is happening.** The selected ticket, one big button, and the
  live feed. This is where your eyes live during a run.
- **Right — what needs *you*.** Approvals first, because it is the only thing
  that blocks, and the summary underneath, because it is what you read when the
  work is done.

Each column scrolls independently so the feed racing on in the middle never
pushes the approve button out of reach. Below 1180px the right column drops to
a full-width row underneath rather than squeezing to an unusable width.

## 2. Agents are told apart by colour, not by labels

Each of the five gets a fixed hue, and that hue is used **everywhere that agent
appears** — roster chip, the left border and avatar of every feed row, its line
in the summary:

| Agent | Hue | Reads as |
|---|---|---|
| Boss | 330 — hot pink | the brand colour; the one in charge |
| Inventory | 38 — amber | warehouse, stock, physical goods |
| Accounting | 152 — green | money |
| Facilities | 200 — blue | the building |
| Customer Service | 268 — violet | the outside world |

The practical effect: during a run you can see *who is talking* from the corner
of your eye, as a band of colour moving down the feed, without reading a word.
A hand-off shows both colours at once — two chips with an arrow between them —
so a delegation is visually obviously different from an agent doing its own
work.

The roster strip above the feed is the team's status light. Agents fade to 42%
opacity until they have done something; the one currently working gets its hue
as a border, a soft glow, and a gently breathing avatar. A small counter shows
how many events each has produced. At a glance: who is on this ticket, and who
is up right now.

## 3. The cash balance is the headline

It sits in the top bar, in large tabular monospace, because in a shop with
$3,400 in the account the balance *is* the status of the business.

Three deliberate details:

- **It counts.** When a payment posts, the number animates from the old value
  to the new one over 700ms on an ease-out curve, turns pink for the duration,
  and a light sweeps across the panel. You see money leave rather than
  discovering a different number later.
- **It shows what is held.** When approvals are queued, a second figure appears
  beside it: the amount held for approval and what the balance *would* be if
  you approved everything. With $3,400 in the account and $3,240 queued, the
  "→ $160.00" is the whole story of the day in one line.
- **A hairline bar** under the panel tracks the balance as a proportion of the
  opening $3,400, so the drain across a session is visible as a shrinking line.

## 4. Approvals look like something you sign

This is the part the architecture exists for: agents can only *propose* a
spend, and `POST /approvals/{id}/approve` is the only thing that moves cash. So
the panel is designed to look like a cheque waiting for a signature rather than
a notification:

- The amount is the largest text in the card.
- Under it, in plain language, who asked and why — the agent's own reason.
- Then the arithmetic you need: **`$3,400.00 → $2,560.00` if approved**. Never
  just the amount; always the consequence.
- Any warning the MCP tool raised (amount disagrees with the invoice, this
  would leave less than the rent) gets an amber block above the buttons.
- **The Approve button is disabled until your name is in the top bar.** The
  backend rejects an unsigned approval with a 400; the UI makes that rule
  visible rather than letting you discover it as an error.

Once decided, the card settles into a quiet one-line receipt — `✓ paid ·
$840.00 · Mukul Gupta` — and stays in the list. The desk keeps its paperwork.

## 5. Resolved tickets get stamped

A resolved ticket is not greyed out or moved away. It gets an actual **rubber
stamp**: the word `RESOLVED` in a boxed outline, rotated −20°, slammed on at a
2.2× scale that springs down to 1 over 350ms. It is the one unashamedly
playful thing on the screen, and it is there because finishing a ticket should
feel like something. The ticket stays in the queue wearing its stamp, the way
paper stays on a desk.

Status pills carry a colour grammar used consistently: pink for open, amber for
in-progress or waiting on approval, green for resolved.

## 6. The feed is a transcript, not a progress bar

Spinners tell you nothing. The centre column streams the actual audit trail —
backed by `GET /events?since=`, polling every 1.2s and asking only for events
newer than the last `seq` it saw, so the payload stays small:

- **Tool calls** render as a monospace chip — `◆ check_inventory` — with the
  arguments underneath. You can see the agent asking the database a specific
  question.
- **Tool results** appear in a scrollable code block, clamped to ~88px so one
  fat JSON row cannot swallow the screen.
- **Hand-offs** get their own treatment: a pink-washed row, both agents as
  coloured chips with an arrow, the depth badge, and the question that was
  asked.
- **Agent conclusions** get a green left border — the milestone in a stream of
  mechanics.
- A pulsing dot next to the header while the run is live.

`final_result` rows are filtered out: that is PydanticAI's own output plumbing,
not a shop tool, and it carries the entire report as arguments. The audit trail
keeps them; the desk does not show them.

The feed auto-scrolls — but only if you are already near the bottom. Scroll up
to read something and it stops fighting you.

## 7. Small things that make it feel inhabited

- **"On duty"** in the top bar instead of a login. It is the name that gets
  stamped on the payment, which quietly makes the point that a person is
  accountable for it.
- **"Dispatch the team"**, not "Run". The button sends people somewhere.
- **"Reset day"**, not "Reset database" — it restores the morning, and it is
  disabled while a run is in flight.
- **"The desk is quiet"** as the empty state, with a line telling you what will
  appear and where.
- Toasts report the *consequence*, not the event: "Paid. Checking $3,400.00 →
  $2,560.00".
- The page restores itself on refresh — it reloads the most recent run and
  replays its events from the trail, so a reload does not wipe the transcript.
- Errors are honest and actionable: if the backend is down the toast says so
  and names the port to check.

## 8. Palette and type

Black room, pink light — the project's house style. Near-black `#07070a` with
two faint pink radial glows bled into the top corners so the page has a light
source instead of being flatly dark. One accent, `#ff3d8b`, used sparingly:
the brand, the selected ticket, the dispatch button, the falling balance. Green
and amber appear *only* for state (resolved, warning), so they always mean
something.

System sans for prose; monospace for every number, tool name, SKU and
timestamp — anything that came out of the database reads as machine output, and
`font-variant-numeric: tabular-nums` keeps the balance from jittering as it
counts.

## 9. What it calls

Every piece of the UI is backed by a Problem 7 route — nothing is mocked:

| UI | Route |
|---|---|
| Ticket queue, status pills, stamp | `GET /tickets` |
| Dispatch the team | `POST /tickets/{id}/run` |
| Live feed | `GET /events?since=&run_id=` (1.2s poll) |
| Run state, summary, usage stats | `GET /runs/{run_id}`, `GET /runs` |
| Approvals panel | `GET /approvals` |
| Approve / Reject | `POST /approvals/{id}/approve` · `/reject` |
| Cash meter | `GET /cash` |
| Reset day | `POST /reset` |

## 10. Running it

```bash
# backend
cd backend && uvicorn main:app --reload --port 8000

# dashboard
cd frontend && npm install && npm run dev     # http://localhost:5173
```

CORS on the backend already allows `http://localhost:5173`. The API base can be
overridden with `VITE_API_BASE` if the backend moves.
