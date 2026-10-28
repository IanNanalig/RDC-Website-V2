import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import RefreshButton from "../../components/portal/RefreshButton";
import { userDisplayName } from "../../utils/userDisplayName";
import { useEncodingWindow, useProgressUpdateWindow } from "../../hooks/useEncodingWindow";
import { MobileSortControls, SortableTableHeader } from "../../components/portal/TableSortControls";
import { sortRows } from "../../utils/tableSort";
import type { SortDirection } from "../../utils/tableSort";

type ApiProject = {
  id: number;
  title?: string;
  name?: string;
  agency?: string;
  primary_agency?: { code?: string; name?: string } | null;
  collaborating_agencies?: Array<{ code?: string; name?: string }>;
  access_level?: "primary" | "collaborator" | "administrative" | "reviewer" | "";
  can_edit?: boolean;
  read_only_reason?: string;
  budget?: number;
  completion?: number;
  status?: string;
  workflow_status?: string;
  workflow_status_label?: string;
  official_priority?: string;
  official_priority_label?: string;
  validation_comment?: string;
  updated_at?: string;
  validated?: boolean;
  is_revision?: boolean;
  revision_id?: number;
  revision_number?: number;
  revision_state?: string;
  revision_type?: string;
  archive_title?: string;
  submitted_by_name?: string;
  submission_type?: string;
  rdip_status?: string;
  review_status?: string;
  reviewed_by_username?: string;
  validator_edited?: boolean;
  validator_edited_fields_count?: number;
  form_version?: number | null;
  current_form_version?: number | null;
  uses_outdated_form?: boolean;
  submitted_by?: {
    username?: string;
    email?: string;
    role?: string;
  };
  profile_data?: Record<string, unknown>;
};

type WorkflowFilter = "all" | "pending_validation" | "needs_revision" | "validated" | "priority" | "non_priority" | "rejected";
const PAGE_SIZE = 10;

type ProjectRevisionRow = {
  id: number;
  project: number;
  project_title?: string;
  project_agency?: string;
  revision_number?: number;
  revision_type?: string;
  state?: string;
  profile_data_snapshot?: Record<string, unknown>;
  budget?: number;
  submission_type?: string;
  changed_fields?: unknown[];
  created_by_name?: string;
  submitted_by_name?: string;
  updated_at?: string;
  form_version?: number | null;
  current_form_version?: number | null;
  uses_outdated_form?: boolean;
};
type BatchArchivePreviewRow = {
  id: number;
  title: string;
  agency: string;
  workflow_status: string;
  eligible: boolean;
  reason: string;
};

const projectListCache = new Map<string, ApiProject[]>();
const projectListRequests = new Map<string, Promise<ApiProject[]>>();

const statusLabel = (status?: string, workflowLabel?: string) => {
  if (workflowLabel) return workflowLabel;
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
  if (status === "needs_revision") return "bg-amber-100 text-amber-800";
  if (status === "pending_validation") return "bg-blue-100 text-blue-700";
  if (status === "validated") return "bg-emerald-100 text-emerald-700";
  if (status === "rejected") return "bg-rose-100 text-rose-700";
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
  if (!vr || typeof vr !== "object") {
    if (!p.review_status && !p.reviewed_by_username && !p.validator_edited) return null;
    return {
      review_status: p.review_status,
      reviewed_by_username: p.reviewed_by_username,
      edited: p.validator_edited,
      edited_fields_count: p.validator_edited_fields_count,
    };
  }
  return vr as Record<string, unknown>;
};

const reviewStateLabel = (p: ApiProject) => {
  if (p.is_revision) {
    const state = String(p.revision_state || "").toLowerCase();
    if (state === "draft") return "Draft";
    if (state === "submitted") return "Submitted";
    if (state === "validator_draft") return "Validator Draft";
    if (state === "reviewed") return "Needs Revision";
    if (state === "endorsed") return "Endorsed";
    if (state === "rejected") return "Rejected";
  }
  const vr = getValidatorReview(p);
  const status = String(vr?.review_status || "").toLowerCase();
  if (status === "draft") return "Draft";
  if (status === "reviewed") return "Needs Revision";
  if (status === "endorsed" || status === "validated") return "Endorsed";
  if (status === "rejected") return "Rejected";
  return "Not Reviewed";
};

const reviewStateBadge = (p: ApiProject) => {
  if (p.is_revision) {
    const state = String(p.revision_state || "").toLowerCase();
    if (state === "draft" || state === "submitted" || state === "validator_draft") return "bg-slate-100 text-slate-700";
    if (state === "reviewed") return "bg-violet-100 text-violet-700";
    if (state === "endorsed") return "bg-emerald-100 text-emerald-700";
    if (state === "rejected") return "bg-rose-100 text-rose-700";
  }
  const vr = getValidatorReview(p);
  const status = String(vr?.review_status || "").toLowerCase();
  if (status === "draft") return "bg-slate-100 text-slate-700";
  if (status === "reviewed") return "bg-violet-100 text-violet-700";
  if (status === "endorsed" || status === "validated") return "bg-emerald-100 text-emerald-700";
  if (status === "rejected") return "bg-rose-100 text-rose-700";
  return "bg-slate-100 text-slate-700";
};

const ProjectsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const archivedView = location.pathname === "/admin/archived";
  const projectsLoadId = useRef(0);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [archiveTarget, setArchiveTarget] = useState<ApiProject | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveError, setArchiveError] = useState("");
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<number>>(new Set());
  const [batchArchivePreview, setBatchArchivePreview] = useState<BatchArchivePreviewRow[] | null>(null);
  const [batchArchiveToken, setBatchArchiveToken] = useState("");
  const [batchArchiveBusy, setBatchArchiveBusy] = useState<"preview" | "archive" | "">("");
  const [batchArchiveNotice, setBatchArchiveNotice] = useState("");
  useEffect(() => {
    if (!archiveTarget) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !archiveBusy) setArchiveTarget(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [archiveTarget, archiveBusy]);

  const user = useMemo(() => {
    const userData = localStorage.getItem("user");
    return userData ? JSON.parse(userData) : null;
  }, []);
  const role = user?.role as "admin" | "validator" | "employee" | undefined;
  const encodingWindow = useEncodingWindow(role === "employee");
  const progressWindow = useProgressUpdateWindow(role === "employee");
  const canEncode = encodingWindow.can_encode;
  const encodeMessage = encodingWindow.message;
  const canProgressUpdate = progressWindow.can_encode;
  const progressMessage = progressWindow.message;

  const selectedWorkflow = (searchParams.get("workflow") || searchParams.get("status") || "all") as WorkflowFilter;

  const endpoint = useMemo(() => {
    const params = new URLSearchParams({ view: "summary" });
    if (selectedWorkflow && selectedWorkflow !== "all") params.set("workflow", selectedWorkflow);
    if (role === "admin") {
      if (archivedView) params.set("archived", "1");
      return `admin/projects/?${params.toString()}`;
    }
    if (role === "validator") {
      params.set("scope", "queue");
      return `validator/projects/?${params.toString()}`;
    }
    return `employee/projects/?${params.toString()}`;
  }, [role, selectedWorkflow, archivedView]);

  const projectCacheKey = `${role || "unknown"}:${user?.id || user?.email || "session"}:${endpoint}`;
  const [projects, setProjects] = useState<ApiProject[]>(() => projectListCache.get(projectCacheKey) || []);
  const [loading, setLoading] = useState(() => !projectListCache.has(projectCacheKey));
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");

  const loadProjects = useCallback(async (silent = false, force = false) => {
    const requestId = ++projectsLoadId.current;
    if (!silent) {
      setRefreshError("");
      setLoading(true);
      setRefreshing(true);
    }
    let request = force ? undefined : projectListRequests.get(projectCacheKey);
    if (!request) {
      request = (async () => {
        const shouldLoadRevisions = role === "validator" || (role === "admin" && !archivedView);
        const revisionParams = new URLSearchParams({ view: "summary" });
        if (role === "validator") revisionParams.set("scope", "queue");
        const [data, revisions] = await Promise.all([
          api.get(endpoint, force),
          shouldLoadRevisions
            ? api.get(`project-revisions/?${revisionParams.toString()}`, force)
            : Promise.resolve([]),
        ]);
        let rows: ApiProject[] = Array.isArray(data) ? data : [];
        if (Array.isArray(revisions)) {
          const projectsById = new Map(rows.map((project) => [project.id, project]));
          const revisionRows: ApiProject[] = revisions.map((r: ProjectRevisionRow) => {
            const project = projectsById.get(r.project);
            const projectTitle = project?.title || project?.name || r.project_title || "Project";
            return {
              id: r.project,
              revision_id: r.id,
              revision_number: r.revision_number,
              revision_state: r.state,
              revision_type: r.revision_type,
              is_revision: true,
              archive_title: projectTitle,
              title: `${r.project_title || "Project"} - Progress Update v${r.revision_number || ""}`,
              name: `${r.project_title || "Project"} - Progress Update v${r.revision_number || ""}`,
              agency: r.project_agency || "",
              budget: Number(r.budget ?? ((r.profile_data_snapshot as any)?.public_summary?.key_facts?.funding_requirement_total || 0)),
              status: r.state === "endorsed" ? "completed" : "proposed",
              rdip_status: project?.rdip_status,
              updated_at: r.updated_at,
              submitted_by_name: r.submitted_by_name || r.created_by_name || "Unknown",
              submission_type: r.submission_type,
              form_version: r.form_version,
              current_form_version: r.current_form_version,
              uses_outdated_form: r.uses_outdated_form,
              profile_data: r.profile_data_snapshot || (r.submission_type === "simplified" ? { submission_type: "simplified", simplified_form: {} } : {}),
            };
          });
          rows = [...revisionRows, ...rows];
        }
        return rows;
      })();
      projectListRequests.set(projectCacheKey, request);
    }
    try {
      const rows = await request;
      if (requestId !== projectsLoadId.current) return;
      projectListCache.set(projectCacheKey, rows);
      setProjects(rows);
    } catch (error) {
      console.error("Failed to load projects:", error);
      if (requestId === projectsLoadId.current && !silent) {
        setRefreshError("Could not refresh projects. Please try again.");
      }
      // Keep the current list visible if a background refresh temporarily fails.
      if (requestId === projectsLoadId.current && !projectListCache.has(projectCacheKey)) setProjects([]);
    } finally {
      if (projectListRequests.get(projectCacheKey) === request) projectListRequests.delete(projectCacheKey);
      if (requestId === projectsLoadId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [endpoint, role, archivedView, projectCacheKey]);

  useEffect(() => {
    if (!user) {
      navigate("/login");
      return;
    }
    const cachedRows = projectListCache.get(projectCacheKey);
    setProjects(cachedRows || []);
    setLoading(!cachedRows);
    setRefreshing(false);
    setRefreshError("");
    void loadProjects(true);
    const onStorage = (e: StorageEvent) => {
      if (e.key === "projects_last_update") void loadProjects(true, true);
    };
    const onDataChanged = (event: Event) => {
      const path = (event as CustomEvent<{ path?: string }>).detail?.path || "";
      if (path.includes("projects/") || path.includes("project-revisions/")) {
        void loadProjects(true, true);
      }
    };
    window.addEventListener("storage", onStorage);
    window.addEventListener("portal:data-changed", onDataChanged);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("portal:data-changed", onDataChanged);
    };
  }, [loadProjects, navigate, user, projectCacheKey]);

  const filtered = useMemo(() => {
    let list = projects;
    if (selectedWorkflow === "pending_validation") list = list.filter((p) => p.workflow_status === "pending_validation" || p.status === "proposed");
    else if (selectedWorkflow === "needs_revision") list = list.filter((p) => p.workflow_status === "needs_revision");
    else if (selectedWorkflow === "validated") list = list.filter((p) => p.workflow_status === "validated" || p.status === "completed");
    else if (selectedWorkflow === "rejected") list = list.filter((p) => p.workflow_status === "rejected");
    else if (selectedWorkflow === "priority") list = list.filter((p) => p.official_priority_label === "Priority");
    else if (selectedWorkflow === "non_priority") list = list.filter((p) => p.official_priority_label === "Non-Priority");

    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((p) => `${p.title || p.name || ""} ${p.agency || ""} ${(p.collaborating_agencies || []).map((agency) => `${agency.code || ""} ${agency.name || ""}`).join(" ")}`.toLowerCase().includes(q));
  }, [projects, selectedWorkflow, query]);
  const sortOptions = useMemo(() => [
    { key: "title", label: "Title" },
    { key: "contributor", label: "Contributor" },
    { key: "agency", label: "Agency" },
    { key: "budget", label: "Budget" },
    { key: "status", label: "Status" },
    { key: "priority", label: "Priority" },
    { key: "review", label: "Review State" },
    { key: "updated", label: "Updated" },
  ].filter((option) => {
    if (option.key === "review") return role === "admin" || role === "validator";
    return option.key !== "contributor" || role === "admin" || role === "validator" || role === "employee";
  }), [role]);
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
      case "status": return statusLabel(project.status, project.workflow_status_label);
      case "priority": return project.official_priority_label || "";
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
  // Revision rows still represent the same underlying project and can be
  // archived through the project-level archive endpoint. Keep every row
  // selectable, while de-duplicating IDs for the batch payload and counts.
  const selectableProjects = useMemo(
    () => Array.from(new Map(sortedProjects.map((project) => [project.id, project])).values()),
    [sortedProjects],
  );
  const selectableVisibleProjects = useMemo(
    () => Array.from(new Map(visibleProjects.map((project) => [project.id, project])).values()),
    [visibleProjects],
  );
  const allPageSelected = selectableVisibleProjects.length > 0 && selectableVisibleProjects.every((project) => selectedProjectIds.has(project.id));
  const allMatchingSelected = selectableProjects.length > 0 && selectableProjects.every((project) => selectedProjectIds.has(project.id));

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  useEffect(() => {
    setPage(1);
  }, [selectedWorkflow]);

  const handleSubmit = async (id: number) => {
    if (role === "employee" && !canEncode) return;
    await api.post(`employee/projects/${id}/submit/`);
    await loadProjects();
    localStorage.setItem("projects_last_update", Date.now().toString());
  };

  const handleArchive = async () => {
    if (!archiveTarget || archiveBusy) return;
    setArchiveBusy(true);
    setArchiveError("");
    try {
      await api.post(`admin/projects/${archiveTarget.id}/archive/`, {
        confirm_archive: true,
        expected_implementation_status: formStatus(archiveTarget),
      });
      setArchiveTarget(null);
      await loadProjects();
      localStorage.setItem("projects_last_update", Date.now().toString());
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : "Could not archive project. Refresh and try again.");
    } finally {
      setArchiveBusy(false);
    }
  };

  const handleRestore = async (id: number) => {
    await api.post(`admin/projects/${id}/unarchive/`, {});
    await loadProjects();
    localStorage.setItem("projects_last_update", Date.now().toString());
  };

  const toggleProjectSelection = (id: number) => setSelectedProjectIds((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const togglePageSelection = () => setSelectedProjectIds((current) => {
    const next = new Set(current);
    selectableVisibleProjects.forEach((project) => allPageSelected ? next.delete(project.id) : next.add(project.id));
    return next;
  });

  const selectAllMatching = () => setSelectedProjectIds((current) => {
    const next = new Set(current);
    selectableProjects.forEach((project) => allMatchingSelected ? next.delete(project.id) : next.add(project.id));
    return next;
  });

  const previewBatchArchive = async () => {
    if (!selectedProjectIds.size) return;
    setBatchArchiveBusy("preview");
    setArchiveError("");
    setBatchArchiveNotice("");
    try {
      const data = await api.post("admin/projects/batch-archive-preview/", { project_ids: [...selectedProjectIds] });
      setBatchArchivePreview(Array.isArray(data?.rows) ? data.rows : []);
      setBatchArchiveToken(String(data?.preview_token || ""));
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : "Could not preview the archive selection.");
    } finally {
      setBatchArchiveBusy("");
    }
  };

  const confirmBatchArchive = async () => {
    if (!batchArchiveToken || batchArchiveBusy) return;
    setBatchArchiveBusy("archive");
    try {
      const data = await api.post("admin/projects/batch-archive/", { preview_token: batchArchiveToken });
      setBatchArchiveNotice(`${Number(data?.archived || 0)} project(s) archived, ${Number(data?.skipped || 0)} skipped, and ${Number(data?.failed || 0)} failed.`);
      setBatchArchivePreview(null);
      setBatchArchiveToken("");
      setSelectedProjectIds(new Set());
      await loadProjects(false, true);
    } catch (error) {
      setArchiveError(error instanceof Error ? error.message : "Could not archive the selected projects.");
    } finally {
      setBatchArchiveBusy("");
    }
  };

  const formStatus = (p: ApiProject) => {
    const pd = p.profile_data as Record<string, any> | undefined;
    const sf = pd?.simplified_form as Record<string, any> | undefined;
    return String(p.rdip_status || sf?.status || "").trim();
  };

  const canStartProgressUpdate = (p: ApiProject) =>
    role === "employee" &&
    p.access_level !== "collaborator" &&
    p.can_edit !== false &&
    !p.is_revision &&
    Boolean(p.validated) &&
    formStatus(p).toLowerCase() !== "completed";

  const canEditProject = (p: ApiProject) =>
    role === "employee" &&
    p.access_level !== "collaborator" &&
    p.can_edit !== false &&
    !p.is_revision &&
    (p.status === "planning" || p.workflow_status === "needs_revision") &&
    (canEncode || p.workflow_status === "needs_revision");

  const canSubmitProject = (p: ApiProject) =>
    role === "employee" &&
    p.access_level !== "collaborator" &&
    p.can_edit !== false &&
    !p.is_revision &&
    canEncode &&
    p.status === "planning";

  const editPath = (p: ApiProject) => `/employee/projects/${p.id}/edit/simplified`;

  const validatorReviewPath = (p: ApiProject) => {
    const path = `/validator/projects/${p.id}/review/simplified`;
    return p.is_revision && p.revision_id
      ? `${path}?revision=${encodeURIComponent(p.revision_id)}`
      : path;
  };

  const setWorkflowFilter = (value: WorkflowFilter) => {
    setPage(1);
    const next = new URLSearchParams(searchParams);
    next.delete("status");
    if (value === "all") next.delete("workflow");
    else next.set("workflow", value);
    setSearchParams(next);
  };

  const handleStartProgressUpdate = async (p: ApiProject) => {
    if (!canProgressUpdate) {
      alert(progressMessage || "Project progress updates are currently closed.");
      return;
    }
    try {
      const revision = await api.post(`employee/projects/${p.id}/start-update/`, {});
      if (revision?.id) {
        navigate(`${editPath(p)}?revision=${revision.id}`);
      }
    } catch (error) {
      console.error("Failed to start progress update:", error);
      const detail = error instanceof Error ? error.message : "";
      alert(detail || "Failed to start progress update.");
    }
  };

  if (!user) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  const displayName = userDisplayName(user);

  const title = archivedView ? "Archived Projects" : role === "admin" ? "Projects Governance" : role === "validator" ? "Validation Queue" : "My Projects";
  const subtitle =
    role === "admin"
      ? "Review all portal submissions, archive, and manage records"
      : role === "validator"
      ? "Process pending submissions and maintain review quality"
      : "Create, submit, view, and print your project records";

  return (
    <PortalLayout
      title={title}
      subtitle={subtitle}
      role={role || "employee"}
      userName={displayName}
      topActions={
        <>
          {role === "admin" && <Link to={archivedView ? "/admin/projects" : "/admin/archived"} className="portal-btn portal-btn-ghost">{archivedView ? "Active Projects" : "Archived"}</Link>}
          {role === "employee" && (
            <Link
              to={canEncode ? "/employee/projects/new" : "#"}
              onClick={(e) => !canEncode && e.preventDefault()}
              className={`portal-btn ${canEncode ? "portal-btn-primary" : "portal-btn-ghost opacity-70 cursor-not-allowed"}`}
            >
              + New Project
            </Link>
          )}
          <RefreshButton loading={refreshing} onClick={() => loadProjects(false, true)} />
        </>
      }
    >
      {role === "employee" && !canEncode && (
        <div className="portal-card p-3 mb-3 border-amber-200 bg-amber-50 text-amber-800">
          {encodeMessage || "Contributor encoding is currently closed. You may still view projects and post comments."}
        </div>
      )}

      <div className="portal-card mb-3">
        <div className="portal-card-body grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }}
            placeholder={role === "employee" ? "Search by project title" : "Search by project title or agency"}
            className="w-full border border-slate-200 rounded-xl px-3 py-2 bg-white"
          />
          <select
            value={selectedWorkflow}
            onChange={(event) => setWorkflowFilter(event.target.value as WorkflowFilter)}
            className="w-full border border-slate-200 rounded-xl px-3 py-2 bg-white"
          >
            <option value="all">All</option>
            <option value="pending_validation">Pending Validation</option>
            <option value="needs_revision">Needs Revision</option>
            <option value="validated">Validated</option>
            <option value="priority">Priority</option>
            <option value="non_priority">Non-Priority</option>
            <option value="rejected">Rejected</option>
          </select>
          <MobileSortControls
            className="lg:col-span-2 2xl:hidden"
            options={sortOptions}
            sortKey={sortKey}
            direction={sortDirection}
            onSortKeyChange={changeSort}
            onToggleDirection={toggleSortDirection}
          />
        </div>
      </div>

      {refreshError && (
        <p role="alert" className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {refreshError}
        </p>
      )}
      {batchArchiveNotice && role === "admin" && !archivedView && (
        <p className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{batchArchiveNotice}</p>
      )}
      {role === "admin" && !archivedView && (
        <div className="portal-card mb-3">
          <div className="portal-card-body flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <label className="flex items-center gap-2"><input type="checkbox" checked={allPageSelected} onChange={togglePageSelection} /> Select current page</label>
              <button type="button" onClick={selectAllMatching} className="font-medium text-blue-700 hover:underline">{allMatchingSelected ? "Clear all matching" : `Select all ${selectableProjects.length} matching projects`}</button>
              <span className="text-slate-600">{selectedProjectIds.size} selected</span>
            </div>
            <button type="button" disabled={!selectedProjectIds.size || Boolean(batchArchiveBusy)} onClick={previewBatchArchive} className="portal-btn portal-btn-ghost disabled:cursor-not-allowed disabled:opacity-50">{batchArchiveBusy === "preview" ? "Checking..." : "Archive Selected"}</button>
          </div>
        </div>
      )}

      <div className="portal-card">
        {loading ? (
          <div className="portal-card-body text-slate-500">Loading projects...</div>
        ) : sortedProjects.length === 0 ? (
          <div className="portal-card-body text-slate-500">No projects found.</div>
        ) : (
          <>
          {role === "validator" && (
            <div className="space-y-3 p-3 lg:hidden">
              {visibleProjects.map((p) => (
                <article
                  key={p.is_revision ? `mobile-revision-${p.revision_id}` : `mobile-project-${p.id}`}
                  className="min-w-0 rounded-xl border border-slate-200 bg-white p-3 shadow-sm"
                >
                  <h2 className="break-words font-semibold text-slate-900">{p.title || p.name || "Untitled"}</h2>
                  {p.uses_outdated_form && (
                    <p className="mt-1 text-xs font-semibold text-amber-700">Uses an older form — may need updating</p>
                  )}
                  <div className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                    <p><span className="font-medium text-slate-800">Contributor:</span> {p.submitted_by_name || p.submitted_by?.username || "Unknown"}</p>
                    <p><span className="font-medium text-slate-800">Agency:</span> {p.agency || "N/A"}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusBadge(p.workflow_status || p.status)}`}>
                      {statusLabel(p.status, p.workflow_status_label)}
                    </span>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${reviewStateBadge(p)}`}>
                      {reviewStateLabel(p)}
                    </span>
                    {p.official_priority_label && (
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{p.official_priority_label}</span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate(validatorReviewPath(p))}
                    className="portal-btn portal-btn-primary mt-3 min-h-11 w-full"
                  >
                    Review
                  </button>
                </article>
              ))}
            </div>
          )}
          <div className="portal-table-wrap">
          <table className={`portal-table ${role === "validator" ? "hidden lg:table" : ""}`}>
            <thead>
              <tr>
                {role === "admin" && !archivedView && <th><span className="sr-only">Select</span></th>}
                <SortableTableHeader label="Title" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                {(role === "admin" || role === "validator" || role === "employee") && (
                  <SortableTableHeader label="Contributor" sortKey="contributor" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="min-w-[160px]" />
                )}
                <SortableTableHeader label="Agency" sortKey="agency" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden lg:table-cell" />
                <SortableTableHeader label="Budget" sortKey="budget" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden xl:table-cell" />
                <SortableTableHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={changeSort} />
                <SortableTableHeader label="Priority" sortKey="priority" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden xl:table-cell" />
                {(role === "admin" || role === "validator") && <SortableTableHeader label="Review State" sortKey="review" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden xl:table-cell" />}
                <SortableTableHeader label="Updated" sortKey="updated" activeKey={sortKey} direction={sortDirection} onSort={changeSort} className="hidden 2xl:table-cell" />
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleProjects.map((p) => (
                <tr key={p.is_revision ? `revision-${p.revision_id}` : `project-${p.id}`}>
                  {role === "admin" && !archivedView && (
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Select ${p.title || p.name || "project"}`}
                        checked={selectedProjectIds.has(p.id)}
                        onChange={() => toggleProjectSelection(p.id)}
                      />
                    </td>
                  )}
                  <td className="max-w-[240px]" title={p.title || p.name || "Untitled"}>
                    <div className="truncate">{p.title || p.name || "Untitled"}</div>
                    {p.access_level === "collaborator" && (
                      <div className="mt-1 text-xs font-semibold text-cyan-700" title={p.read_only_reason || "Read-only collaborating agency access"}>Collaborating agency · Read only</div>
                    )}
                    {p.uses_outdated_form && (
                      <div
                        className="mt-1 text-xs font-semibold text-amber-700"
                        title={`Saved with form version ${p.form_version}; current form version is ${p.current_form_version}.`}
                      >
                        Uses an older form — may need updating
                      </div>
                    )}
                  </td>
                  {(role === "admin" || role === "validator" || role === "employee") && (
                    <td className="max-w-[180px] truncate" title={p.submitted_by_name || p.submitted_by?.username || "Unknown"}>
                      {p.submitted_by_name || p.submitted_by?.username || "Unknown"}
                    </td>
                  )}
                  <td className="hidden lg:table-cell max-w-[170px] truncate" title={p.agency || "N/A"}>{p.agency || "N/A"}</td>
                  <td className="hidden xl:table-cell">PHP {(p.budget || 0).toLocaleString()}</td>
                  <td>
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${statusBadge(p.workflow_status || p.status)}`}>{statusLabel(p.status, p.workflow_status_label)}</span>
                  </td>
                  <td className="hidden xl:table-cell">{p.official_priority_label || "-"}</td>
                  {(role === "admin" || role === "validator") && (
                    <td className="hidden xl:table-cell">
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${reviewStateBadge(p)}`}>
                        {reviewStateLabel(p)}
                      </span>
                    </td>
                  )}
                  <td className="hidden 2xl:table-cell">{p.updated_at ? new Date(p.updated_at).toLocaleString() : "-"}</td>
                  <td className="min-w-[150px]">
                    <div className="flex flex-wrap gap-x-2 gap-y-1 text-[13px]">
                    {role === "employee" && (
                      <>
                        <button onClick={() => navigate(`/employee/projects/${p.id}/view`)} className="text-blue-700 hover:underline whitespace-nowrap">View</button>
                        {!p.is_revision && (p.status === "planning" || p.workflow_status === "needs_revision") && (
                          <button
                            disabled={!canEditProject(p)}
                            onClick={() => navigate(editPath(p))}
                            className={`whitespace-nowrap ${canEditProject(p) ? "text-blue-600 hover:underline" : "text-slate-400 cursor-not-allowed"}`}
                          >
                            {p.workflow_status === "needs_revision" ? "Revise" : "Edit"}
                          </button>
                        )}
                        {!p.is_revision && p.status === "planning" && (
                          <button
                            disabled={!canSubmitProject(p)}
                            onClick={() => handleSubmit(p.id)}
                            className={`whitespace-nowrap ${canSubmitProject(p) ? "text-indigo-600 hover:underline" : "text-slate-400 cursor-not-allowed"}`}
                          >
                            Submit
                          </button>
                        )}
                        {canStartProgressUpdate(p) && (
                          <button
                            disabled={!canProgressUpdate}
                            onClick={() => handleStartProgressUpdate(p)}
                            className={`whitespace-nowrap ${canProgressUpdate ? "text-emerald-700 hover:underline" : "text-slate-400 cursor-not-allowed"}`}
                          >
                            Update
                          </button>
                        )}
                      </>
                    )}
                    {role === "validator" && (
                      <>
                        <button
                          onClick={() => navigate(validatorReviewPath(p))}
                          className="text-blue-600 hover:underline whitespace-nowrap"
                        >
                          Review
                        </button>
                      </>
                    )}
                    {role === "admin" && (
                      <>
                        <button
                          onClick={() =>
                            navigate(
                              p.is_revision && p.revision_id
                                ? `/admin/projects/${p.id}/view/simplified?revision=${p.revision_id}`
                                : `/admin/projects/${p.id}/view/simplified`,
                            )
                          }
                          className="text-blue-600 hover:underline whitespace-nowrap"
                        >
                          View
                        </button>
                        {archivedView ? (
                          <button onClick={() => handleRestore(p.id)} className="text-emerald-700 hover:underline whitespace-nowrap">Restore</button>
                        ) : (
                          <button onClick={() => { setArchiveTarget(p); setArchiveError(""); }} className="text-amber-700 hover:underline whitespace-nowrap">Archive</button>
                        )}
                      </>
                    )}
                    </div>
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
      {archiveTarget && (() => {
        const status = formStatus(archiveTarget);
        const neutral = ["completed", "not implemented"].includes(status.toLowerCase());
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !archiveBusy) setArchiveTarget(null); }}>
            <div role="alertdialog" aria-modal="true" aria-labelledby="archive-title" aria-describedby="archive-description" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
              <h2 id="archive-title" className="text-lg font-semibold text-slate-900">Archive {archiveTarget.archive_title || archiveTarget.title || archiveTarget.name || "this project"}?</h2>
              <p id="archive-description" className="mt-3 text-sm text-slate-700">{neutral
                ? `This project is ${status}. It will be moved to the Archived tab and can be restored later.`
                : `Current status: ${status || "Not specified"}. This project is still ongoing. Archiving it will remove it from active lists. It can be restored later.`}</p>
              {archiveError && <p role="alert" className="mt-3 text-sm text-rose-700">{archiveError}</p>}
              <div className="mt-6 flex justify-end gap-2">
                <button type="button" autoFocus disabled={archiveBusy} onClick={() => setArchiveTarget(null)} className="portal-btn portal-btn-ghost">Cancel</button>
                <button type="button" disabled={archiveBusy} onClick={handleArchive} className={`portal-btn ${neutral ? "portal-btn-primary" : "bg-rose-700 text-white hover:bg-rose-800"}`}>{archiveBusy ? "Archiving..." : "Confirm Archive"}</button>
              </div>
            </div>
          </div>
        );
      })()}
      {batchArchivePreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !batchArchiveBusy) setBatchArchivePreview(null); }}>
          <div role="alertdialog" aria-modal="true" aria-labelledby="batch-archive-title" className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-2xl bg-white p-6 shadow-2xl">
            <h2 id="batch-archive-title" className="text-lg font-semibold text-slate-900">Archive selected projects?</h2>
            <p className="mt-2 text-sm text-slate-600">{batchArchivePreview.filter((row) => row.eligible).length} project(s) are eligible. Ineligible projects will be skipped and remain active.</p>
            <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200"><table className="portal-table min-w-[640px]"><thead><tr><th>Project</th><th>Agency</th><th>Result</th></tr></thead><tbody>{batchArchivePreview.map((row) => <tr key={row.id}><td>{row.title}</td><td>{row.agency || "—"}</td><td><span className={`rounded-full px-2 py-1 text-xs font-semibold ${row.eligible ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{row.eligible ? "Will archive" : "Will skip"}</span>{row.reason && <p className="mt-1 text-xs text-slate-600">{row.reason}</p>}</td></tr>)}</tbody></table></div>
            {archiveError && <p role="alert" className="mt-3 text-sm text-rose-700">{archiveError}</p>}
            <div className="mt-6 flex justify-end gap-2"><button type="button" disabled={Boolean(batchArchiveBusy)} onClick={() => setBatchArchivePreview(null)} className="portal-btn portal-btn-ghost">Cancel</button><button type="button" disabled={Boolean(batchArchiveBusy) || !batchArchivePreview.some((row) => row.eligible)} onClick={confirmBatchArchive} className="portal-btn portal-btn-primary disabled:opacity-50">{batchArchiveBusy === "archive" ? "Archiving..." : "Confirm Batch Archive"}</button></div>
          </div>
        </div>
      )}
    </PortalLayout>
  );
};

export default ProjectsPage;
