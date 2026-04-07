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
      userName={user.username}
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
                  </div>
                  <p className="text-xs text-slate-500">
                    {item.created_at ? new Date(item.created_at).toLocaleString() : "-"}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </PortalLayout>
  );
};

export default Dashboard;
