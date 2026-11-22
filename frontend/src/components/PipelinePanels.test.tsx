import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PipelinePanels } from './PipelinePanels'

afterEach(() => vi.unstubAllEnvs())

async function expand() {
  await userEvent.click(screen.getByRole('button', { name: /pipeline/i }))
}

function sources(): string[] {
  return Array.from(document.querySelectorAll('iframe')).map((f) => f.getAttribute('src') ?? '')
}

describe('PipelinePanels', () => {
  it('starts collapsed and loads nothing from Grafana', () => {
    render(<PipelinePanels />)

    const toggle = screen.getByRole('button', { name: /pipeline/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(document.querySelectorAll('iframe')).toHaveLength(0)
  })

  it('renders one iframe per panel with a descriptive title once expanded', async () => {
    render(<PipelinePanels />)

    await expand()

    expect(screen.getByRole('button', { name: /pipeline/i })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
    for (const title of ['Ingest rate', 'Queue depth', 'Queue wait', 'Failed jobs']) {
      expect(screen.getByTitle(new RegExp(title, 'i'))).toBeInTheDocument()
    }
    expect(document.querySelectorAll('iframe')).toHaveLength(4)
  })

  it('points each iframe at a Grafana solo panel', async () => {
    render(<PipelinePanels />)

    await expand()

    sources().forEach((src, i) => {
      expect(src).toContain('http://localhost:3000/d-solo/pipeline/')
      expect(src).toContain(`panelId=${i + 1}`)
    })
  })

  it('collapses again and removes the iframes', async () => {
    render(<PipelinePanels />)

    await expand()
    await expand()

    expect(document.querySelectorAll('iframe')).toHaveLength(0)
  })

  it('keeps the Open in Grafana link available while collapsed', () => {
    render(<PipelinePanels />)

    const link = screen.getByRole('link', { name: /open in grafana/i })
    expect(link.getAttribute('href')).toBe('http://localhost:3000/d/pipeline')
  })

  it('uses VITE_GRAFANA_URL when it is set', async () => {
    vi.stubEnv('VITE_GRAFANA_URL', 'https://grafana.example.com')
    render(<PipelinePanels />)

    await expand()

    expect(sources()[0]).toContain('https://grafana.example.com/d-solo/pipeline/')
  })
})
