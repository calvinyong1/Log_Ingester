import { LEVEL_COLOR } from '../levelStyle'
import type { LogEvent } from '../types'

interface LogTableProps {
  events: LogEvent[]
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function LogTable({ events }: LogTableProps) {
  if (events.length === 0) {
    return <div className="log-table__empty">No events match the current filters.</div>
  }

  return (
    <div className="log-table-wrapper">
      <table className="log-table">
        <thead>
          <tr>
            <th>Level</th>
            <th>Service</th>
            <th>Message</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.id}>
              <td>
                <span className="level-badge">
                  <span
                    className="level-badge__dot"
                    style={{ background: LEVEL_COLOR[event.level] }}
                    aria-hidden="true"
                  />
                  {event.level}
                </span>
              </td>
              <td>{event.service}</td>
              <td className="log-table__message">{event.message}</td>
              <td className="log-table__time">{formatTime(event.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
