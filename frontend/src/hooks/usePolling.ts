import { useEffect, useRef, useState } from 'react'

export const POLL_INTERVAL_MS = 3000

export interface PollingResult<T> {
  data: T | null
  loading: boolean // true only until the first response or error
  refreshing: boolean // true while any request is in flight
  error: string | null
  lastUpdated: Date | null
}

interface PollingOptions {
  paused?: boolean
  intervalMs?: number
}

/**
 * Calls `fetcher` immediately and then every `intervalMs` until unmounted or
 * paused. Data from the last success is kept while refetching and after an
 * error, so the UI never blanks on a refresh.
 */
export function usePolling<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  { paused = false, intervalMs = POLL_INTERVAL_MS }: PollingOptions = {},
): PollingResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Callers pass inline closures; a ref keeps the loop from restarting on
  // every render.
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    if (paused) return
    let cancelled = false
    const controller = new AbortController()

    async function load() {
      setRefreshing(true)
      try {
        const next = await fetcherRef.current(controller.signal)
        if (cancelled) return
        setData(next)
        setError(null)
        setLastUpdated(new Date())
      } catch (err) {
        if (cancelled || (err instanceof DOMException && err.name === 'AbortError')) return
        setError(err instanceof Error ? err.message : 'Request failed')
      } finally {
        if (!cancelled) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    }

    load()
    const interval = setInterval(load, intervalMs)
    return () => {
      cancelled = true
      controller.abort()
      clearInterval(interval)
    }
  }, [paused, intervalMs])

  return { data, loading, refreshing, error, lastUpdated }
}
