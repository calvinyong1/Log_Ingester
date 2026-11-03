import type { ServiceErrorRates } from './types'

export type ServiceState = 'Alerting' | 'OK' | 'Low volume' | 'No recent events'

export interface ServiceRow {
  service: string
  state: ServiceState
  total: number
  errors: number
  errorRate: number
}

// Window, threshold and min_events come from the API response; the backend
// returns raw numbers and the UI decides what they mean.
export function buildServiceRows(names: string[], rates: ServiceErrorRates): ServiceRow[] {
  const byName = new Map(rates.services.map((s) => [s.service, s]))
  // Union, so a service alerting in Redis is never hidden because the
  // dropdown (Postgres) doesn't list it.
  const all = [...new Set([...names, ...byName.keys()])].sort()

  return all.map((service) => {
    const rate = byName.get(service)
    if (!rate) return { service, state: 'No recent events', total: 0, errors: 0, errorRate: 0 }
    const state: ServiceState =
      rate.total < rates.min_events
        ? 'Low volume'
        : rate.error_rate >= rates.threshold
          ? 'Alerting'
          : 'OK'
    return { service, state, total: rate.total, errors: rate.errors, errorRate: rate.error_rate }
  })
}
