import { useCallback, useEffect, useState } from "react";
import PortalLayout from "../../components/portal/PortalLayout";
import { api } from "../../services/api";

type Activity = { id: number; full_name?: string; username: string; event: string; target_label?: string; project_title?: string; created_at: string; details?: Record<string, unknown> };
const PAGE_SIZE = 10;
const formatChangedField = (value: unknown) => {
  const [root, ...rest] = String(value || "").replace(/^simplified_form\./, "").split(".");
  const known: Record<string, string> = { actualFundingByYear: "Actual/Approved Funding (PHP)", fundingRequirementByYear: "Funding Requirement (PHP)", sdgSelections: "Sustainable Development Goals" };
  const humanize = (part: string) => part.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  return [known[root] || humanize(root), ...rest.map((part) => part === "2022_prior" ? "2022 & Prior" : humanize(part))].join(" · ");
};
const changedFields = (details?: Record<string, unknown>) => Array.isArray(details?.changed_fields) ? details.changed_fields.filter((field): field is string => typeof field === "string") : [];
const changes = (details?: Record<string, unknown>) => Array.isArray(details?.changes) ? details.changes.filter((change): change is { field: string; before: unknown; after: unknown } => Boolean(change && typeof change === "object" && typeof change.field === "string")) : [];
const valueText = (value: unknown) => value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);

export default function AuditLog() {
  const raw = localStorage.getItem("user");
  const user = raw ? JSON.parse(raw) as { full_name?: string; username?: string } : {};
  const [filters, setFilters] = useState({ user: "", event: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<Activity[]>([]);
  const [eventOptions, setEventOptions] = useState<string[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ include_meta: "1", limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) });
      Object.entries(filters).forEach(([key, value]) => { if (value.trim()) params.set(key, value.trim()); });
      const data = await api.get(`admin/activity/?${params.toString()}`) as { results: Activity[]; count: number; event_options?: string[] };
      setItems(data.results);
      setCount(data.count);
      setEventOptions(data.event_options || []);
      if (page > Math.max(1, Math.ceil(data.count / PAGE_SIZE))) setPage(Math.max(1, Math.ceil(data.count / PAGE_SIZE)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Audit log could not be loaded.");
    } finally { setLoading(false); }
  }, [filters, page]);
  useEffect(() => { void load(); }, [load]);
  const change = (key: keyof typeof filters, value: string) => { setPage(1); setFilters((current) => ({ ...current, [key]: value })); };
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return <PortalLayout title="System Audit Log" subtitle="Review portal activity, security actions, and project workflow events" role="admin" userName={user.full_name || user.username || "Admin"}>
    <div className="portal-card">
      <div className="portal-card-header flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Audit records</h2><button type="button" onClick={() => void load()} className="portal-btn portal-btn-ghost">Refresh Log</button></div>
      <div className="portal-card-body grid gap-3 border-b border-slate-200 bg-slate-50 sm:grid-cols-2 xl:grid-cols-4">
        <label className="text-xs font-semibold text-slate-600">User<input value={filters.user} onChange={(event) => change("user", event.target.value)} placeholder="Name, username, or email" className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">Action type<select value={filters.event} onChange={(event) => change("event", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"><option value="">All actions</option>{eventOptions.map((event) => <option key={event} value={event}>{event.replaceAll("_", " ")}</option>)}</select></label>
        <label className="text-xs font-semibold text-slate-600">From date<input type="date" value={filters.date_from} onChange={(event) => change("date_from", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" /></label>
        <label className="text-xs font-semibold text-slate-600">To date<input type="date" value={filters.date_to} onChange={(event) => change("date_to", event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" /></label>
        <button type="button" onClick={() => { setFilters({ user: "", event: "", date_from: "", date_to: "" }); setPage(1); }} className="portal-btn portal-btn-ghost sm:col-span-2 xl:col-span-4 xl:justify-self-end">Clear Filters</button>
      </div>
      {error && <div role="alert" className="portal-card-body text-rose-700">{error} <button type="button" onClick={() => void load()} className="underline">Retry</button></div>}
      {loading ? <div className="portal-card-body text-slate-500">Loading audit records...</div> : !items.length ? <div className="portal-card-body text-slate-500">No matching audit records.</div> : <div className="overflow-x-auto"><table className="portal-table min-w-[680px]"><thead><tr><th>User</th><th>Action</th><th>Target</th><th>Timestamp</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td>{item.full_name || item.username}</td><td>{item.event.replaceAll("_", " ")}</td><td><span>{item.target_label || item.project_title || "—"}</span>{item.details && Object.keys(item.details).length > 0 && <details className="mt-1 text-xs text-slate-600"><summary className="cursor-pointer">Changes and details</summary>{changedFields(item.details).length > 0 && <p>Changed Fields: {changedFields(item.details).map(formatChangedField).join(", ")}</p>}{changes(item.details).length > 0 && <details className="mt-2 rounded border border-slate-200 p-2"><summary>Changes ({changes(item.details).length})</summary><ul>{changes(item.details).map((change, index) => <li key={index} className="mt-2 border-t border-slate-200 pt-2"><strong>{formatChangedField(change.field)}</strong><p>Before: {valueText(change.before)}</p><p>After: {valueText(change.after)}</p></li>)}</ul></details>}<pre className="mt-2 max-w-[350px] whitespace-pre-wrap break-words">{JSON.stringify(Object.fromEntries(Object.entries(item.details).filter(([key]) => !["changes", "changed_fields"].includes(key))), null, 2)}</pre></details>}</td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div>}
      <div className="portal-card-body flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 text-sm"><span>Showing {count ? (page - 1) * PAGE_SIZE + 1 : 0}–{Math.min(page * PAGE_SIZE, count)} of {count} matching records</span><div className="flex items-center gap-2"><button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="portal-btn portal-btn-ghost disabled:opacity-50">Previous</button><span>Page {page} of {pages}</span><button type="button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)} className="portal-btn portal-btn-ghost disabled:opacity-50">Next</button></div></div>
    </div>
  </PortalLayout>;
}
