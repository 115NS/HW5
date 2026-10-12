import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from './api'
import type { AgentEvent, ApprovalResult, Cash, Health, TicketDetail, TicketSummary } from './types'

export const FAST_POLL_MS = 1200 // while an agent run is in progress
export const SLOW_POLL_MS = 6000 // otherwise

export interface Notice {
  id: number
  tone: 'error' | 'success' | 'info'
  title: string
  text: string
}

interface EventLog {
  events: AgentEvent[]
  lastSeq: number
  loaded: boolean
}

export interface Desk {
  health: Health | null
  offline: string | null // set when the backend can't be reached
  tickets: TicketSummary[] | null
  deskDate: string | null
  cash: Cash | null
  cashPulse: number // bumps when the balance changes, to animate the cash tile
  details: Record<number, TicketDetail>
  selectedId: number | null
  select: (id: number) => void
  events: EventLog
  anyRunning: boolean
  notices: Notice[]
  dismiss: (id: number) => void
  startRun: (id: number) => Promise<boolean>
  approve: (args: { ticketId: number; actionId: string; amount: number; approvedBy: string; resolveTicket: boolean }) => Promise<ApprovalResult>
  resolve: (args: { ticketId: number; runId: string; approvedBy: string; acknowledgeUnpaid: boolean; note?: string }) => Promise<void>
  reset: () => Promise<boolean>
  refresh: () => Promise<void>
}

const EMPTY_LOG: EventLog = { events: [], lastSeq: -1, loaded: false }

export function useDesk(): Desk {
  const [health, setHealth] = useState<Health | null>(null)
  const [offline, setOffline] = useState<string | null>(null)
  const [tickets, setTickets] = useState<TicketSummary[] | null>(null)
  const [deskDate, setDeskDate] = useState<string | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [cashPulse, setCashPulse] = useState(0)
  const [details, setDetails] = useState<Record<number, TicketDetail>>({})
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [logs, setLogs] = useState<Record<number, EventLog>>({})
  const [notices, setNotices] = useState<Notice[]>([])

  const noticeId = useRef(0)
  const logsRef = useRef(logs)
  logsRef.current = logs
  const cashRef = useRef<number | null>(null)

  const notify = useCallback((tone: Notice['tone'], title: string, text: string) => {
    const id = ++noticeId.current
    setNotices((n) => [...n.filter((x) => x.title !== title), { id, tone, title, text }].slice(-4))
    if (tone !== 'error') setTimeout(() => setNotices((n) => n.filter((x) => x.id !== id)), 6000)
  }, [])

  const dismiss = useCallback((id: number) => setNotices((n) => n.filter((x) => x.id !== id)), [])

  /** Everything except events: health, tickets, cash, and each ticket's proposal. */
  const refresh = useCallback(async () => {
    try {
      const [h, t, c] = await Promise.all([api.health(), api.tickets(), api.cash()])
      const ds = await Promise.all(t.tickets.map((x) => api.ticket(x.id)))
      setHealth(h)
      setTickets(t.tickets)
      setDeskDate(t.desk_date)
      if (cashRef.current !== null && cashRef.current !== c.balance) setCashPulse((p) => p + 1)
      cashRef.current = c.balance
      setCash(c)
      setDetails(Object.fromEntries(ds.map((d) => [d.ticket.id, d])))
      setOffline(null)
      setSelectedId((cur) => cur ?? t.tickets.find((x) => x.status === 'open')?.id ?? t.tickets[0]?.id ?? null)
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) setOffline(err.message)
      else notify('error', 'Could not refresh the desk', err instanceof Error ? err.message : String(err))
    }
  }, [notify])

  const pullEvents = useCallback(async (ticketId: number) => {
    const log = logsRef.current[ticketId] ?? EMPTY_LOG
    try {
      const res = await api.events(ticketId, log.lastSeq)
      setLogs((all) => {
        const cur = all[ticketId] ?? EMPTY_LOG
        if (cur.lastSeq !== log.lastSeq) return all // a newer pull already landed
        const seen = new Set(cur.events.map((e) => e.seq))
        return { ...all, [ticketId]: { events: [...cur.events, ...res.events.filter((e) => !seen.has(e.seq))], lastSeq: res.last_seq, loaded: true } }
      })
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 0)) notify('error', 'Could not load agent activity', err instanceof Error ? err.message : String(err))
    }
  }, [notify])

  const anyRunning = Object.values(details).some((d) => d.run?.status === 'running')

  // Poll: fast while a run is going, slow otherwise. Events only for the ticket on screen.
  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout>
    const tick = async () => {
      await refresh()
      if (selectedId != null) await pullEvents(selectedId)
      if (alive) timer = setTimeout(tick, anyRunning ? FAST_POLL_MS : SLOW_POLL_MS)
    }
    timer = setTimeout(tick, anyRunning ? FAST_POLL_MS : SLOW_POLL_MS)
    return () => {
      alive = false
      clearTimeout(timer)
    }
  }, [refresh, pullEvents, selectedId, anyRunning])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (selectedId != null && !logsRef.current[selectedId]?.loaded) void pullEvents(selectedId)
  }, [selectedId, pullEvents])

  // Announce when a run finishes, so the result doesn't slip by unnoticed.
  const prevRuns = useRef<Record<number, string | undefined>>({})
  useEffect(() => {
    for (const d of Object.values(details)) {
      const before = prevRuns.current[d.ticket.id]
      const now = d.run?.status
      if (before === 'running' && now === 'completed') notify('success', `Ticket #${d.ticket.id}: the team finished`, 'A new proposal is ready for your review.')
      if (before === 'running' && now === 'failed') notify('error', `Ticket #${d.ticket.id}: the run failed`, d.run?.error ?? 'See the activity feed for details.')
      prevRuns.current[d.ticket.id] = now
    }
  }, [details, notify])

  const startRun = useCallback(async (id: number) => {
    try {
      await api.run(id)
      notify('info', `Ticket #${id}: team dispatched`, 'Agent activity will stream into the feed as it happens.')
      await refresh()
      await pullEvents(id)
      return true
    } catch (err) {
      notify('error', `Couldn't start the run for #${id}`, err instanceof Error ? err.message : String(err))
      return false
    }
  }, [notify, refresh, pullEvents])

  const approve: Desk['approve'] = useCallback(async ({ ticketId, actionId, amount, approvedBy, resolveTicket }) => {
    const result = await api.approve({ ticket_id: ticketId, action_id: actionId, amount, approved_by: approvedBy, confirm: true, resolve_ticket: resolveTicket })
    notify('success', 'Payment recorded', `${approvedBy} approved ${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(result.amount)}. Checking is now ${new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(result.balance_after)}.`)
    await refresh()
    await pullEvents(ticketId)
    return result
  }, [notify, refresh, pullEvents])

  const resolve: Desk['resolve'] = useCallback(async ({ ticketId, runId, approvedBy, acknowledgeUnpaid, note }) => {
    await api.resolve(ticketId, { run_id: runId, approved_by: approvedBy, confirm: true, acknowledge_unpaid: acknowledgeUnpaid, ...(note ? { note } : {}) })
    notify('success', `Ticket #${ticketId} resolved`, `${approvedBy} approved the proposed resolution. No money moved.`)
    await refresh()
    await pullEvents(ticketId)
  }, [notify, refresh, pullEvents])

  const reset = useCallback(async () => {
    try {
      await api.reset()
      notify('success', 'Working database reset', 'Cash, tickets, invoices and payments are back to their original values.')
      setLogs({})
      await refresh()
      return true
    } catch (err) {
      notify('error', 'Reset failed', err instanceof Error ? err.message : String(err))
      return false
    }
  }, [notify, refresh])

  return {
    health, offline, tickets, deskDate, cash, cashPulse, details, selectedId,
    select: setSelectedId,
    events: (selectedId != null && logs[selectedId]) || EMPTY_LOG,
    anyRunning, notices, dismiss, startRun, approve, resolve, reset, refresh,
  }
}
