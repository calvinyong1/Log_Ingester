import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { LogEventPage } from './types'

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

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => SAMPLE_PAGE,
      }),
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
    expect(screen.getByText('Events loaded')).toBeInTheDocument()
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

    const serviceInput = screen.getByLabelText('Service')
    await user.type(serviceInput, 'checkout')

    await waitFor(() => {
      const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls
      const lastUrl = calls[calls.length - 1][0] as string
      expect(lastUrl).toContain('service=checkout')
    })
  })

  it('shows an error state when the API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')))
    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch')
  })
})
