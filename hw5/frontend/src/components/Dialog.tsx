import { useEffect, useRef, type ReactNode } from 'react'
import { Icon } from './Icon'

/** Modal dialog: focus moves inside, Esc and the backdrop close it, focus returns afterwards. */
export function Dialog({ title, children, onClose, tone }: { title: string; children: ReactNode; onClose: () => void; tone?: 'money' | 'danger' }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const first = ref.current?.querySelector<HTMLElement>('input, button:not([disabled]):not(.dialog-x), textarea')
    first?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus?.()
    }
  }, [onClose])
  return (
    <div className="backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`dialog ${tone ? `dialog-${tone}` : ''}`} role="dialog" aria-modal="true" aria-labelledby="dialog-title" ref={ref}>
        <header>
          <h2 id="dialog-title">{title}</h2>
          <button className="icon-btn dialog-x" aria-label="Close" onClick={onClose}><Icon name="x" /></button>
        </header>
        {children}
      </div>
    </div>
  )
}
