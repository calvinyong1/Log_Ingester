import { useEffect, useState } from 'react'
import { fetchAlertEvents } from '../api'
import type { LogEventPage } from '../types'

interface AlertEventsState {
  data: LogEventPage | null
  error: string | null
}

// Fetched once per alert, not polled: the events behind a fired alert are
// fixed. Pass null while nothing is expanded.
export function useAlertEvents(alertId: number | null): AlertEventsState & { loading: boolean } {
  const [state, setState] = useState<AlertEventsState & { forId: number | null }>({
    data: null,
    error: null,
    forId: null,
  })

  useEffect(() => {
    if (alertId === null) return
    const controller = new AbortController()
    fetchAlertEvents(alertId, { signal: controller.signal })
      .then((data) => setState({ data, error: null, forId: alertId }))
      .catch((err) => {
        if (controller.signal.aborted) return
        setState({
          data: null,
          error: err instanceof Error ? err.message : 'Failed to load events',
          forId: alertId,
        })
      })
    return () => controller.abort()
  }, [alertId])

  // Results for a previously expanded alert must not flash under a new one.
  const current = state.forId === alertId
  return {
    data: current ? state.data : null,
    error: current ? state.error : null,
    loading: alertId !== null && !current,
  }
}
