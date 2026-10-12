# Campus Customs Desk — dashboard

React + Vite + TypeScript front end for the agent team. Every panel is backed
by a route on the FastAPI backend; nothing is mocked.

```bash
npm install
npm run dev        # http://localhost:5173
```

The backend must be running first, from `../backend/`:

```bash
uvicorn main:app --reload --port 8000
```

It already allows CORS from `http://localhost:5173`. Point elsewhere with
`VITE_API_BASE=http://host:port npm run dev`.

## What it does

- Lists the three tickets with live status, and stamps resolved ones.
- Dispatches the agent team on the selected ticket and streams what every
  agent says and which MCP tool it calls, as it happens.
- Shows a per-agent summary and the Boss's verdict when the run finishes.
- Queues payment proposals for a human to approve — **agents cannot move
  money**; the approve button is what changes the balance.
- Keeps the checking balance in the top bar and counts it down when a payment
  posts.

Design rationale: `../output/design.md`.

```
src/
  App.tsx              layout, polling, run lifecycle
  api.ts               typed client for the backend + agent colours
  types.ts             shapes mirrored from the API
  index.css            the whole visual system
  components/
    CashMeter.tsx      animated balance + what is held for approval
    TicketRail.tsx     the queue, status pills, resolved stamp
    AgentRoster.tsx    five agents, colour-coded, lit when active
    ActivityFeed.tsx   live transcript of tool calls and hand-offs
    Approvals.tsx      the human-in-the-loop panel
    RunSummary.tsx     verdict + one line per agent
```
