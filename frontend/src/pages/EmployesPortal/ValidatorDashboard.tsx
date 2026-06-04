import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface DashboardStats {
  review_draft?: number;
  review_reviewed?: number;
  review_endorsed?: number;
}

const ValidatorDashboard: React.FC = () => {
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
  const displayName = user?.full_name || user?.username || "Validator";

  const queueMix = [
    { label: "Draft", count: stats.review_draft || 0 },
    { label: "Reviewed", count: stats.review_reviewed || 0 },
    { label: "Endorsed", count: stats.review_endorsed || 0 },
  ];

  return (
    <PortalLayout
      title="Validator Dashboard"
      subtitle="Review queue, decision throughput, and validation workflow"
      role="validator"
      userName={displayName}
      topActions={
        <Link to="/validator/projects" className="portal-btn portal-btn-primary">
          Review Queue
        </Link>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-4 mb-4">
        <div className="portal-stat">
          <p className="portal-stat-title">Draft Reviews</p>
          <p className="portal-stat-value text-amber-600">{loading ? "..." : stats.review_draft || 0}</p>
        </div>
        <div className="portal-stat">
          <p className="portal-stat-title">Reviewed</p>
          <p className="portal-stat-value text-blue-600">{loading ? "..." : stats.review_reviewed || 0}</p>
        </div>
        <div className="portal-stat">
          <p className="portal-stat-title">Endorsed</p>
          <p className="portal-stat-value text-emerald-600">{loading ? "..." : stats.review_endorsed || 0}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="portal-card lg:col-span-2">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Queue Balance</h2>
          </div>
          <div className="portal-card-body h-[210px] md:h-[230px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={queueMix} barCategoryGap={18}>
              <defs>
                <linearGradient id="validatorQueue" x1="0" y1="0" x2="0" y2="1">
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
              <Bar dataKey="count" fill="url(#validatorQueue)" radius={[10, 10, 6, 6]} barSize={34} />
            </BarChart>
          </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="portal-card lg:col-span-2">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Validation Operations</h2>
          </div>
          <div className="portal-card-body grid grid-cols-1 xl:grid-cols-2 gap-3">
            <Link to="/validator/projects" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">Open Pending Projects</p>
              <p className="text-sm text-slate-500 mt-1">Review full template forms and issue approve/reject actions.</p>
            </Link>
            <Link to="/validator/projects/history" className="portal-card p-4 hover:shadow-md transition-shadow">
              <p className="font-semibold">Reviewed & Endorsed History</p>
              <p className="text-sm text-slate-500 mt-1">See projects you already reviewed/endorsed and open them again.</p>
            </Link>
          </div>
        </div>
      </div>
    </PortalLayout>
  );
};

export default ValidatorDashboard;
