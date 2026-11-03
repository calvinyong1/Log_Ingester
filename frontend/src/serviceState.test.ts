import { describe, expect, it } from 'vitest'
import { buildServiceRows } from './serviceState'
import type { ServiceErrorRates } from './types'

const rates = (services: ServiceErrorRates['services']): ServiceErrorRates => ({
  window_seconds: 300,
  threshold: 0.5,
  min_events: 5,
  services,
})

const stateOf = (r: ServiceErrorRates, name: string) =>
  buildServiceRows([name], r).find((row) => row.service === name)?.state

describe('buildServiceRows', () => {
  it('is Low volume below min_events, even at a high error rate', () => {
    const r = rates([{ service: 'a', total: 4, errors: 4, error_rate: 1 }])
    expect(stateOf(r, 'a')).toBe('Low volume')
  })

  it('is Alerting at exactly the threshold', () => {
    const r = rates([{ service: 'a', total: 10, errors: 5, error_rate: 0.5 }])
    expect(stateOf(r, 'a')).toBe('Alerting')
  })

  it('is OK below the threshold', () => {
    const r = rates([{ service: 'a', total: 10, errors: 4, error_rate: 0.4 }])
    expect(stateOf(r, 'a')).toBe('OK')
  })

  it('reads min_events and threshold from the response, not constants', () => {
    const r = { ...rates([{ service: 'a', total: 3, errors: 1, error_rate: 0.33 }]), min_events: 2, threshold: 0.3 }
    expect(stateOf(r, 'a')).toBe('Alerting')
  })

  it('marks a listed service missing from the rates as No recent events', () => {
    expect(stateOf(rates([]), 'a')).toBe('No recent events')
  })

  it('keeps services only present in the rates, sorted by name', () => {
    const r = rates([{ service: 'zeta', total: 9, errors: 9, error_rate: 1 }])
    expect(buildServiceRows(['beta'], r).map((row) => row.service)).toEqual(['beta', 'zeta'])
  })
})
