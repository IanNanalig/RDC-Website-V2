import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PortalLayout from "../../components/portal/PortalLayout";
import { api } from "../../services/api";

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
      userName={user.full_name || user.username || "Validator"}
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
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by project title, contributor, or agency"
            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2"
          />
        </div>
      </div>

      <div className="portal-card portal-table-wrap">
        {loading ? (
          <div className="portal-card-body text-slate-500">Loading projects with older forms...</div>
        ) : filteredProjects.length === 0 ? (
          <div className="portal-card-body text-slate-500">
            {query.trim() ? "No matching projects found." : "No projects are using an older contributor form."}
          </div>
        ) : (
          <table className="portal-table">
            <thead>
              <tr>
                <th>Project</th>
                <th>Contributor</th>
                <th className="hidden lg:table-cell">Agency</th>
                <th>Current Form</th>
                <th>Latest Form</th>
                <th className="hidden xl:table-cell">Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map((project) => {
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
        )}
      </div>
    </PortalLayout>
  );
};

export default UpdateProjectForms;
