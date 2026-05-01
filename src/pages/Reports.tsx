// src/pages/Reports.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Legend,
} from "recharts";
import { getPublicProjectsStats, type PublicProjectsStats } from "../services/publicProjectsApi";

const COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#94A3B8"];

const Reports: React.FC = () => {
  const [stats, setStats] = useState<PublicProjectsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await getPublicProjectsStats({});
        setStats(data);
      } catch (e: any) {
        setError(String(e?.message || e || "Failed to load reports."));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const byStatus = useMemo(() => {
    const map: Record<string, number> = stats?.by_status || {};
    return Object.keys(map).map((k) => ({ name: k, value: map[k] }));
  }, [stats]);

  const byAgency = useMemo(() => {
    const map: Record<string, number> = stats?.by_agency || {};
    return Object.keys(map)
      .map((k) => ({ agency: k, value: map[k] }))
      .sort((a, b) => b.value - a.value);
  }, [stats]);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Reports</h1>

      {loading && <p className="text-slate-600">Loading...</p>}
      {error && <p className="text-red-600">{error}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded p-4 shadow">
          <h3 className="font-semibold mb-2">Projects by Status</h3>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={byStatus}
                  dataKey="value"
                  nameKey="name"
                  outerRadius={70}
                  innerRadius={30}
                >
                  {byStatus.map((s, i) => (
                    <Cell
                      key={i}
                      fill={COLORS[i % COLORS.length]}
                      name={s.name}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: any, name: any) => [
                    `${value} projects`,
                    name,
                  ]}
                />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded p-4 shadow">
          <h3 className="font-semibold mb-2">Projects by Agency</h3>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byAgency} layout="vertical">
                <XAxis type="number" />
                <YAxis dataKey="agency" type="category" width={140} />
                <Tooltip />
                <Bar dataKey="value" fill="#3B82F6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Reports;
