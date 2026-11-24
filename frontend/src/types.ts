export const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as const

export type LogLevel = (typeof LOG_LEVELS)[number]

export interface LogEvent {
  id: number
  service: string
  level: LogLevel
  message: string
  timestamp: string
  received_at: string
}

export interface LogEventPage {
  items: LogEvent[]
  total: number
}

// A preset slides with the clock ("last 15 min"; null minutes = no lower bound).
// A custom range is fixed; from/to are datetime-local values ("2026-11-21T14:00",
// local time) and an empty `to` means "up to now".
export type TimeRange =
  | { kind: 'preset'; minutes: number | null }
  | { kind: 'custom'; from: string; to: string }

// GET /logs is cursor-paged: pass next_cursor back to get the next (older) page.
// It is null on the last page, and there is deliberately no total.
export interface LogEventCursorPage {
  items: LogEvent[]
  next_cursor: string | null
}

export interface LogFilters {
  service: string
  levels: LogLevel[] // empty = every level
  q: string // substring of the message; blank = no search
  range: TimeRange
}

export interface ServiceErrorRate {
  service: string
  total: number
  errors: number
  error_rate: number
}

export interface ServiceErrorRates {
  window_seconds: number
  threshold: number
  min_events: number
  services: ServiceErrorRate[]
}

export interface HistogramBucket {
  start: string
  end: string
  counts: Record<LogLevel, number>
}

export interface LogHistogram {
  buckets: HistogramBucket[]
  total: number
}

export interface Alert {
  id: number
  service: string
  fired_at: string
  window_seconds: number
  total: number
  errors: number
  error_rate: number
  threshold: number
}

export interface AlertPage {
  items: Alert[]
  total: number
}
