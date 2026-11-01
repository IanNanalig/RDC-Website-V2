import { useCallback, useEffect, useRef, useState } from "react";
import PortalLayout from "../../components/portal/PortalLayout";
import RefreshButton from "../../components/portal/RefreshButton";
import { userDisplayName } from "../../utils/userDisplayName";
import { api } from "../../services/api";
import { MobileSortControls, SortableTableHeader } from "../../components/portal/TableSortControls";
import type { SortDirection } from "../../utils/tableSort";

type Option = { value: string; label: string };
type Activity = {
  id: number;
  display_name?: string;
  username: string;
  role: string;
  event: string;
  category: string;
  category_label: string;
  action_label: string;
  description: string;
  result: string;
  result_label: string;
  target_label?: string;
  project_title?: string;
  created_at: string;
};
type ActivityDetail = Activity & {
  ip_address?: string;
  location_hint?: string;
  technical_details?: Record<string, unknown>;
};

const PAGE_SIZE = 10;

const resultClass = (result: string) => {
  if (result === "failed") return "bg-rose-100 text-rose-700";
  if (result === "blocked" || result === "rejected") return "bg-amber-100 text-amber-800";
  if (result === "pending") return "bg-blue-100 text-blue-700";
  return "bg-emerald-100 text-emerald-700";
};

const categoryClass = (category: string) => {
  if (category === "accounts_access") return "bg-violet-100 text-violet-700";
  if (category === "projects") return "bg-blue-100 text-blue-700";
  if (category === "reviews_validation") return "bg-cyan-100 text-cyan-800";
  if (category === "agencies") return "bg-teal-100 text-teal-800";
  if (category === "website_content") return "bg-fuchsia-100 text-fuchsia-700";
  return "bg-slate-100 text-slate-700";
};

const readableKey = (key: string) => key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function TechnicalValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="text-slate-400">Not recorded</span>;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value !== "object") return <span className="break-words">{String(value)}</span>;
  return <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-3 text-xs text-slate-100">{JSON.stringify(value, null, 2)}</pre>;
}

export default function AuditLog() {
  const raw = localStorage.getItem("user");
  const user = raw ? JSON.parse(raw) as { first_name?: string; last_name?: string; username?: string } : {};
  const [filters, setFilters] = useState({ search: "", user: "", category: "", result: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [items, setItems] = useState<Activity[]>([]);
  const [categoryOptions, setCategoryOptions] = useState<Option[]>([]);
  const [resultOptions, setResultOptions] = useState<Option[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detailId, setDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ActivityDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const detailRequest = useRef(0);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ include_meta: "1", limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
      if (sortKey) {
        params.set("sort_by", sortKey);
        params.set("sort_direction", sortDirection);
      }
      Object.entries(filters).forEach(([key, value]) => { if (value.trim()) params.set(key, value.trim()); });
      const data = await api.get(`admin/activity/?${params.toString()}`) as {
        results: Activity[];
        count: number;
        category_options?: Option[];
        result_options?: Option[];
      };
      setItems(data.results);
      setCount(data.count);
      setCategoryOptions(data.category_options || []);
      setResultOptions(data.result_options || []);
      if (page > Math.max(1, Math.ceil(data.count / PAGE_SIZE))) setPage(Math.max(1, Math.ceil(data.count / PAGE_SIZE)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Audit log could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [filters, page, sortKey, sortDirection]);

  useEffect(() => { void load(); }, [load]);

  const change = (key: keyof typeof filters, value: string) => {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  };
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const sortOptions = [
    { key: "timestamp", label: "Timestamp" },
    { key: "user", label: "Actor" },
    { key: "event", label: "Activity" },
    { key: "target", label: "Target" },
  ];
  const changeSort = (key: string) => {
    setPage(1);
    if (sortKey === key) setSortDirection((direction) => direction === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDirection("asc"); }
  };
  const toggleSortDirection = () => {
    setPage(1);
    setSortDirection((direction) => direction === "asc" ? "desc" : "asc");
  };

  const closeDetails = useCallback(() => {
    detailRequest.current += 1;
    setDetailId(null);
    setDetail(null);
    setDetailError("");
    window.setTimeout(() => returnFocusRef.current?.focus(), 0);
  }, []);

  const loadDetails = useCallback(async (id: number) => {
    const generation = ++detailRequest.current;
    setDetailLoading(true);
    setDetailError("");
    setDetail(null);
    try {
      const data = await api.get(`admin/activity/${id}/`) as ActivityDetail;
      if (generation === detailRequest.current) setDetail(data);
    } catch (caught) {
      if (generation === detailRequest.current) setDetailError(caught instanceof Error ? caught.message : "Audit details could not be loaded.");
    } finally {
      if (generation === detailRequest.current) setDetailLoading(false);
    }
  }, []);

  const openDetails = (item: Activity, trigger: HTMLElement) => {
    returnFocusRef.current = trigger;
    setDetailId(item.id);
    void loadDetails(item.id);
  };

  useEffect(() => {
    if (detailId === null) return;
    closeButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDetails();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex='-1'])"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [closeDetails, detailId]);

  const clearFilters = () => {
    setFilters({ search: "", user: "", category: "", result: "", date_from: "", date_to: "" });
    setPage(1);
  };

  return <PortalLayout title="System Audit Log" subtitle="Review portal activity in clear, accountable language" role="admin" userName={userDisplayName(user, "Admin")}>
    <div className="portal-card">
      <div className="portal-card-header flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Audit records</h2>
        <RefreshButton loading={loading} onClick={load} label="Refresh Log" />
      </div>
      <div className="portal-card-body grid gap-3 border-b border-slate-200 bg-slate-50 sm:grid-cols-2 xl:grid-cols-3">
        <label className="text-xs font-semibold text-slate-600">Search activity or target<input value={filters.search} onChange={(event) => change("search", event.target.value)} placeholder="Published Home, project name..." className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Actor<input value={filters.user} onChange={(event) => change("user", event.target.value)} placeholder="Name, username, or email" className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Category<select value={filters.category} onChange={(event) => change("category", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"><option value="">All categories</option>{categoryOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">Result<select value={filters.result} onChange={(event) => change("result", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"><option value="">All results</option>{resultOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">From date<input type="date" value={filters.date_from} onChange={(event) => change("date_from", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">To date<input type="date" value={filters.date_to} onChange={(event) => change("date_to", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" /></label>
        <MobileSortControls className="sm:col-span-2 xl:col-span-3 xl:hidden" options={sortOptions} sortKey={sortKey} direction={sortDirection} onSortKeyChange={changeSort} onToggleDirection={toggleSortDirection} />
        <button type="button" onClick={clearFilters} className="portal-btn portal-btn-ghost sm:col-span-2 xl:col-span-3 xl:justify-self-end">Clear Filters</button>
      </div>
      {error && <div role="alert" className="portal-card-body text-rose-700">{error} <button type="button" onClick={() => void load()} className="underline">Retry</button></div>}
      {loading ? <div className="portal-card-body text-slate-500">Loading audit records...</div> : !items.length ? <div className="portal-card-body text-slate-500">No matching audit records.</div> : <div className="overflow-x-auto"><table className="portal-table min-w-[1120px]"><thead><tr>
        <SortableTableHeader label="Timestamp" sortKey="timestamp" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
        <SortableTableHeader label="Actor" sortKey="user" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
        <th>Category</th>
        <SortableTableHeader label="Activity" sortKey="event" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
        <SortableTableHeader label="Target" sortKey="target" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
        <th>Result</th>
        <th><span className="sr-only">Details</span></th>
      </tr></thead><tbody>{items.map((item) => <tr key={item.id}>
        <td className="whitespace-nowrap text-sm">{new Date(item.created_at).toLocaleString()}</td>
        <td><span className="font-medium text-slate-800">{item.display_name || item.username}</span><span className="block text-xs text-slate-500">{readableKey(item.role)}</span></td>
        <td><span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${categoryClass(item.category)}`}>{item.category_label}</span></td>
        <td className="max-w-[300px]"><span className="font-medium text-slate-800">{item.action_label}</span></td>
        <td className="max-w-[240px] break-words">{item.target_label || item.project_title || "Target not recorded"}</td>
        <td><span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${resultClass(item.result)}`}>{item.result_label}</span></td>
        <td><button type="button" onClick={(event) => openDetails(item, event.currentTarget)} className="portal-btn portal-btn-ghost whitespace-nowrap" aria-label={`View details for ${item.action_label}`}>View details</button></td>
      </tr>)}</tbody></table></div>}
      <div className="portal-card-body flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 text-sm"><span>Showing {count ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, count)} of {count} matching records</span><div className="flex items-center gap-2"><button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="portal-btn portal-btn-ghost disabled:opacity-50">Previous</button><span>Page {page} of {pages}</span><button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)} className="portal-btn portal-btn-ghost disabled:opacity-50">Next</button></div></div>
    </div>

    {detailId !== null && <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 p-3" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDetails(); }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="audit-detail-title" className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="sticky top-0 flex items-start justify-between gap-3 border-b border-slate-200 bg-white p-5">
          <div><h2 id="audit-detail-title" className="text-lg font-semibold text-slate-900">Audit record details</h2><p className="mt-1 text-sm text-slate-500">Technical context is sanitized before display.</p></div>
          <button ref={closeButtonRef} type="button" onClick={closeDetails} className="portal-btn portal-btn-ghost" aria-label="Close audit details">Close</button>
        </div>
        <div className="space-y-5 p-5">
          {detailLoading && <p className="text-sm text-slate-500">Loading audit details...</p>}
          {detailError && <div role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{detailError} <button type="button" onClick={() => void loadDetails(detailId)} className="underline">Retry</button></div>}
          {detail && <>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><p className="font-medium text-slate-900">{detail.description}</p><div className="mt-3 flex flex-wrap gap-2"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${categoryClass(detail.category)}`}>{detail.category_label}</span><span className={`rounded-full px-2 py-1 text-xs font-semibold ${resultClass(detail.result)}`}>{detail.result_label}</span></div></div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div><dt className="font-semibold text-slate-600">Timestamp</dt><dd className="mt-1 text-slate-800">{new Date(detail.created_at).toLocaleString()}</dd></div>
              <div><dt className="font-semibold text-slate-600">Actor</dt><dd className="mt-1 text-slate-800">{detail.display_name || detail.username}</dd></div>
              <div><dt className="font-semibold text-slate-600">Target</dt><dd className="mt-1 text-slate-800">{detail.target_label}</dd></div>
              <div><dt className="font-semibold text-slate-600">Original event</dt><dd className="mt-1 font-mono text-xs text-slate-800">{detail.event}</dd></div>
              <div><dt className="font-semibold text-slate-600">IP address</dt><dd className="mt-1 text-slate-800">{detail.ip_address || "Not recorded"}</dd></div>
              <div><dt className="font-semibold text-slate-600">Location</dt><dd className="mt-1 text-slate-800">{detail.location_hint || "Not recorded"}</dd></div>
            </dl>
            <div><h3 className="font-semibold text-slate-800">Technical context</h3>{detail.technical_details && Object.keys(detail.technical_details).length ? <dl className="mt-3 space-y-3">{Object.entries(detail.technical_details).map(([key, value]) => <div key={key} className="rounded-lg border border-slate-200 p-3"><dt className="text-xs font-semibold text-slate-500">{readableKey(key)}</dt><dd className="mt-1 text-sm text-slate-800"><TechnicalValue value={value} /></dd></div>)}</dl> : <p className="mt-2 text-sm text-slate-500">No additional technical context was recorded.</p>}</div>
          </>}
        </div>
      </div>
    </div>}
  </PortalLayout>;
}
