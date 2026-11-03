import type { LogHistogram } from '../types'

interface StatTilesProps {
  histogram: LogHistogram | null
  rangeLabel: string
  alerting: { count: number; of: number; windowSeconds: number } | null // null until rates load
}

export function StatTiles({ histogram, rangeLabel, alerting }: StatTilesProps) {
  const total = histogram?.total ?? 0
  const errors = (histogram?.buckets ?? []).reduce(
    (sum, b) => sum + b.counts.ERROR + b.counts.CRITICAL,
    0,
  )
  const errorRate = total > 0 ? errors / total : 0
  const isAlerting = (alerting?.count ?? 0) > 0

  return (
    <div className="stat-tiles">
      <div className="stat-tile">
        <span className="stat-tile__label">Events in range</span>
        <span className="stat-tile__value">{total.toLocaleString()}</span>
        <span className="stat-tile__sub">{rangeLabel}</span>
      </div>
      <div className="stat-tile">
        <span className="stat-tile__label">Errors + critical</span>
        <span className="stat-tile__value" style={{ color: 'var(--level-error)' }}>
          {errors.toLocaleString()}
        </span>
        <span className="stat-tile__sub">ERROR and CRITICAL</span>
      </div>
      <div className="stat-tile">
        <span className="stat-tile__label">Error rate</span>
        <span className="stat-tile__value">{(errorRate * 100).toFixed(1)}%</span>
        <span className="stat-tile__sub">of events in range</span>
      </div>
      <div className={`stat-tile${isAlerting ? ' stat-tile--alerting' : ''}`}>
        <span className="stat-tile__label">Services alerting</span>
        <span className="stat-tile__value">
          {alerting ? `${alerting.count} of ${alerting.of}` : '–'}
        </span>
        {alerting && (
          <span className="stat-tile__sub">rolling {Math.round(alerting.windowSeconds / 60)} min window</span>
        )}
      </div>
    </div>
  )
}
