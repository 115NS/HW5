import { describe, expect, it } from 'vitest'
import { buildFeed, crewState, groupRuns, resultHighlights } from '../lib/activity'
import type { AgentEvent } from '../types'
import fixtures from './fixtures.json'

const events101 = fixtures.events['101'].events as AgentEvent[]
const events102 = fixtures.events['102'].events as AgentEvent[]

describe('groupRuns', () => {
  it('finds the Problem 5 live run for #101 with its real stats', () => {
    const runs = groupRuns(events101)
    expect(runs).toHaveLength(1)
    expect(runs[0]).toMatchObject({ ticketId: 101, status: 'completed', models: 'gpt-6-luna', requests: 14, delegations: 4 })
  })

  it('treats a run without run_end as still running', () => {
    const partial = events101.filter((e) => e.action !== 'run_end')
    expect(groupRuns(partial)[0].status).toBe('running')
  })

  it('keeps human approvals out of agent runs', () => {
    const approval: AgentEvent = { ...events101[0], seq: 9999, run_id: 'human-abc', action: 'human_approval', agent: 'human' }
    expect(groupRuns([...events101, approval])).toHaveLength(1)
  })
})

describe('buildFeed', () => {
  const feed = buildFeed(events101)

  it('pairs every tool call with its result', () => {
    const tools = feed.filter((f) => f.kind === 'tool')
    expect(tools.length).toBe(events101.filter((e) => e.action === 'tool_call').length)
    expect(tools.every((t) => t.kind === 'tool' && !t.pending)).toBe(true)
    expect(tools.map((t) => t.kind === 'tool' && t.name)).toContain('check_stock')
  })

  it('shows handoffs and reports with who asked whom', () => {
    const handoffs = feed.filter((f) => f.kind === 'handoff')
    expect(handoffs).toHaveLength(4)
    expect(handoffs.map((h) => h.kind === 'handoff' && `${h.from}>${h.to}`)).toContain('customer_service>inventory')
    expect(feed.filter((f) => f.kind === 'report')).toHaveLength(4)
  })

  it('includes guardrail checks, the resolution, and run markers', () => {
    expect(feed.filter((f) => f.kind === 'check').length).toBeGreaterThan(0)
    expect(feed.some((f) => f.kind === 'resolution')).toBe(true)
    expect(feed[0].kind).toBe('marker')
    expect(feed.at(-1)?.kind).toBe('marker')
  })

  it('marks a tool call without a result as pending', () => {
    const lastCall = events101.findLastIndex((e) => e.action === 'tool_call')
    const cut = buildFeed(events101.slice(0, lastCall + 1))
    expect(cut.filter((f) => f.kind === 'tool' && f.pending)).toHaveLength(1)
  })
})

describe('crewState', () => {
  it('shows which agents worked on #102 and which were not needed', () => {
    const crew = crewState(groupRuns(events102)[0])
    expect(crew.boss.state).toBe('done')
    expect(crew.facilities.state).toBe('done')
    expect(crew.accounting.state).toBe('done')
    expect(crew.inventory.state).toBe('idle')
    expect(crew.customer_service.state).toBe('idle')
    expect(crew.facilities.tools).toContain('get_rent_due')
    expect(crew.accounting.calledBy).toEqual(expect.arrayContaining(['boss', 'facilities']))
    expect(crew.facilities.summary).toBeTruthy()
  })

  it('marks an agent as working while its turn is open in a running run', () => {
    const firstFacilitiesStart = events102.findIndex((e) => e.agent === 'facilities' && e.action === 'agent_start')
    const crew = crewState(groupRuns(events102.slice(0, firstFacilitiesStart + 2))[0])
    expect(crew.facilities.state).toBe('working')
  })
})

describe('resultHighlights', () => {
  it('pulls the useful fields out of check_stock', () => {
    const hl = Object.fromEntries(resultHighlights('check_stock', { on_hand: 0, shortfall: 1, location: 'Aisle B', other_sizes: [{ size: 'M', qty: 5 }] }))
    expect(hl).toMatchObject({ 'on hand': '0', short: '1', location: 'Aisle B', 'other sizes': 'M 5' })
  })

  it('formats money and handles not-found results', () => {
    expect(Object.fromEntries(resultHighlights('project_cash_balance', { total_outflows: 3240, ending_balance: 160, stays_non_negative: true })))
      .toMatchObject({ 'ends at': '$160.00', 'never negative': 'yes' })
    expect(resultHighlights('get_invoice', { found: false, error: 'No invoice with id 9.' })).toEqual([['not found', 'No invoice with id 9.']])
  })
})
