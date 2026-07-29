import { useState } from 'react'
import './App.css'
import { ErrorRateChart } from './components/ErrorRateChart'
import { FilterBar } from './components/FilterBar'
import { LogTable } from './components/LogTable'
import { StatTiles } from './components/StatTiles'
import { useLogs } from './hooks/useLogs'
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

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1>Log Anomaly Detection</h1>
          <p className="app__subtitle">
            Ingestion is asynchronous (worker-backed) — new events may take a moment to appear.
          </p>
        </div>
        <div className="app__status" aria-live="polite">
          <span className={`status-dot${refreshing ? ' status-dot--active' : ''}`} aria-hidden="true" />
          Updated {formatRelativeTime(lastUpdated)}
        </div>
      </header>

      <FilterBar filters={filters} onChange={setFilters} />

      {error && (
        <div className="app__error" role="alert">
          Couldn&apos;t reach the API: {error}
        </div>
      )}

      {loading ? (
        <div className="app__loading">Loading…</div>
      ) : (
        <div className="app__content" style={{ opacity: refreshing ? 0.85 : 1 }}>
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
