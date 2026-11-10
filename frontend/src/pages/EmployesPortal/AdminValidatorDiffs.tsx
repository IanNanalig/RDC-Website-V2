import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import RefreshButton from "../../components/portal/RefreshButton";
import { userDisplayName } from "../../utils/userDisplayName";
import { MobileSortControls, SortableTableHeader } from "../../components/portal/TableSortControls";
import { sortRows } from "../../utils/tableSort";
import type { SortDirection } from "../../utils/tableSort";

type ApiProject = {
  id: number;
  title?: string;
  name?: string;
  agency?: string;
  status?: string;
  workflow_status?: string;
  workflow_status_label?: string;
  validated?: boolean;
  updated_at?: string;
  submitted_by_name?: string;
  reviewed_by_name?: string;
  submitted_by?: {
    username?: string;
  };
  profile_data?: Record<string, unknown>;
  priority_analysis?: {
    score?: number;
    suggested_priority?: string;
    final_priority?: string;
    confirmed?: boolean;
  } | null;
};

type ReviewState = "all" | "draft" | "pending_validation" | "needs_revision" | "validated";
const PAGE_SIZE = 10;

const getValidatorReview = (p: ApiProject): Record<string, unknown> | null => {
  const pd = p.profile_data as Record<string, unknown> | undefined;
  const vr = pd?.validator_review;
  return vr && typeof vr === "object" ? vr as Record<string, unknown> : null;
};

const validatorName = (project: ApiProject) =>
  project.reviewed_by_name || String(getValidatorReview(project)?.reviewed_by_name || getValidatorReview(project)?.reviewed_by_username || "");

const stateLabel = (value: string) => {
  const normalized = String(value || "").toLowerCase();
  if (!normalized) return "Unknown";
  if (normalized === "draft") return "Draft";
  if (normalized === "pending_validation") return "Pending Validation";
  if (normalized === "needs_revision") return "Needs Revision";
  if (normalized === "validated") return "Validated";
  return normalized;
};

const stateBadge = (value: string) => {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "draft") return "bg-slate-100 text-slate-700";
  if (normalized === "pending_validation") return "bg-blue-100 text-blue-700";
  if (normalized === "needs_revision") return "bg-violet-100 text-violet-700";
  if (normalized === "validated") return "bg-emerald-100 text-emerald-700";
  return "bg-slate-100 text-slate-700";
};

const AdminValidatorDiffs: React.FC = () => {
  const navigate = useNavigate();
  const userRaw = localStorage.getItem("user");
  const user = userRaw ? JSON.parse(userRaw) : { username: "admin" };
  const displayName = userDisplayName(user, "Admin");

  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<ApiProject[]>([]);
  const [selected, setSelected] = useState<ApiProject | null>(null);
  const [query, setQuery] = useState("");
  const [reviewState, setReviewState] = useState<ReviewState>("all");
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.get("admin/projects/");
      setItems(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to load validator diffs:", error);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    let list = items;
    if (reviewState !== "all") {
      list = list.filter((p) => p.workflow_status === reviewState);
    }
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((p) => {
      const vr = getValidatorReview(p);
      return [
        p.title || p.name || "",
        p.agency || "",
        p.submitted_by_name || p.submitted_by?.username || "",
        validatorName(p),
        String(vr?.reviewed_by_username || ""),
      ]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [items, query, reviewState]);
  const sortOptions = [
    { key: "title", label: "Title" },
    { key: "contributor", label: "Contributor" },
    { key: "review", label: "Workflow Status" },
    { key: "priority", label: "AI Priority" },
    { key: "validator", label: "Validator" },
    { key: "reviewed", label: "Reviewed At" },
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
  const sortedItems = useMemo(() => sortRows(filtered, sortKey, sortDirection, (project, key) => {
    const review = getValidatorReview(project);
    switch (key) {
      case "title": return project.title || project.name || "Untitled";
      case "contributor": return project.submitted_by_name || project.submitted_by?.username || "";
      case "review": return stateLabel(String(project.workflow_status || ""));
      case "priority": return Number(project.priority_analysis?.score || 0);
      case "validator": return validatorName(project);
      case "reviewed": return review?.reviewed_at ? new Date(String(review.reviewed_at)).getTime() : null;
      default: return "";
    }
  }), [filtered, sortKey, sortDirection]);
  const pageCount = Math.max(1, Math.ceil(sortedItems.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = sortedItems.length ? (currentPage - 1) * PAGE_SIZE + 1 : 0;
  const pageEnd = Math.min(currentPage * PAGE_SIZE, sortedItems.length);
  const visibleItems = sortedItems.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  return (
    <PortalLayout
      title="Validator Tracker"
      subtitle="Track project reviews, AI-assisted priority evaluations, and Validator decisions."
      role="admin"
      userName={displayName}
      topActions={<RefreshButton loading={loading} onClick={load} />}
    >
      <div className="portal-card mb-3">
        <div className="portal-card-body grid grid-cols-1 lg:grid-cols-3 gap-3">
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            placeholder="Search by title, contributor, agency, validator"
            className="border border-slate-200 rounded-xl px-3 py-2 lg:col-span-2"
          />
          <select
            value={reviewState}
            onChange={(e) => { setReviewState(e.target.value as ReviewState); setPage(1); }}
            className="border border-slate-200 rounded-xl px-3 py-2"
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft</option>
            <option value="pending_validation">Pending Validation</option>
            <option value="needs_revision">Needs Revision</option>
            <option value="validated">Validated</option>
          </select>
          <MobileSortControls
          className="lg:col-span-3 2xl:hidden"
            options={sortOptions}
            sortKey={sortKey}
            direction={sortDirection}
            onSortKeyChange={changeSort}
            onToggleDirection={toggleSortDirection}
          />
        </div>
      </div>

      <div className="portal-card">
        {loading ? (
          <div className="portal-card-body text-slate-500">Loading validator reviews...</div>
        ) : sortedItems.length === 0 ? (
          <div className="portal-card-body text-slate-500">No records matched the current filters.</div>
        ) : (
          <>
          <div className="portal-table-wrap">
          <table className="portal-table">
            <thead>
              <tr>
                <SortableTableHeader label="Title" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Contributor" sortKey="contributor" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden md:table-cell" />
                <SortableTableHeader label="Workflow Status" sortKey="review" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="AI Priority" sortKey="priority" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden lg:table-cell" />
                <SortableTableHeader label="Validator" sortKey="validator" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden xl:table-cell" />
                <SortableTableHeader label="Reviewed At" sortKey="reviewed" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden 2xl:table-cell" />
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((p) => {
                const vr = getValidatorReview(p);
                const reviewStatus = String(p.workflow_status || "");
                return (
                  <tr key={p.id}>
                    <td className="max-w-[250px] truncate" title={p.title || p.name || "Untitled"}>
                      {p.title || p.name || "Untitled"}
                    </td>
                    <td className="hidden md:table-cell">{p.submitted_by_name || p.submitted_by?.username || "-"}</td>
                    <td>
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${stateBadge(reviewStatus)}`}>
                        {stateLabel(reviewStatus)}
                      </span>
                    </td>
                    <td className="hidden lg:table-cell">
                      {p.priority_analysis ? (
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${
                          p.priority_analysis.final_priority === "high"
                            ? "bg-emerald-100 text-emerald-700"
                            : p.priority_analysis.final_priority === "low" || p.priority_analysis.final_priority === "medium"
                            ? "bg-rose-100 text-rose-700"
                            : "bg-slate-100 text-slate-700"
                        }`}>
                          {p.priority_analysis.confirmed
                            ? `Confirmed: ${p.priority_analysis.final_priority === "high" ? "high" : "low"}`
                            : "No official decision"} ({Number(p.priority_analysis.score || 0).toFixed(2)})
                        </span>
                      ) : "-"}
                    </td>
                    <td className="hidden xl:table-cell">{validatorName(p) || "-"}</td>
                    <td className="hidden 2xl:table-cell">
                      {vr?.reviewed_at ? new Date(String(vr.reviewed_at)).toLocaleString() : "-"}
                    </td>
                    <td>
                      <button
                        onClick={() => setSelected(p)}
                        className="text-blue-600 hover:underline whitespace-nowrap"
                      >
                        View Review Details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
          <div className="portal-card-body flex flex-col gap-3 border-t border-slate-200 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600" aria-live="polite">
              Showing <span className="font-semibold">{pageStart}</span>–<span className="font-semibold">{pageEnd}</span> of {sortedItems.length} matching records
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={currentPage <= 1} className="portal-btn portal-btn-ghost disabled:cursor-not-allowed disabled:opacity-50">Previous</button>
              <span className="text-sm text-slate-600">Page {currentPage} of {pageCount}</span>
              <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={currentPage >= pageCount} className="portal-btn portal-btn-ghost disabled:cursor-not-allowed disabled:opacity-50">Next</button>
            </div>
          </div>
          </>
        )}
      </div>
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}>
          <div role="dialog" aria-modal="true" aria-labelledby="validator-review-title" tabIndex={-1} onKeyDown={(event) => { if (event.key === "Escape") setSelected(null); }} className="w-full max-w-xl rounded-xl bg-white p-5 shadow-xl">
            <div className="flex items-start justify-between gap-4"><h2 id="validator-review-title" className="text-lg font-semibold">Review Details</h2><button type="button" autoFocus onClick={() => setSelected(null)} className="portal-btn portal-btn-ghost">Close</button></div>
            <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div><dt className="text-slate-500">Project</dt><dd className="font-medium">{selected.title || selected.name || "Untitled"}</dd></div>
              <div><dt className="text-slate-500">Agency</dt><dd>{selected.agency || "Not recorded"}</dd></div>
              <div><dt className="text-slate-500">Contributor</dt><dd>{selected.submitted_by_name || selected.submitted_by?.username || "Not recorded"}</dd></div>
              <div><dt className="text-slate-500">Validator</dt><dd>{validatorName(selected) || "Not recorded"}</dd></div>
              <div><dt className="text-slate-500">Workflow status</dt><dd>{selected.workflow_status_label || stateLabel(String(selected.workflow_status || ""))}</dd></div>
              <div><dt className="text-slate-500">AI recommendation</dt><dd>{selected.priority_analysis?.suggested_priority || "Not available"}</dd></div>
              <div><dt className="text-slate-500">Confirmed priority</dt><dd>{selected.priority_analysis?.confirmed ? selected.priority_analysis.final_priority : "Not confirmed"}</dd></div>
              <div><dt className="text-slate-500">Reviewed at</dt><dd>{getValidatorReview(selected)?.reviewed_at ? new Date(String(getValidatorReview(selected)?.reviewed_at)).toLocaleString("en-PH", { timeZone: "Asia/Manila" }) : "Not recorded"}</dd></div>
              <div className="sm:col-span-2"><dt className="text-slate-500">Review notes</dt><dd className="whitespace-pre-wrap">{String(getValidatorReview(selected)?.review_notes || "None recorded")}</dd></div>
            </dl>
            <div className="mt-5 flex justify-end"><button type="button" onClick={() => navigate(`/admin/projects/${selected.id}/view`)} className="portal-btn portal-btn-primary">Open Project and History</button></div>
          </div>
        </div>
      )}
    </PortalLayout>
  );
};

export default AdminValidatorDiffs;
