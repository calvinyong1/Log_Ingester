import type { LogEventPage, LogFilters } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function fetchLogs(
  filters: LogFilters,
  { limit = 200, signal }: { limit?: number; signal?: AbortSignal } = {},
): Promise<LogEventPage> {
  const params = new URLSearchParams()
  if (filters.service) params.set('service', filters.service)
  if (filters.level) params.set('level', filters.level)
  if (filters.rangeMinutes != null) {
    const start = new Date(Date.now() - filters.rangeMinutes * 60_000)
    params.set('start', start.toISOString())
  }
  params.set('limit', String(limit))

  const res = await fetch(`${API_URL}/logs?${params.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`GET /logs failed: ${res.status}`)
  }
  return res.json()
}

export { API_URL }
