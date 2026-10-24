import type { SortDirection, SortOption } from "../../utils/tableSort";

type SortableHeaderProps = {
  label: string;
  sortKey: string;
  activeKey: string | null;
  direction: SortDirection;
  onSort: (key: string) => void;
  className?: string;
};

export function SortableTableHeader({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
  className = "",
}: SortableHeaderProps) {
  const active = activeKey === sortKey;
  return (
    <th className={className} aria-sort={active ? (direction === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className="inline-flex items-center gap-1 text-left font-medium text-inherit hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
        aria-label={`Sort by ${label}${active ? `, currently ${direction === "asc" ? "ascending" : "descending"}` : ""}`}
      >
        {label}
        <span aria-hidden="true" className={`text-xs ${active ? "text-blue-700" : "text-slate-400"}`}>
          {active ? (direction === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </button>
    </th>
  );
}

type MobileSortControlsProps = {
  options: SortOption[];
  sortKey: string | null;
  direction: SortDirection;
  onSortKeyChange: (key: string) => void;
  onToggleDirection: () => void;
  className?: string;
};

export function MobileSortControls({
  options,
  sortKey,
  direction,
  onSortKeyChange,
  onToggleDirection,
  className = "",
}: MobileSortControlsProps) {
  return (
    <div className={`flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-2 ${className}`}>
      <label className="min-w-0 flex-1 text-xs font-semibold text-slate-600">
        Sort by
        <select
          aria-label="Sort by field"
          value={sortKey || ""}
          onChange={(event) => onSortKeyChange(event.target.value)}
          className="mt-1 block min-h-10 w-full rounded-md border border-slate-200 bg-white px-2 text-sm font-normal text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
        >
          <option value="">Default order</option>
          {options.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
        </select>
      </label>
      <button
        type="button"
        onClick={onToggleDirection}
        disabled={!sortKey}
        aria-label={`Change sort direction, currently ${direction === "asc" ? "ascending" : "descending"}`}
        className="mt-4 min-h-10 shrink-0 rounded-md border border-slate-200 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {direction === "asc" ? "↑ Asc" : "↓ Desc"}
      </button>
    </div>
  );
}
