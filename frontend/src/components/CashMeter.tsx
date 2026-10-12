import { useEffect, useRef, useState } from "react";
import { money } from "../api";
import type { Cash } from "../types";

/** The balance is the thing a shop owner actually watches, so it lives in the
 *  top bar, counts down when a payment posts, and carries a second number for
 *  what is still held for approval. */
export function CashMeter({ cash }: { cash: Cash | null }) {
  const [shown, setShown] = useState(cash?.balance ?? 0);
  const [flash, setFlash] = useState(false);
  const prev = useRef<number | null>(null);

  useEffect(() => {
    if (!cash) return;
    const from = prev.current;
    prev.current = cash.balance;
    if (from === null || from === cash.balance) { setShown(cash.balance); return; }

    setFlash(true);
    const start = performance.now();
    const dur = 700;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(from + (cash.balance - from) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
      else setTimeout(() => setFlash(false), 300);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [cash?.balance]);

  if (!cash) return <div className="cash"><span className="lab">checking</span></div>;

  const held = cash.pending_total > 0;
  const pct = Math.max(0, Math.min(100, (cash.balance / 3400) * 100));

  return (
    <div className={`cash${flash ? " flash dropped" : ""}`} title="cash_accounts via MCP">
      <div>
        <div className="lab">checking · {cash.as_of}</div>
        <div className="amount">{money(shown)}</div>
      </div>
      {held && (
        <div className="held">
          held for approval
          <b>{money(cash.pending_total)}</b>
          → {money(cash.balance_if_all_approved)}
        </div>
      )}
      <div className="bar" style={{ width: `${pct}%` }} />
    </div>
  );
}
