import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface DashboardStats {
  total_projects?: number;
  draft_projects?: number;
  pending_projects?: number;
  approved_projects?: number;
  archived_projects?: number;
  reviewed_projects?: number;
  validator_edited_projects?: number;
  users?: number;
  admin_users?: number;
  validator_users?: number;
  contributor_users?: number;
  review_draft?: number;
  review_reviewed?: number;
  review_endorsed?: number;
}

const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<any>(null);
  const [stats, setStats] = useState<DashboardStats>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const fetchStats = async () => {
      try {
        const data = await api.get("dashboard/");
        if (mounted) setStats(data);
      } catch {
        if (mounted) {
          setStats({});
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    const userData = localStorage.getItem("user");
    if (userData) setUser(JSON.parse(userData));
    else navigate("/login");

    fetchStats();
    const onStorage = (e: StorageEvent) => e.key === "projects_last_update" && fetchStats();
    const pollId = window.setInterval(fetchStats, 10000);
    window.addEventListener("storage", onStorage);
    return () => {
      mounted = false;
      window.clearInterval(pollId);
      window.removeEventListener("storage", onStorage);
    };
  }, [navigate]);

  if (!user) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  const displayName = user?.full_name || user?.username || "Admin";

  const userRoleData = [
    { label: "Admins", count: stats.admin_users || 0 },
    { label: "Validators", count: stats.validator_users || 0 },
    { label: "Contributors", count: stats.contributor_users || 0 },
  ];

  const projectStatusData = [
    { label: "Draft", count: stats.draft_projects || 0 },
    { label: "Submitted", count: stats.pending_projects || 0 },
    { label: "Reviewed", count: stats.review_reviewed || 0 },
    { label: "Endorsed", count: stats.review_endorsed || 0 },
  ];

  return (
    <PortalLayout
      title="Admin Command Center"
      subtitle="Control access, deadlines, and full portal governance"
      role="admin"
      userName={displayName}
      topActions={
        <button
          onClick={async () => {
            setLoading(true);
            try {
              const data = await api.get("dashboard/");
              setStats(data);
            } finally {
              setLoading(false);
            }
          }}
          className="portal-btn portal-btn-ghost"
        >
          Refresh
        </button>
      }
    >
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-8 gap-3 md:gap-4 mb-4">
        <div className="portal-stat"><p className="portal-stat-title">Total</p><p className="portal-stat-value">{loading ? "..." : stats.total_projects || 0}</p></div>
        <div className="portal-stat"><p className="portal-stat-title">Drafts</p><p className="portal-stat-value text-amber-600">{loading ? "..." : stats.draft_projects || 0}</p></div>
        <div className="portal-stat"><p className="portal-stat-title">Pending</p><p className="portal-stat-value text-blue-600">{loading ? "..." : stats.pending_projects || 0}</p></div>
        <div className="portal-stat"><p className="portal-stat-title">Approved</p><p className="portal-stat-value text-emerald-600">{loading ? "..." : stats.approved_projects || 0}</p></div>
        <div className="portal-stat"><p className="portal-stat-title">Archived</p><p className="portal-stat-value text-slate-600">{loading ? "..." : stats.archived_projects || 0}</p></div>
        <div className="portal-stat"><p className="portal-stat-title">Reviewed</p><p className="portal-stat-value text-violet-600">{loading ? "..." : stats.reviewed_projects || 0}</p></div>
        <div className="portal-stat"><p className="portal-stat-title">Validator Edited</p><p className="portal-stat-value text-indigo-600">{loading ? "..." : stats.validator_edited_projects || 0}</p></div>
        <div className="portal-stat"><p className="portal-stat-title">Users</p><p className="portal-stat-value">{loading ? "..." : stats.users || 0}</p></div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">User Roles</h2>
          </div>
          <div className="portal-card-body h-[210px] md:h-[230px] 2xl:h-[240px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={userRoleData} barCategoryGap={18}>
              <defs>
                <linearGradient id="adminUsers" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1d4ed8" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#60a5fa" stopOpacity={0.7} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 4" stroke="#e2e8f7" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
              <Tooltip
                cursor={{ fill: "rgba(37, 99, 235, 0.08)" }}
                contentStyle={{ borderRadius: 12, borderColor: "#e2e8f0" }}
              />
              <Bar dataKey="count" fill="url(#adminUsers)" radius={[10, 10, 6, 6]} barSize={34} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Project Status</h2>
          </div>
          <div className="portal-card-body h-[210px] md:h-[230px] 2xl:h-[240px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={projectStatusData} barCategoryGap={18}>
              <defs>
                <linearGradient id="adminProjects" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.7} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 4" stroke="#e2e8f7" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
              <Tooltip
                cursor={{ fill: "rgba(14, 165, 233, 0.08)" }}
                contentStyle={{ borderRadius: 12, borderColor: "#e2e8f0" }}
              />
              <Bar dataKey="count" fill="url(#adminProjects)" radius={[10, 10, 6, 6]} barSize={34} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="portal-card lg:col-span-2">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Administration Workflows</h2>
          </div>
          <div className="portal-card-body grid grid-cols-1 xl:grid-cols-3 gap-3">
            <Link to="/admin/users" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">User & Access Control</p>
              <p className="text-sm text-slate-500 mt-1">Approve requests, create users, set roles, manage deadlines.</p>
            </Link>
            <Link to="/admin/projects" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">Project Governance</p>
              <p className="text-sm text-slate-500 mt-1">View all projects, archive or delete with admin-only authority.</p>
            </Link>
            <Link to="/admin/validator-diffs" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">Validator Tracker</p>
              <p className="text-sm text-slate-500 mt-1">Review edited fields, reviewed copies, and validator decisions.</p>
            </Link>
          </div>
        </div>
      </div>
    </PortalLayout>
  );
};

export default AdminDashboard;
