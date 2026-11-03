import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePolling } from './usePolling'

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches immediately and again every interval', async () => {
    const fetcher = vi.fn().mockResolvedValue('ok')
    const { result } = renderHook(() => usePolling(fetcher, { intervalMs: 1000 }))

    await waitFor(() => expect(result.current.data).toBe('ok'))
    expect(result.current.loading).toBe(false)
    expect(fetcher).toHaveBeenCalledTimes(1)

    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('keeps the last data when a later poll fails', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce('first')
      .mockRejectedValueOnce(new Error('boom'))
    const { result } = renderHook(() => usePolling(fetcher, { intervalMs: 1000 }))
    await waitFor(() => expect(result.current.data).toBe('first'))

    await act(() => vi.advanceTimersByTimeAsync(1000))
    expect(result.current.error).toBe('boom')
    expect(result.current.data).toBe('first')
  })

  it('stops polling while paused and resumes with an immediate fetch', async () => {
    const fetcher = vi.fn().mockResolvedValue('ok')
    const { result, rerender } = renderHook(
      ({ paused }) => usePolling(fetcher, { paused, intervalMs: 1000 }),
      { initialProps: { paused: false } },
    )
    await waitFor(() => expect(result.current.data).toBe('ok'))

    rerender({ paused: true })
    await act(() => vi.advanceTimersByTimeAsync(5000))
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(result.current.data).toBe('ok')

    rerender({ paused: false })
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  })

  it('refetches once when the key changes, even while paused', async () => {
    const fetcher = vi.fn().mockResolvedValue('ok')
    const { rerender } = renderHook(
      ({ paused, key }) => usePolling(fetcher, { paused, key, intervalMs: 1000 }),
      { initialProps: { paused: false, key: 'a' } },
    )
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1))

    rerender({ paused: true, key: 'a' })
    await act(() => vi.advanceTimersByTimeAsync(2000))
    expect(fetcher).toHaveBeenCalledTimes(1)

    rerender({ paused: true, key: 'b' })
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))

    await act(() => vi.advanceTimersByTimeAsync(5000))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
