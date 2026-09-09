// src/pages/Projects.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getPublicProjects,
  getPublicProject,
  getPublicProjectsStats,
} from "../services/publicProjectsApi";
import cmsApi, { type CMSPageSnapshot } from "../services/cmsApi";
import type {
  PublicProject as Project,
  PublicProjectsStats,
} from "../types/api";
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
  FaArrowRight,
} from "react-icons/fa";
import { ncrCityCenters } from "../services/ncrCityCenters";

const PublicProjectCharts = React.lazy(() => import("../components/PublicProjectCharts"));
const VoronoiBlobMap = React.lazy(() => import("../components/VoronoiBlobMap"));

const money = (value: number | string | null | undefined) => {
  const numeric =
    typeof value === "number"
      ? value
      : Number(String(value ?? "").replace(/[^0-9.-]/g, ""));

  return Number.isFinite(numeric)
    ? `₱ ${numeric.toLocaleString("en-US")}`
    : "₱ 0";
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  Ongoing: <FaHourglassHalf className="text-yellow-500" />,
  Completed: <FaCheckCircle className="text-green-500" />,
  New: <FaLightbulb className="text-blue-500" />,
  Updated: <FaRegCalendarAlt className="text-indigo-500" />,
  Unspecified: <FaRegCalendarAlt className="text-slate-400" />,
};

const getProjectLgus = (project: Project): string[] => {
  const lgus =
    Array.isArray(project.lgus) && project.lgus.length > 0
      ? project.lgus
      : project.lgu
        ? [project.lgu]
        : [];
  return Array.from(new Set(lgus));
};

const projectMatchesLgu = (project: Project, lgu: string) =>
  getProjectLgus(project).includes(lgu);

const projectLocationLabel = (project: Project) => {
  const lgus = getProjectLgus(project);
  return lgus.length > 0 ? lgus.join(", ") : "Unspecified";
};

const formatDateShort = (raw?: string | null) => {
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

const formatDateTime = (raw?: string | null) => {
  if (!raw) return "Date unavailable";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return date.toLocaleString();
};

const publicUpdateCountLabel = (count?: number) => {
  const n = Number(count || 0);
  return `${n} public update${n === 1 ? "" : "s"}`;
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const asString = (value: unknown, fallback = "") =>
  typeof value === "string" && value.trim() ? value.trim() : fallback;

const getPageSection = (page: CMSPageSnapshot | null, sectionKey: string) =>
  asRecord(
    page?.sections.find((section) => section.sectionKey === sectionKey)?.content,
  );

const Projects: React.FC = () => {
  const [cmsPage, setCmsPage] = useState<CMSPageSnapshot | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [yearFilter, setYearFilter] = useState<number | "all">("all");
  const [statusFilter, setStatusFilter] = useState<string | "all">("all");
  const [agencyFilter, setAgencyFilter] = useState<string | "all">("all");
  const [updateFilter, setUpdateFilter] = useState<"all" | "recent">("all");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
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
  const requestSequence = useRef(0);
  const detailRequestSequence = useRef(0);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const fetchData = useCallback(async () => {
    const sequence = ++requestSequence.current;
    setLoading(true);
    setError("");
    try {
      const filters = {
        q: debouncedSearch || undefined,
        agency: agencyFilter === "all" ? undefined : agencyFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
        year: yearFilter === "all" ? undefined : yearFilter,
        lgu: municipalityFilter === "all" ? undefined : municipalityFilter,
      };
      // Fetch stats without agency filter to keep agency dropdown stable
      const statsFilters = {
        q: debouncedSearch || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
        year: yearFilter === "all" ? undefined : yearFilter,
        lgu: municipalityFilter === "all" ? undefined : municipalityFilter,
      };
      const [list, st] = await Promise.all([
        getPublicProjects({
          ...filters,
          limit: 500,
          offset: 0,
          view: "summary",
        }),
        getPublicProjectsStats(statsFilters),
      ]);
      if (sequence !== requestSequence.current) return;
      setProjects(list);
      setStats(st);
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "message" in e
          ? String((e as Error).message)
          : String(e);
      if (sequence === requestSequence.current) setError(msg || "Failed to load projects.");
    } finally {
      if (sequence === requestSequence.current) setLoading(false);
    }
  }, [agencyFilter, debouncedSearch, municipalityFilter, statusFilter, yearFilter]);

  const openProjectDetail = useCallback(async (project: Project) => {
    const sequence = ++detailRequestSequence.current;
    setDetailProject(project);
    try {
      const detail = await getPublicProject(project.id);
      if (sequence === detailRequestSequence.current) setDetailProject(detail);
    } catch {
      // Keep the summary card open as a compatibility fallback during staggered deploys.
    }
  }, []);

  const closeProjectDetail = () => {
    detailRequestSequence.current += 1;
    setDetailProject(null);
  };

  useEffect(() => {
    fetchData();
    const refreshId = window.setInterval(fetchData, 60000);
    const handleFocus = () => fetchData();
    window.addEventListener("focus", handleFocus);
    return () => {
      window.clearInterval(refreshId);
      window.removeEventListener("focus", handleFocus);
    };
  }, [fetchData]);

  useEffect(() => {
    let cancelled = false;
    cmsApi
      .getPublicPage("projects-dashboard")
      .then((page) => {
        if (!cancelled) setCmsPage(page);
      })
      .catch(() => {
        if (!cancelled) setCmsPage(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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

  // Municipality filter is the single source of truth. Keeping a second
  // selected-city state caused the two values to overwrite one another.
  const selectedCity =
    municipalityFilter === "all" || municipalityFilter === "Unspecified"
      ? undefined
      : municipalityFilter;

  // Filter projects by year, status, agency, and search (NOT by municipality yet)
  const filtered = useMemo(() => projects, [projects]);

  // For displaying in the project list - apply city filter
  const displayProjects = useMemo(() => {
    let rows = filtered;
    if (selectedCity) {
      rows = rows.filter((p) => projectMatchesLgu(p, selectedCity));
    } else if (municipalityFilter === "Unspecified") {
      rows = rows.filter((p) => getProjectLgus(p).length === 0);
    } else if (municipalityFilter !== "all") {
      rows = rows.filter((p) => projectMatchesLgu(p, municipalityFilter));
    }
    if (updateFilter === "recent") {
      rows = rows.filter((p) => Boolean(p.has_public_updates));
    }
    return rows;
  }, [filtered, selectedCity, municipalityFilter, updateFilter]);

  const recentlyUpdatedProjects = useMemo(
    () =>
      displayProjects
        .filter((p) => Boolean(p.has_public_updates && p.latest_update_date))
        .sort(
          (a, b) =>
            new Date(b.latest_update_date || "").getTime() -
            new Date(a.latest_update_date || "").getTime(),
        )
        .slice(0, 5),
    [displayProjects],
  );

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
      return filtered.filter((p) => projectMatchesLgu(p, selectedCity));
    }
    if (municipalityFilter === "Unspecified") {
      return filtered.filter((p) => getProjectLgus(p).length === 0);
    }
    if (municipalityFilter !== "all") {
      return filtered.filter((p) => projectMatchesLgu(p, municipalityFilter));
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
    const map: Record<string, number> = totals.byStatus || {};
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
  }, [displayProjects, stats?.by_agency]);

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
    const getSortValue = (
      p: Project,
      col: typeof sortColumn,
    ): string | number => {
      switch (col) {
        case "title":
          return String(p.title || "").toLowerCase();
        case "status":
          return String(p.implementation_status || "Unspecified").toLowerCase();
        case "agency":
          return String(p.agency || "").toLowerCase();
        case "lgu":
          return projectLocationLabel(p).toLowerCase();
        case "year":
          return typeof p.year === "number" ? p.year : Number.NEGATIVE_INFINITY;
        case "budget":
          return Number(p.budget || 0);
        default:
          return String(
            (p as unknown as Record<string, unknown>)[col] ?? "",
          ).toLowerCase();
      }
    };

    sorted.sort((a, b) => {
      const aVal = getSortValue(a, sortColumn);
      const bVal = getSortValue(b, sortColumn);

      let comp = 0;
      if (typeof aVal === "number" && typeof bVal === "number") {
        comp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
      } else {
        const as = String(aVal ?? "");
        const bs = String(bVal ?? "");
        comp = as < bs ? -1 : as > bs ? 1 : 0;
      }

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

  const heroContent = getPageSection(cmsPage, "projects-hero");
  const updatesContent = getPageSection(cmsPage, "projects-updates");
  const dataNoteContent = getPageSection(cmsPage, "projects-data-note");

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-green-50">
      {/* Header */}
      <div className="bg-white shadow-md border-b border-blue-100">
        <div className="container mx-auto px-4 py-6 max-w-7xl">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
            <div>
              <h1 className="text-3xl md:text-4xl font-extrabold text-blue-900 tracking-tight">
                {asString(heroContent.title, "RDIP Projects Dashboard")}
              </h1>
              <p className="text-blue-700 mt-1 text-sm md:text-base">
                {asString(
                  heroContent.subtitle,
                  "Explore, filter, and visualize NCR Regional Development projects",
                )}
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

          <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/70 px-4 py-3">
            <p className="text-sm font-bold text-blue-950">
              {asString(dataNoteContent.title, "About this dashboard")}
            </p>
            <p className="mt-1 text-xs text-blue-800">
              {asString(
                dataNoteContent.body || heroContent.body,
                "Project figures come from endorsed public records that completed the RDC-NCR portal review workflow.",
              )}
            </p>
          </div>

          {recentlyUpdatedProjects.length > 0 && (
            <div className="mt-5 rounded-2xl border border-emerald-200 bg-gradient-to-r from-emerald-50 via-white to-blue-50 p-4 shadow-sm">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">
                    {asString(updatesContent.subtitle, "Recently Updated")}
                  </p>
                  <h2 className="text-lg font-bold text-slate-900">
                    {asString(
                      updatesContent.title,
                      "Latest validator-approved project progress",
                    )}
                  </h2>
                  <p className="text-sm text-slate-600">
                    {asString(
                      updatesContent.body,
                      "Only endorsed public updates are shown here.",
                    )}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setUpdateFilter(
                      updateFilter === "recent" ? "all" : "recent",
                    );
                    setActiveTab("table");
                  }}
                  className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold shadow-sm ${
                    updateFilter === "recent"
                      ? "bg-white text-emerald-700 ring-1 ring-emerald-200 hover:bg-emerald-50"
                      : "bg-emerald-600 text-white hover:bg-emerald-700"
                  }`}
                >
                  {updateFilter === "recent"
                    ? "Back to all projects"
                    : "View updated projects"}{" "}
                  <FaArrowRight />
                </button>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {recentlyUpdatedProjects.slice(0, 3).map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => openProjectDetail(project)}
                    className="rounded-xl border border-emerald-100 bg-white/85 p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-md"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="rounded-full bg-emerald-100 px-2 py-1 text-[11px] font-bold text-emerald-700">
                        Updated {formatDateShort(project.latest_update_date)}
                      </span>
                      <span className="text-[11px] font-semibold text-slate-500">
                        {publicUpdateCountLabel(
                          project.public_progress_update_count,
                        )}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm font-bold text-blue-950">
                      {project.title}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-600">
                      {project.latest_update_headline ||
                        "Approved progress update available for review."}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {updateFilter === "recent" && (
          <div className="mb-4 flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 shadow-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="font-semibold">
                Viewing recently updated projects only.
              </span>{" "}
              <span className="text-emerald-700">
                Clear this filter to return to the full public dashboard.
              </span>
            </div>
            <button
              type="button"
              onClick={() => setUpdateFilter("all")}
              className="inline-flex w-fit items-center justify-center rounded-full bg-white px-3 py-1.5 text-xs font-bold text-emerald-700 ring-1 ring-emerald-200 transition hover:bg-emerald-100"
            >
              Show all projects
            </button>
          </div>
        )}
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
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                      setStatusFilter(e.target.value as string)
                    }
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
                    Updates
                  </label>
                  <select
                    className="w-full border-2 border-blue-100 rounded-lg p-2 focus:ring-2 focus:ring-blue-300 transition text-sm"
                    value={updateFilter}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                      setUpdateFilter(e.target.value as "all" | "recent")
                    }
                  >
                    <option value="all">All Projects</option>
                    <option value="recent">Recently Updated</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-semibold text-blue-800 mb-2">
                    Agency
                  </label>
                  <select
                    className="w-full border-2 border-blue-100 rounded-lg p-2 focus:ring-2 focus:ring-blue-300 transition text-sm"
                    value={agencyFilter}
                    onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                      setAgencyFilter(e.target.value as string)
                    }
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
              <React.Suspense fallback={<div className="h-80 animate-pulse rounded-xl bg-slate-100" />}>
                <PublicProjectCharts statusPie={statusPie} agencyBar={agencyBar} yearBar={yearBar} />
              </React.Suspense>
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
                              p.has_public_updates
                                ? "bg-emerald-50/50"
                                : idx % 2 === 0
                                  ? "bg-white"
                                  : "bg-gray-50"
                            }`}
                          >
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">
                              <button
                                type="button"
                                className="text-left hover:underline text-blue-900"
                                onClick={() => openProjectDetail(p)}
                                title="View project details"
                              >
                                {p.title}
                              </button>
                              {p.has_public_updates && (
                                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-bold text-emerald-700">
                                    Updated{" "}
                                    {formatDateShort(p.latest_update_date)}
                                  </span>
                                  <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700">
                                    {publicUpdateCountLabel(
                                      p.public_progress_update_count,
                                    )}
                                  </span>
                                </div>
                              )}
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
                            <td
                              className="px-4 py-3 text-sm text-gray-700"
                              title={projectLocationLabel(p)}
                            >
                              <span className="block max-w-[240px] truncate">
                                {projectLocationLabel(p)}
                              </span>
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
                        {getProjectLgus(detailProject).length > 0
                          ? ` - ${projectLocationLabel(detailProject)}`
                          : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="px-3 py-1.5 border rounded-lg text-sm hover:bg-slate-50"
                      onClick={closeProjectDetail}
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
                        <p className="font-semibold">
                          {detailProject.year ?? "-"}
                        </p>
                      </div>
                      <div className="border rounded-lg p-3">
                        <p className="text-[11px] text-slate-500">Budget</p>
                        <p className="font-semibold text-green-700">
                          {money(detailProject.budget || 0)}
                        </p>
                      </div>
                    </div>

                    {detailProject.has_public_updates && (
                      <div className="rounded-xl border border-emerald-200 bg-gradient-to-r from-emerald-50 to-blue-50 p-4 shadow-sm">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">
                              Latest Approved Update
                            </p>
                            <p className="mt-1 text-sm font-semibold text-slate-900">
                              {detailProject.latest_update_date
                                ? formatDateTime(
                                    detailProject.latest_update_date,
                                  )
                                : "Date unavailable"}
                            </p>
                          </div>
                          <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-emerald-700 shadow-sm">
                            {publicUpdateCountLabel(
                              detailProject.public_progress_update_count,
                            )}
                          </span>
                        </div>
                        <p className="mt-3 text-sm text-slate-700 whitespace-pre-wrap break-words">
                          {detailProject.latest_update_headline ||
                            "A validator-approved progress update is available for this project."}
                        </p>
                        {Array.isArray(detailProject.latest_update_badges) &&
                          detailProject.latest_update_badges.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {detailProject.latest_update_badges.map(
                                (badge) => (
                                  <span
                                    key={badge}
                                    className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800"
                                  >
                                    {badge}
                                  </span>
                                ),
                              )}
                            </div>
                          )}
                      </div>
                    )}

                    <div className="border rounded-lg p-4 bg-slate-50">
                      <p className="text-sm font-semibold text-slate-900 mb-2">
                        Overview
                      </p>
                      <p className="text-sm text-slate-700 whitespace-pre-wrap break-words">
                        {detailProject.public_summary_text?.trim()
                          ? detailProject.public_summary_text
                          : detailProject.description ||
                            "No summary available."}
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
                                <p className="text-[11px] text-slate-500">
                                  Start Year
                                </p>
                                <p className="text-slate-800">
                                  {String(
                                    detailProject.public_key_facts.start_year,
                                  )}
                                </p>
                              </div>
                            ) : null}
                            {detailProject.public_key_facts.end_year ? (
                              <div>
                                <p className="text-[11px] text-slate-500">
                                  End Year
                                </p>
                                <p className="text-slate-800">
                                  {String(
                                    detailProject.public_key_facts.end_year,
                                  )}
                                </p>
                              </div>
                            ) : null}
                            {detailProject.public_key_facts
                              .development_sector ? (
                              <div className="sm:col-span-2">
                                <p className="text-[11px] text-slate-500">
                                  Development Sector
                                </p>
                                <p className="text-slate-800">
                                  {String(
                                    detailProject.public_key_facts
                                      .development_sector,
                                  )}
                                </p>
                              </div>
                            ) : null}
                            {detailProject.public_key_facts.rdp_main_chapter ? (
                              <div className="sm:col-span-2">
                                <p className="text-[11px] text-slate-500">
                                  RDP Main Chapter
                                </p>
                                <p className="text-slate-800">
                                  {String(
                                    detailProject.public_key_facts
                                      .rdp_main_chapter,
                                  )}
                                </p>
                              </div>
                            ) : null}
                            {typeof detailProject.public_key_facts.sdg_count ===
                            "number" ? (
                              <div>
                                <p className="text-[11px] text-slate-500">
                                  SDG Tags
                                </p>
                                <p className="text-slate-800">
                                  {String(
                                    detailProject.public_key_facts.sdg_count,
                                  )}
                                </p>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      )}

                    <div className="border rounded-lg p-4">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-slate-900">
                            Approved Progress Timeline
                          </p>
                          <p className="text-xs text-slate-500 mt-1">
                            Initial endorsement and validator-approved progress
                            updates are shown publicly.
                          </p>
                        </div>
                        <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
                          {publicUpdateCountLabel(
                            detailProject.public_progress_update_count,
                          )}
                        </span>
                      </div>
                      {detailProject.public_update_timeline?.length ? (
                        <div className="mt-4 space-y-3">
                          {detailProject.public_update_timeline.map((item) => (
                            <div
                              key={`${item.revision_number}-${item.endorsed_at || ""}`}
                              className={`rounded-lg border p-3 ${
                                item.revision_type === "progress_update"
                                  ? "border-emerald-200 bg-emerald-50/50"
                                  : "border-slate-200 bg-slate-50"
                              }`}
                            >
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div>
                                  <div className="flex flex-wrap items-center gap-2 text-sm">
                                    <span className="font-semibold text-slate-900">
                                      Version {item.revision_number}
                                    </span>
                                    <span
                                      className={`rounded-full px-2 py-0.5 text-[11px] font-bold ${
                                        item.revision_type === "progress_update"
                                          ? "bg-emerald-100 text-emerald-700"
                                          : "bg-slate-200 text-slate-700"
                                      }`}
                                    >
                                      {item.revision_type === "progress_update"
                                        ? "Progress Update"
                                        : "Initial Endorsement"}
                                    </span>
                                  </div>
                                  <p className="mt-1 text-xs text-slate-500">
                                    {formatDateTime(item.endorsed_at)}
                                  </p>
                                </div>
                              </div>
                              {item.revision_type === "progress_update" && (
                                <p className="mt-3 text-sm text-slate-700 whitespace-pre-wrap break-words">
                                  {item.headline ||
                                    "Approved project progress update recorded."}
                                </p>
                              )}
                              {Array.isArray(item.change_badges) &&
                                item.change_badges.length > 0 && (
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {item.change_badges.map((badge) => (
                                      <span
                                        key={`${item.revision_number}-${badge}`}
                                        className="rounded-full bg-white px-2 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200"
                                      >
                                        {badge}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              <div className="mt-3 grid gap-2 text-xs text-slate-700 sm:grid-cols-2">
                                {item.status ? (
                                  <div className="rounded-md bg-white/80 px-3 py-2 ring-1 ring-slate-100">
                                    <span className="block text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                      Status
                                    </span>
                                    <span className="font-semibold text-slate-800">
                                      {item.status}
                                    </span>
                                  </div>
                                ) : null}
                                {item.budget !== undefined &&
                                item.budget !== "" ? (
                                  <div className="rounded-md bg-white/80 px-3 py-2 ring-1 ring-slate-100">
                                    <span className="block text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                      Funding
                                    </span>
                                    <span className="font-semibold text-emerald-700">
                                      {money(item.budget)}
                                    </span>
                                  </div>
                                ) : null}
                                {item.location ? (
                                  <div className="rounded-md bg-white/80 px-3 py-2 ring-1 ring-slate-100 sm:col-span-2">
                                    <span className="block text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                                      Location
                                    </span>
                                    <span className="text-slate-800">
                                      {item.location}
                                    </span>
                                  </div>
                                ) : null}
                              </div>
                              {item.public_note ? (
                                <p className="mt-2 text-sm text-slate-700 whitespace-pre-wrap break-words">
                                  {item.public_note}
                                </p>
                              ) : null}
                              {item.changed_fields?.length ? (
                                <div className="mt-3 rounded-lg bg-white/70 p-2">
                                  <p className="text-xs font-semibold text-slate-700">
                                    What changed
                                  </p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {item.changed_fields
                                      .slice(0, 8)
                                      .map((field, index) => (
                                        <span
                                          key={`${item.revision_number}-${field.label}-${index}`}
                                          className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-700"
                                        >
                                          {field.label}
                                        </span>
                                      ))}
                                    {item.changed_fields.length > 8 ? (
                                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-500">
                                        +{item.changed_fields.length - 8} more
                                      </span>
                                    ) : null}
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-3 text-sm text-slate-500">
                          No endorsed progress updates have been recorded yet.
                        </p>
                      )}
                    </div>

                    {Array.isArray(detailProject.public_summary_bullets) &&
                      detailProject.public_summary_bullets.length > 0 && (
                        <div className="border rounded-lg p-4">
                          <p className="text-sm font-semibold text-slate-900 mb-2">
                            Highlights
                          </p>
                          <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
                            {detailProject.public_summary_bullets.map(
                              (b, i) => (
                                <li key={`${i}-${b}`} className="break-words">
                                  {b}
                                </li>
                              ),
                            )}
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
                <React.Suspense fallback={<div className="h-[600px] animate-pulse bg-slate-100" />}>
                  <VoronoiBlobMap
                    projects={mapProjects}
                    selectedCity={selectedCity}
                    selectedStatus={statusFilter === "all" ? "all" : statusFilter}
                    onCitySelect={(city) => setMunicipalityFilter(city || "all")}
                    height={600}
                  />
                </React.Suspense>
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
