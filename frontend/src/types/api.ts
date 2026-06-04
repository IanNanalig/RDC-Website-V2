export type PublicProject = {
  id: number;
  title: string;
  agency: string;
  implementation_status: string;
  budget: number;
  year: number | null;
  lgu: string | null;
  lgus?: string[];
  location_raw?: string;
  description: string;
  public_summary_text?: string;
  public_summary_bullets?: string[];
  public_key_facts?: Record<string, unknown>;
  last_endorsed_update_at?: string | null;
  endorsed_update_count?: number;
  has_public_updates?: boolean;
  public_progress_update_count?: number;
  latest_update_date?: string | null;
  latest_update_headline?: string;
  latest_update_badges?: string[];
  public_update_timeline?: Array<{
    revision_number: number;
    revision_type: string;
    endorsed_at?: string | null;
    status?: string;
    budget?: string | number;
    location?: string;
    changed_fields?: Array<{ label: string; category?: string; before?: string; after?: string }>;
    change_badges?: string[];
    headline?: string;
    public_note?: string;
  }>;
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
  cacheBust?: boolean;
};
