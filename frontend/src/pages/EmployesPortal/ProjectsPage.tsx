import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import { useEncodingWindow, useProgressUpdateWindow } from "../../hooks/useEncodingWindow";

type ApiProject = {
  id: number;
  title?: string;
  name?: string;
  agency?: string;
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
  submitted_by_name?: string;
  submitted_by?: {
    username?: string;
    email?: string;
    role?: string;
  };
  profile_data?: Record<string, unknown>;
};

type WorkflowFilter = "all" | "pending_validation" | "needs_revision" | "validated" | "priority" | "non_priority" | "rejected";

type ProjectRevisionRow = {
  id: number;
  project: number;
  project_title?: string;
  project_agency?: string;
  revision_number?: number;
  revision_type?: string;
  state?: string;
  profile_data_snapshot?: Record<string, unknown>;
  changed_fields?: unknown[];
  created_by_name?: string;
  submitted_by_name?: string;
  updated_at?: string;
};

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
  if (!vr || typeof vr !== "object") return null;
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
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

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
    const workflowParam = selectedWorkflow && selectedWorkflow !== "all" ? `workflow=${encodeURIComponent(selectedWorkflow)}` : "";
    if (role === "admin") {
      return `admin/projects/${workflowParam ? `?${workflowParam}` : ""}`;
    }
    if (role === "validator") {
      return `validator/projects/?scope=queue${workflowParam ? `&${workflowParam}` : ""}`;
    }
    return `employee/projects/${workflowParam ? `?${workflowParam}` : ""}`;
  }, [role, selectedWorkflow]);

  const loadProjects = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get(endpoint);
      let rows: ApiProject[] = Array.isArray(data) ? data : [];
      if (role === "validator" || role === "admin") {
        const revisions = await api.get(`project-revisions/${role === "validator" ? "?scope=queue" : ""}`);
        if (Array.isArray(revisions)) {
          const revisionRows: ApiProject[] = revisions.map((r: ProjectRevisionRow) => ({
            id: r.project,
            revision_id: r.id,
            revision_number: r.revision_number,
            revision_state: r.state,
            revision_type: r.revision_type,
            is_revision: true,
            title: `${r.project_title || "Project"} - Progress Update v${r.revision_number || ""}`,
            name: `${r.project_title || "Project"} - Progress Update v${r.revision_number || ""}`,
            agency: r.project_agency || "",
            budget: Number((r.profile_data_snapshot as any)?.public_summary?.key_facts?.funding_requirement_total || 0),
            status: r.state === "endorsed" ? "completed" : "proposed",
            updated_at: r.updated_at,
            submitted_by_name: r.submitted_by_name || r.created_by_name || "Unknown",
            profile_data: r.profile_data_snapshot || {},
          }));
          rows = [...revisionRows, ...rows];
        }
      }
      setProjects(rows);
    } catch (error) {
      console.error("Failed to load projects:", error);
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, [endpoint, role]);

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
    let list = projects;
    if (selectedWorkflow === "pending_validation") list = list.filter((p) => p.workflow_status === "pending_validation" || p.status === "proposed");
    else if (selectedWorkflow === "needs_revision") list = list.filter((p) => p.workflow_status === "needs_revision");
    else if (selectedWorkflow === "validated") list = list.filter((p) => p.workflow_status === "validated" || p.status === "completed");
    else if (selectedWorkflow === "rejected") list = list.filter((p) => p.workflow_status === "rejected");
    else if (selectedWorkflow === "priority") list = list.filter((p) => p.official_priority_label === "Priority");
    else if (selectedWorkflow === "non_priority") list = list.filter((p) => p.official_priority_label === "Non-Priority");

    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((p) => `${p.title || p.name || ""} ${p.agency || ""}`.toLowerCase().includes(q));
  }, [projects, selectedWorkflow, query]);

  const handleSubmit = async (id: number) => {
    if (role === "employee" && !canEncode) return;
    await api.post(`employee/projects/${id}/submit/`);
    await loadProjects();
    localStorage.setItem("projects_last_update", Date.now().toString());
  };

  const handleArchive = async (id: number) => {
    await api.post(`admin/projects/${id}/archive/`);
    await loadProjects();
    localStorage.setItem("projects_last_update", Date.now().toString());
  };

  const formStatus = (p: ApiProject) => {
    const pd = p.profile_data as Record<string, any> | undefined;
    const sf = pd?.simplified_form as Record<string, any> | undefined;
    return String(sf?.status || "").trim();
  };

  const canStartProgressUpdate = (p: ApiProject) =>
    role === "employee" &&
    !p.is_revision &&
    Boolean(p.validated) &&
    formStatus(p).toLowerCase() !== "completed";

  const canEditProject = (p: ApiProject) =>
    role === "employee" &&
    !p.is_revision &&
    (p.status === "planning" || p.workflow_status === "needs_revision") &&
    (canEncode || p.workflow_status === "needs_revision");

  const canSubmitProject = (p: ApiProject) =>
    role === "employee" &&
    !p.is_revision &&
    ((canEncode && p.status === "planning") || p.workflow_status === "needs_revision");

  const editPath = (p: ApiProject) => {
    const pd = p.profile_data as Record<string, any> | undefined;
    return pd?.simplified_form ? `/employee/projects/${p.id}/edit/simplified` : `/employee/projects/${p.id}/edit`;
  };

  const setWorkflowFilter = (value: WorkflowFilter) => {
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
        navigate(`/employee/projects/${p.id}/edit?revision=${revision.id}`);
      }
    } catch (error) {
      console.error("Failed to start progress update:", error);
      const detail = error instanceof Error ? error.message : "";
      alert(detail || "Failed to start progress update.");
    }
  };

  if (!user) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  const displayName = user?.full_name || user?.username || "User";

  const title = role === "admin" ? "Projects Governance" : role === "validator" ? "Validation Queue" : "My Projects";
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
          {role === "employee" && (
            <Link
              to={canEncode ? "/employee/projects/new" : "#"}
              onClick={(e) => !canEncode && e.preventDefault()}
              className={`portal-btn ${canEncode ? "portal-btn-primary" : "portal-btn-ghost opacity-70 cursor-not-allowed"}`}
            >
              + New Project
            </Link>
          )}
          <button onClick={loadProjects} className="portal-btn portal-btn-ghost">Refresh</button>
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
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by project title or agency"
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
        </div>
      </div>

      <div className="portal-card portal-table-wrap">
        {loading ? (
          <div className="portal-card-body text-slate-500">Loading projects...</div>
        ) : filtered.length === 0 ? (
          <div className="portal-card-body text-slate-500">No projects found.</div>
        ) : (
          <table className="portal-table">
            <thead>
              <tr>
                <th>Title</th>
                {(role === "admin" || role === "validator" || role === "employee") && (
                  <th className="min-w-[160px]">Contributor</th>
                )}
                <th className="hidden lg:table-cell">Agency</th>
                <th className="hidden xl:table-cell">Budget</th>
                <th>Status</th>
                <th className="hidden xl:table-cell">Priority</th>
                {(role === "admin" || role === "validator") && <th className="hidden xl:table-cell">Review State</th>}
                <th className="hidden 2xl:table-cell">Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.is_revision ? `revision-${p.revision_id}` : `project-${p.id}`}>
                  <td className="max-w-[220px] truncate" title={p.title || p.name || "Untitled"}>{p.title || p.name || "Untitled"}</td>
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
                        <button
                          disabled={!canEditProject(p)}
                          onClick={() => navigate(editPath(p))}
                          className={`whitespace-nowrap ${canEditProject(p) ? "text-blue-600 hover:underline" : "text-slate-400 cursor-not-allowed"}`}
                        >
                          {p.workflow_status === "needs_revision" ? "Revise" : "Edit"}
                        </button>
                        <button
                          disabled={!canSubmitProject(p)}
                          onClick={() => handleSubmit(p.id)}
                          className={`whitespace-nowrap ${canSubmitProject(p) ? "text-indigo-600 hover:underline" : "text-slate-400 cursor-not-allowed"}`}
                        >
                          {p.workflow_status === "needs_revision" ? "Resubmit" : "Submit"}
                        </button>
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
                          onClick={() =>
                            navigate(
                              p.is_revision && p.revision_id
                                ? `/validator/projects/${p.id}/review?revision=${p.revision_id}`
                                : `/validator/projects/${p.id}/review`,
                            )
                          }
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
                                ? `/admin/projects/${p.id}/view?revision=${p.revision_id}`
                                : `/admin/projects/${p.id}/view`,
                            )
                          }
                          className="text-blue-600 hover:underline whitespace-nowrap"
                        >
                          View
                        </button>
                        <button onClick={() => handleArchive(p.id)} className="text-amber-700 hover:underline whitespace-nowrap">Archive</button>
                      </>
                    )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PortalLayout>
  );
};

export default ProjectsPage;
