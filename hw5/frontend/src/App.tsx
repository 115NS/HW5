import { useMemo, useState } from 'react'
import { CaseFile } from './components/CaseFile'
import { DecisionPanel } from './components/DecisionPanel'
import { Dialog } from './components/Dialog'
import { Notices, OfflineBanner } from './components/Notices'
import { TicketQueue } from './components/TicketQueue'
import { TopBar } from './components/TopBar'
import { isFailedProposal } from './types'
import { useDesk } from './useDesk'

export default function App() {
  const desk = useDesk()
  const [resetOpen, setResetOpen] = useState(false)

  // Money that would leave checking if a human approved every pending payment/purchase.
  const pending = useMemo(() => {
    let total = 0
    let count = 0
    for (const d of Object.values(desk.details)) {
      if (!d.proposal || isFailedProposal(d.proposal)) continue
      for (const a of d.proposal.proposed_actions) if (a.approvable && a.amount) { total += a.amount; count += 1 }
    }
    return { total, count }
  }, [desk.details])

  const detail = desk.selectedId != null ? desk.details[desk.selectedId] : undefined
  const firstLoad = !desk.tickets && !desk.offline

  return (
    <div className="app">
      <TopBar
        health={desk.health}
        offline={desk.offline}
        date={desk.deskDate}
        cash={desk.cash}
        cashPulse={desk.cashPulse}
        pendingTotal={pending.total}
        pendingCount={pending.count}
        onReset={() => setResetOpen(true)}
      />
      {desk.offline && <OfflineBanner message={desk.offline} />}

      <div className="desk">
        <TicketQueue tickets={desk.tickets} details={desk.details} selectedId={desk.selectedId} onSelect={desk.select} />
        {firstLoad || detail ? (
          <>
            <CaseFile
              key={desk.selectedId ?? 'none'}
              detail={detail}
              events={desk.events.events}
              eventsLoaded={desk.events.loaded}
              anyRunning={desk.anyRunning}
              onRun={desk.startRun}
            />
            <DecisionPanel key={`d-${desk.selectedId}`} detail={detail} cash={desk.cash} onApprove={desk.approve} onResolve={desk.resolve} />
          </>
        ) : (
          <main className="case case-none">
            <p className="muted">{desk.offline ? 'Waiting for the backend…' : 'Select a ticket to open its case file.'}</p>
          </main>
        )}
      </div>

      <Notices notices={desk.notices} onDismiss={desk.dismiss} />

      {resetOpen && <ResetDialog onClose={() => setResetOpen(false)} onReset={desk.reset} />}
    </div>
  )
}

function ResetDialog({ onClose, onReset }: { onClose: () => void; onReset: () => Promise<boolean> }) {
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <Dialog title="Reset the working database?" tone="danger" onClose={onClose}>
      <p>This restores <code>data/campus_customs_new.db</code> from the original values: checking back to the starting balance, all tickets open, payments cleared. The original database is only read. Proposals and the audit trail are kept, and the reset itself is logged.</p>
      <label className="field">
        <span>Type <strong>RESET</strong> to confirm</span>
        <input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </label>
      <div className="dialog-actions">
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-danger" disabled={typed !== 'RESET' || busy} onClick={async () => {
          setBusy(true)
          if (await onReset()) onClose()
          else setBusy(false)
        }}>{busy ? 'Resetting…' : 'Reset database'}</button>
      </div>
    </Dialog>
  )
}
