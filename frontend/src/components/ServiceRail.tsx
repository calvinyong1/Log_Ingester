import type { ServiceRow, ServiceState } from '../serviceState'

interface ServiceRailProps {
  rows: ServiceRow[] | null // null until the rates have loaded
  threshold: number
  windowSeconds: number
  minEvents: number
  error: boolean
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

export function ServiceRail({ rows, threshold, windowSeconds, minEvents, error }: ServiceRailProps) {
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
          {rows.map((row) => (
            <li key={row.service} className="service-row">
              <div className="service-row__head">
                <span className="service-row__name">{row.service}</span>
                <span className={`state-chip state-chip--${STATE_CLASS[row.state]}`}>
                  {row.state}
                </span>
              </div>
              <div className="rate-bar" aria-hidden="true">
                <div
                  className={`rate-bar__fill rate-bar__fill--${STATE_CLASS[row.state]}`}
                  style={{ width: `${Math.min(100, row.errorRate * 100)}%` }}
                />
                <div className="rate-bar__marker" style={{ left: `${threshold * 100}%` }} />
              </div>
              <div className="service-row__foot">
                <span>
                  {row.errors} of {row.total} events
                </span>
                <span className="service-row__rate">{(row.errorRate * 100).toFixed(1)}%</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
