import { AGENTS } from "../api";
import type { AgentEvent, AgentName, RunRecord } from "../types";

/** After the run: the Boss's verdict on top, then one line per agent that
 *  actually did something, in that agent's colour, with the tools it used. */
export function RunSummary({
  run, events,
}: { run: RunRecord | null; events: AgentEvent[] }) {
  if (!run || run.status === "running") {
    return (
      <div className="card">
        <h2>Summary</h2>
        <div className="inner" style={{ color: "var(--faint)", fontSize: 13 }}>
          {run?.status === "running"
            ? "The team is still working. The summary lands here when the ticket is done."
            : "Run a ticket and the wrap-up appears here — what each agent did, and what it cost."}
        </div>
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="card">
        <h2>Summary</h2>
        <div className="inner" style={{ color: "var(--bad)", fontSize: 13 }}>{run.error}</div>
      </div>
    );
  }

  const ends = events.filter(e => e.event === "agent_end" && e.run_id === run.run_id);
  const byAgent = new Map<string, AgentEvent>();
  for (const e of ends) if (e.agent) byAgent.set(e.agent, e);
  const report = run.report;

  return (
    <div className="card sum">
      <h2>
        Summary
        <span className="count">ticket #{run.ticket_id}</span>
      </h2>
      <div className="inner">
        {report && (
          <div className="verdict">
            <h4>Boss's verdict</h4>
            <p>{report.summary}</p>
            <p style={{ color: "var(--dim)", fontSize: 12.5 }}>{report.recommendation}</p>
            <div className="stat">
              <span>{run.delegations ?? 0} hand-offs</span>
              <span>{run.usage?.requests ?? 0} requests</span>
              <span>{(run.usage?.total_tokens ?? 0).toLocaleString()} tokens</span>
            </div>
          </div>
        )}

        {[...byAgent.entries()].map(([name, e]) => {
          const a = AGENTS[name as AgentName];
          if (!a) return null;
          return (
            <div key={name} className="line" style={{ ["--h" as string]: a.hue }}>
              <span className="av">{a.initials}</span>
              <div>
                <div className="nm">{a.full}</div>
                <div className="sm">{e.said}</div>
                {e.tools_used && e.tools_used.length > 0 && (
                  <div className="tools">
                    {e.tools_used.slice(0, 8).map(t => <span key={t}>{t}</span>)}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {report?.customer_message && (
          <div className="draft">
            <b>drafted for the requester</b>
            {report.customer_message}
          </div>
        )}
      </div>
    </div>
  );
}
