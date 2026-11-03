import { fetchHistogram } from '../api'
import type { LogFilters, LogHistogram } from '../types'
import { usePolling, type PollingResult } from './usePolling'

export function useHistogram(
  filters: LogFilters,
  { paused }: { paused: boolean },
): PollingResult<LogHistogram> {
  return usePolling((signal) => fetchHistogram(filters, { signal }), {
    paused,
    key: JSON.stringify(filters),
  })
}
