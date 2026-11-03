interface StatusPillProps {
  paused: boolean
  error: boolean
  lastUpdated: Date | null
  refreshing: boolean
  onTogglePause: () => void
}

function formatRelativeTime(date: Date | null): string {
  if (!date) return 'never'
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000))
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  return `${Math.round(seconds / 60)}m ago`
}

export function StatusPill({ paused, error, lastUpdated, refreshing, onTogglePause }: StatusPillProps) {
  const state = paused ? 'paused' : error ? 'offline' : 'live'
  const label = paused ? 'Paused' : error ? 'Offline' : 'Live'

  return (
    <div className="status-group">
      <div className="status-pill" role="status">
        <span
          className={`status-dot status-dot--${state}${refreshing ? ' status-dot--active' : ''}`}
          aria-hidden="true"
        />
        {label}, updated {formatRelativeTime(lastUpdated)}
      </div>
      <button type="button" className="pause-button" aria-pressed={paused} onClick={onTogglePause}>
        {paused ? 'Resume' : 'Pause'}
      </button>
    </div>
  )
}
