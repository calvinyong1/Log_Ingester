import type { LogEventPage, LogFilters, LogHistogram, ServiceErrorRates } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function fetchLogs(
  filters: LogFilters,
  { limit = 200, offset = 0, signal }: { limit?: number; offset?: number; signal?: AbortSignal } = {},
): Promise<LogEventPage> {
  const params = new URLSearchParams()
  if (filters.service) params.set('service', filters.service)
  if (filters.level) params.set('level', filters.level)
  if (filters.rangeMinutes != null) {
    const start = new Date(Date.now() - filters.rangeMinutes * 60_000)
    params.set('start', start.toISOString())
  }
  params.set('limit', String(limit))
  if (offset > 0) params.set('offset', String(offset))

  const res = await fetch(`${API_URL}/logs?${params.toString()}`, { signal })
  if (!res.ok) {
    throw new Error(`GET /logs failed: ${res.status}`)
  }
  return res.json()
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { signal })
  if (!res.ok) {
    throw new Error(`GET ${path.split('?')[0]} failed: ${res.status}`)
  }
  return res.json()
}

export function fetchServices(signal?: AbortSignal): Promise<string[]> {
  return getJson('/logs/services', signal)
}

export function fetchErrorRates(signal?: AbortSignal): Promise<ServiceErrorRates> {
  return getJson('/services/error-rates', signal)
}

export function fetchHistogram(
  filters: LogFilters,
  { buckets = 24, signal }: { buckets?: number; signal?: AbortSignal } = {},
): Promise<LogHistogram> {
  const params = new URLSearchParams({ buckets: String(buckets) })
  if (filters.service) params.set('service', filters.service)
  if (filters.level) params.set('level', filters.level)
  if (filters.rangeMinutes != null) {
    const start = new Date(Date.now() - filters.rangeMinutes * 60_000)
    params.set('start', start.toISOString())
  }
  return getJson(`/logs/histogram?${params.toString()}`, signal)
}

export { API_URL }
