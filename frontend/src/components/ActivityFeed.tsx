import { useEffect, useRef } from "react";
import { AGENTS } from "../api";
import type { AgentEvent, AgentName } from "../types";

const hue = (a?: string | null) =>
  a && a in AGENTS ? AGENTS[a as AgentName].hue : 320;

const clock = (iso?: string) =>
  iso ? new Date(iso).toLocaleTimeString("en-US", { hour12: false }) : "";

function Row({ e }: { e: AgentEvent }) {
  const a = e.agent && e.agent in AGENTS ? AGENTS[e.agent] : null;

  if (e.event === "delegation" || e.event === "delegation_refused") {
    const from = e.from && AGENTS[e.from], to = e.to && AGENTS[e.to];
    return (
      <div className="ev hand" style={{ ["--h" as string]: hue(e.from) }}>
        <span className="av" style={{ ["--h" as string]: hue(e.from) }}>
          {from ? from.initials : "··"}
        </span>
        <div className="body">
          <div className="who3">
            hand-off <span className="time">{clock(e.at)}</span>
            {e.depth != null && <span className="depth">depth {e.depth}</span>}
          </div>
          <div className="txt">
            <span className="arrowchip" style={{ ["--h2" as string]: hue(e.from) }}>
              {from?.full}
            </span>
            <span style={{ color: "var(--faint)" }}>→</span>
            <span className="arrowchip" style={{ ["--h2" as string]: hue(e.to) }}>
              {to?.full}
            </span>
            {e.event === "delegation_refused" && (
              <span style={{ color: "var(--warn)", fontSize: 12 }}>
                refused — {e.reason}
              </span>
            )}
          </div>
          {e.said && <div className="args">{e.said.split(": ").slice(1).join(": ")}</div>}
        </div>
      </div>
    );
  }

  const milestone = e.event === "agent_end";

  return (
    <div className={`ev${milestone ? " milestone" : ""}`} style={{ ["--h" as string]: hue(e.agent) }}>
      <span className="av">{a ? a.initials : "··"}</span>
      <div className="body">
        <div className="who3">
          {a ? a.full : e.kind}
          <span className="time">{clock(e.at)}</span>
          {e.depth ? <span className="depth">depth {e.depth}</span> : null}
        </div>

        {e.event === "tool_call" && (
          <>
            <span className="tool">◆ {e.tool}</span>
            {e.arguments && Object.keys(e.arguments).length > 0 && (
              <div className="args">{JSON.stringify(e.arguments)}</div>
            )}
          </>
        )}

        {e.event === "tool_result" && (
          <>
            <div className="txt quiet" style={{ fontSize: 12 }}>
              {e.tool} returned
            </div>
            <div className="ret">{e.said}</div>
          </>
        )}

        {e.event === "agent_start" && (
          <div className="txt quiet">picked up: {e.said}</div>
        )}

        {(e.event === "model_text" || e.event === "agent_end") && (
          <div className="txt">{e.said}</div>
        )}

        {e.event === "agent_end" && e.tools_used && e.tools_used.length > 0 && (
          <div className="args">tools: {e.tools_used.join(" · ")}</div>
        )}
      </div>
    </div>
  );
}

/** `final_result` is PydanticAI's own output plumbing, not a shop tool, and it
 *  carries the whole report as arguments. The agent_end row already says what
 *  the agent concluded, so these two rows are noise on the desk. */
const isNoise = (e: AgentEvent) =>
  (e.event === "tool_call" || e.event === "tool_result") && e.tool === "final_result";

export function ActivityFeed({
  events: raw, running,
}: { events: AgentEvent[]; running: boolean }) {
  const events = raw.filter(e => !isNoise(e));
  const ref = useRef<HTMLDivElement>(null);
  const stick = useRef(true);

  useEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  const onScroll = () => {
    const el = ref.current;
    if (!el) return;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 70;
  };

  return (
    <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <h2>
        {running && <span className="livedot" />}
        Agent activity
        <span className="count">{events.length} events</span>
      </h2>
      <div className="feed" ref={ref} onScroll={onScroll}>
        {events.length === 0 ? (
          <div className="empty">
            <span className="big">the desk is quiet</span>
            Pick a ticket and dispatch the team. Every tool call and hand-off
            shows up here as it happens.
          </div>
        ) : (
          events.map(e => <Row key={e.seq} e={e} />)
        )}
      </div>
    </div>
  );
}
