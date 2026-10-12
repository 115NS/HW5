import { itemLine, shortDateTime, ticketType } from '../lib/format'
import type { TicketDetail, TicketSummary } from '../types'
import { isFailedProposal } from '../types'
import { Icon } from './Icon'

interface Props {
  tickets: TicketSummary[] | null
  details: Record<number, TicketDetail>
  selectedId: number | null
  onSelect: (id: number) => void
}

export function TicketQueue({ tickets, details, selectedId, onSelect }: Props) {
  const open = tickets?.filter((t) => t.status === 'open').length ?? 0
  return (
    <nav className="queue" aria-label="Tickets">
      <div className="panel-head">
        <h2>Ticket queue</h2>
        {tickets && <span className="count-chip">{open} open · {tickets.length - open} resolved</span>}
      </div>

      {!tickets && (
        <div className="queue-list" aria-busy>
          {[0, 1, 2].map((i) => <div key={i} className="ticket-card skeleton" />)}
        </div>
      )}
      {tickets && tickets.length === 0 && <p className="empty-line">No tickets in the database.</p>}

      {tickets && tickets.length > 0 && (
        <ul className="queue-list">
          {tickets.map((t) => {
            const type = ticketType(t.type)
            const d = details[t.id]
            const running = t.run?.status === 'running'
            const failed = t.run?.status === 'failed' || isFailedProposal(d?.proposal ?? null)
            const pending = t.proposal?.approvable_actions ?? 0
            return (
              <li key={t.id}>
                <button
                  className={`ticket-card ${selectedId === t.id ? 'selected' : ''} ${t.status === 'resolved' ? 'is-resolved' : ''}`}
                  aria-current={selectedId === t.id ? 'true' : undefined}
                  onClick={() => onSelect(t.id)}
                >
                  <span className={`ticket-icon type-${t.type}`}><Icon name={type.icon} size={20} /></span>
                  <span className="ticket-body">
                    <span className="ticket-top">
                      <span className="ticket-no">#{t.id}</span>
                      <StatusPill status={t.status} />
                    </span>
                    <span className="ticket-subject">{t.subject}</span>
                    <span className="ticket-meta">{type.label} · {t.requester}</span>
                    {itemLine(t) && <span className="ticket-item">{itemLine(t)}</span>}
                    <span className="ticket-foot">
                      {running && <span className="badge badge-run"><span className="pulse-dot" /> Team working</span>}
                      {!running && failed && <span className="badge badge-bad">Last run failed</span>}
                      {!running && !failed && pending > 0 && <span className="badge badge-await">{pending} awaiting approval</span>}
                      {!running && !failed && pending === 0 && t.proposal && <span className="badge badge-quiet">Proposal on file</span>}
                      {!running && !t.proposal && <span className="badge badge-quiet">Not run yet</span>}
                      <span className="ticket-time">{shortDateTime(t.created_at)}</span>
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </nav>
  )
}

export function StatusPill({ status }: { status: 'open' | 'resolved' }) {
  return (
    <span className={`status-pill status-${status}`}>
      {status === 'resolved' ? <Icon name="check" size={12} /> : <span className="status-dot" aria-hidden />}
      {status === 'resolved' ? 'Resolved' : 'Open'}
    </span>
  )
}
