import { api } from "./api";

export type PublicPageContent = {
  id: number;
  page: string;
  page_label: string;
  section_key: string;
  title: string;
  subtitle: string;
  body: string;
  image_url: string;
  cta_label: string;
  cta_url: string;
  metadata: Record<string, unknown>;
  published_at?: string;
  updated_at: string;
};

type PageContentFilters = {
  page?: string;
  sectionKey?: string;
};

export async function getPublicPageContent(filters: PageContentFilters = {}) {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", filters.page);
  if (filters.sectionKey) params.set("section_key", filters.sectionKey);
  const qs = params.toString();
  const data = await api.get(`public/page-content/${qs ? `?${qs}` : ""}`);
  return Array.isArray(data?.results) ? (data.results as PublicPageContent[]) : [];
}

export function contentBySection(items: PublicPageContent[]) {
  return items.reduce<Record<string, PublicPageContent>>((acc, item) => {
    acc[item.section_key] = item;
    return acc;
  }, {});
}
