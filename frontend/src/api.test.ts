import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchErrorRates, fetchHistogram, fetchLogs, fetchServices } from './api'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api', () => {
  it('fetchServices returns the service names', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ['auth-api', 'checkout'] })
    expect(await fetchServices()).toEqual(['auth-api', 'checkout'])
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/logs\/services$/)
  })

  it('fetchErrorRates hits /services/error-rates', async () => {
    const body = { window_seconds: 300, threshold: 0.5, min_events: 5, services: [] }
    fetchMock.mockResolvedValue({ ok: true, json: async () => body })
    expect(await fetchErrorRates()).toEqual(body)
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/services\/error-rates$/)
  })

  it('fetchHistogram sends filters and bucket count', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ buckets: [], total: 0 }) })
    await fetchHistogram(
      { service: 'checkout', levels: ['ERROR'], q: '', rangeMinutes: 15 },
      { buckets: 12 },
    )
    const url = new URL(fetchMock.mock.calls[0][0])
    expect(url.pathname).toBe('/logs/histogram')
    expect(url.searchParams.get('service')).toBe('checkout')
    expect(url.searchParams.get('level')).toBe('ERROR')
    expect(url.searchParams.get('buckets')).toBe('12')
    expect(url.searchParams.get('start')).not.toBeNull()
  })

  it('omits start for the "All" range', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ buckets: [], total: 0 }) })
    await fetchHistogram({ service: '', levels: [], q: '', rangeMinutes: null })
    expect(new URL(fetchMock.mock.calls[0][0]).searchParams.has('start')).toBe(false)
  })

  it('sends one level param per selected level and the trimmed search text', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0 }) })
    const filters = {
      service: '',
      levels: ['ERROR', 'WARNING'] as ('ERROR' | 'WARNING')[],
      q: '  timeout ',
      rangeMinutes: null,
    }

    await fetchLogs(filters)
    await fetchHistogram(filters)

    for (const [href] of fetchMock.mock.calls) {
      const params = new URL(href).searchParams
      expect(params.getAll('level')).toEqual(['ERROR', 'WARNING'])
      expect(params.get('q')).toBe('timeout')
    }
  })

  it('omits level and q when none are selected or the search is blank', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0 }) })

    await fetchLogs({ service: '', levels: [], q: '   ', rangeMinutes: null })

    const params = new URL(fetchMock.mock.calls[0][0]).searchParams
    expect(params.has('level')).toBe(false)
    expect(params.has('q')).toBe(false)
  })

  it('throws with the status on a failed request', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503 })
    await expect(fetchServices()).rejects.toThrow('GET /logs/services failed: 503')
  })
})
