import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../services/api";

type ContentStatus = "draft" | "submitted" | "published" | "rejected" | "archived";

type PublicPageContentRow = {
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
  status: ContentStatus;
  review_notes?: string;
  created_by_name?: string;
  submitted_by_name?: string;
  reviewed_by_name?: string;
  published_at?: string;
  updated_at: string;
};

type ContentForm = {
  id?: number;
  page: string;
  section_key: string;
  title: string;
  subtitle: string;
  body: string;
  image_url: string;
  cta_label: string;
  cta_url: string;
  metadata: string;
};

type Props = {
  mode: "admin" | "editor";
};

const pageOptions = [
  { value: "home", label: "Home" },
  { value: "about_rdc", label: "About RDC" },
  { value: "region_profile", label: "Region Profile" },
  { value: "publications", label: "Publications" },
  { value: "news", label: "News" },
  { value: "projects_dashboard", label: "Projects Dashboard" },
  { value: "contact", label: "Contact Us" },
];

const sectionHints: Record<string, string[]> = {
  home: ["hero", "dashboard_teaser", "development_plans", "investment_programming", "monitoring_evaluation"],
  about_rdc: ["hero", "mandate", "organizational_structure", "committees"],
  region_profile: ["hero", "demographics", "economy", "map_summary"],
  publications: ["hero", "intro", "featured_documents"],
  news: ["hero", "announcements_intro"],
  projects_dashboard: ["hero", "public_summary", "transparency_note"],
  contact: ["hero", "office_details", "inquiry_guidelines"],
};

const emptyForm: ContentForm = {
  page: "home",
  section_key: "hero",
  title: "",
  subtitle: "",
  body: "",
  image_url: "",
  cta_label: "",
  cta_url: "",
  metadata: "{}",
};

const getErrorDetail = (err: unknown, fallback: string) => {
  if (err instanceof Error && err.message) {
    try {
      const parsed = JSON.parse(err.message);
      return parsed?.detail || fallback;
    } catch {
      return err.message;
    }
  }
  return fallback;
};

const statusClass = (status: ContentStatus) => {
  if (status === "published") return "bg-emerald-100 text-emerald-700";
  if (status === "submitted") return "bg-blue-100 text-blue-700";
  if (status === "rejected") return "bg-rose-100 text-rose-700";
  if (status === "archived") return "bg-slate-200 text-slate-700";
  return "bg-amber-100 text-amber-700";
};

const prettyDate = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("en-PH", { timeZone: "Asia/Manila" });
};

const PublicPageContentManager: React.FC<Props> = ({ mode }) => {
  const isAdmin = mode === "admin";
  const [contents, setContents] = useState<PublicPageContentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [pageFilter, setPageFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [form, setForm] = useState<ContentForm>(emptyForm);

  const hints = useMemo(() => sectionHints[form.page] || [], [form.page]);

  const loadContents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (pageFilter !== "all") params.set("page", pageFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const query = params.toString();
      const data = await api.get(`admin/page-content/${query ? `?${query}` : ""}`);
      setContents(Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : []);
    } catch (error) {
      setContents([]);
      setNotice(getErrorDetail(error, "Failed to load public page content."));
    } finally {
      setLoading(false);
    }
  }, [pageFilter, statusFilter]);

  useEffect(() => {
    loadContents();
  }, [loadContents]);

  const updateForm = (patch: Partial<ContentForm>) => setForm((prev) => ({ ...prev, ...patch }));

  const editContent = (row: PublicPageContentRow) => {
    setForm({
      id: row.id,
      page: row.page || "home",
      section_key: row.section_key || "hero",
      title: row.title || "",
      subtitle: row.subtitle || "",
      body: row.body || "",
      image_url: row.image_url || "",
      cta_label: row.cta_label || "",
      cta_url: row.cta_url || "",
      metadata: JSON.stringify(row.metadata || {}, null, 2),
    });
  };

  const saveContent = async (event: React.FormEvent) => {
    event.preventDefault();
    setNotice("");
    if (!form.title.trim() || !form.section_key.trim()) {
      setNotice("Title and section key are required.");
      return;
    }
    let metadata: Record<string, unknown> = {};
    try {
      metadata = form.metadata.trim() ? JSON.parse(form.metadata) : {};
      if (!metadata || Array.isArray(metadata) || typeof metadata !== "object") {
        throw new Error("Metadata must be an object.");
      }
    } catch {
      setNotice('Metadata must be valid JSON, for example: {"tags":["home","hero"]}');
      return;
    }
    const payload = {
      page: form.page,
      section_key: form.section_key.trim(),
      title: form.title.trim(),
      subtitle: form.subtitle.trim(),
      body: form.body.trim(),
      image_url: form.image_url.trim(),
      cta_label: form.cta_label.trim(),
      cta_url: form.cta_url.trim(),
      metadata,
    };
    try {
      if (form.id) {
        await api.put(`admin/page-content/${form.id}/`, payload);
        setNotice("Content draft updated.");
      } else {
        await api.post("admin/page-content/", payload);
        setNotice("Content draft created.");
      }
      setForm(emptyForm);
      await loadContents();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to save content."));
    }
  };

  const runAction = async (row: PublicPageContentRow, action: "submit" | "publish" | "reject" | "archive") => {
    setNotice("");
    try {
      await api.post(`admin/page-content/${row.id}/${action}/`, {});
      const labels: Record<typeof action, string> = {
        submit: "Content submitted for admin review.",
        publish: "Content published to the public website.",
        reject: "Content rejected.",
        archive: "Content archived.",
      };
      setNotice(labels[action]);
      await loadContents();
    } catch (error) {
      setNotice(getErrorDetail(error, `Failed to ${action} content.`));
    }
  };

  return (
    <div className="portal-card">
      <div className="portal-card-header flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Public Page Content</h2>
          <p className="text-xs text-slate-500">
            {isAdmin
              ? "Review and publish editable public website sections."
              : "Prepare public website content drafts for admin approval."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            className="rounded-lg border bg-white px-3 py-2 text-sm"
            value={pageFilter}
            onChange={(e) => setPageFilter(e.target.value)}
          >
            <option value="all">All pages</option>
            {pageOptions.map((page) => (
              <option key={page.value} value={page.value}>
                {page.label}
              </option>
            ))}
          </select>
          <select
            className="rounded-lg border bg-white px-3 py-2 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All status</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="published">Published</option>
            <option value="rejected">Rejected</option>
            <option value="archived">Archived</option>
          </select>
          <button type="button" onClick={loadContents} className="portal-btn portal-btn-ghost">
            Refresh Content
          </button>
        </div>
      </div>

      {notice && (
        <div className="mx-4 mt-4 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
          {notice}
        </div>
      )}

      <form onSubmit={saveContent} className="portal-card-body border-b border-slate-200">
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <label className="block">
            <span className="text-sm text-slate-700">Public Page *</span>
            <select
              className="mt-1 w-full rounded-lg border bg-white px-3 py-2"
              value={form.page}
              onChange={(e) => updateForm({ page: e.target.value, section_key: sectionHints[e.target.value]?.[0] || "section" })}
            >
              {pageOptions.map((page) => (
                <option key={page.value} value={page.value}>
                  {page.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Section Key *</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              list="cms-section-hints"
              value={form.section_key}
              onChange={(e) => updateForm({ section_key: e.target.value })}
              placeholder="hero"
            />
            <datalist id="cms-section-hints">
              {hints.map((hint) => (
                <option key={hint} value={hint} />
              ))}
            </datalist>
            <p className="mt-1 text-xs text-slate-500">Examples: {hints.slice(0, 4).join(", ") || "hero, intro"}</p>
          </label>
          <label className="block xl:col-span-2">
            <span className="text-sm text-slate-700">Title *</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={form.title}
              onChange={(e) => updateForm({ title: e.target.value })}
              placeholder="Main public heading"
            />
          </label>
          <label className="block xl:col-span-2">
            <span className="text-sm text-slate-700">Subtitle / Short Summary</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={form.subtitle}
              onChange={(e) => updateForm({ subtitle: e.target.value })}
              placeholder="One sentence summary for the public page"
            />
          </label>
          <label className="block xl:col-span-2">
            <span className="text-sm text-slate-700">Body Content</span>
            <textarea
              className="mt-1 min-h-[150px] w-full rounded-lg border px-3 py-2"
              value={form.body}
              onChange={(e) => updateForm({ body: e.target.value })}
              placeholder="Write the public-facing paragraph or section details here."
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Image URL / Asset Path</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={form.image_url}
              onChange={(e) => updateForm({ image_url: e.target.value })}
              placeholder="/assets/example.jpg or https://..."
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Button Link</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={form.cta_url}
              onChange={(e) => updateForm({ cta_url: e.target.value })}
              placeholder="/publications or /Projects"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Button Label</span>
            <input
              className="mt-1 w-full rounded-lg border px-3 py-2"
              value={form.cta_label}
              onChange={(e) => updateForm({ cta_label: e.target.value })}
              placeholder="Learn More"
            />
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Metadata JSON</span>
            <textarea
              className="mt-1 min-h-[90px] w-full rounded-lg border px-3 py-2 font-mono text-xs"
              value={form.metadata}
              onChange={(e) => updateForm({ metadata: e.target.value })}
              placeholder='{"tags":["home","hero"]}'
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="submit" className="portal-btn portal-btn-primary">
            {form.id ? "Save Content Draft" : "Create Content Draft"}
          </button>
          {form.id && (
            <button type="button" onClick={() => setForm(emptyForm)} className="portal-btn portal-btn-ghost">
              Cancel Edit
            </button>
          )}
        </div>
      </form>

      <div className="portal-card-body">
        {loading ? (
          <p className="text-sm text-slate-500">Loading public page content...</p>
        ) : contents.length === 0 ? (
          <p className="text-sm text-slate-500">No public page content drafts yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {contents.map((row) => {
              const editorCanEdit = row.status === "draft" || row.status === "rejected";
              return (
                <div key={row.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(row.status)}`}>
                          {row.status}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                          {row.page_label || row.page}
                        </span>
                        <span className="rounded-full bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-700">
                          {row.section_key}
                        </span>
                      </div>
                      <h3 className="mt-2 font-semibold text-slate-900">{row.title}</h3>
                      {row.subtitle && <p className="mt-1 text-sm text-slate-600">{row.subtitle}</p>}
                      <p className="mt-1 text-xs text-slate-500">Updated {prettyDate(row.updated_at) || "recently"}</p>
                    </div>
                    {(isAdmin || editorCanEdit) && (
                      <button type="button" onClick={() => editContent(row)} className="portal-btn portal-btn-ghost w-fit">
                        Edit
                      </button>
                    )}
                  </div>
                  {row.body && <p className="mt-3 line-clamp-3 text-sm text-slate-600">{row.body}</p>}
                  {row.review_notes && (
                    <p className="mt-3 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                      Review note: {row.review_notes}
                    </p>
                  )}
                  <div className="mt-4 flex flex-wrap gap-2">
                    {!isAdmin && editorCanEdit && (
                      <button
                        type="button"
                        onClick={() => runAction(row, "submit")}
                        className="text-sm font-semibold text-blue-600 hover:underline"
                      >
                        Submit for Review
                      </button>
                    )}
                    {isAdmin && row.status !== "published" && row.status !== "archived" && (
                      <button
                        type="button"
                        onClick={() => runAction(row, "publish")}
                        className="text-sm font-semibold text-emerald-600 hover:underline"
                      >
                        Publish
                      </button>
                    )}
                    {isAdmin && (row.status === "submitted" || row.status === "draft") && (
                      <button
                        type="button"
                        onClick={() => runAction(row, "reject")}
                        className="text-sm font-semibold text-rose-600 hover:underline"
                      >
                        Reject
                      </button>
                    )}
                    {isAdmin && row.status !== "archived" && (
                      <button
                        type="button"
                        onClick={() => runAction(row, "archive")}
                        className="text-sm font-semibold text-slate-500 hover:underline"
                      >
                        Archive
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default PublicPageContentManager;
