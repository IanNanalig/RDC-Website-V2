export function ScoringHistoryPagination({ label, page, totalPages, loading, onPage }: {
  label: string;
  page: number;
  totalPages: number;
  loading: boolean;
  onPage: (page: number) => void;
}) {
  return (
    <nav aria-label={label} className="mt-3 flex flex-wrap items-center gap-3">
      <button type="button" className="portal-btn portal-btn-ghost" disabled={loading || page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <span aria-live="polite" className="text-sm text-slate-700">Page {page} of {Math.max(1, totalPages)}</span>
      <button type="button" className="portal-btn portal-btn-ghost" disabled={loading || page >= totalPages} onClick={() => onPage(page + 1)}>Next</button>
    </nav>
  );
}
