import type { ServiceRow, ServiceState } from '../serviceState'

interface ServiceRailProps {
  rows: ServiceRow[] | null // null until the rates have loaded
  threshold: number
  windowSeconds: number
  minEvents: number
  error: boolean
  selected: string // the active service filter, '' for all
  onSelect: (service: string) => void // called with '' to clear
}

const STATE_CLASS: Record<ServiceState, string> = {
  Alerting: 'alerting',
  OK: 'ok',
  'Low volume': 'muted',
  'No recent events': 'muted',
}

function formatWindow(seconds: number): string {
  return seconds % 60 === 0 ? `${seconds / 60} min` : `${seconds}s`
}

export function ServiceRail({
  rows,
  threshold,
  windowSeconds,
  minEvents,
  error,
  selected,
  onSelect,
}: ServiceRailProps) {
  return (
    <section className="service-rail" aria-labelledby="service-rail-title">
      <h2 id="service-rail-title">Services</h2>
      {rows && (
        <p className="service-rail__hint">
          Rolling {formatWindow(windowSeconds)} error rate. Alert at {Math.round(threshold * 100)}% or
          more with at least {minEvents} events.
        </p>
      )}

      {!rows ? (
        <p className="service-rail__empty">{error ? 'Service status unavailable.' : 'Loading…'}</p>
      ) : rows.length === 0 ? (
        <p className="service-rail__empty">No services have reported yet.</p>
      ) : (
        <ul className="service-rail__list">
          {rows.map((row) => {
            const isSelected = row.service === selected
            return (
              <li key={row.service} className="service-row">
                {/* Spans, not divs: a button may only contain phrasing content. */}
                <button
                  type="button"
                  className={[
                    'service-row__button',
                    isSelected && 'service-row__button--selected',
                    row.state === 'Alerting' && 'service-row__button--alerting',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  aria-pressed={isSelected}
                  title={isSelected ? 'Show all services' : `Show only ${row.service}`}
                  onClick={() => onSelect(isSelected ? '' : row.service)}
                >
                  <span className="service-row__head">
                    <span className="service-row__name">{row.service}</span>
                    <span className={`state-chip state-chip--${STATE_CLASS[row.state]}`}>
                      {row.state}
                    </span>
                  </span>
                  <span className="rate-bar" aria-hidden="true">
                    <span
                      className={`rate-bar__fill rate-bar__fill--${STATE_CLASS[row.state]}`}
                      style={{ width: `${Math.min(100, row.errorRate * 100)}%` }}
                    />
                    <span className="rate-bar__marker" style={{ left: `${threshold * 100}%` }} />
                  </span>
                  <span className="service-row__foot">
                    <span>
                      {row.errors} of {row.total} events
                    </span>
                    <span className="service-row__rate">{(row.errorRate * 100).toFixed(1)}%</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
