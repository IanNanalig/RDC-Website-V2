import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface DashboardStats {
  my_projects?: number;
  draft_projects?: number;
  submitted_projects?: number;
  approved_projects?: number;
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<any>(null);
  const [stats, setStats] = useState<DashboardStats>({});
  const [loading, setLoading] = useState(true);
  const [activity, setActivity] = useState<any[]>([]);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activityLimit, setActivityLimit] = useState("10");
  const [activityModal, setActivityModal] = useState<{
    open: boolean;
    title: string;
    changes: Array<{ field: string; before: string; after: string }>;
    editor: string;
    at: string;
    comment: string;
    commentAt: string;
    loadingComment: boolean;
  }>({ open: false, title: "", changes: [], editor: "", at: "", comment: "", commentAt: "", loadingComment: false });

  const simplifiedFieldLabels: Record<string, string> = {
    agencyName: "Agency Name",
    program: "Program",
    projectActivity: "Project/Activity",
    location: "Location",
    description: "Description",
    objective: "Objective",
    startYear: "Start Year",
    endYear: "End Year",
    fundingSource: "Funding Source",
    uacsCode: "UACS Code (if GAA-funded)",
    rdcEndorsed: "RDC-NCR Endorsed",
    pipIncluded: "PIP Included",
    arnipapIncluded: "ARNIPAP Included",
    ludipIncluded: "LUDIP (for SUCs)",
    ifpsIncluded: "IFPs Included",
    pcbIncluded: "Part of the Convergence Program (PCB)",
    pcbProgram: "Convergence Program (PCB)",
    developmentSector: "RDC-NCR Development Sector",
    rdpMainChapter: "RDP-NCR Main Chapter",
    sdgSelections: "Sustainable Development Goals",
    status: "Status",
    physicalAccomplishment: "Physical Accomplishment",
    financialAccomplishment: "Financial Accomplishment",
    remarks: "Remarks",
  };

  const formatChangedFieldLabel = (field: string) => {
    if (!field) return "Field";
    if (field.startsWith("fundingRequirementByYear.")) {
      const key = field.split(".")[1] || "";
      return `Funding Requirement (PHP) ${key === "2022_prior" ? "2022 & Prior" : key}`;
    }
    if (field.startsWith("actualFundingByYear.")) {
      const key = field.split(".")[1] || "";
      return `Actual/Approved Funding (PHP) ${key === "2022_prior" ? "2022 & Prior" : key}`;
    }
    if (simplifiedFieldLabels[field]) return simplifiedFieldLabels[field];
    const base = field.includes(".") ? field.split(".")[0] : field;
    if (simplifiedFieldLabels[base]) return simplifiedFieldLabels[base];
    return base
      .replace(/_/g, " ")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/\s+/g, " ")
      .trim();
  };

  const openChangesModal = async (item: any) => {
    const changesRaw = item?.details?.changes;
    const changes = Array.isArray(changesRaw)
      ? changesRaw
          .map((c) => ({
            field: String(c?.field || ""),
            before: String(c?.before ?? ""),
            after: String(c?.after ?? ""),
          }))
          .filter((c) => c.field)
      : [];
    const editorUsername = String(item?.username || "");
    const activityTime = item?.created_at ? new Date(item.created_at).getTime() : 0;

    setActivityModal({
      open: true,
      title: item?.project_title ? `Changes: ${item.project_title}` : "Changes",
      changes,
      editor: String(item?.full_name || item?.username || "User"),
      at: item?.created_at ? new Date(item.created_at).toLocaleString() : "",
      comment: "",
      commentAt: "",
      loadingComment: true,
    });

    const projectId = item?.project;
    if (!projectId) {
      setActivityModal((prev) => ({ ...prev, loadingComment: false }));
      return;
    }

    try {
      const comments = await api.get(`employee/projects/${projectId}/comments/`);
      const list = Array.isArray(comments) ? comments : [];
      const parsed = list
        .map((c: any) => ({
          comment: String(c?.comment || ""),
          username: String(c?.username || ""),
          full_name: String(c?.full_name || ""),
          created_at: String(c?.created_at || ""),
          created_ms: c?.created_at ? new Date(c.created_at).getTime() : 0,
        }))
        .filter((c) => c.comment);

      let best = null as null | typeof parsed[number];
      const bySameUser = editorUsername ? parsed.filter((c) => c.username === editorUsername) : [];
      const inWindow = activityTime
        ? bySameUser.filter((c) => Math.abs(c.created_ms - activityTime) <= 15 * 60 * 1000)
        : [];
      if (inWindow.length > 0) {
        best = inWindow.sort((a, b) => Math.abs(a.created_ms - activityTime) - Math.abs(b.created_ms - activityTime))[0];
      } else if (bySameUser.length > 0) {
        best = bySameUser.sort((a, b) => b.created_ms - a.created_ms)[0];
      } else if (parsed.length > 0) {
        best = parsed.sort((a, b) => b.created_ms - a.created_ms)[0];
      }

      setActivityModal((prev) => ({
        ...prev,
        comment: best?.comment || "",
        commentAt: best?.created_at ? new Date(best.created_at).toLocaleString() : "",
        loadingComment: false,
      }));
    } catch {
      setActivityModal((prev) => ({ ...prev, loadingComment: false }));
    }
  };

  useEffect(() => {
    let mounted = true;
    const fetchStats = async () => {
      try {
        const data = await api.get("dashboard/");
        if (mounted) setStats(data);
      } catch {
        if (mounted) setStats({});
      } finally {
        if (mounted) setLoading(false);
      }
    };

    const fetchActivity = async () => {
      try {
        const data = await api.get(`agency/activity/?limit=${activityLimit}`);
        if (mounted) setActivity(Array.isArray(data) ? data : []);
      } catch {
        if (mounted) setActivity([]);
      } finally {
        if (mounted) setActivityLoading(false);
      }
    };

    const userData = localStorage.getItem("user");
    if (userData) setUser(JSON.parse(userData));
    else navigate("/login");

    fetchStats();
    fetchActivity();
    const onStorage = (e: StorageEvent) => e.key === "projects_last_update" && fetchStats();
    const pollId = window.setInterval(fetchStats, 10000);
    const activityPoll = window.setInterval(fetchActivity, 15000);
    window.addEventListener("storage", onStorage);
    return () => {
      mounted = false;
      window.clearInterval(pollId);
      window.clearInterval(activityPoll);
      window.removeEventListener("storage", onStorage);
    };
  }, [navigate, activityLimit]);

  if (!user) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  const displayName = user?.full_name || user?.username || "User";

  const funnelData = [
    { name: "Draft", value: stats.draft_projects || 0 },
    { name: "Submitted", value: stats.submitted_projects || 0 },
    { name: "Approved", value: stats.approved_projects || 0 },
  ];

  return (
    <PortalLayout
      title="Contributor Dashboard"
      subtitle="Monitor submissions, deadlines, and project completion"
      role="employee"
      userName={displayName}
      topActions={
        <Link to="/employee/projects/new" className="portal-btn portal-btn-primary">
          + New Submission
        </Link>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 md:gap-4 mb-4">
        <div className="portal-stat">
          <p className="portal-stat-title">Total Projects</p>
          <p className="portal-stat-value">{loading ? "..." : stats.my_projects || 0}</p>
        </div>
        <div className="portal-stat">
          <p className="portal-stat-title">Drafts</p>
          <p className="portal-stat-value text-amber-600">{loading ? "..." : stats.draft_projects || 0}</p>
        </div>
        <div className="portal-stat">
          <p className="portal-stat-title">Submitted</p>
          <p className="portal-stat-value text-blue-600">{loading ? "..." : stats.submitted_projects || 0}</p>
        </div>
        <div className="portal-stat">
          <p className="portal-stat-title">Approved</p>
          <p className="portal-stat-value text-emerald-600">{loading ? "..." : stats.approved_projects || 0}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Workflow Shortcuts</h2>
          </div>
          <div className="portal-card-body grid grid-cols-1 xl:grid-cols-3 gap-3">
            <Link to="/employee/projects/new" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">Create New Project</p>
              <p className="text-sm text-slate-500 mt-1">Start filling the full template form.</p>
            </Link>
            <Link to="/employee/projects?status=draft" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">Continue Drafts</p>
              <p className="text-sm text-slate-500 mt-1">Resume drafts before the admin deadline.</p>
            </Link>
            <Link to="/employee/projects" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">View Submissions</p>
              <p className="text-sm text-slate-500 mt-1">Open submitted projects and print PDF copy.</p>
            </Link>
          </div>
        </div>
      </div>

      <div className="portal-card mt-4">
        <div className="portal-card-header">
          <h2 className="text-lg font-semibold">Delivery Breakdown</h2>
        </div>
        <div className="portal-card-body h-[190px] md:h-[210px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={funnelData} barCategoryGap={18}>
              <defs>
                <linearGradient id="contribBreakdown" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#38bdf8" stopOpacity={0.7} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 4" stroke="#e6edfb" />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
              <Tooltip
                cursor={{ fill: "rgba(37, 99, 235, 0.08)" }}
                contentStyle={{ borderRadius: 12, borderColor: "#e2e8f0" }}
              />
              <Bar dataKey="value" fill="url(#contribBreakdown)" radius={[10, 10, 6, 6]} barSize={32} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="portal-card mt-4">
        <div className="portal-card-header">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">Recent Agency Activity</h2>
            <label className="text-xs text-slate-500 flex items-center gap-2">
              Show
              <select
                value={activityLimit}
                onChange={(e) => setActivityLimit(e.target.value)}
                className="border rounded px-2 py-1 text-xs"
              >
                {["10", "20", "30"].map((value) => (
                  <option key={value} value={value}>{value}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {activityLoading ? (
          <div className="portal-card-body text-slate-500">Loading activity...</div>
        ) : activity.length === 0 ? (
          <div className="portal-card-body text-slate-500">No recent activity for your agency.</div>
        ) : (
          <div className="portal-card-body">
            <div className="space-y-3">
              {activity.map((item) => (
                <div key={item.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">
                      {item.full_name || item.username || "User"}{" "}
                      <span className="text-slate-500 font-normal">- {item.event?.replaceAll("_", " ")}</span>
                    </p>
                    <p className="text-xs text-slate-500">
                      {item.project_title ? `Project: ${item.project_title}` : "Project: -"}
                    </p>
                    {item.details?.edited_fields_count !== undefined && (
                      <p className="text-xs text-slate-500">Edited fields: {item.details.edited_fields_count}</p>
                    )}
                    {item.event === "project_update" && (
                      <>
                        {Array.isArray(item.details?.changes) && item.details.changes.length > 0 ? (
                          <p className="text-xs text-slate-500">
                            Changed:{" "}
                            {item.details.changes
                              .slice(0, 3)
                              .map((c: any) => formatChangedFieldLabel(String(c?.field || "")))
                              .filter(Boolean)
                              .join(", ")}
                            {item.details.changes.length > 3 ? ` (+${item.details.changes.length - 3} more)` : ""}
                          </p>
                        ) : Array.isArray(item.details?.changed_fields) && item.details.changed_fields.length > 0 ? (
                          <p className="text-xs text-slate-500">
                            Changed:{" "}
                            {item.details.changed_fields
                              .slice(0, 3)
                              .map((f: any) => formatChangedFieldLabel(String(f || "")))
                              .filter(Boolean)
                              .join(", ")}
                            {item.details.changed_fields.length > 3 ? ` (+${item.details.changed_fields.length - 3} more)` : ""}
                          </p>
                        ) : null}
                      </>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    {item.event === "project_update" && Array.isArray(item.details?.changes) && item.details.changes.length > 0 && (
                      <button
                        type="button"
                        onClick={() => openChangesModal(item)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        View changes
                      </button>
                    )}
                    <p className="text-xs text-slate-500">
                      {item.created_at ? new Date(item.created_at).toLocaleString() : "-"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {activityModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="portal-card w-full max-w-3xl max-h-[85vh] overflow-hidden">
            <div className="portal-card-header flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold">{activityModal.title}</h3>
              <button
                type="button"
                onClick={() =>
                  setActivityModal({
                    open: false,
                    title: "",
                    changes: [],
                    editor: "",
                    at: "",
                    comment: "",
                    commentAt: "",
                    loadingComment: false,
                  })
                }
                className="portal-btn portal-btn-ghost"
              >
                Close
              </button>
            </div>
            <div className="portal-card-body overflow-auto">
              <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <p>
                  <span className="font-semibold">{activityModal.editor}</span>
                  {activityModal.at ? ` • ${activityModal.at}` : ""}
                </p>
                <p className="mt-1 text-slate-600">
                  Comment:{" "}
                  {activityModal.loadingComment ? (
                    <span className="text-slate-400">Loading...</span>
                  ) : activityModal.comment ? (
                    <span className="text-slate-800">{activityModal.comment}</span>
                  ) : (
                    <span className="text-slate-400">(none)</span>
                  )}
                  {!activityModal.loadingComment && activityModal.commentAt ? (
                    <span className="text-slate-400">{` • ${activityModal.commentAt}`}</span>
                  ) : null}
                </p>
              </div>
              {activityModal.changes.length === 0 ? (
                <p className="text-sm text-slate-500">No change details available for this activity.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">Field</th>
                        <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">From</th>
                        <th className="text-left px-3 py-2 text-xs font-semibold text-slate-600">To</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activityModal.changes.map((c, idx) => (
                        <tr key={`${c.field}-${idx}`} className="border-t">
                          <td className="px-3 py-2 align-top font-medium text-slate-800 whitespace-nowrap">
                            {formatChangedFieldLabel(c.field)}
                          </td>
                          <td className="px-3 py-2 align-top text-slate-700">
                            <div className="max-w-[260px] truncate" title={c.before || ""}>
                              {c.before || <span className="text-slate-400">(empty)</span>}
                            </div>
                          </td>
                          <td className="px-3 py-2 align-top text-slate-700">
                            <div className="max-w-[260px] truncate" title={c.after || ""}>
                              {c.after || <span className="text-slate-400">(empty)</span>}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </PortalLayout>
  );
};

export default Dashboard;
