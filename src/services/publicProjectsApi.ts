import api from "./api";

export type PublicProject = {
  id: number;
  title: string;
  agency: string;
  implementation_status: string;
  budget: number;
  year: number | null;
  lgu: string | null;
  location_raw?: string;
  description: string;
  public_summary_text?: string;
  public_summary_bullets?: string[];
  public_key_facts?: Record<string, any>;
  updated_at: string;
};

export type PublicProjectsStats = {
  total_projects: number;
  total_budget: number;
  by_status: Record<string, number>;
  by_agency: Record<string, number>;
  by_lgu: Record<string, number>;
  unspecified_location_count: number;
};

export type PublicProjectsFilters = {
  q?: string;
  agency?: string;
  lgu?: string;
  year?: number | "all";
  status?: string | "all";
  limit?: number;
  offset?: number;
};

function buildQuery(filters: PublicProjectsFilters) {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.agency && filters.agency !== "all") params.set("agency", filters.agency);
  if (filters.lgu && filters.lgu !== "all") params.set("lgu", filters.lgu);
  if (filters.year !== undefined && filters.year !== "all" && filters.year !== null) params.set("year", String(filters.year));
  if (filters.status && filters.status !== "all") params.set("status", filters.status);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function getPublicProjects(filters: PublicProjectsFilters = {}) {
  const qs = buildQuery(filters);
  return api.get(`public/projects/${qs}`) as Promise<PublicProject[]>;
}

export async function getPublicProject(id: number) {
  return api.get(`public/projects/${id}/`) as Promise<PublicProject>;
}

export async function getPublicProjectsStats(filters: PublicProjectsFilters = {}) {
  const qs = buildQuery(filters);
  return api.get(`public/projects/stats/${qs}`) as Promise<PublicProjectsStats>;
}
