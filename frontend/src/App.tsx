import { useEffect, useState } from 'react'
import './App.css'
import { ErrorRateChart } from './components/ErrorRateChart'
import { FilterBar } from './components/FilterBar'
import { LogTable } from './components/LogTable'
import { StatTiles } from './components/StatTiles'
import { useLogs } from './hooks/useLogs'
import { useServices } from './hooks/useServices'
import type { LogFilters } from './types'

const DEFAULT_FILTERS: LogFilters = {
  service: '',
  level: '',
  rangeMinutes: 60,
}

function formatRelativeTime(date: Date | null): string {
  if (!date) return 'never'
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000))
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  return `${Math.round(seconds / 60)}m ago`
}

function App() {
  const [filters, setFilters] = useState<LogFilters>(DEFAULT_FILTERS)
  const { items, total, loading, refreshing, error, lastUpdated } = useLogs(filters)
  const { data: services } = useServices()

  // A service with no events left drops out of the list; don't keep filtering
  // by a name the dropdown no longer offers.
  useEffect(() => {
    if (services && filters.service && !services.includes(filters.service)) {
      setFilters((f) => ({ ...f, service: '' }))
    }
  }, [services, filters.service])

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
        <div className="status-pill" role="status">
          <span className={`status-dot${refreshing ? ' status-dot--active' : ''}`} aria-hidden="true" />
          Updated {formatRelativeTime(lastUpdated)}
        </div>
      </header>

      <FilterBar filters={filters} services={services ?? []} onChange={setFilters} />

      {error && (
        <div className="app__error" role="alert">
          Couldn&apos;t reach the API: {error}
        </div>
      )}

      {loading ? (
        <div className="app__loading">Loading…</div>
      ) : (
        <div className="app__content">
          <StatTiles events={items} total={total} />
          <ErrorRateChart events={items} filters={filters} />

          <section className="log-section">
            <h2>Recent events</h2>
            <LogTable events={items} />
          </section>
        </div>
      )}
    </div>
  )
}

export default App
