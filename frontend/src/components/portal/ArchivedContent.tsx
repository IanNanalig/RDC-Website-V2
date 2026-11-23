import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../services/api";
import RefreshButton from "./RefreshButton";
import { resolveCmsMediaUrl } from "../../services/cmsApi";

type ArchivedItem = { id: number; title?: string; name?: string; section_key?: string; key?: string; caption?: string; original_filename?: string; status?: string; [key: string]: unknown };
type Group = { label: string; endpoint: string; detail: (id: number) => string; restore: (id: number) => string };

const ARCHIVED_PAGE_SIZE = 10;

const groups: Group[] = [
  { label: "News", endpoint: "admin/cms/articles/?view=summary&archived=1", detail: (id) => `admin/cms/articles/${id}/`, restore: (id) => `admin/cms/articles/${id}/restore/` },
  { label: "Events", endpoint: "admin/cms/events/?view=summary&archived=1", detail: (id) => `admin/cms/events/${id}/`, restore: (id) => `admin/cms/events/${id}/unarchive/` },
  { label: "Media", endpoint: "admin/cms/media/?view=summary&archived=1", detail: (id) => `admin/cms/media/${id}/`, restore: (id) => `admin/cms/media/${id}/restore/` },
];

const display = (value: unknown) => typeof value === "string" || typeof value === "number" || typeof value === "boolean" ? String(value) : "";
const titleFor = (item: ArchivedItem) => item.title || item.caption || item.original_filename || "Archived item";

function archiveDate(value: unknown) {
  if (typeof value !== "string" || !value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("en-PH", { dateStyle: "medium", timeZone: "Asia/Manila" });
}

function safeMedia(value: unknown) {
  const url = resolveCmsMediaUrl(display(value));
  return /^https?:\/\//i.test(url) || /^\/(?![/\\])/.test(url) ? url : "";
}

function contentSummary(item: ArchivedItem) {
  return display(item.summary || item.description || item.caption || item.alt_text);
}

function typeLabel(group: Group, item: ArchivedItem) {
  const kind = group.label === "Media" ? display(item.file_type) : group.label === "Events" ? display(item.event_type) : "News article";
  return kind ? kind.charAt(0).toUpperCase() + kind.slice(1) : group.label;
}

function thumbnail(item: ArchivedItem) {
  return safeMedia(item.thumbnail_url || (item.file_type === "image" ? item.url : ""));
}


type ArchivePage = { rows: ArchivedItem[]; count: number; page: number };

async function fetchGroup(endpoint: string, page: number): Promise<ArchivePage> {
  const url = `${endpoint}&page_size=${ARCHIVED_PAGE_SIZE}`;
  const result = await api.get(`${url}&page=${page}`) as
    ArchivedItem[] | { results: ArchivedItem[]; count?: number; total_pages?: number };
  if (Array.isArray(result)) {
    const offset = (page - 1) * ARCHIVED_PAGE_SIZE;
    return { rows: result.slice(offset, offset + ARCHIVED_PAGE_SIZE), count: result.length, page };
  }
  return { rows: result.results || [], count: result.count ?? result.results?.length ?? 0, page };
}

export default function ArchivedContent({ isAdmin }: { isAdmin: boolean }) {
  const [activeGroup, setActiveGroup] = useState(groups[0]);
  const [notice, setNotice] = useState("");
  const [items, setItems] = useState<Record<string, ArchivePage>>({});
  const [groupPages, setGroupPages] = useState<Record<string, number>>(
    () => Object.fromEntries(groups.map((group) => [group.label, 1])),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [selected, setSelected] = useState<{ group: Group; item: ArchivedItem; detail: ArchivedItem } | null>(null);
  const detailsDialog = useRef<HTMLDialogElement>(null);
  const detailsOpen = selected !== null;
  useEffect(() => {
    const dialog = detailsDialog.current;
    if (detailsOpen && dialog && !dialog.open) dialog.showModal();
  }, [detailsOpen]);
  const [detailLoading, setDetailLoading] = useState(false);
  const page = groupPages[activeGroup.label] || 1;
  const requestId = useRef(0);
  const refresh = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const result = await fetchGroup(activeGroup.endpoint, page);
      if (id === requestId.current) setItems((previous) => ({ ...previous, [activeGroup.label]: result }));
    } catch (caught) {
      if (id === requestId.current) setError(caught instanceof Error ? caught.message : "Archived items could not be loaded.");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [activeGroup, page]);
  useEffect(() => {
    void refresh();
    return () => { requestId.current += 1; };
  }, [refresh]);

  const restore = async (group: Group, id: number) => {
    setBusyId(`${group.label}-${id}`);
    setError("");
    try {
      await api.post(group.restore(id), {});
      setSelected(null);
      setNotice(group.label === "Media" ? "File returned to the Media Library." : "Item returned to its module as a draft.");
      const result = items[group.label];
      if (result?.rows.length === 1 && page > 1) {
        setGroupPages((current) => ({ ...current, [group.label]: page - 1 }));
      } else {
        await refresh();
      }
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
      setSelected((current) => current?.item === item ? { group, item, detail: { ...item, ...detail } } : current);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Archived item details could not be loaded.");
    } finally {
      setDetailLoading(false);
    }
  };

  const groupItems = items[activeGroup.label];
  const totalPages = Math.max(1, Math.ceil((groupItems?.count || 0) / ARCHIVED_PAGE_SIZE));
  const currentPage = groupItems?.page || 1;
  const visibleItems = groupItems?.rows || [];
  const archivedDetails = selected?.detail;
  const fileUrl = safeMedia(archivedDetails?.url);
  const savedSnapshot = archivedDetails?.published_snapshot_json;
  const published = savedSnapshot && typeof savedSnapshot === "object" ? savedSnapshot as Record<string, unknown> : null;

  return (
    <div className="space-y-4">
      <div className="portal-card">
        <div className="portal-card-header flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-bold">Archived Content</h2>
          <RefreshButton loading={loading} onClick={refresh} />
        </div>
        <nav aria-label="Archived content groups" className="flex flex-wrap gap-2 px-4 pb-4">
          {groups.map((group) => (
            <button key={group.label} type="button" disabled={Boolean(busyId)} aria-pressed={group === activeGroup}
              className={group === activeGroup ? "portal-btn portal-btn-primary" : "portal-btn portal-btn-ghost"}
              onClick={() => setActiveGroup(group)}>
              {group.label}{items[group.label] ? ` (${items[group.label].count})` : ""}
            </button>
          ))}
        </nav>
      </div>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      {notice && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      {loading ? <p role="status">Loading archived content...</p> : (
        <section aria-label={activeGroup.label} className="space-y-3">
          {!visibleItems.length && <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">No archived {activeGroup.label.toLowerCase()}.</p>}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visibleItems.map((item) => (
              <article key={item.id} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
                {thumbnail(item) ? <img src={thumbnail(item)} alt={display(item.alt_text)} loading="lazy" className="h-32 w-full bg-slate-100 object-cover" />
                  : <div className="grid h-20 place-items-center bg-slate-100 text-sm font-semibold text-slate-600">{typeLabel(activeGroup, item)}</div>}
                <div className="space-y-2 p-4">
                  <h3 className="break-words font-semibold">{titleFor(item)}</h3>
                  {archiveDate(item.archived_at) && <p className="text-xs text-slate-500">Archived {archiveDate(item.archived_at)}</p>}
                  {contentSummary(item) && <p className="line-clamp-2 break-words text-sm text-slate-600">{contentSummary(item)}</p>}
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="portal-btn portal-btn-ghost" onClick={() => void viewDetails(activeGroup, item)}>View details</button>
                    {isAdmin && <button type="button" disabled={Boolean(busyId)} className="portal-btn portal-btn-primary" onClick={() => void restore(activeGroup, item.id)}>
                      {activeGroup.label === "Media" ? "Restore to Media Library" : "Restore as Draft"}
                    </button>}
                  </div>
                </div>
              </article>
            ))}
          </div>
          {totalPages > 1 && (
            <nav aria-label="Archived items pagination" className="flex flex-wrap items-center gap-3 text-sm">
              <button type="button" className="portal-btn portal-btn-ghost" disabled={Boolean(busyId) || currentPage === 1} onClick={() => setGroupPages({ ...groupPages, [activeGroup.label]: currentPage - 1 })}>Previous</button>
              <span aria-live="polite">Page {currentPage} of {totalPages}</span>
              <button type="button" className="portal-btn portal-btn-ghost" disabled={Boolean(busyId) || currentPage === totalPages} onClick={() => setGroupPages({ ...groupPages, [activeGroup.label]: currentPage + 1 })}>Next</button>
            </nav>
          )}
        </section>
      )}
      {selected && archivedDetails && (
        <dialog ref={detailsDialog} onClose={() => setSelected(null)} aria-labelledby="archived-title"
          className="m-auto max-h-[90vh] w-[min(92vw,42rem)] space-y-4 overflow-auto rounded-xl bg-white p-5 shadow-xl backdrop:bg-slate-950/50">
            <header className="flex flex-wrap items-start justify-between gap-2">
              <h2 id="archived-title" className="break-words text-xl font-bold">{titleFor(archivedDetails)}</h2>
              <form method="dialog"><button type="submit" className="portal-btn portal-btn-ghost" autoFocus>Close</button></form>
            </header>
            {detailLoading && <p role="status">Loading item details...</p>}
            {thumbnail(archivedDetails) && <img src={thumbnail(archivedDetails)} alt={display(archivedDetails.alt_text)} className="max-h-64 rounded-lg object-contain" />}
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              {[
                ["Content type", typeLabel(selected.group, archivedDetails)],
                ["Original module", selected.group.label === "Media" ? "Media Library" : selected.group.label],
                ["Date archived", archiveDate(archivedDetails.archived_at)],
                ["Archived by", display(archivedDetails.archived_by_name || (selected.group.label === "Events" ? archivedDetails.reviewed_by_name : ""))],
                ["Original publication date", archiveDate(published?.publicationDate || archivedDetails.published_at)],
                ["Event date", archiveDate(archivedDetails.start_at)],
                ["Location", display(archivedDetails.location)],
                ["File name", display(archivedDetails.original_filename)],
              ].filter(([, value]) => value).map(([name, value]) => (
                <div key={name}><dt className="font-semibold">{name}</dt><dd className="break-words text-slate-600">{value}</dd></div>
              ))}
            </dl>
            {contentSummary(archivedDetails) && <p className="whitespace-pre-wrap break-words text-sm">{contentSummary(archivedDetails)}</p>}
            {selected.group.label === "News" && published && (published.title || published.summary) ? (
              <section className="space-y-1 rounded-lg bg-slate-50 p-3 text-sm">
                <h3 className="font-semibold">Last published content</h3>
                <p className="break-words">{display(published.title)}</p>
                <p className="break-words text-slate-600">{display(published.summary)}</p>
              </section>
            ) : null}
            {selected.group.label === "Media" && fileUrl && archivedDetails.file_type === "video" && <video controls preload="metadata" src={fileUrl} className="max-h-64 max-w-full rounded-lg" />}
            {selected.group.label === "Media" && fileUrl && archivedDetails.file_type === "audio" && <audio controls preload="metadata" src={fileUrl} className="w-full" />}
            {selected.group.label === "Media" && fileUrl && !["image", "audio", "video"].includes(display(archivedDetails.file_type)) && (
              <a className="portal-btn portal-btn-ghost" href={fileUrl} target="_blank" rel="noopener noreferrer">Open file</a>
            )}
            {isAdmin && <button type="button" className="portal-btn portal-btn-primary" disabled={Boolean(busyId)} onClick={() => void restore(selected.group, selected.item.id)}>
              {selected.group.label === "Media" ? "Restore to Media Library" : "Restore as Draft"}
            </button>}
        </dialog>
      )}
    </div>
  );
}
