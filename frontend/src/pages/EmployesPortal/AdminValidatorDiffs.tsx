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
  updated_at?: string;
  submitted_by_name?: string;
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

type ReviewState = "all" | "draft" | "reviewed" | "endorsed" | "rejected" | "not_reviewed";
const PAGE_SIZE = 10;

const getValidatorReview = (p: ApiProject): Record<string, unknown> | null => {
  const pd = p.profile_data as Record<string, unknown> | undefined;
  const vr = pd?.validator_review;
  if (!vr || typeof vr !== "object") return null;
  return vr as Record<string, unknown>;
};

const stateLabel = (value: string) => {
  const normalized = String(value || "").toLowerCase();
  if (!normalized) return "Not Reviewed";
  if (normalized === "draft") return "Draft";
  if (normalized === "reviewed") return "Needs Revision";
  if (normalized === "endorsed" || normalized === "validated") return "Validated";
  if (normalized === "rejected") return "Rejected";
  return normalized;
};

const stateBadge = (value: string) => {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "draft") return "bg-slate-100 text-slate-700";
  if (normalized === "reviewed") return "bg-violet-100 text-violet-700";
  if (normalized === "endorsed" || normalized === "validated") return "bg-emerald-100 text-emerald-700";
  if (normalized === "rejected") return "bg-rose-100 text-rose-700";
  return "bg-slate-100 text-slate-700";
};

const AdminValidatorDiffs: React.FC = () => {
  const navigate = useNavigate();
  const userRaw = localStorage.getItem("user");
  const user = userRaw ? JSON.parse(userRaw) : { username: "admin" };
  const displayName = userDisplayName(user, "Admin");

  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<ApiProject[]>([]);
  const [query, setQuery] = useState("");
  const [reviewState, setReviewState] = useState<ReviewState>("all");
  const [editedOnly, setEditedOnly] = useState(false);
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
      list = list.filter((p) => {
        const vr = getValidatorReview(p);
        let status = String(vr?.review_status || "").toLowerCase();
        if (status === "validated") status = "endorsed";
        if (reviewState === "not_reviewed") return !status;
        return status === reviewState;
      });
    }
    if (editedOnly) {
      list = list.filter((p) => {
        const vr = getValidatorReview(p);
        return Boolean(vr?.edited);
      });
    }
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((p) => {
      const vr = getValidatorReview(p);
      return [
        p.title || p.name || "",
        p.agency || "",
        p.submitted_by_name || p.submitted_by?.username || "",
        String(vr?.reviewed_by_username || ""),
      ]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });
  }, [items, query, reviewState, editedOnly]);
  const sortOptions = [
    { key: "title", label: "Title" },
    { key: "contributor", label: "Contributor" },
    { key: "review", label: "Review State" },
    { key: "edited", label: "Edited Fields" },
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
      case "review": return stateLabel(String(review?.review_status || ""));
      case "edited": return Number(review?.edited_fields_count || 0);
      case "priority": return Number(project.priority_analysis?.score || 0);
      case "validator": return String(review?.reviewed_by_username || "");
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
      subtitle="Track reviewed copies, edited fields, and validator decisions"
      role="admin"
      userName={displayName}
      topActions={<RefreshButton loading={loading} onClick={load} />}
    >
      <div className="portal-card mb-3">
        <div className="portal-card-body grid grid-cols-1 lg:grid-cols-4 gap-3">
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
            <option value="all">All states</option>
            <option value="draft">Draft</option>
            <option value="reviewed">Reviewed</option>
            <option value="endorsed">Endorsed</option>
            <option value="rejected">Rejected</option>
            <option value="not_reviewed">Not Reviewed</option>
          </select>
          <label className="inline-flex items-center gap-2 border border-slate-200 rounded-xl px-3 py-2">
            <input type="checkbox" checked={editedOnly} onChange={(e) => { setEditedOnly(e.target.checked); setPage(1); }} />
            <span className="text-sm">Edited only</span>
          </label>
          <MobileSortControls
            className="lg:col-span-4 2xl:hidden"
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
          <div className="portal-card-body text-slate-500">Loading validator diffs...</div>
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
                <SortableTableHeader label="Review State" sortKey="review" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Edited Fields" sortKey="edited" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden lg:table-cell" />
                <SortableTableHeader label="AI Priority" sortKey="priority" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden lg:table-cell" />
                <SortableTableHeader label="Validator" sortKey="validator" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden xl:table-cell" />
                <SortableTableHeader label="Reviewed At" sortKey="reviewed" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden 2xl:table-cell" />
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((p) => {
                const vr = getValidatorReview(p);
                const reviewStatus = String(vr?.review_status || "");
                const editedCount = Number(vr?.edited_fields_count || 0);
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
                    <td className="hidden lg:table-cell">{editedCount}</td>
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
                    <td className="hidden xl:table-cell">{String(vr?.reviewed_by_username || "-")}</td>
                    <td className="hidden 2xl:table-cell">
                      {vr?.reviewed_at ? new Date(String(vr.reviewed_at)).toLocaleString() : "-"}
                    </td>
                    <td>
                      <button
                        onClick={() => navigate(`/admin/projects/${p.id}/view?mode=diff`)}
                        className="text-blue-600 hover:underline whitespace-nowrap"
                      >
                        View Diffs
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
    </PortalLayout>
  );
};

export default AdminValidatorDiffs;
