import { fetchErrorRates } from '../api'
import type { ServiceErrorRates } from '../types'
import { usePolling, type PollingResult } from './usePolling'

export function useErrorRates(options?: { paused?: boolean }): PollingResult<ServiceErrorRates> {
  return usePolling(fetchErrorRates, options)
}
