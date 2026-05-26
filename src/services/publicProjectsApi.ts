import api from "./api";
import type { PublicProject, PublicProjectsFilters, PublicProjectsStats } from "../types/api";

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
