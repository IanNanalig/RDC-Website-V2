import { useCallback, useEffect, useState } from "react";
import { api } from "../../services/api";

type ArchivedItem = { id: number; title?: string; name?: string; section_key?: string; key?: string; caption?: string; original_filename?: string; status?: string };
type Group = { label: string; endpoint: string; restore: (id: number) => string };

const groups: Group[] = [
  { label: "Pages", endpoint: "admin/cms/pages/?view=summary&archived=1", restore: (id) => `admin/cms/pages/${id}/restore/` },
  { label: "Page Sections", endpoint: "admin/cms/sections/?archived=1", restore: (id) => `admin/cms/sections/${id}/restore/` },
  { label: "News", endpoint: "admin/cms/articles/?view=summary&archived=1", restore: (id) => `admin/cms/articles/${id}/restore/` },
  { label: "Events", endpoint: "admin/cms/events/?archived=1", restore: (id) => `admin/cms/events/${id}/unarchive/` },
  { label: "Media", endpoint: "admin/cms/media/?view=summary&archived=1", restore: (id) => `admin/cms/media/${id}/restore/` },
  { label: "Contributor Forms", endpoint: "admin/cms/forms/?archived=1", restore: (id) => `admin/cms/forms/${id}/restore/` },
];

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

  return <div className="space-y-4">
    <div className="portal-card"><div className="portal-card-header flex items-center justify-between gap-2"><div><h2 className="font-bold">Archived Content</h2><p className="text-sm text-slate-500">Restored items return as drafts and must be published again.</p></div><button type="button" onClick={() => void refresh()} className="portal-btn portal-btn-ghost">Refresh</button></div></div>
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    {loading ? <p className="text-sm text-slate-500">Loading archived content...</p> : groups.map((group) => <section key={group.label} className="portal-card"><div className="portal-card-header"><h3 className="font-semibold">{group.label} ({items[group.label]?.length || 0})</h3></div><div className="portal-card-body space-y-2">{!items[group.label]?.length ? <p className="text-sm text-slate-500">No archived {group.label.toLowerCase()}.</p> : items[group.label].map((item) => <div key={item.id} className="flex min-w-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3"><span className="min-w-0 break-words text-sm">{item.title || item.name || item.caption || item.original_filename || item.section_key || item.key || `#${item.id}`}</span>{isAdmin && <button type="button" disabled={busyId === `${group.label}-${item.id}`} onClick={() => void restore(group, item.id)} className="portal-btn portal-btn-ghost">Restore as Draft</button>}</div>)}</div></section>)}
  </div>;
}
