import type { LogLevel } from './types'

// Levels map to a fixed severity ramp rather than arbitrary chart colors,
// so "ERROR" always reads the same regardless of what else is on screen.
// Values are CSS variables (defined in index.css) so the chart, badges and
// legend share one source and a future theme only changes the variables.
export const LEVEL_COLOR: Record<LogLevel, string> = {
  DEBUG: 'var(--level-debug)',
  INFO: 'var(--level-info)',
  WARNING: 'var(--level-warning)',
  ERROR: 'var(--level-error)',
  CRITICAL: 'var(--level-critical)',
}

// Stack order bottom -> top: lowest severity at the bottom.
export const LEVEL_STACK_ORDER: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
