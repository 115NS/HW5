// Shapes returned by the Problem 7 FastAPI backend (backend/main.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type Actor = AgentName | 'guardrails' | 'human'

export interface RunInfo {
  ticket_id: number
  status: 'running' | 'completed' | 'failed'
  started_at: string
  finished_at: string | null
  run_id: string | null
  error: string | null
}

export interface TicketRecord {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: 'open' | 'resolved'
  notes: string | null
  created_at: string
}

export interface TicketSummary extends TicketRecord {
  run: RunInfo | null
  proposal: {
    run_id: string | null
    approval_status: string | null
    summary: string | null
    approvable_actions: number
  } | null
}

export interface TicketsResponse {
  desk_date: string
  count: number
  tickets: TicketSummary[]
}

export interface Fact {
  label: string
  value: string
  source: string
}

export interface ApprovalRecord {
  action_id: string
  payment_id: number
  payment_kind: 'invoice' | 'rent' | 'purchase'
  ref_id: number | null
  amount: number
  approved_by: string
  balance_before: number
  balance_after: number
  ticket_status: string
  ts?: string
}

export interface ProposedAction {
  kind: string
  description: string
  amount: number | null
  payee: string | null
  ref: string | null
  requires_human_approval: boolean
  status: 'proposed' | 'blocked_by_guardrail'
  action_id: string | null
  approval: ApprovalRecord | null
  approvable: boolean
}

export interface RuleCheck {
  rule: string
  passed: boolean
  detail: string
}

export interface CustomerReplyDraft {
  to: string
  subject: string
  body: string
  sent: false
  note: string
}

export interface Proposal {
  ticket_id: number
  ticket_type: string
  summary: string
  delegated_to: AgentName[]
  key_facts: Fact[]
  options: string[]
  recommended_option: string
  proposed_actions: ProposedAction[]
  customer_reply_draft: CustomerReplyDraft | null
  open_questions: string[]
  rule_checks: RuleCheck[]
  approval_status: 'pending_human_approval' | 'no_approval_needed' | 'blocked_by_guardrail'
  run_id: string | null
}

export interface FailedProposal {
  ticket_id: number
  status: 'failed'
  error: string
}

export interface TicketDetail {
  ticket: TicketRecord
  run: RunInfo | null
  proposal: Proposal | FailedProposal | null
}

export interface ToolInfo {
  name: string
  args: Record<string, unknown> | null
  result?: unknown
}

export interface DelegationInfo {
  from: string
  to: string
  task: string
  chain?: string[]
  returned_by?: string
}

export interface AgentEvent {
  seq: number
  ts: string
  run_id: string
  ticket_id: number | null
  agent: string | null
  action: string
  message: string
  chain: string[] | null
  step: number | null
  tool: ToolInfo | null
  delegation: DelegationInfo | null
  approval_status: string | null
  error: string | null
}

export interface EventsResponse {
  count: number
  last_seq: number
  events: AgentEvent[]
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  desk_date: string
}

export interface Health {
  status: string
  model: string
  portkey_key_configured: boolean
  database: string
}

export interface ApprovalResult extends ApprovalRecord {
  approved: true
  description: string
  paid_at: string
}

export function isFailedProposal(p: TicketDetail['proposal']): p is FailedProposal {
  return !!p && 'status' in p && p.status === 'failed'
}
