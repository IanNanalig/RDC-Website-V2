import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import { userDisplayName } from "../../utils/userDisplayName";
import { MobileSortControls, SortableTableHeader } from "../../components/portal/TableSortControls";
import { sortRows } from "../../utils/tableSort";
import type { SortDirection } from "../../utils/tableSort";

type ApiProject = {
  id: number;
  title?: string;
  name?: string;
  agency?: string;
  budget?: number;
  status?: string;
  updated_at?: string;
  submitted_by_name?: string;
  submitted_by?: {
    username?: string;
  };
  submission_type?: string;
  profile_data?: Record<string, unknown>;
};
const PAGE_SIZE = 10;

const reviewPath = (project: ApiProject) => `/validator/projects/${project.id}/review/simplified`;

const statusLabel = (status?: string) => {
  switch (status) {
    case "planning":
      return "Draft";
    case "proposed":
      return "Submitted";
    case "completed":
      return "Validated";
    case "ongoing":
      return "Ongoing";
    default:
      return status || "N/A";
  }
};

const statusBadge = (status?: string) => {
  switch (status) {
    case "planning":
      return "bg-amber-100 text-amber-700";
    case "proposed":
      return "bg-blue-100 text-blue-700";
    case "completed":
      return "bg-emerald-100 text-emerald-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
};

const getValidatorReview = (p: ApiProject) => {
  const pd = p.profile_data as Record<string, unknown> | undefined;
  const vr = pd?.validator_review;
  if (!vr || typeof vr !== "object") return null;
  return vr as Record<string, unknown>;
};

const reviewStateLabel = (p: ApiProject) => {
  const vr = getValidatorReview(p);
  const status = String(vr?.review_status || "").toLowerCase();
  if (status === "draft") return "Draft";
  if (status === "reviewed") return "Needs Revision";
  if (status === "endorsed" || status === "validated") return "Validated";
  if (status === "rejected") return "Rejected";
  return "Not Reviewed";
};

const reviewStateBadge = (p: ApiProject) => {
  const vr = getValidatorReview(p);
  const status = String(vr?.review_status || "").toLowerCase();
  if (status === "draft") return "bg-slate-100 text-slate-700";
  if (status === "reviewed") return "bg-violet-100 text-violet-700";
  if (status === "endorsed" || status === "validated") return "bg-emerald-100 text-emerald-700";
  if (status === "rejected") return "bg-rose-100 text-rose-700";
  return "bg-slate-100 text-slate-700";
};

const ValidatorReviewHistory: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const user = useMemo(() => {
    const userData = localStorage.getItem("user");
    return userData ? JSON.parse(userData) : null;
  }, []);
  const displayName = userDisplayName(user, "Validator");

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get("validator/projects/?scope=history");
      setProjects(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error("Failed to load validator history:", error);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      navigate("/login");
      return;
    }
    loadProjects();
    const onStorage = (e: StorageEvent) => {
      if (e.key === "projects_last_update") loadProjects();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [loadProjects, navigate, user]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) =>
      `${p.title || p.name || ""} ${p.agency || ""} ${p.submitted_by_name || p.submitted_by?.username || ""}`
        .toLowerCase()
        .includes(q),
    );
  }, [projects, query]);
  const sortOptions = [
    { key: "title", label: "Title" },
    { key: "contributor", label: "Contributor" },
    { key: "agency", label: "Agency" },
    { key: "budget", label: "Budget" },
    { key: "status", label: "Status" },
    { key: "review", label: "Review State" },
    { key: "updated", label: "Updated" },
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
  const sortedProjects = useMemo(() => sortRows(filtered, sortKey, sortDirection, (project, key) => {
    switch (key) {
      case "title": return project.title || project.name || "Untitled";
      case "contributor": return project.submitted_by_name || project.submitted_by?.username || "Unknown";
      case "agency": return project.agency || "";
      case "budget": return Number(project.budget || 0);
      case "status": return statusLabel(project.status);
      case "review": return reviewStateLabel(project);
      case "updated": return project.updated_at ? new Date(project.updated_at).getTime() : null;
      default: return "";
    }
  }), [filtered, sortKey, sortDirection]);
  const pageCount = Math.max(1, Math.ceil(sortedProjects.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = sortedProjects.length ? (currentPage - 1) * PAGE_SIZE + 1 : 0;
  const pageEnd = Math.min(currentPage * PAGE_SIZE, sortedProjects.length);
  const visibleProjects = sortedProjects.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  if (!user) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;

  return (
    <PortalLayout
      title="Reviewed & Endorsed"
      subtitle="Projects you already reviewed or endorsed"
      role="validator"
      userName={displayName}
      topActions={<button onClick={loadProjects} className="portal-btn portal-btn-ghost">Refresh</button>}
    >
      <div className="portal-card mb-3">
        <div className="portal-card-body space-y-3">
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            placeholder="Search by title, agency, or contributor"
            className="w-full border border-slate-200 rounded-xl px-3 py-2 bg-white"
          />
          <MobileSortControls
            className="2xl:hidden"
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
          <div className="portal-card-body text-slate-500">Loading reviewed history...</div>
        ) : sortedProjects.length === 0 ? (
          <div className="portal-card-body text-slate-500">No reviewed/endorsed projects found yet.</div>
        ) : (
          <>
          <div className="space-y-3 p-3 lg:hidden">
            {visibleProjects.map((p) => (
              <article key={`mobile-history-${p.id}`} className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                <h2 className="break-words font-semibold text-slate-900">{p.title || p.name || "Untitled"}</h2>
                <div className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                  <p><span className="font-medium text-slate-800">Contributor:</span> {p.submitted_by_name || p.submitted_by?.username || "Unknown"}</p>
                  <p><span className="font-medium text-slate-800">Agency:</span> {p.agency || "N/A"}</p>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusBadge(p.status)}`}>{statusLabel(p.status)}</span>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${reviewStateBadge(p)}`}>{reviewStateLabel(p)}</span>
                </div>
                <button
                  type="button"
                  onClick={() => navigate(reviewPath(p))}
                  className="portal-btn portal-btn-primary mt-3 min-h-11 w-full"
                >
                  View
                </button>
              </article>
            ))}
          </div>
          <div className="portal-table-wrap">
          <table className="portal-table hidden lg:table">
            <thead>
              <tr>
                <SortableTableHeader label="Title" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Contributor" sortKey="contributor" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="min-w-[160px]" />
                <SortableTableHeader label="Agency" sortKey="agency" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden lg:table-cell" />
                <SortableTableHeader label="Budget" sortKey="budget" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden xl:table-cell" />
                <SortableTableHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Review State" sortKey="review" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Updated" sortKey="updated" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden 2xl:table-cell" />
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleProjects.map((p) => (
                <tr key={p.id}>
                  <td className="max-w-[220px] truncate" title={p.title || p.name || "Untitled"}>{p.title || p.name || "Untitled"}</td>
                  <td className="max-w-[180px] truncate" title={p.submitted_by_name || p.submitted_by?.username || "Unknown"}>
                    {p.submitted_by_name || p.submitted_by?.username || "Unknown"}
                  </td>
                  <td className="hidden lg:table-cell max-w-[170px] truncate" title={p.agency || "N/A"}>{p.agency || "N/A"}</td>
                  <td className="hidden xl:table-cell">PHP {(p.budget || 0).toLocaleString()}</td>
                  <td>
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${statusBadge(p.status)}`}>
                      {statusLabel(p.status)}
                    </span>
                  </td>
                  <td>
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${reviewStateBadge(p)}`}>
                      {reviewStateLabel(p)}
                    </span>
                  </td>
                  <td className="hidden 2xl:table-cell">{p.updated_at ? new Date(p.updated_at).toLocaleString() : "-"}</td>
                  <td>
                    <button
                      onClick={() => navigate(reviewPath(p))}
                      className="text-blue-600 hover:underline whitespace-nowrap"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <div className="portal-card-body flex flex-col gap-3 border-t border-slate-200 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600" aria-live="polite">
              Showing <span className="font-semibold">{pageStart}</span>–<span className="font-semibold">{pageEnd}</span> of {sortedProjects.length} matching projects
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

export default ValidatorReviewHistory;
