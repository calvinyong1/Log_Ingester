import { LEVEL_STACK_ORDER } from './levelStyle'
import type { LogEvent, LogLevel } from './types'

export interface Bucket {
  start: number
  end: number
  counts: Record<LogLevel, number>
  total: number
  errors: number
}

const BUCKET_COUNT = 24

export function bucketEvents(events: LogEvent[], rangeMinutes: number | null): Bucket[] {
  if (events.length === 0) return []

  const now = Date.now()
  const end = now
  const start =
    rangeMinutes != null
      ? now - rangeMinutes * 60_000
      : Math.min(...events.map((e) => new Date(e.timestamp).getTime()))

  const span = Math.max(end - start, 60_000) // guard against a degenerate/zero-width range
  const bucketWidth = span / BUCKET_COUNT

  const buckets: Bucket[] = Array.from({ length: BUCKET_COUNT }, (_, i) => ({
    start: start + i * bucketWidth,
    end: start + (i + 1) * bucketWidth,
    counts: { DEBUG: 0, INFO: 0, WARNING: 0, ERROR: 0, CRITICAL: 0 },
    total: 0,
    errors: 0,
  }))

  for (const event of events) {
    const t = new Date(event.timestamp).getTime()
    if (t < start || t > end) continue
    const idx = Math.min(BUCKET_COUNT - 1, Math.floor((t - start) / bucketWidth))
    const bucket = buckets[idx]
    bucket.counts[event.level] += 1
    bucket.total += 1
    if (event.level === 'ERROR' || event.level === 'CRITICAL') bucket.errors += 1
  }

  return buckets
}

export { LEVEL_STACK_ORDER }
