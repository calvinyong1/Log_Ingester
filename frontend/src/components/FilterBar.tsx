import type { LogFilters, LogLevel } from '../types'
import { LOG_LEVELS } from '../types'

const RANGE_PRESETS: { label: string; minutes: number | null }[] = [
  { label: 'Last 5 min', minutes: 5 },
  { label: 'Last 15 min', minutes: 15 },
  { label: 'Last 1 hour', minutes: 60 },
  { label: 'Last 24 hours', minutes: 60 * 24 },
  { label: 'All', minutes: null },
]

interface FilterBarProps {
  filters: LogFilters
  onChange: (filters: LogFilters) => void
}

export function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="filter-bar" role="group" aria-label="Filters">
      <div className="filter-bar__presets">
        {RANGE_PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="preset-button"
            data-active={filters.rangeMinutes === preset.minutes}
            onClick={() => onChange({ ...filters, rangeMinutes: preset.minutes })}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="filter-bar__fields">
        <label className="filter-field">
          <span>Service</span>
          <input
            type="text"
            placeholder="All services"
            value={filters.service}
            onChange={(e) => onChange({ ...filters, service: e.target.value })}
          />
        </label>

        <label className="filter-field">
          <span>Level</span>
          <select
            value={filters.level}
            onChange={(e) => onChange({ ...filters, level: e.target.value as LogLevel | '' })}
          >
            <option value="">All levels</option>
            {LOG_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}
