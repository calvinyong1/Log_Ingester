import type { LogFilters, LogLevel } from '../types'
import { RANGE_PRESETS } from '../ranges'
import { LOG_LEVELS } from '../types'

interface FilterBarProps {
  filters: LogFilters
  services: string[]
  onChange: (filters: LogFilters) => void
}

export function FilterBar({ filters, services, onChange }: FilterBarProps) {
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
