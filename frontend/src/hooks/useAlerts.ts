import { fetchAlerts } from '../api'
import type { AlertPage } from '../types'
import { usePolling, type PollingResult } from './usePolling'

export function useAlerts(service: string, { paused }: { paused: boolean }): PollingResult<AlertPage> {
  return usePolling((signal) => fetchAlerts(service, { signal }), { paused, key: service })
}
