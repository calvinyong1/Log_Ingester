import { useState } from 'react'
import { useAlertEvents } from '../hooks/useAlertEvents'
import { LEVEL_COLOR } from '../levelStyle'
import type { AlertPage } from '../types'

interface AlertHistoryProps {
  alerts: AlertPage | null // null until loaded
  service: string // active service filter, '' for all
  error: boolean
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function AlertEvents({ alertId }: { alertId: number }) {
  const { data, error, loading } = useAlertEvents(alertId)

  if (error) return <p className="alert-events__note">Couldn&apos;t load events.</p>
  if (loading || !data) return <p className="alert-events__note">Loading events…</p>
  if (data.items.length === 0) {
    return <p className="alert-events__note">No events were recorded in this window.</p>
  }

  return (
    <>
      <ul className="alert-events">
        {data.items.map((event) => (
          <li key={event.id} className="alert-events__item">
            <span className="level-badge">
              <span
                className="level-badge__dot"
                style={{ background: LEVEL_COLOR[event.level] }}
                aria-hidden="true"
              />
              {event.level}
            </span>
            <span className="alert-events__message">{event.message}</span>
            <span className="alert-events__time">{formatClock(event.timestamp)}</span>
          </li>
        ))}
      </ul>
      {data.total > data.items.length && (
        <p className="alert-events__note">
          Showing {data.items.length} of {data.total} events.
        </p>
      )}
    </>
  )
}

export function AlertHistory({ alerts, service, error }: AlertHistoryProps) {
  const [openId, setOpenId] = useState<number | null>(null)

  return (
    <section className="alert-history" aria-labelledby="alert-history-title">
      <h2 id="alert-history-title">Alert history</h2>
      <p className="alert-history__hint">
        Saved when an alert fires{service ? ` for ${service}` : ''}. Select one to see its events.
      </p>

      {!alerts ? (
        <p className="alert-history__empty">{error ? 'Alert history unavailable.' : 'Loading…'}</p>
      ) : alerts.items.length === 0 ? (
        <p className="alert-history__empty">No alerts have fired yet.</p>
      ) : (
        <ul className="alert-history__list">
          {alerts.items.map((alert) => {
            const isOpen = alert.id === openId
            return (
              <li key={alert.id} className="alert-item">
                <button
                  type="button"
                  className={`alert-item__button${isOpen ? ' alert-item__button--open' : ''}`}
                  aria-expanded={isOpen}
                  onClick={() => setOpenId(isOpen ? null : alert.id)}
                >
                  <span className="alert-item__head">
                    <span className="alert-item__service">{alert.service}</span>
                    <span className="alert-item__rate">{(alert.error_rate * 100).toFixed(0)}%</span>
                  </span>
                  <span className="alert-item__foot">
                    <span>{formatDateTime(alert.fired_at)}</span>
                    <span>
                      {alert.errors} of {alert.total} events
                    </span>
                  </span>
                </button>
                {isOpen && <AlertEvents alertId={alert.id} />}
              </li>
            )
          })}
        </ul>
      )}
      {alerts && alerts.total > alerts.items.length && (
        <p className="alert-history__hint alert-history__more">
          Latest {alerts.items.length} of {alerts.total} alerts.
        </p>
      )}
    </section>
  )
}
