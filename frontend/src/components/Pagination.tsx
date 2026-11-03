interface PaginationProps {
  offset: number
  pageSize: number
  total: number
  onChange: (offset: number) => void
}

export function Pagination({ offset, pageSize, total, onChange }: PaginationProps) {
  if (total === 0) return null

  const first = offset + 1
  const last = Math.min(offset + pageSize, total)

  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="pagination__range">
        Showing {first.toLocaleString()} to {last.toLocaleString()} of {total.toLocaleString()}
      </span>
      <div className="pagination__controls">
        <button
          type="button"
          className="page-button"
          disabled={offset <= 0}
          onClick={() => onChange(Math.max(0, offset - pageSize))}
        >
          Newer
        </button>
        <button
          type="button"
          className="page-button"
          disabled={last >= total}
          onClick={() => onChange(offset + pageSize)}
        >
          Older
        </button>
      </div>
    </nav>
  )
}
