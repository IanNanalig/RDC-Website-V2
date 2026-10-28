import React, { useEffect, useMemo, useRef, useState } from "react";
import PortalLayout from "../../components/portal/PortalLayout";
import { api } from "../../services/api";
import { userDisplayName } from "../../utils/userDisplayName";

type ExportCategory = "projects" | "users";
type ExportFormat = "csv" | "pdf";
type Option = { value: string; label: string };
type ExportOptions = Record<string, Option[]>;
type Filters = Record<string, string>;

const projectDefaults: Filters = {
  search: "",
  agency: "",
  budget_min: "",
  budget_max: "",
  start_year: "",
  end_year: "",
  workflow_status: "",
  implementation_status: "",
  development_sector: "",
  convergence_program: "",
  funding_source: "",
  rdp_main_chapter: "",
  archive_state: "active",
};

const userDefaults: Filters = {
  search: "",
  role: "",
  agency: "",
  account_status: "",
};

const filterLabels: Record<string, string> = {
  search: "Search",
  agency: "Agency",
  budget_min: "Minimum Budget",
  budget_max: "Maximum Budget",
  start_year: "Start Year",
  end_year: "End Year",
  workflow_status: "Workflow Status",
  implementation_status: "Implementation Status",
  development_sector: "Development Sector",
  convergence_program: "Convergence Program",
  funding_source: "Funding Source",
  rdp_main_chapter: "RDP-NCR Main Chapter",
  archive_state: "Archive State",
  role: "Role",
  account_status: "Account Status",
};

const optionGroupByFilter: Record<string, string> = {
  agency: "agencies",
  workflow_status: "workflow_statuses",
  implementation_status: "implementation_statuses",
  development_sector: "development_sectors",
  convergence_program: "convergence_programs",
  funding_source: "funding_sources",
  rdp_main_chapter: "rdp_main_chapters",
  archive_state: "archive_states",
  role: "roles",
  account_status: "account_statuses",
};

const SelectFilter = ({ label, value, options, onChange, allLabel = "All" }: {
  label: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  allLabel?: string;
}) => (
  <label className="block min-w-0">
    <span className="text-xs font-semibold text-slate-600">{label}</span>
    <select
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800"
    >
      <option value="">{allLabel}</option>
      {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  </label>
);

const AdminDataExports: React.FC = () => {
  const storedUser = useMemo(() => {
    try { return JSON.parse(localStorage.getItem("user") || "{}"); } catch { return {}; }
  }, []);
  const [category, setCategory] = useState<ExportCategory>("projects");
  const [format, setFormat] = useState<ExportFormat>("csv");
  const [filters, setFilters] = useState<Filters>(projectDefaults);
  const [options, setOptions] = useState<ExportOptions>({});
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [count, setCount] = useState<number | null>(null);
  const [countLoading, setCountLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const optionsRequest = useRef(0);
  const countRequest = useRef(0);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({ category });
    Object.entries(filters).forEach(([key, value]) => {
      const clean = value.trim();
      if (clean) params.set(key, clean);
    });
    return params.toString();
  }, [category, filters]);

  useEffect(() => {
    const requestId = ++optionsRequest.current;
    setOptionsLoading(true);
    setError("");
    void api.get(`admin/exports/options/?category=${category}`, true)
      .then((data) => {
        if (requestId === optionsRequest.current) setOptions(data?.options || {});
      })
      .catch((reason) => {
        if (requestId === optionsRequest.current) {
          setOptions({});
          setError(reason instanceof Error ? reason.message : "Export options could not be loaded.");
        }
      })
      .finally(() => {
        if (requestId === optionsRequest.current) setOptionsLoading(false);
      });
  }, [category]);

  useEffect(() => {
    const requestId = ++countRequest.current;
    setCountLoading(true);
    setCount(null);
    setNotice("");
    const timer = window.setTimeout(() => {
      void api.get(`admin/exports/count/?${queryString}`, true)
        .then((data) => {
          if (requestId === countRequest.current) {
            setCount(Number(data?.count || 0));
            setError("");
          }
        })
        .catch((reason) => {
          if (requestId === countRequest.current) {
            setCount(null);
            setError(reason instanceof Error ? reason.message : "Matching records could not be counted.");
          }
        })
        .finally(() => {
          if (requestId === countRequest.current) setCountLoading(false);
        });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [queryString]);

  const setFilter = (key: string, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setNotice("");
  };

  const switchCategory = (next: ExportCategory) => {
    if (next === category) return;
    setCategory(next);
    setFilters(next === "projects" ? projectDefaults : userDefaults);
    setFormat("csv");
    setOptions({});
    setCount(null);
    setNotice("");
    setError("");
  };

  const clearFilters = () => {
    setFilters(category === "projects" ? projectDefaults : userDefaults);
    setNotice("");
    setError("");
  };

  const selectedCriteria = useMemo(() => Object.entries(filters)
    .filter(([, value]) => value.trim())
    .map(([key, value]) => {
      const group = optionGroupByFilter[key];
      const display = options[group]?.find((option) => option.value === value)?.label || value;
      return { key, label: filterLabels[key] || key, value: display };
    }),
  [filters, options]);

  const generateExport = async () => {
    if (!count || exporting) return;
    setExporting(true);
    setError("");
    setNotice("");
    try {
      const result = await api.download(`admin/exports/download/?${queryString}&file_format=${format}`);
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setNotice(`${category === "projects" ? "Project" : "User"} export downloaded successfully.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The export could not be generated.");
    } finally {
      setExporting(false);
    }
  };

  const selectOptions = (group: string) => options[group] || [];
  const inputClass = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800";

  return (
    <PortalLayout
      title="Data Exports"
      subtitle="Create filtered project and user reports"
      role="admin"
      userName={userDisplayName(storedUser, "Admin")}
    >
      <div className="portal-card mb-4">
        <div className="portal-card-header">
          <h2 className="text-lg font-semibold text-slate-900">Choose records</h2>
          <p className="mt-1 text-sm text-slate-500">Only records matching every selected filter will be exported.</p>
        </div>
        <div className="portal-card-body">
          <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1 sm:max-w-md" role="group" aria-label="Export category">
            {(["projects", "users"] as ExportCategory[]).map((item) => (
              <button
                type="button"
                key={item}
                aria-pressed={category === item}
                onClick={() => switchCategory(item)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${category === item ? "bg-white text-blue-700 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
              >
                {item === "projects" ? "Projects" : "Users"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="portal-card mb-4">
        <div className="portal-card-header flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{category === "projects" ? "Project" : "User"} filters</h2>
            <p className="mt-1 text-xs text-slate-500">Filter choices come from current system records.</p>
          </div>
          <button type="button" onClick={clearFilters} className="portal-btn portal-btn-ghost">Clear Filters</button>
        </div>
        <div className="portal-card-body">
          {optionsLoading ? <p className="text-sm text-slate-500">Loading filter options...</p> : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <label className="block min-w-0 xl:col-span-2">
                <span className="text-xs font-semibold text-slate-600">Search</span>
                <input
                  type="search"
                  aria-label="Search"
                  value={filters.search}
                  onChange={(event) => setFilter("search", event.target.value)}
                  placeholder={category === "projects" ? "Title, description, agency, or contributor" : "Name, username, or email"}
                  className={inputClass}
                />
              </label>
              <SelectFilter label="Agency" value={filters.agency} options={selectOptions("agencies")} onChange={(value) => setFilter("agency", value)} allLabel="All agencies" />
              {category === "projects" ? <>
                <SelectFilter label="Archive State" value={filters.archive_state} options={selectOptions("archive_states")} onChange={(value) => setFilter("archive_state", value)} allLabel="Select archive state" />
                <label className="block min-w-0">
                  <span className="text-xs font-semibold text-slate-600">Minimum Budget (PHP)</span>
                  <input type="number" min="0" step="1" aria-label="Minimum Budget" value={filters.budget_min} onChange={(event) => setFilter("budget_min", event.target.value)} className={inputClass} placeholder="0" />
                </label>
                <label className="block min-w-0">
                  <span className="text-xs font-semibold text-slate-600">Maximum Budget (PHP)</span>
                  <input type="number" min="0" step="1" aria-label="Maximum Budget" value={filters.budget_max} onChange={(event) => setFilter("budget_max", event.target.value)} className={inputClass} placeholder="No maximum" />
                </label>
                <label className="block min-w-0">
                  <span className="text-xs font-semibold text-slate-600">Start Year</span>
                  <input type="number" min="1900" max="2200" step="1" aria-label="Start Year" value={filters.start_year} onChange={(event) => setFilter("start_year", event.target.value)} className={inputClass} placeholder="Any year" />
                </label>
                <label className="block min-w-0">
                  <span className="text-xs font-semibold text-slate-600">End Year</span>
                  <input type="number" min="1900" max="2200" step="1" aria-label="End Year" value={filters.end_year} onChange={(event) => setFilter("end_year", event.target.value)} className={inputClass} placeholder="Any year" />
                </label>
                <SelectFilter label="Workflow Status" value={filters.workflow_status} options={selectOptions("workflow_statuses")} onChange={(value) => setFilter("workflow_status", value)} allLabel="All workflow statuses" />
                <SelectFilter label="Implementation Status" value={filters.implementation_status} options={selectOptions("implementation_statuses")} onChange={(value) => setFilter("implementation_status", value)} allLabel="All implementation statuses" />
                <SelectFilter label="Development Sector" value={filters.development_sector} options={selectOptions("development_sectors")} onChange={(value) => setFilter("development_sector", value)} allLabel="All development sectors" />
                <SelectFilter label="Convergence Program" value={filters.convergence_program} options={selectOptions("convergence_programs")} onChange={(value) => setFilter("convergence_program", value)} allLabel="All convergence programs" />
                <SelectFilter label="Funding Source" value={filters.funding_source} options={selectOptions("funding_sources")} onChange={(value) => setFilter("funding_source", value)} allLabel="All funding sources" />
                <SelectFilter label="RDP-NCR Main Chapter" value={filters.rdp_main_chapter} options={selectOptions("rdp_main_chapters")} onChange={(value) => setFilter("rdp_main_chapter", value)} allLabel="All chapters" />
              </> : <>
                <SelectFilter label="Role" value={filters.role} options={selectOptions("roles")} onChange={(value) => setFilter("role", value)} allLabel="All roles" />
                <SelectFilter label="Account Status" value={filters.account_status} options={selectOptions("account_statuses")} onChange={(value) => setFilter("account_status", value)} allLabel="All account statuses" />
              </>}
            </div>
          )}
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-header">
          <h2 className="text-lg font-semibold text-slate-900">Review and download</h2>
        </div>
        <div className="portal-card-body space-y-4">
          {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p>}
          {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Selected criteria</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {selectedCriteria.map((criterion) => (
                <span key={criterion.key} className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-800">
                  {criterion.label}: {criterion.value}
                </span>
              ))}
              {selectedCriteria.length === 0 && <span className="text-sm text-slate-500">All {category}</span>}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(260px,auto)] md:items-end">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Matching records</p>
              <p className="mt-1 text-3xl font-bold text-slate-900" aria-live="polite">
                {countLoading ? "..." : count === null ? "Unavailable" : count.toLocaleString()}
              </p>
              {!countLoading && count === 0 && <p className="mt-1 text-sm text-amber-700">No records match the selected criteria.</p>}
            </div>
            <div className="space-y-3">
              <fieldset>
                <legend className="text-xs font-semibold uppercase tracking-wide text-slate-500">File format</legend>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {(["csv", "pdf"] as ExportFormat[]).map((item) => (
                    <label key={item} className={`cursor-pointer rounded-lg border px-4 py-2 text-center text-sm font-semibold ${format === item ? "border-blue-500 bg-blue-50 text-blue-700" : "border-slate-300 bg-white text-slate-700"}`}>
                      <input type="radio" name="export-format" value={item} checked={format === item} onChange={() => setFormat(item)} className="sr-only" />
                      {item.toUpperCase()}
                    </label>
                  ))}
                </div>
              </fieldset>
              <button
                type="button"
                onClick={() => void generateExport()}
                disabled={exporting || countLoading || !count || Boolean(error)}
                className="portal-btn portal-btn-primary w-full justify-center disabled:cursor-not-allowed disabled:opacity-50"
              >
                {exporting ? "Generating Export..." : `Generate ${format.toUpperCase()}`}
              </button>
            </div>
          </div>
        </div>
      </div>
    </PortalLayout>
  );
};

export default AdminDataExports;
