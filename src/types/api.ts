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
  public_key_facts?: Record<string, unknown>;
  updated_at: string;
};

export type PublicProjectsStats = {
  total_projects: number;
  total_budget: number;
  by_status: Record<string, number>;
  by_agency: Record<string, number>;
  by_lgu: Record<string, number>;
  by_year?: Record<string, number>;
  unspecified_location_count: number;
  last_updated_at?: string | null;
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
