import type { Ticket } from "../types";

const pillClass = (s: string) =>
  s === "resolved" || s === "closed" ? "resolved"
  : s === "in_progress" ? "progress"
  : s === "waiting_approval" ? "waiting" : "open";

export function TicketRail({
  tickets, selected, onSelect,
}: {
  tickets: Ticket[];
  selected: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <div className="card">
      <h2>
        Ticket queue
        <span className="count">{tickets.filter(t => t.is_open).length} open</span>
      </h2>
      <div className="inner">
        {tickets.map(t => (
          <button
            key={t.id}
            className={`ticket${t.is_resolved ? " resolved" : ""}`}
            data-sel={selected === t.id}
            onClick={() => onSelect(t.id)}
          >
            <div className="row1">
              <span className="id">#{t.id}</span>
              <span className="kind">{t.type}</span>
              <span className={`pill ${pillClass(t.status)}`}>
                {t.status.replace("_", " ")}
              </span>
            </div>
            <div className="subject">{t.subject}</div>
            <div className="who2">{t.requester}</div>
            {t.sku && (
              <div className="want">
                {t.sku}{t.size ? ` · ${t.size}` : ""}{t.qty ? ` × ${t.qty}` : ""}
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
