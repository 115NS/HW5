import { useState, type CSSProperties, type ReactNode } from 'react'
import { ApiError } from '../api'
import { actorMeta } from '../lib/agents'
import { money } from '../lib/format'
import type { Cash, Proposal, ProposedAction, TicketDetail } from '../types'
import { isFailedProposal } from '../types'
import { labelStatus } from './CaseFile'
import { Dialog } from './Dialog'
import { Icon } from './Icon'

interface Props {
  detail: TicketDetail | undefined
  cash: Cash | null
  onApprove: (args: { ticketId: number; actionId: string; amount: number; approvedBy: string; resolveTicket: boolean }) => Promise<unknown>
  onResolve: (args: { ticketId: number; runId: string; approvedBy: string; acknowledgeUnpaid: boolean; note?: string }) => Promise<void>
}

const KIND_LABEL: Record<string, string> = {
  payment: 'Payment', restock_order: 'Purchase', discount_offer: 'Discount offer', customer_reply: 'Customer reply',
  substitute_offer: 'Substitute offer', hold: 'Hold', escalate: 'Escalate', other: 'Other',
}

export function DecisionPanel({ detail, cash, onApprove, onResolve }: Props) {
  const [approving, setApproving] = useState<ProposedAction | null>(null)
  const [resolving, setResolving] = useState(false)

  if (!detail) return <aside className="decision" aria-busy><div className="skeleton-block tall" /></aside>
  const p = detail.proposal
  const running = detail.run?.status === 'running'

  return (
    <aside className="decision" aria-label="Proposal and approvals">
      <div className="panel-head">
        <h2>Decision</h2>
        {detail.ticket.status === 'resolved'
          ? <span className="approval-chip ap-resolved">resolved by a human</span>
          : p && !isFailedProposal(p) && <span className={`approval-chip ap-${p.approval_status}`}>{labelStatus(p.approval_status)}</span>}
      </div>

      {running && (
        <div className="callout callout-info"><span className="spinner sm" /> The team is preparing a new proposal. The one below is from the previous run.</div>
      )}

      {!p && (
        <Empty icon="inbox" title="No proposal yet">
          Run the agent team on this ticket to get a proposed resolution. Nothing runs until you press the button.
        </Empty>
      )}

      {p && isFailedProposal(p) && (
        <div className="callout callout-bad"><Icon name="alert" size={16} /> The last run didn’t produce a proposal: {p.error}</div>
      )}

      {p && !isFailedProposal(p) && (
        <>
          <ProposalSummary p={p} />
          <Approvals p={p} ticketStatus={detail.ticket.status} onReview={setApproving} />
          <ResolveCard p={p} ticketStatus={detail.ticket.status} running={running} onOpen={() => setResolving(true)} />
          {p.customer_reply_draft && <ReplyDraft draft={p.customer_reply_draft} />}
          <Details p={p} />
        </>
      )}

      {approving && p && !isFailedProposal(p) && (
        <ApproveDialog
          action={approving}
          ticketId={detail.ticket.id}
          cash={cash}
          onClose={() => setApproving(null)}
          onApprove={onApprove}
          lastPending={p.proposed_actions.filter((a) => a.approvable).length === 1}
        />
      )}

      {resolving && p && !isFailedProposal(p) && (
        <ResolveDialog p={p} ticketId={detail.ticket.id} onClose={() => setResolving(false)} onResolve={onResolve} />
      )}
    </aside>
  )
}

function ProposalSummary({ p }: { p: Proposal }) {
  return (
    <section className="proposal">
      <p className="proposal-summary">{p.summary}</p>
      <div className="recommend">
        <span className="eyebrow">Recommended</span>
        <p>{p.recommended_option}</p>
      </div>
      {p.options.length > 1 && (
        <details className="options">
          <summary>{p.options.length} options considered</summary>
          <ol>{p.options.map((o, i) => <li key={i}>{o}</li>)}</ol>
        </details>
      )}
    </section>
  )
}

function Approvals({ p, ticketStatus, onReview }: { p: Proposal; ticketStatus: string; onReview: (a: ProposedAction) => void }) {
  const payable = p.proposed_actions.filter((a) => a.kind === 'payment' || a.kind === 'restock_order')
  const slips = payable.filter((a) => a.approvable || a.approval)
  const others = p.proposed_actions.filter((a) => !slips.includes(a))
  return (
    <section className="approvals" aria-label="Payments and purchases">
      <h3 className="section-title">Payments &amp; purchases</h3>
      {slips.length === 0 && (
        <Empty icon="coin" title="Nothing to approve on this proposal">
          {payable.length
            ? 'The agents suggested a payment or purchase, but it has no verified amount, so the guardrails blocked it. Nothing can be paid from this proposal.'
            : 'The agents didn’t propose a payment or purchase with an amount for this ticket.'}{' '}
          {ticketStatus === 'open' && 'A new run might produce one. That uses Portkey credits, so it only happens when you press Run.'}
        </Empty>
      )}
      {slips.map((a) => <Slip key={a.action_id} a={a} onReview={() => onReview(a)} />)}

      {others.length > 0 && (
        <>
          <h3 className="section-title">Other proposed actions</h3>
          <ul className="action-list">
            {others.map((a, i) => (
              <li key={a.action_id ?? i}>
                <span className={`kind-chip kind-${a.kind}`}>{KIND_LABEL[a.kind] ?? a.kind}</span>
                <span className="action-desc">{a.description}</span>
                <span className="action-why">{whyNotPayable(a)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

function whyNotPayable(a: ProposedAction): string {
  if (a.status === 'blocked_by_guardrail') return a.amount ? 'Blocked by a guardrail' : 'Blocked: no amount to check against cash'
  if (a.kind === 'customer_reply') return 'Draft for a human to send'
  if (a.kind === 'discount_offer') return 'A pricing decision, not a payment'
  if (a.kind === 'substitute_offer') return 'Offer for a human to make'
  return a.requires_human_approval ? 'Needs a human decision' : 'Informational'
}

function Slip({ a, onReview }: { a: ProposedAction; onReview: () => void }) {
  const approved = a.approval
  return (
    <article className={`slip ${approved ? 'slip-approved' : ''}`}>
      <div className="slip-top">
        <span className={`kind-chip kind-${a.kind}`}>{KIND_LABEL[a.kind]}</span>
        <span className="slip-amount">{money(a.amount)}</span>
      </div>
      <dl className="slip-lines">
        <div><dt>Pay to</dt><dd>{a.payee ?? '—'}</dd></div>
        <div><dt>For</dt><dd>{a.description}</dd></div>
        {a.ref && <div><dt>Ref</dt><dd>{a.ref}</dd></div>}
      </dl>
      {approved ? (
        <div className="stamp-approved" role="status">
          <Icon name="check" size={16} /> Approved by {approved.approved_by} · payment #{approved.payment_id}
          <span className="muted"> · checking {money(approved.balance_before)} → {money(approved.balance_after)}</span>
        </div>
      ) : (
        <div className="slip-foot">
          <span className="await"><span className="status-dot amber" /> Awaiting your approval</span>
          <button className="btn btn-money" onClick={onReview}>Review &amp; approve</button>
        </div>
      )}
    </article>
  )
}

function ApproveDialog({ action, ticketId, cash, onClose, onApprove, lastPending }: {
  action: ProposedAction; ticketId: number; cash: Cash | null; onClose: () => void; onApprove: Props['onApprove']; lastPending: boolean
}) {
  const [name, setName] = useState('')
  const [checked, setChecked] = useState(false)
  // Only default to resolving the ticket when this is its last pending payment/purchase.
  const [resolve, setResolve] = useState(lastPending)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const amount = action.amount ?? 0
  const after = cash ? cash.balance - amount : null
  const short = after != null && after < 0
  const ready = name.trim().length >= 2 && checked && !busy && !short

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await onApprove({ ticketId, actionId: action.action_id!, amount, approvedBy: name.trim(), resolveTicket: resolve })
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status ? `${err.status}: ` : ''}${err.message}` : String(err))
      setBusy(false)
    }
  }

  return (
    <Dialog title={`Approve ${KIND_LABEL[action.kind]?.toLowerCase() ?? 'payment'}`} tone="money" onClose={onClose}>
      <div className="approve-amount">{money(amount)}</div>
      <dl className="slip-lines">
        <div><dt>Pay to</dt><dd>{action.payee ?? '—'}</dd></div>
        <div><dt>For</dt><dd>{action.description}</dd></div>
        {action.ref && <div><dt>Ref</dt><dd>{action.ref}</dd></div>}
        <div><dt>Ticket</dt><dd>#{ticketId}</dd></div>
      </dl>
      <div className={`cash-preview ${short ? 'neg' : ''}`}>
        <span>Checking</span><strong>{money(cash?.balance)}</strong>
        <Icon name="arrow" size={14} />
        <strong>{money(after)}</strong>
      </div>
      {short && <div className="callout callout-bad"><Icon name="alert" size={16} /> This would take checking below $0, so it can’t be approved.</div>}

      <label className="field">
        <span>Your name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Navya Sharma" maxLength={80} autoComplete="name" />
      </label>
      <label className="check">
        <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
        <span>I approve paying <strong>{money(amount)}</strong> to <strong>{action.payee ?? 'this payee'}</strong> from checking.</span>
      </label>
      <label className="check subtle">
        <input type="checkbox" checked={resolve} onChange={(e) => setResolve(e.target.checked)} />
        <span>Mark ticket #{ticketId} resolved</span>
      </label>
      <p className="fine-print">The backend re-checks the proposal, the linked invoice or lease, and the cash balance before recording anything.</p>
      {error && <div className="callout callout-bad" role="alert"><Icon name="alert" size={16} /> {error}</div>}
      <div className="dialog-actions">
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-money" disabled={!ready} onClick={submit}>{busy ? 'Recording…' : `Approve ${money(amount)}`}</button>
      </div>
    </Dialog>
  )
}

function ResolveCard({ p, ticketStatus, running, onOpen }: { p: Proposal; ticketStatus: string; running: boolean; onOpen: () => void }) {
  if (ticketStatus !== 'open') return null
  const pending = p.proposed_actions.filter((a) => a.approvable).length
  return (
    <section className="resolve-card" aria-label="Approve resolution">
      <h3 className="section-title">Resolution</h3>
      <p>
        {pending
          ? `${pending} payment${pending === 1 ? '' : 's'} still await${pending === 1 ? 's' : ''} your decision above. Approve ${pending === 1 ? 'it' : 'them'} first, or resolve and leave ${pending === 1 ? 'it' : 'them'} unpaid.`
          : 'When you agree with the recommended option, approve the resolution to close the ticket. No money moves.'}
      </p>
      <button className="btn btn-primary" disabled={running} onClick={onOpen}><Icon name="check" size={15} /> Approve resolution…</button>
    </section>
  )
}

function ResolveDialog({ p, ticketId, onClose, onResolve }: { p: Proposal; ticketId: number; onClose: () => void; onResolve: Props['onResolve'] }) {
  const [name, setName] = useState('')
  const [checked, setChecked] = useState(false)
  const [ackUnpaid, setAckUnpaid] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pending = p.proposed_actions.filter((a) => a.approvable)
  const paid = p.proposed_actions.filter((a) => a.approval)
  const ready = name.trim().length >= 2 && checked && (pending.length === 0 || ackUnpaid) && !busy

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      await onResolve({ ticketId, runId: p.run_id!, approvedBy: name.trim(), acknowledgeUnpaid: ackUnpaid, note: note.trim() || undefined })
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? `${err.status ? `${err.status}: ` : ''}${err.message}` : String(err))
      setBusy(false)
    }
  }

  return (
    <Dialog title={`Resolve ticket #${ticketId}?`} onClose={onClose}>
      <div className="recommend"><span className="eyebrow">Recommended by the team</span><p>{p.recommended_option}</p></div>
      <ul className="plain-list">
        <li><Icon name="coin" size={16} /> {paid.length ? `Paid: ${paid.map((a) => money(a.amount)).join(', ')}` : 'No payment has been approved for this ticket.'}</li>
        <li><Icon name="shield" size={16} /> Resolving moves no money and sends nothing. It only closes the ticket.</li>
      </ul>
      {pending.length > 0 && (
        <label className="check">
          <input type="checkbox" checked={ackUnpaid} onChange={(e) => setAckUnpaid(e.target.checked)} />
          <span>Leave {pending.map((a) => `${money(a.amount)} (${a.description})`).join(', ')} <strong>unpaid</strong>.</span>
        </label>
      )}
      <label className="field">
        <span>Your name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Navya Sharma" maxLength={80} autoComplete="name" />
      </label>
      <label className="field">
        <span>Note (optional)</span>
        <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder="What was decided" />
      </label>
      <label className="check">
        <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
        <span>I approve resolving ticket <strong>#{ticketId}</strong> as proposed.</span>
      </label>
      {error && <div className="callout callout-bad" role="alert"><Icon name="alert" size={16} /> {error}</div>}
      <div className="dialog-actions">
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={!ready} onClick={submit}>{busy ? 'Resolving…' : 'Resolve ticket'}</button>
      </div>
    </Dialog>
  )
}

function ReplyDraft({ draft }: { draft: NonNullable<Proposal['customer_reply_draft']> }) {
  return (
    <section className="letter" aria-label="Customer reply draft">
      <span className="draft-stamp">Draft · not sent</span>
      <div className="letter-head"><Icon name="mail" size={16} /> To <strong>{draft.to}</strong> · {draft.subject}</div>
      <p className="letter-body">{draft.body}</p>
      <p className="fine-print">{draft.note}</p>
    </section>
  )
}

function Details({ p }: { p: Proposal }) {
  const failed = p.rule_checks.filter((c) => !c.passed).length
  return (
    <section className="proposal-details">
      <details open={failed > 0}>
        <summary>Rule checks <span className={`mini ${failed ? 'bad' : 'ok'}`}>{p.rule_checks.length - failed}/{p.rule_checks.length} pass</span></summary>
        <ul className="checks">
          {p.rule_checks.map((c, i) => (
            <li key={i} className={c.passed ? 'ok' : 'bad'}>
              <span className="stamp">{c.passed ? 'PASS' : 'FAIL'}</span>
              <span><strong>{c.rule}.</strong> {c.detail}</span>
            </li>
          ))}
        </ul>
      </details>
      <details>
        <summary>Key facts <span className="mini">{p.key_facts.length}</span></summary>
        <table className="facts">
          <tbody>
            {p.key_facts.map((f, i) => (
              <tr key={i}><th>{f.label}</th><td>{f.value}</td><td><span className="source" style={{ '--agent': actorMeta(f.source.split(/[ .]/)[0]).color } as CSSProperties}>{f.source}</span></td></tr>
            ))}
          </tbody>
        </table>
      </details>
      {p.open_questions.length > 0 && (
        <details>
          <summary>Open questions for you <span className="mini">{p.open_questions.length}</span></summary>
          <ul className="questions">{p.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </details>
      )}
    </section>
  )
}

function Empty({ icon, title, children }: { icon: 'inbox' | 'coin'; title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} size={26} />
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  )
}
