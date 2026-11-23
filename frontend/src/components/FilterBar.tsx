import { useEffect, useRef, useState } from 'react'
import { LEVEL_COLOR } from '../levelStyle'
import { RANGE_PRESETS } from '../ranges'
import type { LogFilters, LogLevel } from '../types'
import { LOG_LEVELS } from '../types'

// Wait for a pause in typing before querying: each change refetches the table and
// the chart, so one request per keystroke would be wasteful.
export const SEARCH_DEBOUNCE_MS = 300

interface FilterBarProps {
  filters: LogFilters
  services: string[]
  onChange: (filters: LogFilters) => void
}

export function FilterBar({ filters, services, onChange }: FilterBarProps) {
  const [text, setText] = useState(filters.q)
  const timer = useRef<number | undefined>(undefined)
  // The debounce fires later; it must apply to the filters as they are then, not
  // as they were when typing started (a level toggled in between would be lost).
  const latest = useRef({ filters, onChange })
  latest.current = { filters, onChange }

  useEffect(() => () => window.clearTimeout(timer.current), [])

  function applySearch(value: string) {
    window.clearTimeout(timer.current)
    const { filters: current, onChange: change } = latest.current
    if (value !== current.q) change({ ...current, q: value })
  }

  function onSearchInput(value: string) {
    setText(value)
    window.clearTimeout(timer.current)
    // Clearing is applied at once: waiting would leave stale results on screen.
    if (value === '') applySearch(value)
    else timer.current = window.setTimeout(() => applySearch(value), SEARCH_DEBOUNCE_MS)
  }

  function toggleLevel(level: LogLevel) {
    const selected = new Set(filters.levels)
    if (!selected.delete(level)) selected.add(level)
    // Canonical order keeps the query string (and the polling key) stable.
    onChange({ ...filters, levels: LOG_LEVELS.filter((l) => selected.has(l)) })
  }

  // Until the list loads (or if it fails), keep the selected service as an
  // option so the select never shows a value it can't represent.
  const options =
    filters.service && !services.includes(filters.service)
      ? [filters.service, ...services]
      : services

  return (
    <div className="filter-bar" role="group" aria-label="Filters">
      <div className="filter-bar__presets">
        {RANGE_PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="preset-button"
            aria-pressed={filters.rangeMinutes === preset.minutes}
            onClick={() => onChange({ ...filters, rangeMinutes: preset.minutes })}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="filter-bar__fields">
        <label className="filter-field">
          <span>Service</span>
          <select
            value={filters.service}
            onChange={(e) => onChange({ ...filters, service: e.target.value })}
          >
            <option value="">All services ({services.length})</option>
            {options.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <div className="filter-field" role="group" aria-label="Level">
          <span>Level</span>
          <div className="filter-bar__presets">
            {LOG_LEVELS.map((level) => (
              <button
                key={level}
                type="button"
                className="preset-button level-chip"
                aria-pressed={filters.levels.includes(level)}
                onClick={() => toggleLevel(level)}
              >
                <span
                  className="level-badge__dot"
                  style={{ background: LEVEL_COLOR[level] }}
                  aria-hidden="true"
                />
                {level}
              </button>
            ))}
          </div>
        </div>
      </div>

      <label className="filter-field filter-field--search">
        <span>Search messages</span>
        <input
          type="search"
          value={text}
          placeholder="e.g. timeout"
          maxLength={200}
          onChange={(e) => onSearchInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') applySearch(text)
          }}
        />
      </label>
    </div>
  )
}
