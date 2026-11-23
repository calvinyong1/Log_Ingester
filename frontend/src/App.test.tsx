import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { Alert, LogEventPage, ServiceErrorRates } from './types'

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
let alertItems: Alert[] = []
let alertEvents: LogEventPage = { items: [], total: 0 }

function respond(url: string): unknown {
  if (url.includes('/logs/services')) return serviceNames
  if (url.includes('/logs/histogram')) return SAMPLE_HISTOGRAM
  if (url.includes('/services/error-rates')) return rates
  if (/\/alerts\/\d+\/events/.test(url)) return alertEvents
  if (url.includes('/alerts')) return { items: alertItems, total: alertItems.length }
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
    alertItems = []
    alertEvents = { items: [], total: 0 }
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
    // ("ERROR"/"INFO" also appear as level filter chips, hence getAllByText).
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

  it('shows saved alerts and loads the events behind one when opened', async () => {
    const user = userEvent.setup()
    alertItems = [
      {
        id: 7,
        service: 'checkout',
        fired_at: new Date().toISOString(),
        window_seconds: 300,
        total: 10,
        errors: 8,
        error_rate: 0.8,
        threshold: 0.5,
      },
    ]
    alertEvents = {
      total: 2,
      items: [
        {
          id: 31,
          service: 'checkout',
          level: 'ERROR',
          message: 'card processor timeout',
          timestamp: new Date().toISOString(),
          received_at: new Date().toISOString(),
        },
      ],
    }
    render(<App />)

    const history = await screen.findByRole('region', { name: 'Alert history' })
    const item = await within(history).findByRole('button', { name: /checkout/ })
    expect(within(history).getByText('80%')).toBeInTheDocument()
    expect(within(history).getByText('8 of 10 events')).toBeInTheDocument()
    expect(within(history).queryByText('card processor timeout')).not.toBeInTheDocument()

    await user.click(item)
    expect(await within(history).findByText('card processor timeout')).toBeInTheDocument()
    expect(within(history).getByText('Showing 1 of 2 events.')).toBeInTheDocument()
    expect(item).toHaveAttribute('aria-expanded', 'true')

    await user.click(item)
    expect(within(history).queryByText('card processor timeout')).not.toBeInTheDocument()
  })

  it('shows an empty state when no alerts have fired, and scopes history to the service filter', async () => {
    const user = userEvent.setup()
    render(<App />)
    const history = await screen.findByRole('region', { name: 'Alert history' })
    expect(await within(history).findByText('No alerts have fired yet.')).toBeInTheDocument()

    await screen.findByRole('option', { name: 'checkout' })
    await user.selectOptions(screen.getByLabelText('Service'), 'checkout')
    await waitFor(() => {
      const urls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0] as string)
      expect(urls.filter((u) => u.includes('/alerts?')).at(-1)).toContain('service=checkout')
    })
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
    await user.click(screen.getByRole('button', { name: 'ERROR' }))
    await screen.findByText('Showing 1 to 25 of 60')
    expect(logUrls().at(-1)).not.toContain('offset')
  })

  it('filters by several levels at once, and none selected means all levels', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('payment gateway timeout')
    expect(logUrls().at(-1)).not.toContain('level=')

    await user.click(screen.getByRole('button', { name: 'ERROR' }))
    await user.click(screen.getByRole('button', { name: 'WARNING' }))

    await waitFor(() => expect(logUrls().at(-1)).toContain('level=WARNING&level=ERROR'))
    expect(screen.getByRole('button', { name: 'ERROR' })).toHaveAttribute('aria-pressed', 'true')
    const histogramUrls = (fetch as ReturnType<typeof vi.fn>).mock.calls
      .map((c) => c[0] as string)
      .filter((u) => u.includes('/logs/histogram'))
    expect(histogramUrls.at(-1)).toContain('level=WARNING&level=ERROR')

    await user.click(screen.getByRole('button', { name: 'ERROR' }))
    await user.click(screen.getByRole('button', { name: 'WARNING' }))
    await waitFor(() => expect(logUrls().at(-1)).not.toContain('level='))
  })

  it('searches messages after a pause in typing, not on every keystroke', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('payment gateway timeout')

    await user.type(screen.getByRole('searchbox', { name: 'Search messages' }), 'timeout')

    await waitFor(() => expect(logUrls().at(-1)).toContain('q=timeout'))
    const searched = logUrls().filter((u) => u.includes('q='))
    expect(searched.every((u) => u.includes('q=timeout'))).toBe(true)
  })

  it('applies the search at once on Enter and when the box is cleared', async () => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('payment gateway timeout')
    const box = screen.getByRole('searchbox', { name: 'Search messages' })

    await user.type(box, 'abc{Enter}')
    await waitFor(() => expect(logUrls().at(-1)).toContain('q=abc'), { timeout: 200 })

    await user.clear(box)
    await waitFor(() => expect(logUrls().at(-1)).not.toContain('q='), { timeout: 200 })
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
