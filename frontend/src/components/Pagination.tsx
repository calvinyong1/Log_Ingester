interface PaginationProps {
  page: number // 1-based; page 1 is the newest events
  hasOlder: boolean
  onOlder: () => void
  onNewer: () => void
}

// No total: counting every matching row on each poll is what keyset paging avoids,
// so the position is "Page N" and the only moves are Newer and Older.
export function Pagination({ page, hasOlder, onOlder, onNewer }: PaginationProps) {
  if (page === 1 && !hasOlder) return null

  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="pagination__range">Page {page}</span>
      <div className="pagination__controls">
        <button type="button" className="page-button" disabled={page === 1} onClick={onNewer}>
          Newer
        </button>
        <button type="button" className="page-button" disabled={!hasOlder} onClick={onOlder}>
          Older
        </button>
      </div>
    </nav>
  )
}
