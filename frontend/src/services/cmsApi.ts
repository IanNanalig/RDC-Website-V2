import { api } from "./api";

export type CMSStatus = "draft" | "published";

export type CMSSection = {
  id: number;
  page: number;
  section_key: string;
  section_type: string;
  order: number;
  content_json: Record<string, unknown>;
  schema_version: number;
  is_visible: boolean;
  created_at: string;
  updated_at: string;
};

export type CMSPage = {
  id: number;
  title: string;
  slug: string;
  status: CMSStatus;
  published_snapshot_json: Record<string, unknown>;
  has_unpublished_changes: boolean;
  sections: CMSSection[];
  published_at?: string | null;
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
  featured: boolean;
  status: CMSStatus;
  published_snapshot_json: Record<string, unknown>;
  has_unpublished_changes: boolean;
  published_at?: string | null;
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

export type CMSArticleSnapshot = {
  title: string;
  slug: string;
  category: string;
  summary: string;
  body: string;
  thumbnailUrl: string;
  featured: boolean;
  author: string;
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

const listFromResponse = <T>(data: unknown): T[] => {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object" && Array.isArray((data as { results?: unknown }).results)) {
    return (data as { results: T[] }).results;
  }
  return [];
};

export const cmsApi = {
  listPages: async () => listFromResponse<CMSPage>(await api.get("admin/cms/pages/")),
  createPage: (payload: Pick<CMSPage, "title" | "slug">) => api.post("admin/cms/pages/", payload),
  updatePage: (id: number, payload: Pick<CMSPage, "title" | "slug">) =>
    api.put(`admin/cms/pages/${id}/`, payload),
  publishPage: (id: number) => api.post(`admin/cms/pages/${id}/publish/`),
  reorderSections: (pageId: number, sectionIds: number[]) =>
    api.post(`admin/cms/pages/${pageId}/reorder_sections/`, { section_ids: sectionIds }),

  listSections: async (pageId?: number) => {
    const query = pageId ? `?page=${pageId}` : "";
    return listFromResponse<CMSSection>(await api.get(`admin/cms/sections/${query}`));
  },
  createSection: (payload: Partial<CMSSection>) => api.post("admin/cms/sections/", payload),
  updateSection: (id: number, payload: Partial<CMSSection>) =>
    api.put(`admin/cms/sections/${id}/`, payload),

  listArticles: async () => listFromResponse<CMSArticle>(await api.get("admin/cms/articles/")),
  createArticle: (payload: Partial<CMSArticle>) => api.post("admin/cms/articles/", payload),
  updateArticle: (id: number, payload: Partial<CMSArticle>) =>
    api.put(`admin/cms/articles/${id}/`, payload),
  publishArticle: (id: number) => api.post(`admin/cms/articles/${id}/publish/`),

  listMedia: async () => listFromResponse<CMSMediaAsset>(await api.get("admin/cms/media/")),
  uploadMedia: (formData: FormData) => api.postForm("admin/cms/media/", formData),
  archiveMedia: (id: number) => api.post(`admin/cms/media/${id}/archive/`),

  getPublicPage: (slug: string) => api.get(`public/cms/pages/${slug}/`) as Promise<CMSPageSnapshot>,
  listPublicNews: async (limit = 20) => {
    const data = await api.get(`public/cms/news/?limit=${limit}`);
    if (data && typeof data === "object" && Array.isArray((data as { results?: unknown }).results)) {
      return (data as { results: CMSArticleSnapshot[] }).results;
    }
    return [];
  },
  getPublicArticle: (slug: string) => api.get(`public/cms/news/${slug}/`) as Promise<CMSArticleSnapshot>,
};

export default cmsApi;
