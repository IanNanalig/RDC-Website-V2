import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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

  const trendData = [
    { month: "Jan", value: Math.max(0, (stats.my_projects || 0) - 4) },
    { month: "Feb", value: Math.max(0, (stats.my_projects || 0) - 3) },
    { month: "Mar", value: Math.max(0, (stats.my_projects || 0) - 2) },
    { month: "Apr", value: Math.max(0, (stats.my_projects || 0) - 1) },
    { month: "May", value: stats.my_projects || 0 },
    { month: "Jun", value: (stats.my_projects || 0) + 1 },
  ];
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

      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-4 mb-4">
        <div className="portal-card lg:col-span-2 2xl:col-span-2">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Submission Trend</h2>
          </div>
          <div className="portal-card-body h-[210px] md:h-[230px] 2xl:h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="contribTrend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.06} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#d9e2f5" />
                <XAxis dataKey="month" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Area type="monotone" dataKey="value" stroke="#1d4ed8" fill="url(#contribTrend)" strokeWidth={2.2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Pipeline Mix</h2>
          </div>
          <div className="portal-card-body h-[210px] md:h-[230px] 2xl:h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={funnelData} dataKey="value" nameKey="name" outerRadius={85} innerRadius={45} fill="#1d4ed8" />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-4">
        <div className="portal-card lg:col-span-2 2xl:col-span-2">
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

        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Status Guide</h2>
          </div>
          <div className="portal-card-body text-sm text-slate-600 space-y-2">
            <p><span className="font-semibold text-amber-700">Draft:</span> editable while encoding window is open.</p>
            <p><span className="font-semibold text-blue-700">Submitted:</span> queued for validator review.</p>
            <p><span className="font-semibold text-emerald-700">Approved:</span> accepted and visible for reporting.</p>
            <p><span className="font-semibold text-slate-700">Reminder:</span> submitted projects are view-only.</p>
          </div>
        </div>
      </div>

      <div className="portal-card mt-4">
        <div className="portal-card-header">
          <h2 className="text-lg font-semibold">Delivery Breakdown</h2>
        </div>
        <div className="portal-card-body h-[190px] md:h-[210px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={funnelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e6edfb" />
              <XAxis dataKey="name" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="value" fill="#0ea5e9" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </PortalLayout>
  );
};

export default Dashboard;
