import type { TimeRange } from './types'

export const RANGE_PRESETS: { label: string; short: string; minutes: number | null }[] = [
  { label: 'Last 5 min', short: 'last 5 min', minutes: 5 },
  { label: 'Last 15 min', short: 'last 15 min', minutes: 15 },
  { label: 'Last 1 hour', short: 'last hour', minutes: 60 },
  { label: 'Last 24 hours', short: 'last 24 hours', minutes: 60 * 24 },
  { label: 'All', short: 'all time', minutes: null },
]

const MINUTE_MS = 60_000

// datetime-local values have no zone, and `new Date("2026-11-21T14:00")` reads
// them as local time, which is what the person picking them means.
function parseLocal(value: string): Date {
  return new Date(value)
}

export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

export function customRangeError(from: string, to: string): string | null {
  if (!from) return 'Pick a start time'
  // A typed 6-digit year gives a value Date can't parse, and toISOString() would
  // throw on it, so it has to be caught here rather than reach the API call.
  if (Number.isNaN(parseLocal(from).getTime())) return 'Enter a valid start time'
  if (to) {
    if (Number.isNaN(parseLocal(to).getTime())) return 'Enter a valid end time'
    if (parseLocal(to) < parseLocal(from)) return 'The end time is before the start time'
  }
  return null
}

// The API's `end` is exclusive and the inputs only have minute precision, so the
// picked end minute is included by ending one minute later.
export function customBounds(from: string, to: string): { start: Date; end: Date | null } {
  return {
    start: parseLocal(from),
    end: to ? new Date(parseLocal(to).getTime() + MINUTE_MS) : null,
  }
}

function formatPoint(value: string): string {
  return parseLocal(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function rangeLabel(range: TimeRange): string {
  if (range.kind === 'custom') {
    if (!range.from) return ''
    return range.to
      ? `${formatPoint(range.from)} – ${formatPoint(range.to)}`
      : `since ${formatPoint(range.from)}`
  }
  return RANGE_PRESETS.find((p) => p.minutes === range.minutes)?.short ?? ''
}
