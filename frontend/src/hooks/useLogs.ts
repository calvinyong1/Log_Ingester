import { fetchLogs } from '../api'
import type { LogEventCursorPage, LogFilters } from '../types'
import { usePolling, type PollingResult } from './usePolling'

export const PAGE_SIZE = 25

// `cursor` is null for the first (newest) page, which keeps polling live; a later
// page is addressed by a cursor, so it stays put while new events arrive.
export function useLogs(
  filters: LogFilters,
  { cursor, paused }: { cursor: string | null; paused: boolean },
): PollingResult<LogEventCursorPage> {
  return usePolling((signal) => fetchLogs(filters, { limit: PAGE_SIZE, cursor, signal }), {
    paused,
    key: JSON.stringify([filters, cursor]),
  })
}
