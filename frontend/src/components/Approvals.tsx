import { money } from "../api";
import type { Approval } from "../types";

/** Agents can only *propose* a spend. This panel is the hand on the cheque
 *  book: nothing moves until a person types their name and clicks approve. */
export function Approvals({
  approvals, who, busy, onApprove, onReject,
}: {
  approvals: Approval[];
  who: string;
  busy: number | null;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}) {
  const pending = approvals.filter(a => a.status === "pending");
  const settled = approvals.filter(a => a.status !== "pending");

  return (
    <div className="card">
      <h2>
        Needs your signature
        <span className="count">{pending.length} pending</span>
      </h2>
      <div className="inner">
        {approvals.length === 0 && (
          <div style={{ color: "var(--faint)", fontSize: 13 }}>
            Nothing to approve. Agents queue payments here instead of making them —
            the balance cannot move without you.
          </div>
        )}

        {pending.map(a => (
          <div key={a.id} className="appr pending">
            <div className="amt">{money(a.amount)}</div>
            <div className="for">
              {a.kind}{a.ref_id != null ? ` · #${a.ref_id}` : ""} · asked by {a.requested_by}
            </div>
            <div className="why">{a.reason}</div>
            <div className="after">
              {money(a.balance_before)} → {money(a.balance_if_approved)} if approved
            </div>
            {a.warnings.map((w, i) => <div key={i} className="warn">⚠ {w}</div>)}
            <div className="acts">
              <button
                className="btn-yes"
                disabled={busy === a.id || !who.trim()}
                title={who.trim() ? "" : "Put your name in the top bar first"}
                onClick={() => onApprove(a.id)}
              >
                {busy === a.id ? "Posting…" : "Approve"}
              </button>
              <button
                className="btn-no"
                disabled={busy === a.id || !who.trim()}
                onClick={() => onReject(a.id)}
              >
                Reject
              </button>
            </div>
          </div>
        ))}

        {settled.map(a => (
          <div key={a.id} className="appr settled">
            <div className="done ok" style={{ color: a.status === "approved" ? "var(--ok)" : "var(--faint)" }}>
              {a.status === "approved" ? "✓ paid" : "✕ rejected"} · {money(a.amount)}
              {a.approved_by ? ` · ${a.approved_by}` : ""}
            </div>
            <div className="for" style={{ margin: "6px 0 0" }}>{a.reason}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
