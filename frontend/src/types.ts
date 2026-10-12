export type AgentName =
  | "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  status: string;
  notes: string | null;
  created_at: string;
  is_open: boolean;
  is_resolved: boolean;
  state: "open" | "resolved";
}

export interface TicketsResponse {
  as_of: string;
  count: number;
  open: number;
  resolved: number;
  tickets: Ticket[];
}

export interface AgentEvent {
  seq: number;
  at: string;
  kind: string;
  event?: string;
  run_id?: string;
  agent?: AgentName | null;
  depth?: number | null;
  tool?: string;
  arguments?: Record<string, unknown>;
  said?: string;
  from?: AgentName;
  to?: AgentName;
  reason?: string;
  tools_used?: string[];
  approvals_needed?: { what: string; why: string; amount: number | null }[];
}

export interface EventsResponse {
  since: number;
  latest_seq: number;
  returned: number;
  events: AgentEvent[];
}

export interface FactChecked { claim: string; mcp_tool: string; value: string }
export interface ActionTaken { description: string; mcp_tool: string; approved_by: string; result: string }

export interface AgentReport {
  agent: string;
  summary: string;
  facts: FactChecked[];
  actions: ActionTaken[];
  approvals_needed: { what: string; why: string; amount: number | null }[];
  delegated_to: string[];
  recommendation: string;
  customer_message: string | null;
}

export interface RunRecord {
  run_id: string;
  ticket_id: number;
  status: "running" | "complete" | "failed";
  started_at: string;
  finished_at?: string;
  since_seq: number;
  report?: AgentReport;
  error?: string;
  delegations?: number;
  usage?: { requests: number; total_tokens: number };
}

export interface Approval {
  id: number;
  status: "pending" | "approved" | "rejected";
  kind: string;
  ref_id: number | null;
  amount: number;
  account: string;
  reason: string;
  requested_by: string;
  balance_before: number;
  balance_if_approved: number;
  warnings: string[];
  money_moved: boolean;
  approved_by?: string;
  detail?: Record<string, unknown>;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
  pending_approvals: number;
  pending_total: number;
  balance_if_all_approved: number;
}
