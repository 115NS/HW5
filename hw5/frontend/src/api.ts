// Thin client for the Problem 7 backend. The dashboard never touches the database:
// every read and every write goes through these routes and their safeguards.
import type {
  ApprovalResult,
  Cash,
  EventsResponse,
  Health,
  RunInfo,
  TicketDetail,
  TicketsResponse,
} from './types'

export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number // 0 = the backend could not be reached
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type ValidationItem = { loc?: (string | number)[]; msg?: string }

function describe(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((d) => `${(d.loc ?? []).filter((p) => p !== 'body').join('.') || 'request'}: ${d.msg ?? 'invalid'}`)
      .join('; ')
  }
  return 'Unexpected response from the backend.'
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`)
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // non-JSON body (e.g. a proxy error page); fall through with null
  }
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail: unknown }).detail : null
    throw new ApiError(res.status, detail ? describe(detail) : `${res.status} ${res.statusText || 'request failed'}`)
  }
  return body as T
}

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/api/health'),
  tickets: () => request<TicketsResponse>('/api/tickets'),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  cash: () => request<Cash>('/api/cash'),
  events: (ticketId: number, afterSeq = -1, limit = 500) =>
    request<EventsResponse>(`/api/events?ticket_id=${ticketId}&after_seq=${afterSeq}&limit=${limit}`),
  /** Starts the agent team in the background (202). Only ever called from an explicit button + confirmation. */
  run: (id: number) => request<{ run: RunInfo }>(`/api/tickets/${id}/run`, post({ wait: false })),
  /** A human's explicit approval of one proposed payment or purchase. */
  approve: (body: { ticket_id: number; action_id: string; amount: number; approved_by: string; confirm: true; resolve_ticket: boolean }) =>
    request<ApprovalResult>('/api/approvals', post(body)),
  /** A human approves a ticket's latest proposed resolution (no money moves). */
  resolve: (id: number, body: { run_id: string; approved_by: string; confirm: true; acknowledge_unpaid: boolean; note?: string }) =>
    request<{ resolved: true; ticket_id: number; ticket_status: string; left_unpaid: unknown[]; paid: unknown[] }>(`/api/tickets/${id}/resolve`, post(body)),
  reset: () => request<{ reset: boolean; cash: Cash }>('/api/reset', post({ confirm: true })),
}
