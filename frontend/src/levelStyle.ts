import type { LogLevel } from './types'

// Levels map to a fixed severity ramp rather than arbitrary chart colors,
// so "ERROR" always reads the same regardless of what else is on screen.
// DEBUG is below "good" severity so it just gets a neutral gray.
// Same hex values work in light and dark mode, so no theme lookup needed.
export const LEVEL_COLOR: Record<LogLevel, string> = {
  DEBUG: '#898781',
  INFO: '#0ca30c',
  WARNING: '#fab219',
  ERROR: '#ec835a',
  CRITICAL: '#d03b3b',
}

// Stack order bottom -> top: lowest severity at the bottom.
export const LEVEL_STACK_ORDER: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
