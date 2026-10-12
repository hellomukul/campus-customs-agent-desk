import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AGENTS, api } from "./api";
import { ActivityFeed } from "./components/ActivityFeed";
import { AgentRoster } from "./components/AgentRoster";
import { Approvals } from "./components/Approvals";
import { CashMeter } from "./components/CashMeter";
import { RunSummary } from "./components/RunSummary";
import { TicketRail } from "./components/TicketRail";
import type { AgentEvent, AgentName, Approval, Cash, RunRecord, Ticket } from "./types";

const POLL_MS = 1200;

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [cash, setCash] = useState<Cash | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [who, setWho] = useState("Mukul Gupta");
  const [busy, setBusy] = useState<number | null>(null);
  const [toast, setToast] = useState<{ msg: string; bad?: boolean } | null>(null);
  const [starting, setStarting] = useState(false);
  const since = useRef(0);

  const say = (msg: string, bad = false) => {
    setToast({ msg, bad });
    setTimeout(() => setToast(null), 4200);
  };

  const refreshStatics = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()]);
      setTickets(t.tickets);
      setCash(c);
      setApprovals(a.approvals);
      setSelected(prev => prev ?? t.tickets[0]?.id ?? null);
    } catch (e) {
      say(`Backend unreachable — is uvicorn running on :8000? (${(e as Error).message})`, true);
    }
  }, []);

  useEffect(() => { void refreshStatics(); }, [refreshStatics]);

  // Survive a page refresh: pick up the most recent run and replay its events
  // from the audit trail, so the feed and summary are not lost on reload.
  useEffect(() => {
    (async () => {
      try {
        const { runs } = await api.runs();
        const last = runs.at(-1);
        if (!last) return;
        setRun(last);
        setSelected(last.ticket_id);
        const ev = await api.events(0, last.run_id);
        setEvents(ev.events);
        since.current = ev.events.at(-1)?.seq ?? last.since_seq;
      } catch { /* nothing to restore */ }
    })();
  }, []);

  // While a run is live, poll the append-only event trail with ?since= so we
  // only ever pull what is new, and refresh the numbers alongside it.
  useEffect(() => {
    if (!run || run.status !== "running") return;
    let stop = false;
    const tick = async () => {
      try {
        const [ev, state] = await Promise.all([
          api.events(since.current, run.run_id),
          api.run(run.run_id),
        ]);
        if (stop) return;
        if (ev.events.length) {
          since.current = ev.events[ev.events.length - 1].seq;
          setEvents(prev => [...prev, ...ev.events]);
        }
        if (state.status !== "running") {
          setRun(state);
          await refreshStatics();
          say(state.status === "complete"
            ? `Ticket #${state.ticket_id} worked — see the summary.`
            : `Run failed: ${state.error}`, state.status !== "complete");
        }
      } catch { /* a dropped poll is not worth shouting about */ }
    };
    const id = setInterval(tick, POLL_MS);
    void tick();
    return () => { stop = true; clearInterval(id); };
  }, [run, refreshStatics]);

  const dispatch = async () => {
    if (selected == null) return;
    setStarting(true);
    setEvents([]);
    try {
      const started = await api.runTicket(selected);
      since.current = started.since_seq;
      setRun(started);
      say(`Boss picked up ticket #${selected}.`);
    } catch (e) {
      say((e as Error).message, true);
    } finally {
      setStarting(false);
    }
  };

  const approve = async (id: number) => {
    setBusy(id);
    try {
      const r = await api.approve(id, who.trim());
      await refreshStatics();
      say(`Paid. Checking ${r.balance_before.toLocaleString("en-US", { style: "currency", currency: "USD" })} → ${r.balance_after.toLocaleString("en-US", { style: "currency", currency: "USD" })}`);
    } catch (e) {
      say((e as Error).message, true);
    } finally { setBusy(null); }
  };

  const reject = async (id: number) => {
    setBusy(id);
    try {
      await api.reject(id, who.trim(), "Rejected at the desk.");
      await refreshStatics();
      say("Rejected. No money moved.");
    } catch (e) {
      say((e as Error).message, true);
    } finally { setBusy(null); }
  };

  const reset = async () => {
    try {
      await api.reset();
      setEvents([]); setRun(null); since.current = 0;
      await refreshStatics();
      say("Working database restored to opening state.");
    } catch (e) { say((e as Error).message, true); }
  };

  const ticket = tickets.find(t => t.id === selected) ?? null;
  const running = run?.status === "running";

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of events) if (e.agent) c[e.agent] = (c[e.agent] ?? 0) + 1;
    return c;
  }, [events]);

  const active: AgentName | null = useMemo(() => {
    if (!running) return null;
    for (let i = events.length - 1; i >= 0; i--) {
      const a = events[i].agent;
      if (a && a in AGENTS) return a;
    }
    return null;
  }, [events, running]);

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <h1>Campus Customs <b>Desk</b></h1>
          <span className="tag">agent operations</span>
        </div>
        <CashMeter cash={cash} />
        <div className="spacer" />
        <div className="who">
          <label htmlFor="who">on duty</label>
          <input id="who" value={who} onChange={e => setWho(e.target.value)} placeholder="your name" />
        </div>
        <button className="ghost-btn" onClick={reset} disabled={running}>Reset day</button>
      </header>

      <div className="stage">
        <div className="col">
          <TicketRail tickets={tickets} selected={selected} onSelect={setSelected} />
        </div>

        <div className="col console">
          <div className="runhead">
            <div className="t">
              <h3>{ticket ? `#${ticket.id} · ${ticket.subject}` : "No ticket selected"}</h3>
              {ticket && (
                <span className={`pill ${ticket.is_resolved ? "resolved" : "open"}`}>
                  {ticket.status.replace("_", " ")}
                </span>
              )}
              <button
                className={`go${running ? " running" : ""}`}
                disabled={!ticket || running || starting}
                onClick={dispatch}
              >
                {running ? "Team is working…" : starting ? "Dispatching…" : "Dispatch the team"}
              </button>
            </div>
            {ticket && (
              <>
                <div className="meta">
                  {ticket.requester} · {ticket.type}
                  {ticket.sku && ` · ${ticket.sku}${ticket.size ? ` / ${ticket.size}` : ""}${ticket.qty ? ` × ${ticket.qty}` : ""}`}
                </div>
                {ticket.notes && <div className="notes">{ticket.notes}</div>}
              </>
            )}
          </div>

          <AgentRoster active={active} counts={counts} />
          <ActivityFeed events={events} running={!!running} />
        </div>

        <div className="col right">
          <Approvals
            approvals={approvals}
            who={who}
            busy={busy}
            onApprove={approve}
            onReject={reject}
          />
          <RunSummary run={run} events={events} />
        </div>
      </div>

      {toast && <div className={`toast${toast.bad ? " bad" : ""}`}>{toast.msg}</div>}
    </div>
  );
}
