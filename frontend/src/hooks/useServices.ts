import { fetchServices } from '../api'
import { usePolling, type PollingResult } from './usePolling'

export function useServices(options?: { paused?: boolean }): PollingResult<string[]> {
  return usePolling(fetchServices, options)
}
