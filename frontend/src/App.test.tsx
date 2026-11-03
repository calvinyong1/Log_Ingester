import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { LogEventPage, ServiceErrorRates } from './types'

const SAMPLE_PAGE: LogEventPage = {
  total: 2,
  items: [
    {
      id: 2,
      service: 'checkout',
      level: 'ERROR',
      message: 'payment gateway timeout',
      timestamp: new Date().toISOString(),
      received_at: new Date().toISOString(),
    },
    {
      id: 1,
      service: 'auth-api',
      level: 'INFO',
      message: 'user logged in',
      timestamp: new Date(Date.now() - 60_000).toISOString(),
      received_at: new Date(Date.now() - 60_000).toISOString(),
    },
  ],
}

const SAMPLE_RATES: ServiceErrorRates = {
  window_seconds: 300,
  threshold: 0.5,
  min_events: 5,
  services: [{ service: 'checkout', total: 10, errors: 6, error_rate: 0.6 }],
}

const SAMPLE_HISTOGRAM = {
  total: 2,
  buckets: [
    {
      start: new Date(Date.now() - 120_000).toISOString(),
      end: new Date().toISOString(),
      counts: { DEBUG: 0, INFO: 1, WARNING: 0, ERROR: 1, CRITICAL: 0 },
    },
  ],
}

let rates: ServiceErrorRates = SAMPLE_RATES
let page: LogEventPage = SAMPLE_PAGE
let serviceNames = ['auth-api', 'checkout']

function respond(url: string): unknown {
  if (url.includes('/logs/services')) return serviceNames
  if (url.includes('/logs/histogram')) return SAMPLE_HISTOGRAM
  if (url.includes('/services/error-rates')) return rates
  return page
}

function logUrls(): string[] {
  const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
  return calls.map((c) => c[0] as string).filter((u) => u.includes('/logs?'))
}

describe('App', () => {
  beforeEach(() => {
    rates = SAMPLE_RATES
    page = SAMPLE_PAGE
    serviceNames = ['auth-api', 'checkout']
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (url: string) => ({
        ok: true,
        json: async () => respond(url),
      })),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllTimers()
  })

  it('loads and renders the log feed, chart, and table', async () => {
    render(<App />)

    expect(await screen.findByText('payment gateway timeout')).toBeInTheDocument()
    expect(screen.getByText('user logged in')).toBeInTheDocument()

    // Stat tiles reflect the fetched data.
    expect(screen.getByText('Events in range')).toBeInTheDocument()
    expect(screen.getByText('Error rate')).toBeInTheDocument()

    // Chart renders with a title (Recharts needs a real layout pass, but the
    // card and its heading should always be present).
    expect(screen.getByText('Events over time')).toBeInTheDocument()

    // Table shows both severity levels with text labels, not color alone
    // ("ERROR"/"INFO" also appear as <option>s in the level filter, hence getAllByText).
    expect(screen.getAllByText('ERROR').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INFO').length).toBeGreaterThan(0)
  })

  it('refetches with the service filter applied when changed', async () => {
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('payment gateway timeout')

    const serviceSelect = screen.getByLabelText('Service')
    await screen.findByRole('option', { name: 'checkout' })
    await user.selectOptions(serviceSelect, 'checkout')

    await waitFor(() => {
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
      const logCalls = calls.map((c) => c[0] as string).filter((u) => u.includes('/logs?'))
      expect(logCalls[logCalls.length - 1]).toContain('service=checkout')
    })
  })

  it('shows an error state when the API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')))
    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch')
  })

  it('populates the service dropdown from the API', async () => {
    render(<App />)
    const select = await screen.findByLabelText('Service')
    await screen.findByRole('option', { name: 'checkout' })
    const options = within(select).getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['All services (2)', 'auth-api', 'checkout'])
  })

  it('shows each service state as text in the rail', async () => {
    serviceNames = ['auth-api', 'checkout', 'search', 'ghost']
    rates = {
      ...SAMPLE_RATES,
      services: [
        { service: 'auth-api', total: 20, errors: 2, error_rate: 0.1 },
        { service: 'checkout', total: 10, errors: 6, error_rate: 0.6 },
        { service: 'search', total: 3, errors: 3, error_rate: 1 },
      ],
    }
    render(<App />)
    const rail = await screen.findByRole('region', { name: 'Services' })
    await within(rail).findByText('Alerting')

    const rowOf = (name: string) => within(rail).getByText(name).closest('li') as HTMLElement
    expect(within(rowOf('auth-api')).getByText('OK')).toBeInTheDocument()
    expect(within(rowOf('checkout')).getByText('Alerting')).toBeInTheDocument()
    expect(within(rowOf('checkout')).getByText('6 of 10 events')).toBeInTheDocument()
    expect(within(rowOf('search')).getByText('Low volume')).toBeInTheDocument()
    expect(within(rowOf('ghost')).getByText('No recent events')).toBeInTheDocument()

    // Only the alerting row gets the red highlight class.
    const buttonOf = (name: string) => rowOf(name).querySelector('button') as HTMLElement
    expect(buttonOf('checkout')).toHaveClass('service-row__button--alerting')
    expect(buttonOf('auth-api')).not.toHaveClass('service-row__button--alerting')
    expect(buttonOf('search')).not.toHaveClass('service-row__button--alerting')

    // "Services alerting" tile counts only the Alerting service.
    const tile = screen.getByText('Services alerting').parentElement as HTMLElement
    expect(within(tile).getByText('1 of 4')).toBeInTheDocument()
  })

  it('filters to a service when its rail row is clicked, and clears on a second click', async () => {
    const user = userEvent.setup()
    render(<App />)
    const rail = await screen.findByRole('region', { name: 'Services' })
    await screen.findByRole('option', { name: 'checkout' })

    const row = await within(rail).findByRole('button', { name: /checkout/ })
    expect(row).toHaveAttribute('aria-pressed', 'false')

    await user.click(row)
    await waitFor(() => expect(logUrls().at(-1)).toContain('service=checkout'))
    expect(row).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('Service')).toHaveValue('checkout')

    await user.click(row)
    await waitFor(() => expect(logUrls().at(-1)).not.toContain('service='))
    expect(row).toHaveAttribute('aria-pressed', 'false')
  })

  it('pages with limit and offset, and resets to the first page on a filter change', async () => {
    const user = userEvent.setup()
    page = { ...SAMPLE_PAGE, total: 60 }
    render(<App />)
    await screen.findByText('Showing 1 to 25 of 60')
    expect(logUrls().at(-1)).not.toContain('offset')
    expect(logUrls().at(-1)).toContain('limit=25')

    await user.click(screen.getByRole('button', { name: 'Older' }))
    await screen.findByText('Showing 26 to 50 of 60')
    expect(logUrls().at(-1)).toContain('offset=25')

    await user.click(screen.getByRole('button', { name: 'Newer' }))
    await screen.findByText('Showing 1 to 25 of 60')

    await user.click(screen.getByRole('button', { name: 'Older' }))
    await screen.findByText('Showing 26 to 50 of 60')
    await user.selectOptions(screen.getByLabelText('Level'), 'ERROR')
    await screen.findByText('Showing 1 to 25 of 60')
    expect(logUrls().at(-1)).not.toContain('offset')
  })

  it('stops polling when paused and shows Paused', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('payment gateway timeout')

    await user.click(screen.getByRole('button', { name: 'Pause' }))
    expect(screen.getByRole('status')).toHaveTextContent('Paused')
    expect(screen.getByRole('button', { name: 'Resume' })).toHaveAttribute('aria-pressed', 'true')

    const before = (fetch as ReturnType<typeof vi.fn>).mock.calls.length
    await new Promise((r) => setTimeout(r, 3500))
    expect((fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(before)
  }, 10_000)
})
