import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { LEVEL_COLOR, LEVEL_STACK_ORDER } from '../levelStyle'
import type { LogHistogram } from '../types'

interface ErrorRateChartProps {
  histogram: LogHistogram | null
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

export function ErrorRateChart({ histogram }: ErrorRateChartProps) {
  const data = (histogram?.buckets ?? []).map((b) => ({
    time: new Date(b.start).getTime(),
    ...b.counts,
  }))
  const hasData = (histogram?.total ?? 0) > 0

  return (
    <div className="chart-card">
      <div className="chart-card__header">
        <h2>Events over time</h2>
        <ul className="chart-legend">
          {LEVEL_STACK_ORDER.map((level) => (
            <li key={level}>
              <span
                className="chart-legend__swatch"
                style={{ background: LEVEL_COLOR[level] }}
                aria-hidden="true"
              />
              {level}
            </li>
          ))}
        </ul>
      </div>
      {!hasData ? (
        <div className="chart-card__empty">No events in this window yet.</div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="0" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={formatTick}
              stroke="var(--border)"
              tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--border)' }}
            />
            <YAxis
              allowDecimals={false}
              stroke="var(--border)"
              tick={{ fill: 'var(--text-muted)', fontSize: 11, fontFamily: 'var(--font-mono)' }}
              tickLine={false}
              axisLine={false}
              width={32}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--bg-inset)', opacity: 0.6 }} />
            {LEVEL_STACK_ORDER.map((level, i) => (
              <Bar
                key={level}
                dataKey={level}
                name={level}
                stackId="events"
                fill={LEVEL_COLOR[level]}
                stroke="var(--bg-surface)"
                strokeWidth={1}
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
