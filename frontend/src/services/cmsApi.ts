import { api } from "./api";
import { API_BASE_URL } from "../config/api";
import type { ContributorFormPayload, ContributorFormSchema } from "../types/contributorForm";

export type CMSStatus = "draft" | "submitted" | "published" | "rejected" | "archived";

export type CMSSection = {
  id: number;
  page: number;
  section_key: string;
  section_type: string;
  order: number;
  content_json: Record<string, unknown>;
  schema_version: number;
  is_visible: boolean;
  status: CMSStatus;
  lock_owner?: number | null;
  lock_owner_name?: string;
  lock_acquired_at?: string | null;
  lock_expires_at?: string | null;
  is_locked?: boolean;
  locked_by_me?: boolean;
  created_at: string;
  updated_at: string;
};

export type CMSPage = {
  id: number;
  title: string;
  slug: string;
  status: CMSStatus;
  published_snapshot_json?: Record<string, unknown>;
  published_slug?: string;
  section_count?: number;
  has_unpublished_changes: boolean;
  sections: CMSSection[];
  published_at?: string | null;
  archived_at?: string | null;
  review_notes?: string;
  updated_at: string;
};

export type CMSArticle = {
  id: number;
  title: string;
  slug: string;
  category: string;
  summary: string;
  body: string;
  thumbnail?: number | null;
  thumbnail_url?: string;
  author: string;
  publication_date?: string | null;
  featured: boolean;
  status: CMSStatus;
  published_snapshot_json?: Record<string, unknown>;
  published_slug?: string;
  has_unpublished_changes: boolean;
  published_at?: string | null;
  archived_at?: string | null;
  review_notes?: string;
  updated_at: string;
};

export type CMSMediaAsset = {
  id: number;
  file?: string;
  url: string;
  file_type: "image" | "document" | "other";
  mime_type: string;
  size: number;
  alt_text: string;
  caption: string;
  is_archived: boolean;
  used_by?: Array<{
    type: string;
    title: string;
    slug: string;
    location: string;
    is_public: boolean;
  }>;
  usage_count?: number;
  can_archive?: boolean;
  created_at: string;
};

export type CMSRevision = {
  id: number;
  content_type: "page" | "article" | "section" | "media" | "form";
  object_id: number;
  version_number: number;
  action: string;
  status_before: string;
  status_after: string;
  snapshot_json: Record<string, unknown>;
  changed_by_name: string;
  is_target_deleted: boolean;
  created_at: string;
};

export type CMSSiteSetting = {
  id: number;
  key: string;
  value_json: unknown;
  description: string;
  updated_by_name?: string;
  updated_at: string;
};

export type CMSContributorForm = {
  id: number;
  key: string;
  name: string;
  description: string;
  status: CMSStatus;
  draft_schema_json: ContributorFormSchema;
  current_published_version?: number | null;
  current_published_version_number?: number | null;
  has_unpublished_changes: boolean;
  updated_by_name?: string;
  submitted_by_name?: string;
  reviewed_by_name?: string;
  review_notes?: string;
  published_at?: string | null;
  lock_owner?: number | null;
  lock_owner_name?: string;
  lock_acquired_at?: string | null;
  lock_expires_at?: string | null;
  is_locked?: boolean;
  locked_by_me?: boolean;
  updated_at: string;
};

export type CMSContributorFormVersion = {
  id: number;
  form: number;
  version_number: number;
  schema_json: ContributorFormSchema;
  published_by_name?: string;
  published_at: string;
};

export type CMSReviewQueue = {
  pages: CMSPage[];
  sections: CMSSection[];
  news: CMSArticle[];
  events: Array<Record<string, unknown>>;
  forms: CMSContributorForm[];
};

export type CMSAIOutcomeRule = {
  key: string;
  label: string;
  weight: number;
  keywords: string[];
  description: string;
  matching_guidance: string;
  match_mode: "keyword" | "contextual";
  context_phrases: string[];
};

export type CMSAIScaleRule = {
  key: string;
  raw: number;
  guideline: string;
};

export type CMSAIRuleConfig = {
  thresholds: {
    high: number;
    regional_project_cost: number;
    pap_weights: {
      readiness: number;
      gad_responsiveness: number;
      spatial_coverage: number;
    };
  };
  sector_criteria: Record<string, CMSAIOutcomeRule[]>;
  keyword_dictionaries: {
    common_outcomes: CMSAIOutcomeRule[];
    negative_rules: Array<{ key: string; label: string; keywords: string[] }>;
    readiness: CMSAIScaleRule[];
    gad: CMSAIScaleRule[];
    outcome_rating: {
      chapter_and_two_keywords: number;
      chapter_or_three_keywords: number;
      one_keyword: number;
      no_keywords: number;
    };
    guidelines: string[];
  };
};

export type CMSAIHistoricalProject = {
  confirmation_id: number;
  project_id: number;
  project_title: string;
  agency: string;
  sector: string;
  submission_type: string;
  project_status: string;
  suggested_priority: string;
  final_priority: string;
  base_score: number;
  rule_version: string;
  validator_name: string;
  override_rationale: string;
  confirmed_at: string;
  training_record_id?: number;
  training_eligible?: boolean;
  in_active_reference?: boolean;
  exclusion_reason?: string;
};

export type CMSAIModelVersion = {
  id: number;
  version: string;
  algorithm: string;
  feature_schema_version: string;
  dataset_version: string;
  sample_count: number;
  class_labels: string[];
  feature_names: string[];
  metrics: {
    accuracy?: number | null;
    sample_count?: number;
    held_out_count?: number;
    evaluation_scope?: string;
    warning?: string;
    label_counts?: Record<string, number>;
  };
  status: "active" | "retired";
  trained_by_name: string;
  created_at: string;
};

export type CMSAITrainingDataset = {
  candidate_count: number;
  eligible_project_count: number;
  excluded_count: number;
  label_counts: Record<"low" | "high", number> & { medium?: number };
  minimum_projects: number;
  required_labels: string[];
  ready_to_train: boolean;
  dataset_version?: string;
  active_dataset_version?: string;
  active_model_version?: string;
  active_sample_count?: number;
  last_trained_at?: string | null;
  is_current?: boolean;
  requires_retraining?: boolean;
};

export type CMSAIScoringWorkspace = {
  system_type: "groq_rag_rules" | "hybrid_rules_similarity_ml" | "deterministic_rule_based";
  learns_from_historical_projects: boolean;
  learning_explanation: string;
  ai_provider?: {
    name: "groq" | "local";
    enabled: boolean;
    primary_model: string;
    backup_model: string;
    historical_mode: "retrieval_augmented_generation" | "versioned_rag_calibration" | "trained_local_model";
  };
  rag_pipeline?: {
    rules_primary: boolean;
    hosted_model_fine_tuned: boolean;
    retrieval_limit: number;
    reference_model_version: string;
    dataset_version: string;
    reference_dataset_current: boolean;
    requires_retraining: boolean;
    steps: Array<{
      key: string;
      title: string;
      description: string;
    }>;
  };
  active_rule_set: {
    id: number;
    version: string;
    algorithm_version: string;
    created_at: string;
    config: CMSAIRuleConfig;
    draft_config?: CMSAIRuleConfig;
  };
  rule_versions: Array<{
    id: number;
    version: string;
    algorithm_version: string;
    is_active: boolean;
    analysis_count: number;
    created_at: string;
  }>;
  historical_projects: CMSAIHistoricalProject[];
  historical_count: number;
  training_dataset?: CMSAITrainingDataset;
  active_model?: CMSAIModelVersion | null;
  model_versions?: CMSAIModelVersion[];
  detail?: string;
};

export type CMSArticleSnapshot = {
  title: string;
  slug: string;
  category: string;
  summary: string;
  body: string;
  thumbnailUrl: string;
  featured: boolean;
  author: string;
  publicationDate?: string;
  publishedAt: string;
};

export type CMSPageSnapshot = {
  title: string;
  slug: string;
  publishedAt: string;
  sections: Array<{
    sectionKey: string;
    sectionType: string;
    order: number;
    schemaVersion: number;
    content: Record<string, unknown>;
  }>;
};

export const resolveCmsMediaUrl = (value?: string | null) => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (/^(data:|blob:)/i.test(raw)) return raw;

  try {
    const browserOrigin =
      typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1";
    const apiOrigin = new URL(API_BASE_URL, browserOrigin).origin;
    const parsed = new URL(raw, apiOrigin);
    if (parsed.pathname.startsWith("/media/")) {
      return new URL(`${parsed.pathname}${parsed.search}`, apiOrigin).toString();
    }
    return /^(https?:)/i.test(raw)
      ? raw
      : new URL(raw.startsWith("/") ? raw : `/${raw}`, apiOrigin).toString();
  } catch {
    return raw;
  }
};

const normalizeCmsValue = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(normalizeCmsValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, child]) => [
        key,
        normalizeCmsValue(child),
      ]),
    );
  }
  if (typeof value === "string" && /(?:^\/media\/|\/media\/)/i.test(value)) {
    return resolveCmsMediaUrl(value);
  }
  return value;
};

const normalizeArticleSnapshot = (article: CMSArticleSnapshot): CMSArticleSnapshot => ({
  ...article,
  thumbnailUrl: resolveCmsMediaUrl(article.thumbnailUrl),
});

const listFromResponse = <T>(data: unknown): T[] => {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object" && Array.isArray((data as { results?: unknown }).results)) {
    return (data as { results: T[] }).results;
  }
  return [];
};

const summaryQuery = (params: Record<string, string | number | undefined> = {}) => {
  const query = new URLSearchParams({ view: "summary", page_size: "30" });
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && String(value).trim()) query.set(key, String(value));
  });
  return query.toString();
};

export const cmsApi = {
  listPages: async (search = "", page = 1) =>
    listFromResponse<CMSPage>(await api.get(`admin/cms/pages/?${summaryQuery({ q: search, page })}`)),
  getPage: (id: number) => api.get(`admin/cms/pages/${id}/?view=editor`) as Promise<CMSPage>,
  createPage: (payload: Pick<CMSPage, "title" | "slug">) => api.post("admin/cms/pages/", payload),
  updatePage: (id: number, payload: Pick<CMSPage, "title" | "slug">) =>
    api.put(`admin/cms/pages/${id}/`, payload),
  publishPage: (id: number) => api.post(`admin/cms/pages/${id}/publish/`),
  submitPage: (id: number) => api.post(`admin/cms/pages/${id}/submit/`),
  rejectPage: (id: number, remarks = "") => api.post(`admin/cms/pages/${id}/reject/`, { remarks }),
  archivePage: (id: number) => api.post(`admin/cms/pages/${id}/archive/`),
  reorderSections: (pageId: number, sectionIds: number[]) =>
    api.post(`admin/cms/pages/${pageId}/reorder_sections/`, { section_ids: sectionIds }),

  listSections: async (pageId?: number) => {
    const query = pageId ? `?page=${pageId}` : "";
    return listFromResponse<CMSSection>(await api.get(`admin/cms/sections/${query}`));
  },
  createSection: (payload: Partial<CMSSection>) => api.post("admin/cms/sections/", payload),
  updateSection: (id: number, payload: Partial<CMSSection>) =>
    api.put(`admin/cms/sections/${id}/`, payload),
  lockSection: (id: number) => api.post(`admin/cms/sections/${id}/lock/`),
  unlockSection: (id: number) => api.post(`admin/cms/sections/${id}/unlock/`),
  heartbeatSection: (id: number) => api.post(`admin/cms/sections/${id}/heartbeat/`),
  requestSectionAccess: (id: number) => api.post(`admin/cms/sections/${id}/request-access/`),
  submitSection: (id: number) => api.post(`admin/cms/sections/${id}/submit/`),
  publishSection: (id: number) => api.post(`admin/cms/sections/${id}/publish/`),
  rejectSection: (id: number, remarks = "") => api.post(`admin/cms/sections/${id}/reject/`, { remarks }),
  archiveSection: (id: number) => api.post(`admin/cms/sections/${id}/archive/`),

  listArticles: async (search = "", page = 1) =>
    listFromResponse<CMSArticle>(await api.get(`admin/cms/articles/?${summaryQuery({ q: search, page })}`)),
  getArticle: (id: number) => api.get(`admin/cms/articles/${id}/?view=editor`) as Promise<CMSArticle>,
  createArticle: (payload: Partial<CMSArticle>) => api.post("admin/cms/articles/", payload),
  updateArticle: (id: number, payload: Partial<CMSArticle>) =>
    api.put(`admin/cms/articles/${id}/`, payload),
  publishArticle: (id: number) => api.post(`admin/cms/articles/${id}/publish/`),
  submitArticle: (id: number) => api.post(`admin/cms/articles/${id}/submit/`),
  rejectArticle: (id: number, remarks = "") => api.post(`admin/cms/articles/${id}/reject/`, { remarks }),
  archiveArticle: (id: number) => api.post(`admin/cms/articles/${id}/archive/`),

  listContributorForms: async () =>
    listFromResponse<CMSContributorForm>(await api.get("admin/cms/forms/")),
  updateContributorForm: (
    id: number,
    payload: {
      name: string;
      description: string;
      draft_schema_json: ContributorFormSchema;
      expected_updated_at: string;
      edit_mode: "update" | "change";
    },
  ) => api.patch(`admin/cms/forms/${id}/`, payload),
  lockContributorForm: (id: number) => api.post(`admin/cms/forms/${id}/lock/`),
  unlockContributorForm: (id: number) => api.post(`admin/cms/forms/${id}/unlock/`),
  heartbeatContributorForm: (id: number) => api.post(`admin/cms/forms/${id}/heartbeat/`),
  requestContributorFormAccess: (id: number) => api.post(`admin/cms/forms/${id}/request-access/`),
  submitContributorForm: (id: number) => api.post(`admin/cms/forms/${id}/submit/`),
  publishContributorForm: (id: number) => api.post(`admin/cms/forms/${id}/publish/`),
  rejectContributorForm: (id: number, remarks = "") =>
    api.post(`admin/cms/forms/${id}/reject/`, { remarks }),
  listContributorFormVersions: async (id: number) =>
    listFromResponse<CMSContributorFormVersion>(await api.get(`admin/cms/forms/${id}/versions/`)),
  restoreContributorFormVersion: (id: number, versionId: number) =>
    api.post(`admin/cms/forms/${id}/restore-version/`, { version_id: versionId }),

  getContributorForm: (key = "simplified-rdip") =>
    api.get(`contributor-forms/${key}/current/`) as Promise<ContributorFormPayload>,
  getContributorFormVersion: (key: string, version: number) =>
    api.get(`contributor-forms/${key}/versions/${version}/`) as Promise<ContributorFormPayload>,

  listMedia: async (search = "", page = 1) =>
    listFromResponse<CMSMediaAsset>(await api.get(`admin/cms/media/?${summaryQuery({ q: search, page })}`)).map((asset) => ({
      ...asset,
      file: resolveCmsMediaUrl(asset.file),
      url: resolveCmsMediaUrl(asset.url),
    })),
  uploadMedia: (formData: FormData) => api.postForm("admin/cms/media/", formData),
  archiveMedia: (id: number) => api.post(`admin/cms/media/${id}/archive/`),

  listSettings: async () => listFromResponse<CMSSiteSetting>(await api.get("admin/cms/settings/")),
  updateSetting: (key: string, payload: Pick<CMSSiteSetting, "value_json" | "description">) =>
    api.patch(`admin/cms/settings/${key}/`, payload),
  listRevisions: async (search = "", page = 1) =>
    listFromResponse<CMSRevision>(await api.get(`admin/cms/revisions/?${summaryQuery({ q: search, page })}`)),
  restoreRevision: (id: number) => api.post(`admin/cms/revisions/${id}/restore-revision/`),
  getReviewQueue: () => api.get("admin/cms/review-queue/?view=summary") as Promise<CMSReviewQueue>,
  getAIScoringWorkspace: () => api.get("admin/cms/ai-scoring/?limit=200") as Promise<CMSAIScoringWorkspace>,
  activateAIScoringRules: (config: CMSAIRuleConfig, changeNote: string) =>
    api.post("admin/cms/ai-scoring/", { config, change_note: changeNote }) as Promise<CMSAIScoringWorkspace>,
  trainAIModel: () => api.post("admin/ai/models/train/", {}),
  updateAITrainingRecord: (id: number, isEligible: boolean, exclusionReason = "") =>
    api.patch(`admin/ai/training-data/${id}/`, {
      is_eligible: isEligible,
      exclusion_reason: exclusionReason,
    }),

  getPublicPage: (slug: string) =>
    api
      .get(`public/cms/pages/${slug}/`)
      .then((page) => normalizeCmsValue(page) as CMSPageSnapshot),
  listPublicNews: async (limit = 20) => {
    const data = await api.get(`public/cms/news/?limit=${limit}`);
    if (data && typeof data === "object" && Array.isArray((data as { results?: unknown }).results)) {
      return (data as { results: CMSArticleSnapshot[] }).results.map(normalizeArticleSnapshot);
    }
    return [];
  },
  getPublicArticle: async (slug: string) =>
    normalizeArticleSnapshot(
      (await api.get(`public/cms/news/${slug}/`)) as CMSArticleSnapshot,
    ),
  getPublicSettings: () => api.get("public/cms/site-settings/"),
};

export default cmsApi;
