import React, { useCallback, useEffect, useMemo, useState } from "react";
import cmsApi, {
  type CMSArticle,
  type CMSMediaAsset,
  type CMSPage,
  type CMSSection,
} from "../../services/cmsApi";

type Props = {
  mode: "admin" | "editor";
};

type ResourceTab = "pages" | "news" | "media";

type PageForm = {
  id?: number;
  title: string;
  slug: string;
};

type SectionForm = {
  id?: number;
  page: number | "";
  section_key: string;
  section_type: string;
  order: string;
  schema_version: string;
  is_visible: boolean;
  content_json: string;
};

type ArticleForm = {
  id?: number;
  title: string;
  slug: string;
  category: string;
  summary: string;
  body: string;
  thumbnail: number | "";
  author: string;
  featured: boolean;
};

const emptyPageForm: PageForm = { title: "", slug: "" };
const emptySectionForm: SectionForm = {
  page: "",
  section_key: "",
  section_type: "hero",
  order: "1",
  schema_version: "1",
  is_visible: true,
  content_json: '{\n  "title": "",\n  "subtitle": "",\n  "buttonText": "",\n  "buttonLink": ""\n}',
};
const emptyArticleForm: ArticleForm = {
  title: "",
  slug: "",
  category: "Updates",
  summary: "",
  body: "",
  thumbnail: "",
  author: "",
  featured: false,
};

const sectionTypes = ["hero", "text", "image_text", "cards", "news_preview", "project_highlight", "faq"];

const statusClass = (status: string) =>
  status === "published" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700";

const formatDate = (value?: string | null) => {
  if (!value) return "Not published";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not published";
  return date.toLocaleString();
};

const getErrorDetail = (err: unknown, fallback: string) => {
  if (err instanceof Error && err.message) {
    try {
      const parsed = JSON.parse(err.message);
      return parsed?.detail || JSON.stringify(parsed) || fallback;
    } catch {
      return err.message;
    }
  }
  return fallback;
};

const slugify = (value: string) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

const CmsManager: React.FC<Props> = ({ mode }) => {
  const [activeTab, setActiveTab] = useState<ResourceTab>("pages");
  const [pages, setPages] = useState<CMSPage[]>([]);
  const [articles, setArticles] = useState<CMSArticle[]>([]);
  const [media, setMedia] = useState<CMSMediaAsset[]>([]);
  const [selectedPageId, setSelectedPageId] = useState<number | null>(null);
  const [pageForm, setPageForm] = useState<PageForm>(emptyPageForm);
  const [sectionForm, setSectionForm] = useState<SectionForm>(emptySectionForm);
  const [articleForm, setArticleForm] = useState<ArticleForm>(emptyArticleForm);
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaAlt, setMediaAlt] = useState("");
  const [mediaCaption, setMediaCaption] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");

  const isAdmin = mode === "admin";
  const selectedPage = useMemo(
    () => pages.find((page) => page.id === selectedPageId) || null,
    [pages, selectedPageId],
  );
  const selectedPageSections = selectedPage?.sections || [];

  const loadAll = useCallback(async () => {
    setLoading(true);
    setNotice("");
    try {
      const [pageRows, articleRows, mediaRows] = await Promise.all([
        cmsApi.listPages(),
        cmsApi.listArticles(),
        cmsApi.listMedia(),
      ]);
      setPages(pageRows);
      setArticles(articleRows);
      setMedia(mediaRows);
      if (!selectedPageId && pageRows[0]) {
        setSelectedPageId(pageRows[0].id);
        setSectionForm((prev) => ({ ...prev, page: pageRows[0].id }));
      }
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to load CMS workspace."));
    } finally {
      setLoading(false);
    }
  }, [selectedPageId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const editPage = (page: CMSPage) => {
    setPageForm({ id: page.id, title: page.title, slug: page.slug });
    setSelectedPageId(page.id);
    setSectionForm((prev) => ({ ...prev, page: page.id }));
  };

  const savePage = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!pageForm.title.trim() || !pageForm.slug.trim()) {
      setNotice("Page title and slug are required.");
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      const payload = { title: pageForm.title.trim(), slug: slugify(pageForm.slug) };
      if (pageForm.id) {
        await cmsApi.updatePage(pageForm.id, payload);
        setNotice("Page draft updated. Publish when ready.");
      } else {
        await cmsApi.createPage(payload);
        setNotice("Page draft created.");
      }
      setPageForm(emptyPageForm);
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to save page."));
    } finally {
      setLoading(false);
    }
  };

  const publishPage = async (page: CMSPage) => {
    if (!isAdmin) return;
    if (!window.confirm(`Publish "${page.title}" to the public website?`)) return;
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.publishPage(page.id);
      setNotice("Page published. Public site now uses the new snapshot.");
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to publish page."));
    } finally {
      setLoading(false);
    }
  };

  const editSection = (section: CMSSection) => {
    setSelectedPageId(section.page);
    setSectionForm({
      id: section.id,
      page: section.page,
      section_key: section.section_key,
      section_type: section.section_type,
      order: String(section.order),
      schema_version: String(section.schema_version),
      is_visible: section.is_visible,
      content_json: JSON.stringify(section.content_json || {}, null, 2),
    });
  };

  const saveSection = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!sectionForm.page || !sectionForm.section_key.trim() || !sectionForm.section_type.trim()) {
      setNotice("Section page, key, and type are required.");
      return;
    }
    let parsedContent: Record<string, unknown>;
    try {
      const parsed = JSON.parse(sectionForm.content_json || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Section content must be a JSON object.");
      }
      parsedContent = parsed as Record<string, unknown>;
    } catch {
      setNotice("Section content must be valid JSON.");
      return;
    }

    setLoading(true);
    setNotice("");
    try {
      const payload = {
        page: Number(sectionForm.page),
        section_key: slugify(sectionForm.section_key),
        section_type: sectionForm.section_type,
        order: Number(sectionForm.order || 1),
        schema_version: Number(sectionForm.schema_version || 1),
        is_visible: sectionForm.is_visible,
        content_json: parsedContent,
      };
      if (sectionForm.id) {
        await cmsApi.updateSection(sectionForm.id, payload);
        setNotice("Section updated. Publish the page when ready.");
      } else {
        await cmsApi.createSection(payload);
        setNotice("Section created. Publish the page when ready.");
      }
      setSectionForm({ ...emptySectionForm, page: Number(sectionForm.page) });
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to save section."));
    } finally {
      setLoading(false);
    }
  };

  const moveSection = async (section: CMSSection, direction: -1 | 1) => {
    if (!selectedPage) return;
    const sorted = [...selectedPageSections].sort((a, b) => a.order - b.order || a.id - b.id);
    const index = sorted.findIndex((item) => item.id === section.id);
    const nextIndex = index + direction;
    if (index < 0 || nextIndex < 0 || nextIndex >= sorted.length) return;
    const swapped = [...sorted];
    [swapped[index], swapped[nextIndex]] = [swapped[nextIndex], swapped[index]];
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.reorderSections(selectedPage.id, swapped.map((item) => item.id));
      setNotice("Section order updated. Publish the page when ready.");
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to reorder sections."));
    } finally {
      setLoading(false);
    }
  };

  const editArticle = (article: CMSArticle) => {
    setArticleForm({
      id: article.id,
      title: article.title,
      slug: article.slug,
      category: article.category,
      summary: article.summary,
      body: article.body,
      thumbnail: article.thumbnail || "",
      author: article.author,
      featured: article.featured,
    });
  };

  const saveArticle = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!articleForm.title.trim() || !articleForm.slug.trim()) {
      setNotice("News title and slug are required.");
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      const payload = {
        title: articleForm.title.trim(),
        slug: slugify(articleForm.slug),
        category: articleForm.category.trim() || "Updates",
        summary: articleForm.summary,
        body: articleForm.body,
        thumbnail: articleForm.thumbnail || null,
        author: articleForm.author,
        featured: articleForm.featured,
      };
      if (articleForm.id) {
        await cmsApi.updateArticle(articleForm.id, payload);
        setNotice("News draft updated. Publish when ready.");
      } else {
        await cmsApi.createArticle(payload);
        setNotice("News draft created.");
      }
      setArticleForm(emptyArticleForm);
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to save article."));
    } finally {
      setLoading(false);
    }
  };

  const publishArticle = async (article: CMSArticle) => {
    if (!isAdmin) return;
    if (!window.confirm(`Publish "${article.title}" to the News page?`)) return;
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.publishArticle(article.id);
      setNotice("News article published.");
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to publish article."));
    } finally {
      setLoading(false);
    }
  };

  const uploadMedia = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!mediaFile) {
      setNotice("Choose an image or PDF to upload.");
      return;
    }
    const form = new FormData();
    form.append("file", mediaFile);
    form.append("alt_text", mediaAlt);
    form.append("caption", mediaCaption);
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.uploadMedia(form);
      setNotice("Media uploaded.");
      setMediaFile(null);
      setMediaAlt("");
      setMediaCaption("");
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to upload media."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="portal-card">
        <div className="portal-card-body flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Website CMS V1</h2>
            <p className="text-sm text-slate-500">
              Edit drafts safely. Public pages only change after Admin publishes a snapshot.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["pages", "news", "media"] as ResourceTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`portal-btn ${activeTab === tab ? "portal-btn-primary" : "portal-btn-ghost"}`}
              >
                {tab === "pages" ? "Pages" : tab === "news" ? "News" : "Media Library"}
              </button>
            ))}
            <button type="button" onClick={loadAll} className="portal-btn portal-btn-ghost" disabled={loading}>
              Refresh
            </button>
          </div>
        </div>
        {notice && (
          <div className="border-t border-slate-200 px-5 py-3 text-sm text-blue-700">
            {notice}
          </div>
        )}
      </div>

      {activeTab === "pages" && (
        <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
          <div className="space-y-4">
            <form onSubmit={savePage} className="portal-card">
              <div className="portal-card-header">
                <h3 className="font-bold text-slate-900">{pageForm.id ? "Edit Page Draft" : "Create Page Draft"}</h3>
              </div>
              <div className="portal-card-body space-y-3">
                <Field
                  label="Page Title"
                  value={pageForm.title}
                  onChange={(value) =>
                    setPageForm((prev) => ({
                      ...prev,
                      title: value,
                      slug: prev.id || prev.slug ? prev.slug : slugify(value),
                    }))
                  }
                />
                <Field
                  label="Slug"
                  value={pageForm.slug}
                  onChange={(value) => setPageForm((prev) => ({ ...prev, slug: value }))}
                  helper="Example: home, about-rdc, contact"
                />
                <div className="flex gap-2">
                  <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                    {pageForm.id ? "Save Page Draft" : "Create Page"}
                  </button>
                  {pageForm.id && (
                    <button type="button" className="portal-btn portal-btn-ghost" onClick={() => setPageForm(emptyPageForm)}>
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            </form>

            <div className="portal-card">
              <div className="portal-card-header">
                <h3 className="font-bold text-slate-900">Pages</h3>
              </div>
              <div className="portal-card-body space-y-3">
                {pages.length === 0 ? (
                  <p className="text-sm text-slate-500">No CMS pages yet.</p>
                ) : (
                  pages.map((page) => (
                    <div
                      key={page.id}
                      className={`rounded-xl border p-3 ${selectedPageId === page.id ? "border-blue-400 bg-blue-50" : "border-slate-200"}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <strong>{page.title}</strong>
                            <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(page.status)}`}>
                              {page.status}
                            </span>
                            {page.has_unpublished_changes && (
                              <span className="rounded-full bg-orange-100 px-2 py-1 text-xs font-semibold text-orange-700">
                                unpublished changes
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500">/{page.slug}</p>
                          <p className="text-xs text-slate-500">Published: {formatDate(page.published_at)}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button type="button" className="text-sm text-blue-600" onClick={() => editPage(page)}>
                            Edit
                          </button>
                          {isAdmin && (
                            <button type="button" className="text-sm text-emerald-700" onClick={() => publishPage(page)}>
                              Publish
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <form onSubmit={saveSection} className="portal-card">
              <div className="portal-card-header">
                <h3 className="font-bold text-slate-900">{sectionForm.id ? "Edit Section Block" : "Add Section Block"}</h3>
              </div>
              <div className="portal-card-body space-y-4">
                <div className="grid gap-3 md:grid-cols-2">
                  <Select
                    label="Page"
                    value={String(sectionForm.page)}
                    onChange={(value) => {
                      const pageId = value ? Number(value) : "";
                      setSelectedPageId(pageId || null);
                      setSectionForm((prev) => ({ ...prev, page: pageId }));
                    }}
                    options={pages.map((page) => ({ label: page.title, value: String(page.id) }))}
                  />
                  <Select
                    label="Section Type"
                    value={sectionForm.section_type}
                    onChange={(value) => setSectionForm((prev) => ({ ...prev, section_type: value }))}
                    options={sectionTypes.map((type) => ({ label: type.replace(/_/g, " "), value: type }))}
                  />
                  <Field
                    label="Section Key"
                    value={sectionForm.section_key}
                    onChange={(value) => setSectionForm((prev) => ({ ...prev, section_key: value }))}
                    helper="Unique per page, e.g. home-hero"
                  />
                  <Field
                    label="Order"
                    value={sectionForm.order}
                    onChange={(value) => setSectionForm((prev) => ({ ...prev, order: value }))}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={sectionForm.is_visible}
                    onChange={(event) => setSectionForm((prev) => ({ ...prev, is_visible: event.target.checked }))}
                  />
                  Visible when page is published
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-slate-700">Content JSON</span>
                  <textarea
                    className="mt-1 h-52 w-full rounded-xl border border-slate-300 px-3 py-2 font-mono text-sm"
                    value={sectionForm.content_json}
                    onChange={(event) => setSectionForm((prev) => ({ ...prev, content_json: event.target.value }))}
                  />
                </label>
                <div className="flex gap-2">
                  <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                    {sectionForm.id ? "Save Section" : "Add Section"}
                  </button>
                  {sectionForm.id && (
                    <button
                      type="button"
                      className="portal-btn portal-btn-ghost"
                      onClick={() => setSectionForm({ ...emptySectionForm, page: selectedPageId || "" })}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            </form>

            <div className="portal-card">
              <div className="portal-card-header">
                <h3 className="font-bold text-slate-900">Sections {selectedPage ? `for ${selectedPage.title}` : ""}</h3>
              </div>
              <div className="portal-card-body space-y-3">
                {!selectedPage ? (
                  <p className="text-sm text-slate-500">Select or create a page to manage sections.</p>
                ) : selectedPageSections.length === 0 ? (
                  <p className="text-sm text-slate-500">No sections yet.</p>
                ) : (
                  [...selectedPageSections]
                    .sort((a, b) => a.order - b.order || a.id - b.id)
                    .map((section, index, list) => (
                      <div key={section.id} className="rounded-xl border border-slate-200 bg-white p-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <strong>{section.order}. {section.section_key}</strong>
                            <p className="text-xs text-slate-500">
                              {section.section_type} · {section.is_visible ? "visible" : "hidden"}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2 text-sm">
                            <button type="button" className="text-slate-600" disabled={index === 0} onClick={() => moveSection(section, -1)}>
                              Up
                            </button>
                            <button type="button" className="text-slate-600" disabled={index === list.length - 1} onClick={() => moveSection(section, 1)}>
                              Down
                            </button>
                            <button type="button" className="text-blue-600" onClick={() => editSection(section)}>
                              Edit
                            </button>
                          </div>
                        </div>
                        <pre className="mt-3 max-h-32 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                          {JSON.stringify(section.content_json, null, 2)}
                        </pre>
                      </div>
                    ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "news" && (
        <div className="grid gap-4 xl:grid-cols-[460px_1fr]">
          <form onSubmit={saveArticle} className="portal-card">
            <div className="portal-card-header">
              <h3 className="font-bold text-slate-900">{articleForm.id ? "Edit News Draft" : "Create News Draft"}</h3>
            </div>
            <div className="portal-card-body space-y-3">
              <Field
                label="Title"
                value={articleForm.title}
                onChange={(value) =>
                  setArticleForm((prev) => ({
                    ...prev,
                    title: value,
                    slug: prev.id || prev.slug ? prev.slug : slugify(value),
                  }))
                }
              />
              <Field
                label="Slug"
                value={articleForm.slug}
                onChange={(value) => setArticleForm((prev) => ({ ...prev, slug: value }))}
              />
              <div className="grid gap-3 md:grid-cols-2">
                <Field
                  label="Category"
                  value={articleForm.category}
                  onChange={(value) => setArticleForm((prev) => ({ ...prev, category: value }))}
                />
                <Select
                  label="Thumbnail"
                  value={String(articleForm.thumbnail)}
                  onChange={(value) => setArticleForm((prev) => ({ ...prev, thumbnail: value ? Number(value) : "" }))}
                  options={media
                    .filter((item) => item.file_type === "image")
                    .map((item) => ({ label: item.caption || item.alt_text || `Image #${item.id}`, value: String(item.id) }))}
                  emptyLabel="No thumbnail"
                />
              </div>
              <Field
                label="Short Summary"
                value={articleForm.summary}
                onChange={(value) => setArticleForm((prev) => ({ ...prev, summary: value }))}
              />
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Article Body</span>
                <textarea
                  className="mt-1 h-48 w-full rounded-xl border border-slate-300 px-3 py-2"
                  value={articleForm.body}
                  onChange={(event) => setArticleForm((prev) => ({ ...prev, body: event.target.value }))}
                  placeholder="<p>Public article content. Basic HTML is allowed and sanitized when published.</p>"
                />
              </label>
              <Field
                label="Author"
                value={articleForm.author}
                onChange={(value) => setArticleForm((prev) => ({ ...prev, author: value }))}
              />
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={articleForm.featured}
                  onChange={(event) => setArticleForm((prev) => ({ ...prev, featured: event.target.checked }))}
                />
                Feature this article
              </label>
              <div className="flex gap-2">
                <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                  {articleForm.id ? "Save News Draft" : "Create News"}
                </button>
                {articleForm.id && (
                  <button type="button" className="portal-btn portal-btn-ghost" onClick={() => setArticleForm(emptyArticleForm)}>
                    Cancel
                  </button>
                )}
              </div>
            </div>
          </form>

          <div className="portal-card">
            <div className="portal-card-header">
              <h3 className="font-bold text-slate-900">News Articles</h3>
            </div>
            <div className="portal-card-body space-y-3">
              {articles.length === 0 ? (
                <p className="text-sm text-slate-500">No CMS news articles yet.</p>
              ) : (
                articles.map((article) => (
                  <div key={article.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong>{article.title}</strong>
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(article.status)}`}>
                            {article.status}
                          </span>
                          {article.has_unpublished_changes && (
                            <span className="rounded-full bg-orange-100 px-2 py-1 text-xs font-semibold text-orange-700">
                              unpublished changes
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500">/news/{article.slug}</p>
                        <p className="mt-1 text-sm text-slate-600">{article.summary || "No summary yet."}</p>
                      </div>
                      <div className="flex flex-wrap gap-2 text-sm">
                        <button type="button" className="text-blue-600" onClick={() => editArticle(article)}>
                          Edit
                        </button>
                        {isAdmin && (
                          <button type="button" className="text-emerald-700" onClick={() => publishArticle(article)}>
                            Publish
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === "media" && (
        <div className="grid gap-4 xl:grid-cols-[420px_1fr]">
          <form onSubmit={uploadMedia} className="portal-card">
            <div className="portal-card-header">
              <h3 className="font-bold text-slate-900">Upload Media</h3>
            </div>
            <div className="portal-card-body space-y-3">
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Image or PDF</span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
                  className="mt-1 block w-full text-sm"
                  onChange={(event) => setMediaFile(event.target.files?.[0] || null)}
                />
              </label>
              <Field label="Alt Text" value={mediaAlt} onChange={setMediaAlt} />
              <Field label="Caption" value={mediaCaption} onChange={setMediaCaption} />
              <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                Upload Media
              </button>
            </div>
          </form>

          <div className="portal-card">
            <div className="portal-card-header">
              <h3 className="font-bold text-slate-900">Media Library</h3>
            </div>
            <div className="portal-card-body">
              {media.length === 0 ? (
                <p className="text-sm text-slate-500">No uploaded media yet.</p>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {media.map((item) => (
                    <div key={item.id} className="rounded-xl border border-slate-200 p-3">
                      <div className="aspect-video overflow-hidden rounded-lg bg-slate-100">
                        {item.file_type === "image" ? (
                          <img src={item.url} alt={item.alt_text || item.caption || "CMS media"} className="h-full w-full object-cover" />
                        ) : (
                          <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-500">
                            {item.file_type.toUpperCase()}
                          </div>
                        )}
                      </div>
                      <p className="mt-2 truncate text-sm font-semibold text-slate-900">{item.caption || item.alt_text || `Media #${item.id}`}</p>
                      <p className="text-xs text-slate-500">{item.mime_type} · {Math.round(item.size / 1024)} KB</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-sm">
                        <a href={item.url} target="_blank" rel="noreferrer" className="text-blue-600">
                          Open
                        </a>
                        <button type="button" className="text-slate-600" onClick={() => navigator.clipboard?.writeText(item.url)}>
                          Copy URL
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Field = ({
  label,
  value,
  onChange,
  helper,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  helper?: string;
}) => (
  <label className="block">
    <span className="text-sm font-medium text-slate-700">{label}</span>
    <input
      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
    {helper && <span className="mt-1 block text-xs text-slate-500">{helper}</span>}
  </label>
);

const Select = ({
  label,
  value,
  onChange,
  options,
  emptyLabel = "Choose",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  emptyLabel?: string;
}) => (
  <label className="block">
    <span className="text-sm font-medium text-slate-700">{label}</span>
    <select
      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">{emptyLabel}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  </label>
);

export default CmsManager;
