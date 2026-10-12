import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { AGENTS, CREW_ORDER, actorMeta } from '../lib/agents'
import { buildFeed, crewState, deskEvents, groupRuns, resultHighlights, type CrewMember, type FeedItem, type Run } from '../lib/activity'
import { argList, clock, duration, itemLine, shortDateTime, ticketType } from '../lib/format'
import type { AgentEvent, AgentName, TicketDetail } from '../types'
import { Icon } from './Icon'
import { StatusPill } from './TicketQueue'
import { Dialog } from './Dialog'

interface Props {
  detail: TicketDetail | undefined
  events: AgentEvent[]
  eventsLoaded: boolean
  anyRunning: boolean
  onRun: (id: number) => Promise<boolean>
}

export function CaseFile({ detail, events, eventsLoaded, anyRunning, onRun }: Props) {
  const runs = useMemo(() => groupRuns(events), [events])
  const [runId, setRunId] = useState<string | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [starting, setStarting] = useState(false)

  // Follow the newest run automatically (e.g. one that just started).
  const latest = runs.at(-1)
  useEffect(() => setRunId(latest?.runId ?? null), [latest?.runId])
  const run = runs.find((r) => r.runId === runId) ?? latest
  const decisions = useMemo(() => buildFeed(deskEvents(events).filter((e) => e.action.startsWith('human_'))), [events])

  if (!detail) {
    return (
      <main className="case" aria-busy>
        <div className="case-head skeleton-block" />
        <div className="feed skeleton-block tall" />
      </main>
    )
  }
  const t = detail.ticket
  const type = ticketType(t.type)
  const running = detail.run?.status === 'running'
  const canRun = t.status === 'open' && !running && !anyRunning

  return (
    <main className="case" aria-label={`Ticket ${t.id}`}>
      <section className="case-head">
        <div className="case-title">
          <span className={`ticket-icon big type-${t.type}`}><Icon name={type.icon} size={26} /></span>
          <div>
            <div className="case-kicker">
              <span>#{t.id} · {type.label}</span>
              <StatusPill status={t.status} />
            </div>
            <h1>{t.subject}</h1>
            <p className="case-notes">“{t.notes}”</p>
          </div>
        </div>
        <dl className="case-facts">
          <div><dt>Requester</dt><dd>{t.requester}</dd></div>
          {itemLine(t) && <div><dt>{t.sku ? 'Item' : 'Linked'}</dt><dd>{itemLine(t)}</dd></div>}
          {t.invoice_id != null && <div><dt>Invoice</dt><dd>#{t.invoice_id}</dd></div>}
          {t.lease_id != null && <div><dt>Lease</dt><dd>#{t.lease_id}</dd></div>}
          <div><dt>Received</dt><dd>{shortDateTime(t.created_at)}</dd></div>
        </dl>

        <div className="run-bar">
          <div className="run-state">
            {running && <><span className="pulse-dot" /> <span><strong>The team is working on this ticket.</strong> Activity updates every second.</span></>}
            {!running && t.status === 'resolved' && <><Icon name="check" size={16} /> <span>Resolved by a human decision. See “Your decisions” below.</span></>}
            {!running && t.status === 'open' && detail.run?.status === 'failed' && <span className="text-bad"><Icon name="alert" size={16} /> The last run failed: {detail.run.error}</span>}
            {!running && t.status === 'open' && detail.run?.status !== 'failed' && (
              <><Icon name="shield" size={16} /> <span>Agents only <em>propose</em>. Nothing is paid, ordered or sent until you approve it.</span></>
            )}
          </div>
          <button className="btn btn-primary" disabled={!canRun || starting} onClick={() => setConfirm(true)}
            title={t.status === 'resolved' ? 'Resolved tickets can’t be run again' : anyRunning && !running ? 'Another run is in progress' : undefined}>
            <Icon name="play" size={15} /> {running ? 'Team working…' : 'Run the agent team'}
          </button>
        </div>
      </section>

      {runs.length > 0 && (
        <div className="run-tabs" role="tablist" aria-label="Agent runs for this ticket">
          {runs.map((r, i) => (
            <button key={r.runId} role="tab" aria-selected={r.runId === run?.runId} className="run-tab" onClick={() => setRunId(r.runId)}>
              <span className={`run-dot run-${r.status}`} />
              Run {i + 1} · {shortDateTime(r.startedAt)}
              {r.requests != null && <span className="muted"> · {r.requests} model calls</span>}
            </button>
          ))}
        </div>
      )}

      <CrewStrip run={run} />

      <section className="feed" aria-label="Agent activity">
        <div className="panel-head">
          <h2>Agent activity</h2>
          {run && (
            <span className="count-chip">
              {run.models} · {run.delegations} handoffs
              {run.endedAt ? ` · ${duration(run.startedAt, run.endedAt)}` : ' · live'}
            </span>
          )}
        </div>
        {!eventsLoaded && <div className="feed-empty"><span className="spinner" /> Loading activity…</div>}
        {eventsLoaded && !run && (
          <div className="feed-empty">
            <Icon name="inbox" size={28} />
            <p><strong>No agent runs for this ticket yet.</strong></p>
            <p className="muted">Press <em>Run the agent team</em> to watch Boss route the ticket to the right specialists.</p>
          </div>
        )}
        {run && <Feed items={buildFeed(run.events)} live={run.status === 'running'} />}
        {decisions.length > 0 && (
          <div className="decisions-log">
            <h3 className="section-title">Your decisions</h3>
            <ol className="timeline">{decisions.map((it) => <FeedRow key={it.key} item={it} />)}</ol>
          </div>
        )}
      </section>

      {run && run.status !== 'running' && <CrewReport run={run} />}

      {confirm && (
        <Dialog title={`Run the agent team on #${t.id}?`} onClose={() => setConfirm(false)}>
          <p>Boss will read the ticket and hand parts of it to the specialists it needs. You’ll see each step in the activity feed.</p>
          <ul className="plain-list">
            <li><Icon name="coin" size={16} /> Uses <strong>gpt-6-luna through Portkey</strong>. A run is typically 12–20 model calls.</li>
            <li><Icon name="shield" size={16} /> Agents only propose. Nothing is paid, ordered or sent.</li>
          </ul>
          <div className="dialog-actions">
            <button className="btn" onClick={() => setConfirm(false)}>Cancel</button>
            <button className="btn btn-primary" disabled={starting} onClick={async () => {
              setStarting(true)
              const ok = await onRun(t.id)
              setStarting(false)
              if (ok) setConfirm(false)
            }}>{starting ? 'Starting…' : 'Start run'}</button>
          </div>
        </Dialog>
      )}
    </main>
  )
}

function CrewStrip({ run }: { run: Run | undefined }) {
  const crew = crewState(run)
  return (
    <ol className="crew" aria-label="Agent team">
      {CREW_ORDER.map((a) => {
        const m = crew[a]
        const meta = AGENTS[a]
        return (
          <li key={a} className={`crew-member crew-${m.state}`} style={{ '--agent': meta.color } as CSSProperties}>
            <span className="avatar">{meta.monogram}</span>
            <span className="crew-text">
              <span className="crew-name" title={meta.label}>{meta.short}</span>
              <span className="crew-status">
                {m.state === 'working' && 'Working…'}
                {m.state === 'done' && `${m.tools.length} tool call${m.tools.length === 1 ? '' : 's'}`}
                {m.state === 'idle' && (run ? 'Not needed' : 'Standing by')}
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function Feed({ items, live }: { items: FeedItem[]; live: boolean }) {
  return (
    <ol className="timeline" aria-live={live ? 'polite' : 'off'}>
      {items.map((it) => <FeedRow key={it.key} item={it} />)}
      {live && <li className="tl-row tl-live"><span className="spinner" /> Waiting for the next step…</li>}
    </ol>
  )
}

function Who({ agent }: { agent: string }) {
  const meta = actorMeta(agent)
  return (
    <span className="who" style={{ '--agent': meta.color } as CSSProperties}>
      <span className="avatar sm">{meta.monogram}</span>
      {meta.label}
    </span>
  )
}

function FeedRow({ item }: { item: FeedItem }) {
  const indent = { '--depth': item.depth } as CSSProperties
  switch (item.kind) {
    case 'marker':
      return <li className={`tl-marker tl-${item.tone}`}><span>{item.text}</span><time>{clock(item.ts)}</time></li>
    case 'start':
      return <li className="tl-row" style={indent}><div className="tl-line"><Who agent={item.agent} /> <span className="tl-text">opened the ticket.</span><time>{clock(item.ts)}</time></div></li>
    case 'thought':
      return <li className="tl-row" style={indent}><div className="tl-line"><Who agent={item.agent} /> <span className="tl-text">{item.text}</span><time>{clock(item.ts)}</time></div></li>
    case 'handoff': {
      const to = actorMeta(item.to)
      return (
        <li className="tl-row tl-handoff" style={{ ...indent, '--agent': to.color } as CSSProperties}>
          <div className="tl-line">
            <Who agent={item.from} /> <Icon name="arrow" size={14} className="muted" /> <Who agent={item.to} />
            <time>{clock(item.ts)}</time>
          </div>
          <blockquote>{item.task}</blockquote>
        </li>
      )
    }
    case 'report':
      return (
        <li className="tl-row tl-report" style={{ ...indent, '--agent': actorMeta(item.from).color } as CSSProperties}>
          <div className="tl-line"><Who agent={item.from} /> <span className="tl-text">reported back to {actorMeta(item.to).label}</span><time>{clock(item.ts)}</time></div>
          <p>{item.summary}</p>
        </li>
      )
    case 'tool':
      return <ToolRow item={item} />
    case 'output':
      return (
        <li className="tl-row tl-output" style={indent}>
          <div className="tl-line"><Who agent={item.agent} /> <span className="tl-text">wrote the proposal</span><time>{clock(item.ts)}</time></div>
          <p>{item.summary}</p>
        </li>
      )
    case 'check':
      return (
        <li className={`tl-check ${item.passed ? 'ok' : 'bad'}`}>
          <span className="stamp">{item.passed ? 'PASS' : 'FAIL'}</span><span>{item.text}</span>
        </li>
      )
    case 'resolution':
      return <li className="tl-marker tl-resolution"><span><Icon name="shield" size={14} /> Proposal ready: {labelStatus(item.status)}</span><time>{clock(item.ts)}</time></li>
    case 'approval':
      return <li className={`tl-row tl-approval ${item.ok ? 'ok' : 'bad'}`}><div className="tl-line"><Who agent="human" /> <span className="tl-text">{item.text}</span><time>{clock(item.ts)}</time></div></li>
    case 'notice':
      return <li className={`tl-row tl-notice tone-${item.tone}`} style={indent}><div className="tl-line"><Who agent={item.agent} /> <span className="tl-text">{item.text}</span><time>{clock(item.ts)}</time></div></li>
  }
}

function ToolRow({ item }: { item: Extract<FeedItem, { kind: 'tool' }> }) {
  const [open, setOpen] = useState(false)
  const hl = item.pending ? [] : resultHighlights(item.name, item.result)
  return (
    <li className="tl-row tl-tool" style={{ '--depth': item.depth, '--agent': actorMeta(item.agent).color } as CSSProperties}>
      <div className="tl-line">
        <Who agent={item.agent} />
        <code className="call"><Icon name="tool" size={13} /> {item.name}<span className="args">({argList(item.args)})</span></code>
        <time>{clock(item.ts)}</time>
      </div>
      {item.pending ? (
        <div className="result pending"><span className="spinner sm" /> waiting for MCP…</div>
      ) : (
        <div className="result">
          {hl.map(([k, v]) => <span key={k} className="kv"><span>{k}</span>{v}</span>)}
          <button className="link-btn" aria-expanded={open} onClick={() => setOpen((o) => !o)}>{open ? 'hide' : 'raw'}</button>
        </div>
      )}
      {open && <pre className="raw">{JSON.stringify(item.result, null, 2)}</pre>}
    </li>
  )
}

function CrewReport({ run }: { run: Run }) {
  const crew = crewState(run)
  const members = CREW_ORDER.map((a) => crew[a]).filter((m) => m.state !== 'idle')
  return (
    <section className="report" aria-label="What each agent did">
      <div className="panel-head">
        <h2>Crew report</h2>
        <span className="count-chip">{members.length} of 5 agents involved</span>
      </div>
      <div className="report-grid">
        {members.map((m) => <ReportCard key={m.agent} m={m} />)}
      </div>
    </section>
  )
}

function ReportCard({ m }: { m: CrewMember }) {
  const meta = AGENTS[m.agent as AgentName]
  const tools = [...new Set(m.tools)]
  return (
    <article className="report-card" style={{ '--agent': meta.color } as CSSProperties}>
      <header>
        <span className="avatar">{meta.monogram}</span>
        <div>
          <h3>{meta.label}</h3>
          <span className="muted">{m.calledBy.length ? `asked by ${m.calledBy.map((c) => actorMeta(c).label).join(', ')}` : 'ran the ticket'}</span>
        </div>
      </header>
      <p>{m.summary ?? 'No summary recorded.'}</p>
      <footer>
        {tools.length ? tools.map((t) => <code key={t} className="tool-chip">{t}</code>) : <span className="muted">no MCP tools</span>}
      </footer>
    </article>
  )
}

export function labelStatus(s: string | null | undefined): string {
  switch (s) {
    case 'pending_human_approval': return 'waiting for human approval'
    case 'no_approval_needed': return 'nothing to approve'
    case 'blocked_by_guardrail': return 'blocked by a guardrail'
    default: return s ?? 'unknown'
  }
}
