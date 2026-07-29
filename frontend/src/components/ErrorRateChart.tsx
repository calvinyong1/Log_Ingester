import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { bucketEvents } from '../bucketEvents'
import { LEVEL_COLOR, LEVEL_STACK_ORDER } from '../levelStyle'
import type { LogEvent, LogFilters } from '../types'

interface ErrorRateChartProps {
  events: LogEvent[]
  filters: LogFilters
}

function formatTick(ms: number): string {
  const d = new Date(ms)
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

interface TooltipPayloadEntry {
  dataKey: string
  value: number
  color: string
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: TooltipPayloadEntry[]
  label?: number
}) {
  if (!active || !payload || payload.length === 0) return null
  const total = payload.reduce((sum, entry) => sum + (entry.value ?? 0), 0)
  if (total === 0) return null

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__time">{label != null ? formatTick(label) : ''}</div>
      {payload
        .filter((entry) => entry.value > 0)
        .reverse()
        .map((entry) => (
          <div className="chart-tooltip__row" key={entry.dataKey}>
            <span className="chart-tooltip__swatch" style={{ background: entry.color }} />
            <span className="chart-tooltip__value">{entry.value}</span>
            <span className="chart-tooltip__label">{entry.dataKey}</span>
          </div>
        ))}
      <div className="chart-tooltip__total">
        <span className="chart-tooltip__value">{total}</span>
        <span className="chart-tooltip__label">total</span>
      </div>
    </div>
  )
}

export function ErrorRateChart({ events, filters }: ErrorRateChartProps) {
  const buckets = bucketEvents(events, filters.rangeMinutes)
  const data = buckets.map((b) => ({ time: b.start, ...b.counts }))
  const hasData = buckets.some((b) => b.total > 0)

  return (
    <div className="chart-card">
      <div className="chart-card__header">
        <h2>Events over time</h2>
        <span className="chart-card__subtitle">by level, {LEVEL_STACK_ORDER.length}-level severity</span>
      </div>
      {!hasData ? (
        <div className="chart-card__empty">No events in this window yet.</div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--gridline)" strokeDasharray="0" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={formatTick}
              stroke="var(--baseline)"
              tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: 'var(--baseline)' }}
            />
            <YAxis
              allowDecimals={false}
              stroke="var(--baseline)"
              tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={32}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--gridline)', opacity: 0.4 }} />
            <Legend
              verticalAlign="top"
              align="right"
              height={32}
              iconType="square"
              iconSize={10}
              formatter={(value: string) => (
                <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{value}</span>
              )}
            />
            {LEVEL_STACK_ORDER.map((level, i) => (
              <Bar
                key={level}
                dataKey={level}
                name={level}
                stackId="events"
                fill={LEVEL_COLOR[level]}
                stroke="var(--surface-1)"
                strokeWidth={2}
                barSize={20}
                radius={i === LEVEL_STACK_ORDER.length - 1 ? [4, 4, 0, 0] : 0}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
