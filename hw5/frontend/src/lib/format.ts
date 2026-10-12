const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export function money(n: number | null | undefined): string {
  return n == null ? '—' : usd.format(n)
}

export function deskDate(iso: string | undefined): string {
  if (!iso) return ''
  const d = new Date(`${iso}T12:00:00`)
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })
}

export function shortDateTime(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function duration(fromIso: string, toIso: string): string {
  const s = Math.max(0, Math.round((new Date(toIso).getTime() - new Date(fromIso).getTime()) / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`
}

export const TICKET_TYPES: Record<string, { label: string; icon: 'tee' | 'building' | 'tag' | 'ticket' }> = {
  customer_order: { label: 'Customer order', icon: 'tee' },
  rent_notice: { label: 'Rent notice', icon: 'building' },
  price_override: { label: 'Price override', icon: 'tag' },
}

export function ticketType(type: string) {
  return TICKET_TYPES[type] ?? { label: type.replace(/_/g, ' '), icon: 'ticket' as const }
}

export function itemLine(t: { qty: number | null; sku: string | null; size: string | null; lease_id: number | null; invoice_id: number | null }): string {
  if (t.sku) return `${t.qty ?? 1} × ${t.sku}${t.size ? ` · size ${t.size}` : ''}`
  if (t.lease_id != null) return `Lease ${t.lease_id}`
  if (t.invoice_id != null) return `Invoice ${t.invoice_id}`
  return ''
}

/** Render tool arguments the way a person reads them: check_stock(sku "CC-TEE-WHITE", size "S", qty 1). */
export function argList(args: Record<string, unknown> | null | undefined): string {
  if (!args) return ''
  return Object.entries(args)
    .map(([k, v]) => {
      if (Array.isArray(v)) return `${k} [${v.length}]`
      return `${k} ${typeof v === 'string' ? `"${v}"` : JSON.stringify(v)}`
    })
    .join(', ')
}
