import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PortalLayout from "../../components/portal/PortalLayout";
import { userDisplayName } from "../../utils/userDisplayName";
import { api } from "../../services/api";
import { MobileSortControls, SortableTableHeader } from "../../components/portal/TableSortControls";
import { sortRows } from "../../utils/tableSort";
import type { SortDirection } from "../../utils/tableSort";

type OutdatedProject = {
  id: number;
  title?: string;
  name?: string;
  agency?: string;
  status?: string;
  submitted_by_name?: string;
  form_version?: number | null;
  current_form_version?: number | null;
};
const PAGE_SIZE = 10;

const statusLabel = (status?: string) => {
  switch (status) {
    case "planning":
      return "Draft";
    case "proposed":
      return "Submitted";
    case "ongoing":
      return "Ongoing";
    case "completed":
      return "Validated";
    default:
      return status || "N/A";
  }
};

const UpdateProjectForms: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<OutdatedProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const user = useMemo(() => {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  }, []);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("validator/projects/?view=summary&scope=update_forms");
      setProjects(Array.isArray(data) ? data : []);
    } catch (loadError) {
      setProjects([]);
      setError(loadError instanceof Error ? loadError.message : "Failed to load projects.");
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
  }, [loadProjects, navigate, user]);

  const filteredProjects = useMemo(() => {
    const search = query.trim().toLowerCase();
    if (!search) return projects;
    return projects.filter((project) =>
      `${project.title || project.name || ""} ${project.agency || ""} ${project.submitted_by_name || ""}`
        .toLowerCase()
        .includes(search),
    );
  }, [projects, query]);
  const sortOptions = [
    { key: "title", label: "Project" },
    { key: "contributor", label: "Contributor" },
    { key: "agency", label: "Agency" },
    { key: "current", label: "Current Form" },
    { key: "latest", label: "Latest Form" },
    { key: "status", label: "Status" },
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
  const sortedProjects = useMemo(() => sortRows(filteredProjects, sortKey, sortDirection, (project, key) => {
    switch (key) {
      case "title": return project.title || project.name || "Untitled project";
      case "contributor": return project.submitted_by_name || "Unknown";
      case "agency": return project.agency || "";
      case "current": return project.form_version ?? null;
      case "latest": return project.current_form_version ?? null;
      case "status": return statusLabel(project.status);
      default: return "";
    }
  }), [filteredProjects, sortKey, sortDirection]);
  const pageCount = Math.max(1, Math.ceil(sortedProjects.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = sortedProjects.length ? (currentPage - 1) * PAGE_SIZE + 1 : 0;
  const pageEnd = Math.min(currentPage * PAGE_SIZE, sortedProjects.length);
  const visibleProjects = sortedProjects.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  const updateForm = async (project: OutdatedProject) => {
    const title = project.title || project.name || "Untitled project";
    const confirmed = window.confirm(
      `Update “${title}” from form version ${project.form_version ?? "old"} to version ${project.current_form_version ?? "latest"}?\n\n` +
        "Existing answers and project history will be preserved. Newly added fields may be blank and may require sending the project back to the contributor for revisions. This will not submit, validate, or change the project’s workflow status.\n\nContinue?",
    );
    if (!confirmed) return;

    setUpdatingId(project.id);
    setNotice("");
    setError("");
    try {
      const result = await api.post(`validator/projects/${project.id}/update-form/`);
      setProjects((current) => current.filter((item) => item.id !== project.id));
      setNotice(result?.detail || `${title} now uses the latest contributor form.`);
      localStorage.setItem("projects_last_update", String(Date.now()));
      window.dispatchEvent(new CustomEvent("portal:data-changed"));
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Failed to update the project form.");
    } finally {
      setUpdatingId(null);
    }
  };

  if (!user) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;

  return (
    <PortalLayout
      title="Update Older Project Forms"
      subtitle="Move selected projects to the latest published contributor form"
      role="validator"
      userName={userDisplayName(user, "Validator")}
      topActions={
        <div className="flex flex-wrap gap-2">
          <Link to="/validator/dashboard" className="portal-btn portal-btn-ghost">Back to Dashboard</Link>
          <button type="button" onClick={loadProjects} className="portal-btn portal-btn-ghost">Refresh</button>
        </div>
      }
    >
      <div className="portal-card mb-3">
        <div className="portal-card-body space-y-3">
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Updating a project changes only the contributor-form version it uses. Existing answers and history are
            preserved, but fields added in the newer form may remain blank until revisions are requested.
          </div>
          {notice && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
          {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
          <input
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPage(1); }}
            placeholder="Search by project title, contributor, or agency"
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
          />
          <MobileSortControls
            className="xl:hidden"
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
          <div className="portal-card-body text-slate-500">Loading projects with older forms...</div>
        ) : sortedProjects.length === 0 ? (
          <div className="portal-card-body text-slate-500">
            {query.trim() ? "No matching projects found." : "No projects are using an older contributor form."}
          </div>
        ) : (
          <>
          <div className="space-y-3 p-3 lg:hidden">
            {visibleProjects.map((project) => (
              <article key={`mobile-update-${project.id}`} className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                <h2 className="break-words font-semibold text-slate-900">{project.title || project.name || "Untitled project"}</h2>
                <div className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                  <p><span className="font-medium text-slate-800">Contributor:</span> {project.submitted_by_name || "Unknown"}</p>
                  <p><span className="font-medium text-slate-800">Agency:</span> {project.agency || "N/A"}</p>
                  <p><span className="font-medium text-slate-800">Current form:</span> Version {project.form_version ?? "-"}</p>
                  <p><span className="font-medium text-slate-800">Latest form:</span> Version {project.current_form_version ?? "-"}</p>
                </div>
                <button
                  type="button"
                  onClick={() => updateForm(project)}
                  disabled={updatingId !== null}
                  className="portal-btn portal-btn-primary mt-3 min-h-11 w-full disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {updatingId === project.id ? "Updating..." : "Update Form"}
                </button>
              </article>
            ))}
          </div>
          <div className="portal-table-wrap">
          <table className="portal-table hidden lg:table">
            <thead>
              <tr>
                <SortableTableHeader label="Project" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Contributor" sortKey="contributor" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Agency" sortKey="agency" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden lg:table-cell" />
                <SortableTableHeader label="Current Form" sortKey="current" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Latest Form" sortKey="latest" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden xl:table-cell" />
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {visibleProjects.map((project) => {
                const title = project.title || project.name || "Untitled project";
                return (
                  <tr key={project.id}>
                    <td className="max-w-[260px] truncate" title={title}>{title}</td>
                    <td className="max-w-[190px] truncate" title={project.submitted_by_name || "Unknown"}>
                      {project.submitted_by_name || "Unknown"}
                    </td>
                    <td className="hidden lg:table-cell max-w-[170px] truncate" title={project.agency || "N/A"}>
                      {project.agency || "N/A"}
                    </td>
                    <td>Version {project.form_version ?? "-"}</td>
                    <td>Version {project.current_form_version ?? "-"}</td>
                    <td className="hidden xl:table-cell">{statusLabel(project.status)}</td>
                    <td>
                      <button
                        type="button"
                        onClick={() => updateForm(project)}
                        disabled={updatingId !== null}
                        className="portal-btn portal-btn-primary whitespace-nowrap disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {updatingId === project.id ? "Updating..." : "Update Form"}
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

export default UpdateProjectForms;
