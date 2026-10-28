import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PortalLayout from "../../components/portal/PortalLayout";
import RefreshButton from "../../components/portal/RefreshButton";
import { api } from "../../services/api";
import { userDisplayName } from "../../utils/userDisplayName";

type Project = {
  id: number;
  title?: string;
  name?: string;
  agency?: string;
  submitted_by_name?: string;
  form_version?: number | null;
  current_form_version?: number | null;
};
type PreviewRow = {
  id: number;
  title: string;
  agency: string;
  source_version?: number;
  target_version?: number;
  attention_fields: string[];
  eligible: boolean;
  reason: string;
};
const PAGE_SIZE = 10;

export default function UpdateProjectForms() {
  const user = useMemo(() => JSON.parse(localStorage.getItem("user") || "{}"), []);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"preview" | "migrate" | "">("");
  const [preview, setPreview] = useState<PreviewRow[]>([]);
  const [previewToken, setPreviewToken] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("admin/projects/?view=summary&scope=update_forms", true);
      setProjects(Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : []);
      setSelected(new Set());
      setPage(1);
      setPreview([]);
      setPreviewToken("");
      setConfirmOpen(false);
    } catch (err) {
      setProjects([]);
      setError(err instanceof Error ? err.message : "Outdated projects could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    return search ? projects.filter((project) => `${project.title || project.name || ""} ${project.agency || ""} ${project.submitted_by_name || ""}`.toLocaleLowerCase().includes(search)) : projects;
  }, [projects, query]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = filtered.length ? (currentPage - 1) * PAGE_SIZE + 1 : 0;
  const pageEnd = Math.min(currentPage * PAGE_SIZE, filtered.length);
  const visibleProjects = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const allPageSelected = visibleProjects.length > 0 && visibleProjects.every((project) => selected.has(project.id));
  const allMatchingSelected = filtered.length > 0 && filtered.every((project) => selected.has(project.id));

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  const toggle = (id: number) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const togglePage = () => setSelected((current) => {
    const next = new Set(current);
    visibleProjects.forEach((project) => allPageSelected ? next.delete(project.id) : next.add(project.id));
    return next;
  });
  const toggleAllMatching = () => setSelected((current) => {
    const next = new Set(current);
    filtered.forEach((project) => allMatchingSelected ? next.delete(project.id) : next.add(project.id));
    return next;
  });

  const previewMigration = async () => {
    if (!selected.size) { setError("Select at least one project."); return; }
    setBusy("preview"); setError(""); setNotice("");
    try {
      const data = await api.post("admin/projects/form-migration-preview/", { project_ids: [...selected] });
      setPreview(Array.isArray(data?.rows) ? data.rows : []);
      setPreviewToken(String(data?.preview_token || ""));
      setConfirmOpen(false);
    } catch (err) { setError(err instanceof Error ? err.message : "The migration could not be previewed."); }
    finally { setBusy(""); }
  };
  const migrate = async () => {
    if (!previewToken) { setError("The migration preview has expired. Preview the selected projects again."); return; }
    setBusy("migrate"); setError("");
    try {
      const data = await api.post("admin/projects/migrate-forms/", { preview_token: previewToken });
      setNotice(`${Number(data?.migrated || 0)} planning draft(s) migrated and ${Number(data?.prepared || 0)} validated project update draft(s) prepared. ${Number(data?.blocked || 0) + Number(data?.skipped || 0)} skipped or blocked.`);
      setConfirmOpen(false);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "The migration could not be completed."); }
    finally { setBusy(""); }
  };
  const eligibleCount = preview.filter((row) => row.eligible).length;

  return (
    <PortalLayout title="Update Older Project Forms" subtitle="Safely migrate project answers into the latest published contributor form" role="admin" userName={userDisplayName(user, "Administrator")} topActions={<div className="flex gap-2"><Link to="/admin/dashboard" className="portal-btn portal-btn-ghost">Back to Dashboard</Link><RefreshButton loading={loading} onClick={load} /></div>}>
      <div className="mb-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">Validated projects are not changed directly. Migration prepares a non-public progress-update draft; the migrated answers become current only after the normal submission and endorsement workflow.</div>
      {notice && <p className="mb-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {error && <p role="alert" className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      <section className="portal-card">
        <div className="portal-card-body flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search project, agency, or contributor" className="w-full rounded-xl border border-slate-200 px-3 py-2 sm:max-w-lg" />
          <div className="flex flex-wrap items-center justify-end gap-2">
            {filtered.length > PAGE_SIZE && <button type="button" className="text-sm font-medium text-blue-700 hover:underline" onClick={toggleAllMatching}>{allMatchingSelected ? "Clear all matching" : `Select all ${filtered.length} matching projects`}</button>}
            <span className="text-sm text-slate-600">{selected.size} selected</span>
            <button type="button" className="portal-btn portal-btn-ghost" onClick={previewMigration} disabled={Boolean(busy) || !selected.size}>{busy === "preview" ? "Checking..." : "Preview Migration"}</button>
          </div>
        </div>
        {loading ? <div className="portal-card-body text-slate-500">Loading older forms...</div> : filtered.length === 0 ? <div className="portal-card-body text-slate-500">No projects are using an older published form.</div> : <><div className="overflow-x-auto"><table className="portal-table min-w-[760px]"><thead><tr><th><input type="checkbox" aria-label="Select current page" checked={allPageSelected} onChange={togglePage} /></th><th>Project</th><th>Contributor</th><th>Agency</th><th>Current Form</th><th>Latest Form</th></tr></thead><tbody>{visibleProjects.map((project) => <tr key={project.id}><td><input type="checkbox" aria-label={`Select ${project.title || project.name}`} checked={selected.has(project.id)} onChange={() => toggle(project.id)} /></td><td>{project.title || project.name || "Untitled project"}</td><td>{project.submitted_by_name || "Unknown"}</td><td>{project.agency || "—"}</td><td>Version {project.form_version ?? "—"}</td><td>Version {project.current_form_version ?? "—"}</td></tr>)}</tbody></table></div><div className="portal-card-body flex flex-col gap-3 border-t border-slate-200 sm:flex-row sm:items-center sm:justify-between"><p className="text-sm text-slate-600" aria-live="polite">Showing <span className="font-semibold">{pageStart}</span>–<span className="font-semibold">{pageEnd}</span> of {filtered.length} matching projects</p><div className="flex flex-wrap items-center gap-2"><button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={currentPage <= 1} className="portal-btn portal-btn-ghost disabled:cursor-not-allowed disabled:opacity-50">Previous</button><span className="text-sm text-slate-600">Page {currentPage} of {pageCount}</span><button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={currentPage >= pageCount} className="portal-btn portal-btn-ghost disabled:cursor-not-allowed disabled:opacity-50">Next</button></div></div></>}
      </section>
      {preview.length > 0 && (
        <section className="portal-card mt-4">
          <div className="portal-card-header flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-semibold">Migration Preview</h2>
              <p className="text-sm text-slate-500">The server will recheck every project during execution.</p>
            </div>
            <button
              type="button"
              className="portal-btn portal-btn-primary"
              disabled={Boolean(busy) || !previewToken || eligibleCount === 0}
              onClick={() => setConfirmOpen(true)}
            >
              {busy === "migrate" ? "Migrating..." : "Confirm Migration"}
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="portal-table min-w-[780px]">
              <thead><tr><th>Project</th><th>Version</th><th>Result</th><th>Required Attention</th></tr></thead>
              <tbody>{preview.map((row) => <tr key={row.id}><td><p className="font-medium">{row.title}</p><p className="text-xs text-slate-500">{row.agency}</p></td><td>{row.source_version ?? "—"} → {row.target_version ?? "—"}</td><td><span className={`rounded-full px-2 py-1 text-xs font-semibold ${row.eligible ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{row.eligible ? "Safe to prepare" : "Blocked"}</span>{row.reason && <p className="mt-1 max-w-xl text-xs text-slate-600">{row.reason}</p>}</td><td>{row.attention_fields?.length ? row.attention_fields.join(", ") : "None"}</td></tr>)}</tbody>
            </table>
          </div>
        </section>
      )}
      {confirmOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4"
          role="presentation"
          onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) setConfirmOpen(false); }}
        >
          <div role="dialog" aria-modal="true" aria-labelledby="migration-confirm-title" className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl">
            <h2 id="migration-confirm-title" className="text-lg font-semibold text-slate-900">Confirm project form migration</h2>
            <p className="mt-2 text-sm text-slate-600">Prepare {eligibleCount} eligible project{eligibleCount === 1 ? "" : "s"} using the reviewed migration preview?</p>
            <p className="mt-2 text-sm text-slate-600">Validated public records will remain unchanged until their update drafts are submitted and endorsed.</p>
            {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p>}
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button type="button" autoFocus className="portal-btn portal-btn-ghost" disabled={Boolean(busy)} onClick={() => setConfirmOpen(false)}>Cancel</button>
              <button type="button" className="portal-btn portal-btn-primary" disabled={Boolean(busy)} onClick={migrate}>
                {busy === "migrate" ? "Migrating..." : `Migrate ${eligibleCount} Project${eligibleCount === 1 ? "" : "s"}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </PortalLayout>
  );
}
