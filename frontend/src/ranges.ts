export const RANGE_PRESETS: { label: string; short: string; minutes: number | null }[] = [
  { label: 'Last 5 min', short: 'last 5 min', minutes: 5 },
  { label: 'Last 15 min', short: 'last 15 min', minutes: 15 },
  { label: 'Last 1 hour', short: 'last hour', minutes: 60 },
  { label: 'Last 24 hours', short: 'last 24 hours', minutes: 60 * 24 },
  { label: 'All', short: 'all time', minutes: null },
]

export function rangeLabel(minutes: number | null): string {
  return RANGE_PRESETS.find((p) => p.minutes === minutes)?.short ?? ''
}
