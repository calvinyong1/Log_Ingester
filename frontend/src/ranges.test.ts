import { describe, expect, it } from 'vitest'
import { customRangeError, rangeLabel, toLocalInputValue } from './ranges'

describe('customRangeError', () => {
  it('requires a start time', () => {
    expect(customRangeError('', '')).toBe('Pick a start time')
  })

  it('rejects an end before the start, and allows the same minute or no end', () => {
    expect(customRangeError('2026-11-21T14:00', '2026-11-21T13:59')).toBe(
      'The end time is before the start time',
    )
    expect(customRangeError('2026-11-21T14:00', '2026-11-21T14:00')).toBeNull()
    expect(customRangeError('2026-11-21T14:00', '')).toBeNull()
  })
})

describe('customRangeError with unparseable dates', () => {
  // Chrome lets a 6-digit year be typed, giving values like "202612-11-21T00:00",
  // which Date can't read.
  it('rejects an unreadable start or end instead of letting it reach the API', () => {
    expect(customRangeError('202612-11-21T00:00', '')).toBe('Enter a valid start time')
    expect(customRangeError('2026-11-21T14:00', 'garbage')).toBe('Enter a valid end time')
  })
})

describe('rangeLabel', () => {
  it('keeps the preset wording', () => {
    expect(rangeLabel({ kind: 'preset', minutes: 60 })).toBe('last hour')
    expect(rangeLabel({ kind: 'preset', minutes: null })).toBe('all time')
  })

  it('describes a custom window, and an open-ended one as "since"', () => {
    const both = rangeLabel({ kind: 'custom', from: '2026-11-21T14:00', to: '2026-11-21T16:30' })
    expect(both).toContain('–')
    const open = rangeLabel({ kind: 'custom', from: '2026-11-21T14:00', to: '' })
    expect(open.startsWith('since ')).toBe(true)
  })
})

describe('toLocalInputValue', () => {
  it('formats a date as a local datetime-local value', () => {
    expect(toLocalInputValue(new Date('2026-11-21T09:05'))).toBe('2026-11-21T09:05')
  })
})
