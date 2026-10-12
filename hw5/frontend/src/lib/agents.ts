import type { Actor, AgentName } from '../types'

export interface AgentMeta {
  label: string
  short: string
  role: string
  monogram: string
  color: string // identity colour, also used for tints via color-mix()
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: { label: 'Boss', short: 'Boss', role: 'Coordinates the team and proposes the resolution', monogram: 'B', color: '#1d3f72' },
  customer_service: { label: 'Customer Service', short: 'Service', role: 'Reads the request, drafts the reply', monogram: 'CS', color: '#c2410c' },
  inventory: { label: 'Inventory', short: 'Inventory', role: 'Stock, shortfalls, vendor lead times', monogram: 'IN', color: '#0f766e' },
  accounting: { label: 'Accounting', short: 'Accounting', role: 'Cash, invoices, pricing, projections', monogram: 'AC', color: '#a16207' },
  facilities: { label: 'Facilities', short: 'Facilities', role: 'Leases, rent, the shop space', monogram: 'FA', color: '#6d28d9' },
}

export const CREW_ORDER: AgentName[] = ['boss', 'customer_service', 'inventory', 'accounting', 'facilities']

const OTHERS: Record<'guardrails' | 'human', AgentMeta> = {
  guardrails: { label: 'Guardrails', short: 'Rules', role: 'Code-level shop-rule checks', monogram: '✓', color: '#475569' },
  human: { label: 'You', short: 'You', role: 'Human approval', monogram: '★', color: '#15803d' },
}

export function actorMeta(actor: string | null | undefined): AgentMeta {
  if (actor && actor in AGENTS) return AGENTS[actor as AgentName]
  if (actor && actor in OTHERS) return OTHERS[actor as 'guardrails' | 'human']
  return { label: actor ?? 'System', short: actor ?? 'System', role: '', monogram: '·', color: '#64748b' }
}

export function isAgent(actor: string | null | undefined): actor is AgentName {
  return !!actor && actor in AGENTS
}

export type ActorName = Actor
