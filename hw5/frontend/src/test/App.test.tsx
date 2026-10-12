import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import type { TicketDetail } from '../types'
import fixtures from './fixtures.json'

// A mocked Problem 7 backend built from real (snapshotted) responses.
type Handler = (init: RequestInit | undefined, url: URL) => { status?: number; body: unknown }

function clone<T>(x: T): T {
  return JSON.parse(JSON.stringify(x)) as T
}

function backend(overrides: Record<string, Handler> = {}) {
  const state = { details: clone(fixtures.details) as Record<string, TicketDetail>, cash: clone(fixtures.cash), tickets: clone(fixtures.tickets) }
  const routes: Record<string, Handler> = {
    'GET /api/health': () => ({ body: fixtures.health }),
    'GET /api/tickets': () => ({ body: state.tickets }),
    'GET /api/cash': () => ({ body: state.cash }),
    'GET /api/events': (_i, url) => {
      const id = url.searchParams.get('ticket_id')!
      const after = Number(url.searchParams.get('after_seq') ?? -1)
      const evs = (fixtures.events as Record<string, { events: { seq: number }[] }>)[id].events.filter((e) => e.seq > after)
      return { body: { count: evs.length, last_seq: evs.at(-1)?.seq ?? after, events: evs } }
    },
    ...overrides,
  }
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    const method = init?.method ?? 'GET'
    const detailMatch = url.pathname.match(/^\/api\/tickets\/(\d+)$/)
    const key = `${method} ${detailMatch ? '/api/tickets/:id' : url.pathname}`
    const handler = routes[key] ?? (detailMatch && method === 'GET' ? () => ({ body: state.details[detailMatch[1]] }) : undefined)
    if (!handler) return new Response(JSON.stringify({ detail: `no mock for ${key}` }), { status: 404 })
    const { status = 200, body } = handler(init, url)
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  const posts = () => fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST').map(([u, init]) => ({ url: String(u), body: JSON.parse(String(init!.body)) }))
  return { fetchMock, state, posts }
}

/** Test-only: add an approvable payment to #102's proposal (the real saved proposals have none). */
function withApprovableRent(state: ReturnType<typeof backend>['state']) {
  const d = state.details['102']
  const p = d.proposal as Extract<TicketDetail['proposal'], { proposed_actions: unknown }>
  p.approval_status = 'pending_human_approval'
  p.proposed_actions = [{
    kind: 'payment', description: 'Pay Chapel Street shop rent to Elm City Properties', amount: 2400, payee: 'Elm City Properties',
    ref: 'lease 1', requires_human_approval: true, status: 'proposed', action_id: `${p.run_id}:0`, approval: null, approvable: true,
  }]
  state.tickets.tickets[1].proposal!.approvable_actions = 1
}

beforeEach(() => vi.useRealTimers())
afterEach(() => vi.unstubAllGlobals())

describe('dashboard', () => {
  it('shows the three tickets, their status, the desk date and the checking balance', async () => {
    backend()
    render(<App />)
    const queue = await screen.findByRole('navigation', { name: 'Tickets' })
    for (const subject of ['Bulldog tee', 'Rent due', 'Bulk hoodie discount']) expect(await within(queue).findByText(subject)).toBeInTheDocument()
    expect(within(queue).getAllByText('Open')).toHaveLength(3)
    expect(screen.getByTestId('cash-balance')).toHaveTextContent('$3,400.00')
    expect(screen.getByText(/Aug 31, 2026/)).toBeInTheDocument()
  })

  it('opens a case file with the real agent activity, crew report and handoffs, without sending anything', async () => {
    const { posts } = backend()
    render(<App />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Bulldog tee' })).toBeInTheDocument()
    const feed = screen.getByRole('region', { name: 'Agent activity' })
    expect(await within(feed).findAllByText('check_stock')).not.toHaveLength(0)
    expect(within(feed).getAllByText(/reported back to/).length).toBeGreaterThan(0)
    expect(screen.getByRole('region', { name: 'What each agent did' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Rent due/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Rent due' })).toBeInTheDocument()
    expect(posts()).toEqual([]) // selecting tickets never runs, pays, or resets anything
  })

  it('shows a helpful empty state when the saved proposal has nothing to approve', async () => {
    backend()
    render(<App />)
    const decision = await screen.findByRole('complementary', { name: 'Proposal and approvals' })
    expect(await within(decision).findByText('Nothing to approve on this proposal')).toBeInTheDocument()
    expect(within(decision).getByText(/uses Portkey credits/)).toBeInTheDocument()
    expect(within(decision).queryByRole('button', { name: /review & approve/i })).toBeNull() // no payment to approve
    expect(within(decision).getByRole('button', { name: /Approve resolution/ })).toBeEnabled() // resolution is a separate action
    expect(within(decision).getByText('Draft · not sent')).toBeInTheDocument()
  })

  it('only starts a run after an explicit confirmation', async () => {
    const { posts } = backend({ 'POST /api/tickets/101/run': () => ({ status: 202, body: { run: { ticket_id: 101, status: 'running' } } }) })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /Run the agent team/ }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/gpt-6-luna through Portkey/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
    expect(posts()).toEqual([])

    await userEvent.click(screen.getByRole('button', { name: /Run the agent team/ }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Start run' }))
    await waitFor(() => expect(posts()).toEqual([{ url: 'http://localhost:8000/api/tickets/101/run', body: { wait: false } }]))
  })

  it('approves a payment only with a name and an explicit confirmation, then shows the new balance and Resolved', async () => {
    const mock = backend({
      'POST /api/approvals': (init) => {
        const body = JSON.parse(String(init!.body))
        mock.state.cash.balance = 1000
        mock.state.tickets.tickets[1].status = 'resolved'
        const d = mock.state.details['102']
        d.ticket.status = 'resolved'
        const p = d.proposal as { proposed_actions: { approval: unknown; approvable: boolean }[] }
        p.proposed_actions[0].approval = { action_id: body.action_id, payment_id: 1, payment_kind: 'rent', ref_id: 1, amount: 2400, approved_by: body.approved_by, balance_before: 3400, balance_after: 1000, ticket_status: 'resolved' }
        p.proposed_actions[0].approvable = false
        return { body: { approved: true, action_id: body.action_id, payment_id: 1, payment_kind: 'rent', ref_id: 1, amount: 2400, approved_by: body.approved_by, balance_before: 3400, balance_after: 1000, ticket_status: 'resolved', description: 'rent', paid_at: '2026-08-31' } }
      },
    })
    withApprovableRent(mock.state)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /Rent due/ }))
    const decision = await screen.findByRole('complementary', { name: 'Proposal and approvals' })
    expect(await within(decision).findByText('$2,400.00')).toBeInTheDocument()
    expect(within(decision).getByText('Awaiting your approval')).toBeInTheDocument()

    await userEvent.click(within(decision).getByRole('button', { name: 'Review & approve' }))
    const dialog = screen.getByRole('dialog')
    const approve = within(dialog).getByRole('button', { name: 'Approve $2,400.00' })
    expect(within(dialog).getByText('$1,000.00')).toBeInTheDocument() // cash preview after payment
    expect(approve).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Your name'), 'Navya Sharma')
    expect(approve).toBeDisabled() // still needs the explicit checkbox
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /I approve paying/ }))
    expect(approve).toBeEnabled()
    await userEvent.click(approve)

    await waitFor(() => expect(mock.posts()).toEqual([{
      url: 'http://localhost:8000/api/approvals',
      body: { ticket_id: 102, action_id: '764bd24fd7ee:0', amount: 2400, approved_by: 'Navya Sharma', confirm: true, resolve_ticket: true },
    }]))
    await waitFor(() => expect(screen.getByTestId('cash-balance')).toHaveTextContent('$1,000.00'))
    expect(await within(decision).findByText(/Approved by Navya Sharma/)).toBeInTheDocument()
    expect(within(screen.getByRole('navigation', { name: 'Tickets' })).getByText('Resolved')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Run the agent team/ })).toBeDisabled()
  })

  it('keeps the approval dialog open and explains a refusal from the backend', async () => {
    const mock = backend({ 'POST /api/approvals': () => ({ status: 409, body: { detail: 'Insufficient cash: checking has $100.00; $2,400.00 would leave $-2,300.00.' } }) })
    withApprovableRent(mock.state)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /Rent due/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Review & approve' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Your name'), 'Navya Sharma')
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /I approve paying/ }))
    await userEvent.click(within(dialog).getByRole('button', { name: /Approve/ }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('409: Insufficient cash')
    expect(screen.getByTestId('cash-balance')).toHaveTextContent('$3,400.00')
  })

  it('blocks approval in the UI when it would take checking below zero', async () => {
    const mock = backend()
    withApprovableRent(mock.state)
    mock.state.cash.balance = 100
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /Rent due/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Review & approve' }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/below \$0/)).toBeInTheDocument()
    await userEvent.type(within(dialog).getByLabelText('Your name'), 'Navya Sharma')
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /I approve paying/ }))
    expect(within(dialog).getByRole('button', { name: /Approve/ })).toBeDisabled()
    expect(mock.posts()).toEqual([])
  })

  it('explains clearly when the backend is offline', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    render(<App />)
    expect(await screen.findByText('The dashboard can’t reach the backend.')).toBeInTheDocument()
    expect(screen.getByText(/uvicorn main:app --reload --port 8000/)).toBeInTheDocument()
    expect(screen.getByText('Backend offline')).toBeInTheDocument()
  })

  it('shows an error notice when a request fails', async () => {
    backend({ 'GET /api/cash': () => ({ status: 500, body: { detail: 'database is locked' } }) })
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('database is locked')
  })

  it('requires typing RESET before resetting the working database', async () => {
    const { posts } = backend({ 'POST /api/reset': () => ({ body: { reset: true, cash: fixtures.cash } }) })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Desk tools' }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Reset working database/ }))
    const dialog = screen.getByRole('dialog')
    const go = within(dialog).getByRole('button', { name: 'Reset database' })
    expect(go).toBeDisabled()
    await userEvent.type(within(dialog).getByRole('textbox'), 'reset')
    expect(go).toBeDisabled()
    await userEvent.clear(within(dialog).getByRole('textbox'))
    await userEvent.type(within(dialog).getByRole('textbox'), 'RESET')
    await userEvent.click(go)
    await waitFor(() => expect(posts()).toEqual([{ url: 'http://localhost:8000/api/reset', body: { confirm: true } }]))
  })

  it('resolves a ticket only after a name and explicit confirmation, without moving money', async () => {
    const mock = backend({
      'POST /api/tickets/:id/resolve': () => ({ body: {} }),
    })
    // route the dynamic resolve path through the generic handler
    const fetchMock = mock.fetchMock
    const original = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input))
      if (url.pathname === '/api/tickets/101/resolve' && init?.method === 'POST') {
        mock.state.tickets.tickets[0].status = 'resolved'
        mock.state.details['101'].ticket.status = 'resolved'
        return new Response(JSON.stringify({ resolved: true, ticket_id: 101, ticket_status: 'resolved', left_unpaid: [], paid: [] }), { status: 200 })
      }
      return original(input, init)
    })
    render(<App />)
    const decision = await screen.findByRole('complementary', { name: 'Proposal and approvals' })
    await userEvent.click(await within(decision).findByRole('button', { name: /Approve resolution/ }))
    const dialog = screen.getByRole('dialog')
    const go = within(dialog).getByRole('button', { name: 'Resolve ticket' })
    expect(within(dialog).getByText(/moves no money/)).toBeInTheDocument()
    expect(go).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText('Your name'), 'Navya Sharma')
    expect(go).toBeDisabled()
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /I approve resolving ticket/ }))
    await userEvent.click(go)
    await waitFor(() => expect(mock.posts()).toEqual([{
      url: 'http://localhost:8000/api/tickets/101/resolve',
      body: { run_id: '091629024cde', approved_by: 'Navya Sharma', confirm: true, acknowledge_unpaid: false },
    }]))
    expect(await within(screen.getByRole('navigation', { name: 'Tickets' })).findByText('Resolved')).toBeInTheDocument()
  })

  it('makes the human explicitly leave pending payments unpaid before resolving', async () => {
    const mock = backend()
    withApprovableRent(mock.state)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: /Rent due/ }))
    const decision = await screen.findByRole('complementary', { name: 'Proposal and approvals' })
    expect(await within(decision).findByText(/still awaits your decision/)).toBeInTheDocument()
    await userEvent.click(within(decision).getByRole('button', { name: /Approve resolution/ }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText('Your name'), 'Navya Sharma')
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /I approve resolving ticket/ }))
    const go = within(dialog).getByRole('button', { name: 'Resolve ticket' })
    expect(go).toBeDisabled() // still needs the explicit "leave unpaid" choice
    await userEvent.click(within(dialog).getByRole('checkbox', { name: /unpaid/ }))
    expect(go).toBeEnabled()
    expect(mock.posts()).toEqual([])
  })
})

