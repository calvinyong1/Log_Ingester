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

export interface LogFilters {
  service: string
  level: LogLevel | ''
  rangeMinutes: number | null // null = no lower bound ("All")
}
