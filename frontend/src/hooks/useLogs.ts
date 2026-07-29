import { useEffect, useRef, useState } from 'react'
import { fetchLogs } from '../api'
import type { LogEvent, LogFilters } from '../types'

const POLL_INTERVAL_MS = 3000

interface UseLogsResult {
  items: LogEvent[]
  total: number
  loading: boolean // true only on the very first load
  refreshing: boolean // true on every poll, including background refreshes
  error: string | null
  lastUpdated: Date | null
}

export function useLogs(filters: LogFilters): UseLogsResult {
  const [items, setItems] = useState<LogEvent[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Filters are read inside the interval closure via a ref so changing them
  // doesn't need to tear down and restart the poll loop.
  const filtersRef = useRef(filters)
  filtersRef.current = filters

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    async function load() {
      setRefreshing(true)
      try {
        const page = await fetchLogs(filtersRef.current, { signal: controller.signal })
        if (cancelled) return
        setItems(page.items)
        setTotal(page.total)
        setError(null)
        setLastUpdated(new Date())
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) return
        setError(err instanceof Error ? err.message : 'Failed to load logs')
      } finally {
        if (!cancelled) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    }

    load()
    const interval = setInterval(load, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      controller.abort()
      clearInterval(interval)
    }
    // Re-run the whole loop when the filters actually change (new query),
    // not on every render — filtersRef carries the current value into load().
  }, [filters.service, filters.level, filters.rangeMinutes])

  return { items, total, loading, refreshing, error, lastUpdated }
}
