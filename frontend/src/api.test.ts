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
      { service: 'checkout', levels: ['ERROR'], q: '', range: { kind: 'preset', minutes: 15 } },
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
    await fetchHistogram({ service: '', levels: [], q: '', range: { kind: 'preset', minutes: null } })
    expect(new URL(fetchMock.mock.calls[0][0]).searchParams.has('start')).toBe(false)
  })

  it('sends one level param per selected level and the trimmed search text', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0 }) })
    const filters = {
      service: '',
      levels: ['ERROR', 'WARNING'] as ('ERROR' | 'WARNING')[],
      q: '  timeout ',
      range: { kind: 'preset' as const, minutes: null },
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

    await fetchLogs({ service: '', levels: [], q: '   ', range: { kind: 'preset', minutes: null } })

    const params = new URL(fetchMock.mock.calls[0][0]).searchParams
    expect(params.has('level')).toBe(false)
    expect(params.has('q')).toBe(false)
  })

  it('sends a custom range as fixed start and end, with the end minute included', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0 }) })

    await fetchLogs({
      service: '',
      levels: [],
      q: '',
      range: { kind: 'custom', from: '2026-11-21T14:00', to: '2026-11-21T16:30' },
    })

    const params = new URL(fetchMock.mock.calls[0][0]).searchParams
    expect(params.get('start')).toBe(new Date('2026-11-21T14:00').toISOString())
    // `end` is exclusive on the API, so 16:30 means "through 16:30:59".
    expect(params.get('end')).toBe(new Date('2026-11-21T16:31').toISOString())
  })

  it('leaves end off a custom range with no end time, so it runs up to now', async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ buckets: [], total: 0 }) })

    await fetchHistogram({
      service: '',
      levels: [],
      q: '',
      range: { kind: 'custom', from: '2026-11-21T14:00', to: '' },
    })

    const params = new URL(fetchMock.mock.calls[0][0]).searchParams
    expect(params.get('start')).toBe(new Date('2026-11-21T14:00').toISOString())
    expect(params.has('end')).toBe(false)
  })

  it('sends the cursor when given and never an offset', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], next_cursor: null }),
    })
    const filters = { service: '', levels: [], q: '', range: { kind: 'preset' as const, minutes: null } }

    await fetchLogs(filters, { limit: 25, cursor: 'abc123' })
    await fetchLogs(filters, { limit: 25 })

    const [withCursor, without] = fetchMock.mock.calls.map((c) => new URL(c[0]).searchParams)
    expect(withCursor.get('cursor')).toBe('abc123')
    expect(withCursor.get('limit')).toBe('25')
    expect(without.has('cursor')).toBe(false)
    expect(withCursor.has('offset') || without.has('offset')).toBe(false)
  })

  it('throws with the status on a failed request', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503 })
    await expect(fetchServices()).rejects.toThrow('GET /logs/services failed: 503')
  })
})
