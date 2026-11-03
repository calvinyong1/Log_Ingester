import { fetchLogs } from '../api'
import type { LogEventPage, LogFilters } from '../types'
import { usePolling, type PollingResult } from './usePolling'

export const PAGE_SIZE = 25

export function useLogs(
  filters: LogFilters,
  { offset, paused }: { offset: number; paused: boolean },
): PollingResult<LogEventPage> {
  return usePolling((signal) => fetchLogs(filters, { limit: PAGE_SIZE, offset, signal }), {
    paused,
    key: JSON.stringify([filters, offset]),
  })
}
