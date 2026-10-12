// Turns raw audit-trail events (GET /api/events) into what the dashboard shows:
// runs, a readable feed, the crew's live state, and per-agent summaries.
import type { AgentEvent, AgentName } from '../types'
import { isAgent } from './agents'
import { money } from './format'

export interface Run {
  runId: string
  ticketId: number | null
  events: AgentEvent[]
  startedAt: string
  endedAt: string | null
  status: 'running' | 'completed' | 'failed'
  models: string
  requests: number | null
  delegations: number | null
  approvalStatus: string | null
}

/** Agent runs for a ticket, oldest first. Human approvals and resets are "desk" events, not runs. */
export function groupRuns(events: AgentEvent[]): Run[] {
  const runs = new Map<string, AgentEvent[]>()
  for (const e of events) {
    if (e.run_id.startsWith('human-') || e.run_id.startsWith('reset-')) continue
    const list = runs.get(e.run_id) ?? []
    list.push(e)
    runs.set(e.run_id, list)
  }
  return [...runs.entries()]
    .map(([runId, evs]) => {
      evs.sort((a, b) => a.seq - b.seq)
      const start = evs.find((e) => e.action === 'run_start')
      const end = evs.find((e) => e.action === 'run_end')
      const endDetails = end ? parseRunEnd(end.message) : null
      return {
        runId,
        ticketId: evs[0].ticket_id,
        events: evs,
        startedAt: evs[0].ts,
        endedAt: end?.ts ?? null,
        status: !end ? 'running' : end.error ? 'failed' : 'completed',
        models: start ? start.message.replace(/^Run started on /, '') : '',
        requests: endDetails?.requests ?? null,
        delegations: evs.filter((e) => e.action === 'delegation_request').length,
        approvalStatus: end?.approval_status ?? null,
      } satisfies Run
    })
    .sort((a, b) => a.events[0].seq - b.events[0].seq)
}

function parseRunEnd(message: string): { requests: number | null } {
  const m = message.match(/(\d+) model requests/)
  return { requests: m ? Number(m[1]) : null }
}

export function deskEvents(events: AgentEvent[]): AgentEvent[] {
  return events.filter((e) => e.run_id.startsWith('human-') || e.run_id.startsWith('reset-'))
}

// ---------------------------------------------------------------------------------------------

export type FeedItem =
  | { kind: 'start'; key: string; ts: string; agent: string; text: string; depth: number }
  | { kind: 'thought'; key: string; ts: string; agent: string; text: string; depth: number }
  | { kind: 'tool'; key: string; ts: string; agent: string; name: string; args: Record<string, unknown> | null; result: unknown; pending: boolean; depth: number }
  | { kind: 'handoff'; key: string; ts: string; from: string; to: string; task: string; depth: number }
  | { kind: 'report'; key: string; ts: string; from: string; to: string; summary: string; depth: number }
  | { kind: 'output'; key: string; ts: string; agent: string; summary: string; depth: number }
  | { kind: 'notice'; key: string; ts: string; agent: string; text: string; tone: 'warn' | 'error' | 'info'; depth: number }
  | { kind: 'check'; key: string; ts: string; passed: boolean; text: string; depth: number }
  | { kind: 'marker'; key: string; ts: string; text: string; tone: 'start' | 'end' | 'failed'; depth: number }
  | { kind: 'resolution'; key: string; ts: string; status: string | null; text: string; depth: number }
  | { kind: 'approval'; key: string; ts: string; text: string; ok: boolean; depth: number }

const depthOf = (e: AgentEvent) => Math.max(0, (e.chain?.length ?? 1) - 1)

/** One readable feed per run: tool calls are paired with their results, handoffs and reports are explicit. */
export function buildFeed(events: AgentEvent[]): FeedItem[] {
  const items: FeedItem[] = []
  const openTools = new Map<string, Extract<FeedItem, { kind: 'tool' }>>()
  for (const e of [...events].sort((a, b) => a.seq - b.seq)) {
    const key = String(e.seq)
    const agent = e.agent ?? 'system'
    const depth = depthOf(e)
    switch (e.action) {
      case 'run_start':
        items.push({ kind: 'marker', key, ts: e.ts, text: e.message, tone: 'start', depth: 0 })
        break
      case 'run_end':
        items.push({ kind: 'marker', key, ts: e.ts, text: e.message, tone: e.error ? 'failed' : 'end', depth: 0 })
        break
      case 'agent_start':
        if (agent === 'boss') items.push({ kind: 'start', key, ts: e.ts, agent, text: e.message, depth })
        break
      case 'model_step': {
        // "Decided to call: x, y" is already visible as the tool rows that follow; keep only real words.
        if (e.message && !e.message.startsWith('Decided to call') && e.message !== 'Thinking') {
          items.push({ kind: 'thought', key, ts: e.ts, agent, text: e.message, depth })
        }
        break
      }
      case 'tool_call': {
        const item = { kind: 'tool' as const, key, ts: e.ts, agent, name: e.tool?.name ?? '?', args: e.tool?.args ?? null, result: undefined, pending: true, depth }
        openTools.set(toolKey(e), item)
        items.push(item)
        break
      }
      case 'tool_result': {
        const open = openTools.get(toolKey(e))
        if (open) {
          open.result = e.tool?.result
          open.pending = false
          openTools.delete(toolKey(e))
        } else {
          items.push({ kind: 'tool', key, ts: e.ts, agent, name: e.tool?.name ?? '?', args: e.tool?.args ?? null, result: e.tool?.result, pending: false, depth })
        }
        break
      }
      case 'delegation_request':
        items.push({ kind: 'handoff', key, ts: e.ts, from: e.delegation?.from ?? agent, to: e.delegation?.to ?? '?', task: e.delegation?.task ?? '', depth })
        break
      case 'delegation_result':
        items.push({ kind: 'report', key, ts: e.ts, from: e.delegation?.to ?? '?', to: e.delegation?.from ?? agent, summary: e.message.replace(/^\w+ reported: /, ''), depth })
        break
      case 'delegation_reused':
        items.push({ kind: 'notice', key, ts: e.ts, agent, text: `Repeat request to ${e.delegation?.to}: the earlier answer was reused instead of running it again.`, tone: 'info', depth })
        break
      case 'delegation_blocked':
      case 'delegation_failed':
        items.push({ kind: 'notice', key, ts: e.ts, agent, text: e.message, tone: e.action === 'delegation_failed' ? 'error' : 'warn', depth })
        break
      case 'agent_output':
        if (agent === 'boss') items.push({ kind: 'output', key, ts: e.ts, agent, summary: e.message, depth })
        break
      case 'guardrail_check':
        items.push({ kind: 'check', key, ts: e.ts, passed: e.message.startsWith('PASS'), text: e.message.replace(/^(PASS|FAIL): /, ''), depth: 0 })
        break
      case 'resolution':
        items.push({ kind: 'resolution', key, ts: e.ts, status: e.approval_status, text: e.message.replace(/^Proposed resolution \([^)]*\): /, ''), depth: 0 })
        break
      case 'human_approval':
      case 'human_approval_rejected':
      case 'human_resolution':
      case 'human_resolution_rejected':
        items.push({ kind: 'approval', key, ts: e.ts, text: e.message, ok: !e.action.endsWith('_rejected'), depth: 0 })
        break
      case 'error':
        items.push({ kind: 'notice', key, ts: e.ts, agent, text: e.error ?? e.message, tone: 'error', depth })
        break
      default:
        break
    }
  }
  return items
}

function toolKey(e: AgentEvent): string {
  return `${(e.chain ?? []).join('>')}|${e.agent}|${e.tool?.name}|${JSON.stringify(e.tool?.args ?? null)}`
}

// ---------------------------------------------------------------------------------------------

export interface CrewMember {
  agent: AgentName
  state: 'idle' | 'working' | 'done'
  tools: string[]
  steps: number
  summary: string | null
  calledBy: string[]
}

/** Who took part in a run, what they are doing now, and what they concluded. */
export function crewState(run: Run | undefined): Record<AgentName, CrewMember> {
  const crew = {} as Record<AgentName, CrewMember>
  for (const a of ['boss', 'customer_service', 'inventory', 'accounting', 'facilities'] as AgentName[]) {
    crew[a] = { agent: a, state: 'idle', tools: [], steps: 0, summary: null, calledBy: [] }
  }
  if (!run) return crew
  const open = new Map<AgentName, number>()
  for (const e of run.events) {
    if (!isAgent(e.agent)) {
      if (e.action === 'delegation_request' && e.delegation && isAgent(e.delegation.to)) crew[e.delegation.to].calledBy.push(e.delegation.from)
      continue
    }
    const m = crew[e.agent]
    if (e.action === 'agent_start') open.set(e.agent, (open.get(e.agent) ?? 0) + 1)
    if (e.action === 'agent_output') {
      open.set(e.agent, Math.max(0, (open.get(e.agent) ?? 1) - 1))
      m.summary = e.message
    }
    if (e.action === 'model_step') m.steps += 1
    if (e.action === 'tool_call' && e.tool) m.tools.push(e.tool.name)
    if (e.action === 'delegation_request' && e.delegation && isAgent(e.delegation.to)) crew[e.delegation.to].calledBy.push(e.delegation.from)
  }
  for (const a of Object.keys(crew) as AgentName[]) {
    const m = crew[a]
    const ran = m.steps > 0 || m.summary !== null || (open.get(a) ?? 0) > 0
    m.state = (open.get(a) ?? 0) > 0 && run.status === 'running' ? 'working' : ran ? 'done' : 'idle'
    m.calledBy = [...new Set(m.calledBy)]
  }
  return crew
}

// ---------------------------------------------------------------------------------------------

type Obj = Record<string, unknown>
const isObj = (v: unknown): v is Obj => !!v && typeof v === 'object' && !Array.isArray(v)

/** The few fields of a tool result a person actually needs, as label/value pairs. */
export function resultHighlights(name: string, result: unknown): [string, string][] {
  if (!isObj(result)) return result === undefined ? [] : [['result', String(result)]]
  if (result.found === false) return [['not found', String(result.error ?? '')]]
  const r = result
  const inv = isObj(r.invoice) ? r.invoice : null
  const t = isObj(r.ticket) ? r.ticket : null
  switch (name) {
    case 'check_stock':
      return [['on hand', String(r.on_hand)], ['short', String(r.shortfall)], ['location', String(r.location)],
        ['other sizes', Array.isArray(r.other_sizes) ? (r.other_sizes as Obj[]).map((o) => `${o.size} ${o.qty}`).join(' · ') : '']]
    case 'get_rent_due':
      return [['rent', money(r.monthly_rent as number)], ['due', String(r.next_due)], ['in', `${r.days_until_due} days`]]
    case 'quote_bulk_order':
      return [['discount', `${r.discount_pct}%`], ['unit', money(r.unit_price as number)], ['revenue', money(r.total_revenue as number)],
        ['profit', money(r.gross_profit as number)], ['margin', `${r.margin_pct}%`]]
    case 'get_cash_position':
      return [['cash', money(r.total_balance as number)]]
    case 'project_cash_balance':
      return [['outflows', money(r.total_outflows as number)], ['ends at', money(r.ending_balance as number)],
        ['never negative', r.stays_non_negative ? 'yes' : 'NO']]
    case 'get_invoice':
      return inv ? [['invoice', `#${inv.invoice_id}`], ['amount', money(inv.amount as number)], ['due', String(inv.due_date)], ['status', inv.overdue ? 'overdue' : String(inv.status)]] : []
    case 'list_open_invoices':
      return [['open', String(r.count)], ['total', money(r.total_open as number)]]
    case 'list_payments':
      return [['payments', String(r.count)], ['total paid', money(r.total_paid as number)]]
    case 'list_vendors':
      return [['vendors', Array.isArray(r.vendors) && r.vendors.length ? (r.vendors as Obj[]).map((v) => `${v.name} (${v.lead_days}d)`).join(', ') : 'none found']]
    case 'get_ticket':
      return t ? [['type', String(t.type)], ['requester', String(t.requester)]] : []
    case 'list_open_tickets':
    case 'list_tickets':
      return [['tickets', String(r.count)]]
    default:
      return Object.entries(r).filter(([, v]) => v === null || typeof v !== 'object').slice(0, 4).map(([k, v]) => [k, String(v)])
  }
}

export function toolLabel(name: string): string {
  return name.startsWith('delegate_to_') ? `ask ${name.slice(12).replace('_', ' ')}` : name
}
