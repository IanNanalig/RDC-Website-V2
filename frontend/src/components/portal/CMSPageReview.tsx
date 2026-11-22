import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { CMSPageSnapshot } from "../../services/cmsApi";

const publicPages = {
  home: lazy(() => import("../../pages/Home")),
  publications: lazy(() => import("../../pages/Publication")),
  "about-rdc": lazy(() => import("../../pages/About_RDC")),
  "regional-profile": lazy(() => import("../../pages/RegionalProfile")),
  contact: lazy(() => import("../../pages/Contact")),
};

const systemSections = new Set(["dashboard-teaser", "latest-media", "upcoming-events"]);
const ignoredFields = new Set(["editorRowId", "updatedAt", "publishedAt", "createdAt", "schemaVersion"]);

function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right))
      .filter(([key]) => !ignoredFields.has(key))
      .map(([key, child]) => [key, canonical(child)]));
  }
  return value;
}

const equal = (left: unknown, right: unknown) =>
  JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));

const label = (value: string) => value.replace(/([a-z])([A-Z])/g, "$1 $2")
  .replace(/[-_]/g, " ").replace(/^./, (first) => first.toUpperCase());

function changesFor(draft: CMSPageSnapshot, published: CMSPageSnapshot | null) {
  const include = (section: CMSPageSnapshot["sections"][number]) =>
    draft.slug !== "home" || !systemSections.has(section.sectionKey);
  const before = new Map((published?.sections || []).filter(include).map((section) => [section.sectionKey, section]));
  const after = new Map(draft.sections.filter(include).map((section) => [section.sectionKey, section]));
  return Array.from(new Set([...after.keys(), ...before.keys()])).map((key) => {
    const previous = before.get(key);
    const current = after.get(key);
    const title = current?.content.title || previous?.content.title;
    const name = typeof title === "string" && title ? title : label(key);
    if (!previous) return { key, name, change: "Added", fields: [] };
    if (!current) return { key, name, change: "Removed from the public page", fields: [] };
    const fields = Array.from(new Set([...Object.keys(previous.content), ...Object.keys(current.content)]))
      .filter((field) => !ignoredFields.has(field) && !equal(previous.content[field], current.content[field]))
      .map(label);
    if (previous.order !== current.order) fields.push("Section order");
    if (previous.sectionType !== current.sectionType) fields.push("Section layout");
    return { key, name, change: fields.length ? "Modified" : "Unchanged", fields };
  });
}

type Props = {
  preview: { draft: CMSPageSnapshot; published: CMSPageSnapshot | null };
  onClose: () => void;
  onPublish?: () => void;
  onReject?: () => void;
};

export default function CMSPageReview({ preview, onClose, onPublish, onReject }: Props) {
  const { draft, published } = preview;
  const dialog = useRef<HTMLDialogElement>(null);
  const [fullPage, setFullPage] = useState(false);
  const Page = publicPages[draft.slug as keyof typeof publicPages];
  const changes = changesFor(draft, published);
  const changed = changes.filter((row) => row.change !== "Unchanged");
  const unchanged = changes.filter((row) => row.change === "Unchanged");
  useEffect(() => {
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
  }, []);

  return (
    <dialog ref={dialog} onClose={onClose} aria-labelledby="cms-review-title"
      className="m-auto max-h-[94vh] w-[min(96vw,76rem)] max-w-none overflow-y-auto rounded-xl bg-white text-slate-900 shadow-2xl backdrop:bg-slate-950/60">
      <header className="sticky top-0 z-[5] space-y-3 border-b border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold text-amber-800">Unpublished preview</p>
            <h2 id="cms-review-title" className="text-lg font-bold">{draft.title}</h2>
          </div>
          <form method="dialog"><button type="submit" className="portal-btn portal-btn-ghost" autoFocus>Close preview</button></form>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" aria-pressed={!fullPage} className={!fullPage ? "portal-btn portal-btn-primary" : "portal-btn portal-btn-ghost"} onClick={() => setFullPage(false)}>Change Review</button>
          <button type="button" aria-pressed={fullPage} className={fullPage ? "portal-btn portal-btn-primary" : "portal-btn portal-btn-ghost"} onClick={() => setFullPage(true)}>Full-Page Preview</button>
        </div>
      </header>
      {fullPage && Page ? (
        <div onClickCapture={(event) => {
          const link = (event.target as HTMLElement).closest<HTMLAnchorElement>("a[href]");
          if (link && link.origin === location.origin && !link.target && !link.getAttribute("href")?.startsWith("#")) {
            event.preventDefault();
            window.open(link.href, "_blank", "noopener,noreferrer");
          }
        }}>
          <Suspense fallback={<p role="status" className="p-4">Loading preview...</p>}>
            <Page previewSnapshot={draft} />
          </Suspense>
        </div>
      ) : (
        <div className="space-y-4 p-4">
          {published && published.title !== draft.title && (
            <p className="rounded-lg bg-blue-50 p-3 text-sm">Page title changed from {published.title} to {draft.title}.</p>
          )}
          {changed.length ? (
            <ul className="space-y-2">
              {changed.map((row) => <li key={row.key} className="rounded-lg border border-slate-200 p-3">
                <strong>{row.name}</strong>
                <p className="text-sm text-slate-600">{row.change}{row.fields.length ? ` · ${row.fields.join(", ")}` : ""}</p>
              </li>)}
            </ul>
          ) : <p className="text-sm text-slate-600">No section changes.</p>}
          {!!unchanged.length && <details className="rounded-lg border border-slate-200 p-3">
            <summary className="cursor-pointer text-sm font-semibold">Unchanged sections ({unchanged.length})</summary>
            <ul className="mt-2 list-inside list-disc text-sm text-slate-600">
              {unchanged.map((row) => <li key={row.key}>{row.name}</li>)}
            </ul>
          </details>}
        </div>
      )}
      {(onReject || onPublish) && (
        <footer className="flex flex-wrap justify-end gap-2 border-t border-slate-200 p-4">
          {onReject && <button type="button" className="portal-btn portal-btn-ghost" onClick={onReject}>Reject Page</button>}
          {onPublish && <button type="button" className="portal-btn portal-btn-primary" onClick={onPublish}>Publish Page and Sections</button>}
        </footer>
      )}
    </dialog>
  );
}
