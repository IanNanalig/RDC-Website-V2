import { api } from "./api";

export type PublicEvent = {
  id: number;
  title: string;
  description: string;
  event_type: string;
  start_at: string;
  end_at?: string;
  day?: number;
  month?: string;
  time?: string;
  end_time?: string;
  location: string;
  is_virtual: boolean;
  meeting_link: string;
  status: "published";
};

type EventFilters = {
  limit?: number;
  includePast?: boolean;
  type?: string;
  month?: string;
  q?: string;
};

export async function getPublicEvents(filters: EventFilters = {}) {
  const params = new URLSearchParams();
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.includePast) params.set("include_past", "1");
  if (filters.type) params.set("type", filters.type);
  if (filters.month) params.set("month", filters.month);
  if (filters.q) params.set("q", filters.q);
  const qs = params.toString();
  const data = await api.get(`public/events/${qs ? `?${qs}` : ""}`);
  return Array.isArray(data?.results) ? (data.results as PublicEvent[]) : [];
}
