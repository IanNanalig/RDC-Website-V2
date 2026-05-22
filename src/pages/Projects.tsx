// src/pages/Projects.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from "recharts";
import {
  getPublicProjects,
  getPublicProjectsStats,
  type PublicProject as Project,
  type PublicProjectsStats,
} from "../services/publicProjectsApi";
import {
  FaSearch,
  FaBuilding,
  FaCheckCircle,
  FaHourglassHalf,
  FaLightbulb,
  FaRegCalendarAlt,
  FaBars,
  FaTimes,
  FaChartBar,
  FaTable,
  FaMap,
  FaSortUp,
  FaSortDown,
} from "react-icons/fa";
import VoronoiBlobMap from "../components/VoronoiBlobMap";
import { ncrCityCenters } from "../services/ncrCityCenters";

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

const money = (n: number) => `₱ ${n.toLocaleString()}`;

const STATUS_ICONS: Record<string, React.ReactNode> = {
  Ongoing: <FaHourglassHalf className="text-yellow-500" />,
  Completed: <FaCheckCircle className="text-green-500" />,
  New: <FaLightbulb className="text-blue-500" />,
  Updated: <FaRegCalendarAlt className="text-indigo-500" />,
  Unspecified: <FaRegCalendarAlt className="text-slate-400" />,
};

const Projects: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [yearFilter, setYearFilter] = useState<number | "all">("all");
  const [statusFilter, setStatusFilter] = useState<string | "all">("all");
  const [agencyFilter, setAgencyFilter] = useState<string | "all">("all");
  const [search, setSearch] = useState("");
  const [selectedCity, setSelectedCity] = useState<string | undefined>(
    undefined,
  );
  const [municipalityFilter, setMunicipalityFilter] = useState<string>("all");
  const [activeTab, setActiveTab] = useState<"visual" | "table" | "map">(
    "visual",
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sortColumn, setSortColumn] = useState<
    "title" | "year" | "status" | "budget" | "agency" | "lgu"
  >("title");
  const [sortDesc, setSortDesc] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [stats, setStats] = useState<PublicProjectsStats | null>(null);
  const [detailProject, setDetailProject] = useState<Project | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const filters = {
        q: search || undefined,
        agency: agencyFilter === "all" ? undefined : agencyFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
        year: yearFilter === "all" ? undefined : yearFilter,
        lgu: municipalityFilter === "all" ? undefined : municipalityFilter,
      };
      // Fetch stats without agency filter to keep agency dropdown stable
      const statsFilters = {
        q: search || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        year: yearFilter === "all" ? undefined : yearFilter,
        lgu: municipalityFilter === "all" ? undefined : municipalityFilter,
      };
      const [list, st] = await Promise.all([
        getPublicProjects({ ...filters, limit: 500, offset: 0 }),
        getPublicProjectsStats(statsFilters),
      ]);
      setProjects(list);
      setStats(st);
    } catch (e: any) {
      setError(String(e?.message || e || "Failed to load projects."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yearFilter, statusFilter, agencyFilter, municipalityFilter, search]);

  const yearOptions = useMemo(
    () =>
      Array.from(
        new Set(
          projects
            .map((p) => p.year)
            .filter((y): y is number => typeof y === "number"),
        ),
      ).sort(),
    [projects],
  );

  const agencyOptions = useMemo(() => {
    if (stats?.by_agency) {
      return Object.keys(stats.by_agency).sort();
    }
    return Array.from(new Set(projects.map((p) => p.agency || "Other")));
  }, [stats, projects]);

  const municipalityOptions = useMemo(() => {
    return [...Object.keys(ncrCityCenters).sort(), "Unspecified"];
  }, []);

  useEffect(() => {
    if (municipalityFilter === "all" || municipalityFilter === "Unspecified") {
      setSelectedCity(undefined);
    } else {
      setSelectedCity(municipalityFilter);
    }
  }, [municipalityFilter]);

  useEffect(() => {
    if (!selectedCity) {
      if (municipalityFilter !== "Unspecified") {
        setMunicipalityFilter("all");
      }
    } else {
      setMunicipalityFilter(selectedCity);
    }
  }, [selectedCity]);

  // Filter projects by year, status, agency, and search (NOT by municipality yet)
  const filtered = useMemo(() => projects, [projects]);

  // For displaying in the project list - apply city filter
  const displayProjects = useMemo(() => {
    if (selectedCity) {
      return filtered.filter((p) => p.lgu === selectedCity);
    } else if (municipalityFilter === "Unspecified") {
      return filtered.filter((p) => !p.lgu);
    } else if (municipalityFilter !== "all") {
      return filtered.filter((p) => p.lgu === municipalityFilter);
    }
    return filtered;
  }, [filtered, selectedCity, municipalityFilter]);

  const totals = useMemo(() => {
    const totalProjects = displayProjects.length;
    const totalBudget = displayProjects.reduce(
      (s, p) => s + (p.budget || 0),
      0,
    );
    const byStatus = displayProjects.reduce<Record<string, number>>(
      (acc, p) => {
        const st =
          (p.implementation_status || "Unspecified").trim() || "Unspecified";
        acc[st] = (acc[st] || 0) + 1;
        return acc;
      },
      {},
    );
    return { totalProjects, totalBudget, byStatus };
  }, [displayProjects]);

  // Projects to send to the map
  const mapProjects = useMemo(() => {
    if (selectedCity) {
      return filtered.filter((p) => p.lgu === selectedCity);
    }
    if (municipalityFilter === "Unspecified") {
      return filtered.filter((p) => !p.lgu);
    }
    if (municipalityFilter !== "all") {
      return filtered.filter((p) => p.lgu === municipalityFilter);
    }
    return filtered;
  }, [filtered, selectedCity, municipalityFilter]);

  const statusPie = useMemo(
    () =>
      Object.keys(totals.byStatus).map((k) => ({
        name: k,
        value: totals.byStatus[k],
      })),
    [totals],
  );

  const statusCount = (label: string) => {
    const map: any = totals.byStatus || {};
    return (
      map[label] ??
      map[String(label).toLowerCase()] ??
      map[String(label).toUpperCase()] ??
      0
    );
  };

  const agencyBar = useMemo(() => {
    if (stats?.by_agency) {
      return Object.keys(stats.by_agency)
        .map((k) => ({ agency: k, value: stats.by_agency[k] }))
        .sort((a, b) => b.value - a.value);
    }
    const m = displayProjects.reduce<Record<string, number>>((acc, p) => {
      const a = p.agency || "Other";
      acc[a] = (acc[a] || 0) + 1;
      return acc;
    }, {});
    return Object.keys(m)
      .map((k) => ({ agency: k, value: m[k] }))
      .sort((a, b) => b.value - a.value);
  }, [displayProjects]);

  const yearBar = useMemo(() => {
    const m = displayProjects.reduce<Record<number, number>>((acc, p) => {
      if (typeof p.year === "number") {
        acc[p.year] = (acc[p.year] || 0) + 1;
      }
      return acc;
    }, {});
    return Object.keys(m)
      .map((k) => ({ year: Number(k), value: m[Number(k)] }))
      .sort((a, b) => a.year - b.year);
  }, [displayProjects]);

  const sortedTableProjects = useMemo(() => {
    const sorted = [...displayProjects];
    sorted.sort((a, b) => {
      let aVal: any = (a as any)[sortColumn];
      let bVal: any = (b as any)[sortColumn];

      if (sortColumn === "status") {
        aVal = a.implementation_status || "Unspecified";
        bVal = b.implementation_status || "Unspecified";
      }
      if (sortColumn === "agency") {
        aVal = a.agency || "";
        bVal = b.agency || "";
      }
      if (sortColumn === "lgu") {
        aVal = a.lgu || "Unspecified";
        bVal = b.lgu || "Unspecified";
      }

      // Normalize strings for consistent sorting
      if (
        sortColumn === "title" ||
        sortColumn === "status" ||
        sortColumn === "agency" ||
        sortColumn === "lgu"
      ) {
        aVal = String(aVal).toLowerCase();
        bVal = String(bVal).toLowerCase();
      }

      const comp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      const primary = sortDesc ? -comp : comp;
      if (primary !== 0) return primary;

      // Stable tie-breaker: Project Name (A-Z)
      const at = String(a.title || "").toLowerCase();
      const bt = String(b.title || "").toLowerCase();
      return at < bt ? -1 : at > bt ? 1 : 0;
    });
    return sorted;
  }, [displayProjects, sortColumn, sortDesc]);

  const handleSort = (
    col: "title" | "year" | "status" | "budget" | "agency" | "lgu",
  ) => {
    if (sortColumn === col) {
      setSortDesc(!sortDesc);
    } else {
      setSortColumn(col);
      setSortDesc(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50">
      {/* Header */}
      <div className="bg-white shadow-md border-b border-blue-100">
        <div className="container mx-auto px-4 py-6 max-w-7xl">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-3xl md:text-4xl font-extrabold text-blue-900 tracking-tight">
                Projects Dashboard
              </h1>
              <p className="text-blue-700 mt-1 text-sm md:text-base">
                Explore, filter, and visualize NCR Regional Development projects
              </p>
            </div>
            <div className="flex gap-3 items-center">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="lg:hidden p-2 rounded-lg bg-blue-100 text-blue-900 hover:bg-blue-200 transition"
                aria-label="Toggle filters"
              >
                {sidebarOpen ? <FaTimes size={20} /> : <FaBars size={20} />}
              </button>
              <div className="relative flex-1 lg:w-64">
                <input
                  placeholder="Search projects..."
                  className="w-full border-2 border-blue-200 rounded-lg px-4 py-2 pl-10 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-all duration-200 shadow-sm"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <FaSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-blue-400" />
              </div>
            </div>
          </div>

          {/* Summary Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-3 border border-blue-200">
              <div className="text-xs font-semibold text-blue-700 mb-1">
                Total Projects
              </div>
              <div className="text-2xl font-bold text-blue-900">
                {totals.totalProjects}
              </div>
            </div>
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-3 border border-green-200">
              <div className="text-xs font-semibold text-green-700 mb-1">
                Total Budget
              </div>
              <div className="text-lg font-bold text-green-900 truncate">
                {money(totals.totalBudget)}
              </div>
            </div>
            <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-lg p-3 border border-yellow-200">
              <div className="text-xs font-semibold text-yellow-700 mb-1">
                Ongoing
              </div>
              <div className="text-2xl font-bold text-yellow-900">
                {statusCount("Ongoing")}
              </div>
            </div>
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-3 border border-purple-200">
              <div className="text-xs font-semibold text-purple-700 mb-1">
                Completed
              </div>
              <div className="text-2xl font-bold text-purple-900">
                {statusCount("Completed")}
              </div>
            </div>
          </div>

          {(loading || error) && (
            <div className="mt-3">
              {loading && (
                <div className="text-sm text-slate-600">Loading projects…</div>
              )}
              {error && (
                <div className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 flex items-center justify-between gap-3">
                  <span className="truncate">{error}</span>
                  <button
                    type="button"
                    className="shrink-0 underline"
                    onClick={fetchData}
                  >
                    Retry
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Sidebar Filters */}
          <div
            className={`${
              sidebarOpen ? "block" : "hidden"
            } lg:block w-full lg:w-72 flex-shrink-0`}
          >
            <div className="bg-white rounded-xl p-4 md:p-6 shadow-lg sticky top-24">
              <h3 className="text-lg font-bold text-blue-900 mb-4 flex items-center gap-2">
                <FaBuilding className="text-blue-400" /> Filters
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-blue-800 mb-2">
                    Year
                  </label>
                  <select
                    className="w-full border-2 border-blue-100 rounded-lg p-2 focus:ring-2 focus:ring-blue-300 transition text-sm"
                    value={yearFilter}
                    onChange={(e) =>
                      setYearFilter(
                        e.target.value === "all"
                          ? "all"
                          : Number(e.target.value),
                      )
                    }
                  >
                    <option value="all">All Years</option>
                    {yearOptions.map((y) => (
                      <option key={y} value={y}>
                        {y}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-blue-800 mb-2">
                    Status
                  </label>
                  <select
                    className="w-full border-2 border-blue-100 rounded-lg p-2 focus:ring-2 focus:ring-blue-300 transition text-sm"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value as any)}
                  >
                    <option value="all">All Status</option>
                    <option value="Completed">Completed</option>
                    <option value="New">New</option>
                    <option value="Updated">Updated</option>
                    <option value="Ongoing">Ongoing</option>
                    <option value="Discontinued">Discontinued</option>
                    <option value="Not Implemented">Not Implemented</option>
                    <option value="N/A">N/A</option>
                    <option value="Dropped">Dropped</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-blue-800 mb-2">
                    Agency
                  </label>
                  <select
                    className="w-full border-2 border-blue-100 rounded-lg p-2 focus:ring-2 focus:ring-blue-300 transition text-sm"
                    value={agencyFilter}
                    onChange={(e) => setAgencyFilter(e.target.value as any)}
                  >
                    <option value="all">All Agencies</option>
                    {agencyOptions.map((a) => (
                      <option key={a} value={a}>
                        {a}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-blue-800 mb-2">
                    Municipality
                  </label>
                  <select
                    className="w-full border-2 border-blue-100 rounded-lg p-2 focus:ring-2 focus:ring-blue-300 transition text-sm"
                    value={municipalityFilter}
                    onChange={(e) => setMunicipalityFilter(e.target.value)}
                  >
                    <option value="all">All Municipalities</option>
                    {municipalityOptions.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Tab Navigation & Content */}
          <div className="flex-1 min-w-0">
            {/* Tab Buttons */}
            <div className="flex gap-2 mb-6 border-b border-gray-200 bg-white rounded-t-xl p-4 overflow-x-auto">
              <button
                onClick={() => setActiveTab("visual")}
                className={`flex items-center gap-2 px-4 py-2 font-semibold rounded-t-lg transition flex-shrink-0 ${
                  activeTab === "visual"
                    ? "text-blue-900 border-b-2 border-blue-600 bg-blue-50"
                    : "text-gray-600 hover:text-blue-700"
                }`}
              >
                <FaChartBar size={18} /> Visual
              </button>
              <button
                onClick={() => setActiveTab("table")}
                className={`flex items-center gap-2 px-4 py-2 font-semibold rounded-t-lg transition flex-shrink-0 ${
                  activeTab === "table"
                    ? "text-blue-900 border-b-2 border-blue-600 bg-blue-50"
                    : "text-gray-600 hover:text-blue-700"
                }`}
              >
                <FaTable size={18} /> Table
              </button>
              <button
                onClick={() => setActiveTab("map")}
                className={`flex items-center gap-2 px-4 py-2 font-semibold rounded-t-lg transition flex-shrink-0 ${
                  activeTab === "map"
                    ? "text-blue-900 border-b-2 border-blue-600 bg-blue-50"
                    : "text-gray-600 hover:text-blue-700"
                }`}
              >
                <FaMap size={18} /> Map
              </button>
            </div>

            {/* Visual Tab */}
            {activeTab === "visual" && (
              <div className="space-y-6">
                {/* Charts Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Status Pie Chart */}
                  <div className="bg-white rounded-xl p-4 md:p-6 shadow-lg hover:shadow-xl transition-shadow">
                    <h3 className="font-semibold mb-4 text-blue-800 flex items-center gap-2 text-base md:text-lg">
                      <FaCheckCircle className="text-green-400" /> Projects by
                      Status
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
                            label={(props: {
                              name?: string;
                              percent?: number;
                            }) =>
                              props.name
                                ? `${
                                    props.name.charAt(0).toUpperCase() +
                                    props.name.slice(1)
                                  } ${Math.round((props.percent ?? 0) * 100)}%`
                                : ""
                            }
                            isAnimationActive
                          >
                            {statusPie.map((entry, index) => (
                              <Cell
                                key={index}
                                fill={COLORS[entry.name] || "#ccc"}
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            formatter={(value: any) => `${value} projects`}
                          />
                          <Legend verticalAlign="bottom" height={36} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Agency Bar Chart */}
                  <div className="bg-white rounded-xl p-4 md:p-6 shadow-lg hover:shadow-xl transition-shadow">
                    <h3 className="font-semibold mb-4 text-blue-800 flex items-center gap-2 text-base md:text-lg">
                      <FaBuilding className="text-blue-400" /> Projects by
                      Agency
                    </h3>
                    <div className="h-64 md:h-80">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={agencyBar}
                          layout="vertical"
                          margin={{ left: 120, right: 10 }}
                        >
                          <XAxis type="number" hide />
                          <YAxis
                            dataKey="agency"
                            type="category"
                            width={110}
                            tick={{ fontSize: 12 }}
                          />
                          <Tooltip />
                          <Bar
                            dataKey="value"
                            fill="#3B82F6"
                            radius={[0, 8, 8, 0]}
                            isAnimationActive
                          >
                            {agencyBar.map((_, idx) => (
                              <Cell
                                key={idx}
                                fill={`hsl(${200 + idx * 20}, 80%, 60%)`}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                </div>

                {/* Year Chart */}
                <div className="bg-white rounded-xl p-4 md:p-6 shadow-lg hover:shadow-xl transition-shadow">
                  <h3 className="font-semibold mb-4 text-blue-800 flex items-center gap-2 text-base md:text-lg">
                    <FaRegCalendarAlt className="text-orange-400" /> Projects by
                    Year
                  </h3>
                  <div className="h-64 md:h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={yearBar}
                        layout="vertical"
                        margin={{ left: 28, right: 12, top: 8, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis type="number" />
                        <YAxis
                          type="category"
                          dataKey="year"
                          width={56}
                          tick={{ fontSize: 12 }}
                        />
                        <Tooltip
                          formatter={(value: any) => [`${value}`, "Projects"]}
                        />
                        <Bar
                          dataKey="value"
                          fill="#F59E0B"
                          radius={[0, 10, 10, 0]}
                          isAnimationActive
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* Table Tab */}
            {activeTab === "table" && (
              <div className="bg-white rounded-xl shadow-lg overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-blue-50 border-b-2 border-blue-200">
                      <tr>
                        <th className="px-4 py-3 text-left">
                          <button
                            onClick={() => handleSort("title")}
                            className="font-semibold text-blue-900 hover:text-blue-600 flex items-center gap-2"
                          >
                            Project Name
                            {sortColumn === "title" && (
                              <span className="text-blue-700">
                                {sortDesc ? <FaSortDown /> : <FaSortUp />}
                              </span>
                            )}
                          </button>
                        </th>
                        <th className="px-4 py-3 text-left">
                          <button
                            onClick={() => handleSort("year")}
                            className="font-semibold text-blue-900 hover:text-blue-600 flex items-center gap-2"
                          >
                            Year
                            {sortColumn === "year" && (
                              <span className="text-blue-700">
                                {sortDesc ? <FaSortDown /> : <FaSortUp />}
                              </span>
                            )}
                          </button>
                        </th>
                        <th className="px-4 py-3 text-left">
                          <button
                            onClick={() => handleSort("status")}
                            className="font-semibold text-blue-900 hover:text-blue-600 flex items-center gap-2"
                          >
                            Status
                            {sortColumn === "status" && (
                              <span className="text-blue-700">
                                {sortDesc ? <FaSortDown /> : <FaSortUp />}
                              </span>
                            )}
                          </button>
                        </th>
                        <th className="px-4 py-3 text-left">
                          <button
                            onClick={() => handleSort("agency")}
                            className="font-semibold text-blue-900 hover:text-blue-600 flex items-center gap-2"
                          >
                            Agency
                            {sortColumn === "agency" && (
                              <span className="text-blue-700">
                                {sortDesc ? <FaSortDown /> : <FaSortUp />}
                              </span>
                            )}
                          </button>
                        </th>
                        <th className="px-4 py-3 text-left">
                          <button
                            onClick={() => handleSort("budget")}
                            className="font-semibold text-blue-900 hover:text-blue-600 flex items-center gap-2"
                          >
                            Budget
                            {sortColumn === "budget" && (
                              <span className="text-blue-700">
                                {sortDesc ? <FaSortDown /> : <FaSortUp />}
                              </span>
                            )}
                          </button>
                        </th>
                        <th className="px-4 py-3 text-left">
                          <button
                            onClick={() => handleSort("lgu")}
                            className="font-semibold text-blue-900 hover:text-blue-600 flex items-center gap-2"
                          >
                            Location
                            {sortColumn === "lgu" && (
                              <span className="text-blue-700">
                                {sortDesc ? <FaSortDown /> : <FaSortUp />}
                              </span>
                            )}
                          </button>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedTableProjects.length > 0 ? (
                        sortedTableProjects.map((p, idx) => (
                          <tr
                            key={p.id}
                            className={`border-b border-gray-100 hover:bg-blue-50 transition ${
                              idx % 2 === 0 ? "bg-white" : "bg-gray-50"
                            }`}
                          >
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">
                              <button
                                type="button"
                                className="text-left hover:underline text-blue-900"
                                onClick={() => setDetailProject(p)}
                                title="View project details"
                              >
                                {p.title}
                              </button>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-700">
                              {p.year}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <span
                                className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold ${
                                  p.implementation_status === "Completed"
                                    ? "bg-green-100 text-green-800"
                                    : p.implementation_status === "Ongoing"
                                      ? "bg-yellow-100 text-yellow-800"
                                      : p.implementation_status === "New"
                                        ? "bg-blue-100 text-blue-800"
                                        : "bg-gray-100 text-gray-800"
                                }`}
                              >
                                {
                                  STATUS_ICONS[
                                    p.implementation_status || "Unspecified"
                                  ]
                                }{" "}
                                {p.implementation_status || "Unspecified"}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-700">
                              {p.agency}
                            </td>
                            <td className="px-4 py-3 text-sm font-semibold text-green-700">
                              {money(p.budget)}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-700">
                              {p.lgu || "Unspecified"}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td
                            colSpan={6}
                            className="px-4 py-12 text-center text-gray-500"
                          >
                            <FaSearch className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                            <p className="text-lg">No projects found</p>
                            <p className="text-sm">
                              Try adjusting your filters
                            </p>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {detailProject && (
              <div
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
                role="dialog"
                aria-modal="true"
              >
                <div className="w-full max-w-3xl bg-white rounded-xl shadow-xl overflow-hidden flex flex-col max-h-[calc(100vh-2rem)]">
                  <div className="flex items-center justify-between px-5 py-4 border-b">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-slate-900 truncate">
                        {detailProject.title}
                      </h3>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {detailProject.agency || "N/A"}{" "}
                        {detailProject.lgu ? `• ${detailProject.lgu}` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="px-3 py-1.5 border rounded-lg text-sm hover:bg-slate-50"
                      onClick={() => setDetailProject(null)}
                    >
                      Close
                    </button>
                  </div>
                  <div className="p-5 space-y-4 overflow-y-auto flex-1 min-h-0">
                    <div className="grid sm:grid-cols-3 gap-3">
                      <div className="border rounded-lg p-3">
                        <p className="text-[11px] text-slate-500">Status</p>
                        <p className="font-semibold">
                          {detailProject.implementation_status || "Unspecified"}
                        </p>
                      </div>
                      <div className="border rounded-lg p-3">
                        <p className="text-[11px] text-slate-500">Year</p>
                        <p className="font-semibold">{detailProject.year ?? "-"}</p>
                      </div>
                      <div className="border rounded-lg p-3">
                        <p className="text-[11px] text-slate-500">Budget</p>
                        <p className="font-semibold text-green-700">
                          {money(detailProject.budget || 0)}
                        </p>
                      </div>
                    </div>

                    <div className="border rounded-lg p-4 bg-slate-50">
                      <p className="text-sm font-semibold text-slate-900 mb-2">
                        Overview
                      </p>
                      <p className="text-sm text-slate-700 whitespace-pre-wrap break-words">
                        {detailProject.public_summary_text?.trim()
                          ? detailProject.public_summary_text
                          : detailProject.description || "No summary available."}
                      </p>
                    </div>

                    {(detailProject.public_key_facts?.objective ||
                      detailProject.description) && (
                      <div className="grid md:grid-cols-2 gap-3">
                        {detailProject.public_key_facts?.objective ? (
                          <div className="border rounded-lg p-4">
                            <p className="text-sm font-semibold text-slate-900 mb-2">
                              Objective
                            </p>
                            <p className="text-sm text-slate-700 whitespace-pre-wrap break-words">
                              {String(detailProject.public_key_facts.objective)}
                            </p>
                          </div>
                        ) : null}
                        {detailProject.description ? (
                          <div className="border rounded-lg p-4">
                            <p className="text-sm font-semibold text-slate-900 mb-2">
                              Description
                            </p>
                            <p className="text-sm text-slate-700 whitespace-pre-wrap break-words">
                              {detailProject.description}
                            </p>
                          </div>
                        ) : null}
                      </div>
                    )}

                    {detailProject.public_key_facts &&
                      typeof detailProject.public_key_facts === "object" && (
                        <div className="border rounded-lg p-4">
                          <p className="text-sm font-semibold text-slate-900 mb-2">
                            Key Facts
                          </p>
                          <div className="grid sm:grid-cols-2 gap-3 text-sm">
                            {detailProject.public_key_facts.start_year ? (
                              <div>
                                <p className="text-[11px] text-slate-500">Start Year</p>
                                <p className="text-slate-800">
                                  {String(detailProject.public_key_facts.start_year)}
                                </p>
                              </div>
                            ) : null}
                            {detailProject.public_key_facts.end_year ? (
                              <div>
                                <p className="text-[11px] text-slate-500">End Year</p>
                                <p className="text-slate-800">
                                  {String(detailProject.public_key_facts.end_year)}
                                </p>
                              </div>
                            ) : null}
                            {detailProject.public_key_facts.development_sector ? (
                              <div className="sm:col-span-2">
                                <p className="text-[11px] text-slate-500">Development Sector</p>
                                <p className="text-slate-800">
                                  {String(detailProject.public_key_facts.development_sector)}
                                </p>
                              </div>
                            ) : null}
                            {detailProject.public_key_facts.rdp_main_chapter ? (
                              <div className="sm:col-span-2">
                                <p className="text-[11px] text-slate-500">RDP Main Chapter</p>
                                <p className="text-slate-800">
                                  {String(detailProject.public_key_facts.rdp_main_chapter)}
                                </p>
                              </div>
                            ) : null}
                            {typeof detailProject.public_key_facts.sdg_count === "number" ? (
                              <div>
                                <p className="text-[11px] text-slate-500">SDG Tags</p>
                                <p className="text-slate-800">
                                  {String(detailProject.public_key_facts.sdg_count)}
                                </p>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      )}

                    {Array.isArray(detailProject.public_summary_bullets) &&
                      detailProject.public_summary_bullets.length > 0 && (
                        <div className="border rounded-lg p-4">
                          <p className="text-sm font-semibold text-slate-900 mb-2">
                            Highlights
                          </p>
                          <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
                            {detailProject.public_summary_bullets.map((b, i) => (
                              <li key={`${i}-${b}`} className="break-words">
                                {b}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                  </div>
                </div>
              </div>
            )}

            {/* Map Tab */}
            {activeTab === "map" && (
              <div className="bg-white rounded-xl shadow-lg overflow-hidden">
                <VoronoiBlobMap
                  projects={mapProjects}
                  selectedCity={selectedCity}
                  selectedStatus={statusFilter === "all" ? "all" : statusFilter}
                  onCitySelect={(city) => setSelectedCity(city)}
                  height={600}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Styles */}
      <style>
        {`
        .line-clamp-2 {
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        `}
      </style>
    </div>
  );
};

export default Projects;
