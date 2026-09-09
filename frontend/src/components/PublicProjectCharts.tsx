import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { FaBuilding, FaCheckCircle, FaRegCalendarAlt } from "react-icons/fa";

const COLORS: Record<string, string> = {
  Completed: "#10B981",
  Ongoing: "#F59E0B",
  New: "#3B82F6",
  Updated: "#6366F1",
  Discontinued: "#EF4444",
  "Not Implemented": "#94A3B8",
  Dropped: "#F97316",
  "N/A": "#64748B",
  Unspecified: "#94A3B8",
};

type Props = {
  statusPie: Array<{ name: string; value: number }>;
  agencyBar: Array<{ agency: string; value: number }>;
  yearBar: Array<{ year: number; value: number }>;
};

const PublicProjectCharts: React.FC<Props> = ({ statusPie, agencyBar, yearBar }) => (
  <div className="space-y-6">
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <div className="rounded-xl bg-white p-4 shadow-lg transition-shadow hover:shadow-xl md:p-6">
        <h3 className="mb-4 flex items-center gap-2 text-base font-semibold text-blue-800 md:text-lg">
          <FaCheckCircle className="text-green-400" /> Projects by Status
        </h3>
        <div className="h-64 md:h-80">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={statusPie}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius="70%"
                innerRadius="40%"
                labelLine={false}
                label={(props: { name?: string; percent?: number }) =>
                  props.name
                    ? `${props.name.charAt(0).toUpperCase() + props.name.slice(1)} ${Math.round((props.percent ?? 0) * 100)}%`
                    : ""
                }
                isAnimationActive
              >
                {statusPie.map((entry, index) => (
                  <Cell key={index} fill={COLORS[entry.name] || "#ccc"} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number | string) => `${value} projects`} />
              <Legend verticalAlign="bottom" height={36} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl bg-white p-4 shadow-lg transition-shadow hover:shadow-xl md:p-6">
        <h3 className="mb-4 flex items-center gap-2 text-base font-semibold text-blue-800 md:text-lg">
          <FaBuilding className="text-blue-400" /> Projects by Agency
        </h3>
        <div className="h-64 md:h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={agencyBar} layout="vertical" margin={{ left: 120, right: 10 }}>
              <XAxis type="number" hide />
              <YAxis dataKey="agency" type="category" width={110} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#3B82F6" radius={[0, 8, 8, 0]} isAnimationActive>
                {agencyBar.map((_, index) => (
                  <Cell key={index} fill={`hsl(${200 + index * 20}, 80%, 60%)`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>

    <div className="rounded-xl bg-white p-4 shadow-lg transition-shadow hover:shadow-xl md:p-6">
      <h3 className="mb-4 flex items-center gap-2 text-base font-semibold text-blue-800 md:text-lg">
        <FaRegCalendarAlt className="text-orange-400" /> Projects by Year
      </h3>
      <div className="h-64 md:h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={yearBar} layout="vertical" margin={{ left: 28, right: 12, top: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis type="number" />
            <YAxis type="category" dataKey="year" width={56} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value: number | string) => [`${value}`, "Projects"]} />
            <Bar dataKey="value" fill="#F59E0B" radius={[0, 10, 10, 0]} isAnimationActive />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  </div>
);

export default PublicProjectCharts;
