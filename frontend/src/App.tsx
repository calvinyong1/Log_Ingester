import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { ErrorRateChart } from './components/ErrorRateChart'
import { FilterBar } from './components/FilterBar'
import { LogTable } from './components/LogTable'
import { Pagination } from './components/Pagination'
import { ServiceRail } from './components/ServiceRail'
import { StatTiles } from './components/StatTiles'
import { StatusPill } from './components/StatusPill'
import { useErrorRates } from './hooks/useErrorRates'
import { useHistogram } from './hooks/useHistogram'
import { PAGE_SIZE, useLogs } from './hooks/useLogs'
import { useServices } from './hooks/useServices'
import { rangeLabel } from './ranges'
import { buildServiceRows } from './serviceState'
import type { LogFilters } from './types'

const DEFAULT_FILTERS: LogFilters = {
  service: '',
  level: '',
  rangeMinutes: 60,
}

function App() {
  const [filters, setFilters] = useState<LogFilters>(DEFAULT_FILTERS)
  const [offset, setOffset] = useState(0)
  const [paused, setPaused] = useState(false)

  const logs = useLogs(filters, { offset, paused })
  const histogram = useHistogram(filters, { paused })
  const { data: services } = useServices({ paused })
  const rates = useErrorRates({ paused })

  const items = logs.data?.items ?? []
  const total = logs.data?.total ?? 0
  const error = logs.error ?? histogram.error ?? rates.error ?? null

  const rows = useMemo(
    () => (rates.data ? buildServiceRows(services ?? [], rates.data) : null),
    [services, rates.data],
  )
  const alerting = rows ? rows.filter((r) => r.state === 'Alerting').length : null

  // A new query starts at the first page; staying on page 7 of a different
  // result set would show an arbitrary slice.
  function changeFilters(next: LogFilters) {
    setFilters(next)
    setOffset(0)
  }

  // A service with no events left drops out of the list; don't keep filtering
  // by a name the dropdown no longer offers.
  useEffect(() => {
    if (services && filters.service && !services.includes(filters.service)) {
      setFilters((f) => ({ ...f, service: '' }))
      setOffset(0)
    }
  }, [services, filters.service])

  // The range slides with the clock, so the result set can shrink under us.
  useEffect(() => {
    if (logs.data && offset > 0 && offset >= logs.data.total) {
      setOffset(Math.max(0, (Math.ceil(logs.data.total / PAGE_SIZE) - 1) * PAGE_SIZE))
    }
  }, [logs.data, offset])

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <div className="app__logo">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 12h4l3-8 4 16 3-8h4" />
            </svg>
          </div>
          <div>
            <h1>Log Anomaly Detection</h1>
            <p className="app__subtitle">
              Ingestion is worker-backed, so new events can take a moment to appear.
            </p>
          </div>
        </div>
        <StatusPill
          paused={paused}
          error={error !== null}
          lastUpdated={logs.lastUpdated}
          refreshing={logs.refreshing}
          onTogglePause={() => setPaused((p) => !p)}
        />
      </header>

      <FilterBar filters={filters} services={services ?? []} onChange={changeFilters} />

      {error && (
        <div className="app__error" role="alert">
          Couldn&apos;t reach the API: {error}
        </div>
      )}

      {logs.loading ? (
        <div className="app__loading">Loading…</div>
      ) : (
        <div className="app__columns">
          <ServiceRail
            rows={rows}
            threshold={rates.data?.threshold ?? 0}
            windowSeconds={rates.data?.window_seconds ?? 0}
            minEvents={rates.data?.min_events ?? 0}
            error={rates.error !== null}
          />
          <div className="app__content">
            <StatTiles
              histogram={histogram.data}
              rangeLabel={rangeLabel(filters.rangeMinutes)}
              alerting={
                rows && rates.data
                  ? { count: alerting ?? 0, of: rows.length, windowSeconds: rates.data.window_seconds }
                  : null
              }
            />
            <ErrorRateChart histogram={histogram.data} />

            <section className="log-section">
              <h2>Recent events</h2>
              <LogTable
                events={items}
                footer={
                  <Pagination offset={offset} pageSize={PAGE_SIZE} total={total} onChange={setOffset} />
                }
              />
            </section>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
