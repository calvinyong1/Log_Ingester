import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PipelinePanels } from './PipelinePanels'

afterEach(() => vi.unstubAllEnvs())

describe('PipelinePanels', () => {
  it('renders one iframe per panel with a descriptive title', () => {
    render(<PipelinePanels />)

    for (const title of ['Ingest rate', 'Queue depth', 'Queue wait', 'Failed jobs']) {
      expect(screen.getByTitle(new RegExp(title, 'i'))).toBeInTheDocument()
    }
    expect(document.querySelectorAll('iframe')).toHaveLength(4)
  })

  it('points each iframe at a Grafana solo panel', () => {
    render(<PipelinePanels />)

    const sources = Array.from(document.querySelectorAll('iframe')).map((f) => f.getAttribute('src') ?? '')
    sources.forEach((src, i) => {
      expect(src).toContain('http://localhost:3000/d-solo/pipeline/')
      expect(src).toContain(`panelId=${i + 1}`)
    })
  })

  it('links to the full dashboard in Grafana', () => {
    render(<PipelinePanels />)

    const link = screen.getByRole('link', { name: /open in grafana/i })
    expect(link.getAttribute('href')).toBe('http://localhost:3000/d/pipeline')
  })

  it('uses VITE_GRAFANA_URL when it is set', () => {
    vi.stubEnv('VITE_GRAFANA_URL', 'https://grafana.example.com')
    render(<PipelinePanels />)

    expect(document.querySelector('iframe')?.getAttribute('src')).toContain(
      'https://grafana.example.com/d-solo/pipeline/',
    )
  })
})
