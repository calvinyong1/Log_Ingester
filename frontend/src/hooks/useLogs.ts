import { fetchLogs } from '../api'
import type { LogEventCursorPage, LogFilters } from '../types'
import { usePolling, type PollingResult } from './usePolling'

export const PAGE_SIZE = 25

// `cursor` is null for the first (newest) page, which keeps polling live; a later
// page is addressed by a cursor, so it stays put while new events arrive.
//
// `current` is false while `data` still belongs to a previous cursor or filter (the
// poller keeps the old page on screen during a refetch). Its `next_cursor` must not be
// used then: it would page from the wrong position.
export function useLogs(
  filters: LogFilters,
  { cursor, paused }: { cursor: string | null; paused: boolean },
): PollingResult<LogEventCursorPage> & { current: boolean } {
  const key = JSON.stringify([filters, cursor])
  const result = usePolling((signal) => fetchLogs(filters, { limit: PAGE_SIZE, cursor, signal }), {
    paused,
    key,
  })
  return { ...result, current: result.dataKey === key }
}
