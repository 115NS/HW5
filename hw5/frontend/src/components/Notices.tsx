import type { Notice } from '../useDesk'
import { Icon } from './Icon'

export function Notices({ notices, onDismiss }: { notices: Notice[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toasts" role="region" aria-label="Notifications">
      {notices.map((n) => (
        <div key={n.id} className={`toast toast-${n.tone}`} role={n.tone === 'error' ? 'alert' : 'status'}>
          <Icon name={n.tone === 'error' ? 'alert' : n.tone === 'success' ? 'check' : 'spark'} size={18} />
          <div>
            <strong>{n.title}</strong>
            <p>{n.text}</p>
          </div>
          <button className="icon-btn" aria-label="Dismiss" onClick={() => onDismiss(n.id)}><Icon name="x" size={14} /></button>
        </div>
      ))}
    </div>
  )
}

export function OfflineBanner({ message }: { message: string }) {
  return (
    <div className="offline" role="alert">
      <Icon name="alert" size={20} />
      <div>
        <strong>The dashboard can’t reach the backend.</strong>
        <p>{message} Start it from <code>Homework-5/backend</code> with <code>uvicorn main:app --reload --port 8000</code>. This page retries automatically.</p>
      </div>
    </div>
  )
}
