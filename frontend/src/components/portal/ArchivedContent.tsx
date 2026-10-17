import { useCallback, useEffect, useState } from "react";
import { api } from "../../services/api";

type ArchivedItem = { id: number; title?: string; name?: string; section_key?: string; key?: string; caption?: string; original_filename?: string; status?: string; [key: string]: unknown };
type Group = { label: string; endpoint: string; detail: (id: number) => string; restore: (id: number) => string };

const groups: Group[] = [
  { label: "Pages", endpoint: "admin/cms/pages/?view=summary&archived=1", detail: (id) => `admin/cms/pages/${id}/`, restore: (id) => `admin/cms/pages/${id}/restore/` },
  { label: "Page Sections", endpoint: "admin/cms/sections/?archived=1", detail: (id) => `admin/cms/sections/${id}/`, restore: (id) => `admin/cms/sections/${id}/restore/` },
  { label: "News", endpoint: "admin/cms/articles/?view=summary&archived=1", detail: (id) => `admin/cms/articles/${id}/`, restore: (id) => `admin/cms/articles/${id}/restore/` },
  { label: "Events", endpoint: "admin/cms/events/?archived=1", detail: (id) => `admin/cms/events/${id}/`, restore: (id) => `admin/cms/events/${id}/unarchive/` },
  { label: "Media", endpoint: "admin/cms/media/?view=summary&archived=1", detail: (id) => `admin/cms/media/${id}/`, restore: (id) => `admin/cms/media/${id}/restore/` },
  { label: "Contributor Forms", endpoint: "admin/cms/forms/?archived=1", detail: (id) => `admin/cms/forms/${id}/`, restore: (id) => `admin/cms/forms/${id}/restore/` },
];

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const display = (value: unknown) => typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : "";
const niceLabel = (value: string) => value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

async function fetchGroup(endpoint: string): Promise<ArchivedItem[]> {
  const rows: ArchivedItem[] = [];
  let page = 1;
  while (true) {
    const separator = endpoint.includes("?") ? "&" : "?";
    const result = await api.get(`${endpoint}${separator}page=${page}`) as ArchivedItem[] | { results: ArchivedItem[]; next?: string | null };
    if (Array.isArray(result)) return result;
    rows.push(...(result.results || []));
    if (!result.next) return rows;
    page += 1;
  }
}

export default function ArchivedContent({ isAdmin }: { isAdmin: boolean }) {
  const [items, setItems] = useState<Record<string, ArchivedItem[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [selected, setSelected] = useState<{ group: Group; item: ArchivedItem; detail: ArchivedItem } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const results = await Promise.all(groups.map(async (group) => [group.label, await fetchGroup(group.endpoint)] as const));
      setItems(Object.fromEntries(results));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Archived items could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const restore = async (group: Group, id: number) => {
    setBusyId(`${group.label}-${id}`);
    setError("");
    try {
      await api.post(group.restore(id), {});
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Restore failed.");
    } finally {
      setBusyId("");
    }
  };

  const viewDetails = async (group: Group, item: ArchivedItem) => {
    setSelected({ group, item, detail: item });
    setDetailLoading(true);
    setError("");
    try {
      const detail = await api.get(group.detail(item.id)) as ArchivedItem;
      setSelected({ group, item, detail });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Archived item details could not be loaded.");
    } finally {
      setDetailLoading(false);
    }
  };

  const pageSections = Array.isArray(selected?.detail.sections) ? selected.detail.sections.map(record) : [];

  return <div className="space-y-4">
    <div className="portal-card"><div className="portal-card-header flex items-center justify-between gap-2"><div><h2 className="font-bold">Archived Content</h2><p className="text-sm text-slate-500">Restored items return as drafts and must be published again.</p></div><button type="button" onClick={() => void refresh()} className="portal-btn portal-btn-ghost">Refresh</button></div></div>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {loading ? <p className="text-sm text-slate-500">Loading archived content...</p> : groups.map((group) => <section key={group.label} className="portal-card"><div className="portal-card-header"><h3 className="font-semibold">{group.label} ({items[group.label]?.length || 0})</h3></div><div className="portal-card-body space-y-2">{!items[group.label]?.length ? <p className="text-sm text-slate-500">No archived {group.label.toLowerCase()}.</p> : items[group.label].map((item) => <div key={item.id} className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3"><span className="min-w-0 break-words text-sm">{item.title || item.name || item.caption || item.original_filename || item.section_key || item.key || `#${item.id}`}</span><div className="flex flex-wrap items-center gap-3"><button type="button" onClick={() => void viewDetails(group, item)} className="text-sm font-semibold text-blue-700">View details</button>{isAdmin && <button type="button" disabled={busyId === `${group.label}-${item.id}`} onClick={() => void restore(group, item.id)} className="portal-btn portal-btn-ghost">Restore as Draft</button>}</div></div>)}</div></section>)}
    {selected && <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-950/50 p-3 sm:p-6" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}>
      <section role="dialog" aria-modal="true" aria-labelledby="archived-content-title" className="max-h-[92vh] w-full max-w-4xl overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 p-4 sm:p-5"><div><h2 id="archived-content-title" className="text-lg font-bold">{selected.item.title || selected.item.name || selected.item.caption || selected.item.original_filename || selected.item.section_key || selected.item.key || "Archived item"}</h2><p className="text-sm text-slate-500">{selected.group.label} · archived content preview</p></div><button type="button" className="portal-btn portal-btn-ghost" onClick={() => setSelected(null)}>Close</button></div>
        <div className="max-h-[calc(92vh-5rem)] overflow-y-auto p-4 sm:p-5">
          {detailLoading ? <p className="text-sm text-slate-600">Loading item details…</p> : <div className="space-y-4">
            {selected.detail.file_type === "image" && display(selected.detail.url) && <img src={display(selected.detail.url)} alt={display(selected.detail.alt_text || selected.detail.caption)} className="max-h-80 max-w-full rounded-xl border border-slate-200 object-contain" />}
            {selected.detail.file_type === "video" && display(selected.detail.url) && <video controls preload="metadata" src={display(selected.detail.url)} className="max-h-80 max-w-full rounded-xl" />}
            {selected.detail.file_type === "audio" && display(selected.detail.url) && <audio controls preload="metadata" src={display(selected.detail.url)} className="w-full" />}
            {selected.detail.file_type === "document" && display(selected.detail.url) && <a className="portal-btn portal-btn-ghost" href={display(selected.detail.url)} target="_blank" rel="noreferrer">Open archived document</a>}
            {Object.entries(selected.detail).filter(([key, value]) => !["sections", "published_snapshot_json", "draft_schema_json", "current_published_schema_json", "url", "file", "id"].includes(key) && value !== null && value !== "").map(([key, value]) => <div key={key} className="grid gap-1 border-b border-slate-100 pb-2 sm:grid-cols-[12rem_minmax(0,1fr)]"><strong className="text-sm text-slate-700">{niceLabel(key)}</strong><span className="break-words text-sm text-slate-600">{display(value) || (typeof value === "object" ? JSON.stringify(value) : "—")}</span></div>)}
            {typeof selected.detail.body === "string" && <section><h3 className="font-semibold">Article content</h3><p className="mt-2 whitespace-pre-wrap rounded-lg border border-slate-200 p-3 text-sm">{selected.detail.body}</p></section>}
            {typeof selected.detail.description === "string" && selected.group.label === "Events" && <section><h3 className="font-semibold">Description</h3><p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{selected.detail.description}</p></section>}
            {pageSections.length > 0 && <section className="space-y-3"><h3 className="font-semibold">Page sections</h3>{pageSections.map((section, index) => <details key={String(section.id || section.section_key || index)} className="rounded-lg border border-slate-200 p-3"><summary className="cursor-pointer font-semibold">{display(section.section_key) || `Section ${index + 1}`} · {display(section.section_type) || "Content"}</summary><pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs">{JSON.stringify(section.content_json || {}, null, 2)}</pre></details>)}</section>}
            {selected.group.label === "Page Sections" && <section><h3 className="font-semibold">Section content</h3><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-xs">{JSON.stringify(selected.detail.content_json || {}, null, 2)}</pre></section>}
            {selected.detail.draft_schema_json != null && <section><h3 className="font-semibold">Form schema</h3><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-xs">{JSON.stringify(selected.detail.draft_schema_json, null, 2)}</pre></section>}
            {selected.detail.published_snapshot_json != null && <details className="rounded-lg border border-slate-200 p-3"><summary className="cursor-pointer font-semibold">Last published snapshot</summary><pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-xs">{JSON.stringify(selected.detail.published_snapshot_json, null, 2)}</pre></details>}
          </div>}
        </div>
      </section>
    </div>}
  </div>;
}
