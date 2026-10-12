import { useEffect, useRef, useState } from 'react'
import { deskDate, money } from '../lib/format'
import type { Cash, Health } from '../types'
import { Icon } from './Icon'

interface Props {
  health: Health | null
  offline: string | null
  date: string | null
  cash: Cash | null
  cashPulse: number
  pendingTotal: number
  pendingCount: number
  onReset: () => void
}

export function TopBar({ health, offline, date, cash, cashPulse, pendingTotal, pendingCount, onReset }: Props) {
  const [flash, setFlash] = useState(false)
  useEffect(() => {
    if (!cashPulse) return
    setFlash(true)
    const t = setTimeout(() => setFlash(false), 1600)
    return () => clearTimeout(t)
  }, [cashPulse])

  const [menu, setMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!menu) return
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenu(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menu])

  const after = cash ? cash.balance - pendingTotal : null

  return (
    <header className="topbar">
      <div className="brand">
        <span className="crest" aria-hidden>CC</span>
        <div>
          <div className="brand-name">Campus Customs</div>
          <div className="brand-sub">Operations Desk</div>
        </div>
      </div>

      <div className="topbar-mid">
        <div className="desk-day">
          <span className="eyebrow">Desk day</span>
          <span className="desk-day-date">{date ? deskDate(date) : '—'}</span>
        </div>
        <div className={`conn ${offline ? 'conn-down' : health ? 'conn-up' : ''}`} title={offline ?? (health ? `Connected · ${health.database}` : 'Connecting…')}>
          <span className="conn-dot" aria-hidden />
          <span>{offline ? 'Backend offline' : health ? `Live · ${health.model}` : 'Connecting…'}</span>
        </div>
      </div>

      <section className={`ledger ${flash ? 'ledger-flash' : ''}`} aria-label="Checking balance">
        <div className="ledger-main">
          <span className="eyebrow">Checking</span>
          <span className="ledger-amount" aria-live="polite" data-testid="cash-balance">{cash ? money(cash.balance) : '—'}</span>
          <span className="ledger-asof">{cash ? `as of ${cash.as_of}` : 'loading…'}</span>
        </div>
        <div className="ledger-side">
          <div>
            <span className="eyebrow">Awaiting approval</span>
            <span className="ledger-small">{!cash ? '—' : pendingCount ? `${money(pendingTotal)} · ${pendingCount}` : 'nothing'}</span>
          </div>
          <div>
            <span className="eyebrow">If all approved</span>
            <span className={`ledger-small ${after != null && after < 0 ? 'neg' : ''}`}>{after == null ? '—' : money(after)}</span>
          </div>
        </div>
      </section>

      <div className="menu" ref={menuRef}>
        <button className="icon-btn" aria-label="Desk tools" aria-expanded={menu} onClick={() => setMenu((m) => !m)}>
          <Icon name="dots" />
        </button>
        {menu && (
          <div className="menu-pop" role="menu">
            <button role="menuitem" onClick={() => { setMenu(false); onReset() }}>
              <Icon name="refresh" size={16} /> Reset working database…
            </button>
            <p className="menu-note">Restores cash, tickets, invoices and payments to their original values. The audit trail is kept.</p>
          </div>
        )}
      </div>
    </header>
  )
}
