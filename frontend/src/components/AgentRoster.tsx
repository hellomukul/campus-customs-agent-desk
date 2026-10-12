import { AGENTS } from "../api";
import type { AgentName } from "../types";

/** Five faces across the top of the console. Each has its own hue, used
 *  everywhere that agent appears — chip, feed row, summary line — so you can
 *  follow one agent by colour without reading a word. */
export function AgentRoster({
  active, counts,
}: {
  active: AgentName | null;
  counts: Record<string, number>;
}) {
  return (
    <div className="roster">
      {(Object.keys(AGENTS) as AgentName[]).map(name => {
        const a = AGENTS[name];
        const used = (counts[name] ?? 0) > 0;
        return (
          <div
            key={name}
            className="agent-chip"
            data-active={active === name}
            data-used={used}
            style={{ ["--h" as string]: a.hue }}
            title={a.full}
          >
            <span className="av">{a.initials}</span>
            <span className="nm">{a.full}</span>
            {used && <span className="ct">{counts[name]}</span>}
          </div>
        );
      })}
    </div>
  );
}
