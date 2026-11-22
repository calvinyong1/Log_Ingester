import { useState } from 'react'

// The numbers come from the Grafana dashboard provisioned in monitoring/ (uid
// "pipeline"); the ids below are its panel ids.
const DASHBOARD_UID = 'pipeline'

const PANELS = [
  { id: 1, title: 'Ingest rate' },
  { id: 2, title: 'Queue depth' },
  { id: 3, title: 'Queue wait (p50, p95)' },
  { id: 4, title: 'Failed jobs' },
] as const

// Read at render so a test can change it; Vite inlines it at build time.
function grafanaUrl(): string {
  return import.meta.env.VITE_GRAFANA_URL ?? 'http://localhost:3000'
}

export function PipelinePanels() {
  const base = grafanaUrl()
  // Collapsed by default, and the iframes only exist while open, so Grafana is
  // not contacted (and its queries not run) until someone asks to see it.
  const [open, setOpen] = useState(false)

  return (
    <section className="pipeline-section">
      <div className="pipeline-section__header">
        <button
          type="button"
          className="pipeline-section__toggle"
          aria-expanded={open}
          aria-controls="pipeline-panels"
          onClick={() => setOpen((o) => !o)}
        >
          <span className="pipeline-section__chevron" aria-hidden="true">
            {open ? '▾' : '▸'}
          </span>
          <h2>Pipeline</h2>
        </button>
        <a href={`${base}/d/${DASHBOARD_UID}`} target="_blank" rel="noreferrer">
          Open in Grafana
        </a>
      </div>
      {open && (
        <div className="pipeline-panels" id="pipeline-panels">
          {PANELS.map((panel) => (
            <iframe
              key={panel.id}
              className="pipeline-panels__frame"
              title={`${panel.title} chart`}
              src={`${base}/d-solo/${DASHBOARD_UID}/pipeline?orgId=1&panelId=${panel.id}&refresh=15s&from=now-1h&to=now`}
            />
          ))}
        </div>
      )}
    </section>
  )
}
