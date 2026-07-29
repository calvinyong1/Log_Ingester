import type { LogEvent } from '../types'

interface StatTilesProps {
  events: LogEvent[]
  total: number
}

export function StatTiles({ events, total }: StatTilesProps) {
  const errors = events.filter((e) => e.level === 'ERROR' || e.level === 'CRITICAL').length
  const errorRate = events.length > 0 ? errors / events.length : 0

  return (
    <div className="stat-tiles">
      <div className="stat-tile">
        <span className="stat-tile__label">Events loaded</span>
        <span className="stat-tile__value">{events.length.toLocaleString()}</span>
        <span className="stat-tile__sub">{total.toLocaleString()} total matching filters</span>
      </div>
      <div className="stat-tile">
        <span className="stat-tile__label">Errors + critical</span>
        <span className="stat-tile__value" style={{ color: 'var(--status-serious)' }}>
          {errors.toLocaleString()}
        </span>
      </div>
      <div className="stat-tile">
        <span className="stat-tile__label">Error rate</span>
        <span
          className="stat-tile__value"
          style={{ color: errorRate >= 0.5 ? 'var(--status-critical)' : 'var(--text-primary)' }}
        >
          {(errorRate * 100).toFixed(1)}%
        </span>
        <span className="stat-tile__sub">of loaded events</span>
      </div>
    </div>
  )
}
