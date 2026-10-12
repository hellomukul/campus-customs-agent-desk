import type {
  Approval, Cash, EventsResponse, RunRecord, TicketsResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "content-type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* keep status text */ }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  tickets: () => req<TicketsResponse>("/tickets"),
  cash: () => req<Cash>("/cash"),
  events: (since: number, runId?: string) =>
    req<EventsResponse>(
      `/events?since=${since}&limit=200${runId ? `&run_id=${runId}` : ""}`,
    ),
  runTicket: (id: number) =>
    req<RunRecord>(`/tickets/${id}/run`, { method: "POST", body: JSON.stringify({}) }),
  run: (runId: string) => req<RunRecord>(`/runs/${runId}`),
  runs: () => req<{ runs: RunRecord[] }>("/runs"),
  approvals: () => req<{ count: number; pending: number; approvals: Approval[] }>("/approvals"),
  approve: (id: number, approvedBy: string, note?: string) =>
    req<{ ok: boolean; balance_before: number; balance_after: number }>(
      `/approvals/${id}/approve`,
      { method: "POST", body: JSON.stringify({ approved_by: approvedBy, note }) },
    ),
  reject: (id: number, rejectedBy: string, reason?: string) =>
    req<{ ok: boolean }>(`/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ rejected_by: rejectedBy, reason }),
    }),
  reset: () => req<{ ok: boolean; balance: number }>("/reset", { method: "POST" }),
};

export const AGENTS = {
  boss:             { label: "Boss",    full: "Boss",             hue: 330, initials: "BO" },
  inventory:        { label: "Inv",     full: "Inventory",        hue: 38,  initials: "IN" },
  accounting:       { label: "Acct",    full: "Accounting",       hue: 152, initials: "AC" },
  facilities:       { label: "Fac",     full: "Facilities",       hue: 200, initials: "FA" },
  customer_service: { label: "CS",      full: "Customer Service", hue: 268, initials: "CS" },
} as const;

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD" });
