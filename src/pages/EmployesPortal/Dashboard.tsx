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
    </PortalLayout>
  );
};

export default Dashboard;
