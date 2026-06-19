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
  section_type: "hero_carousel",
  order: "1",
  schema_version: "1",
  is_visible: true,
  content_json:
    '{\n  "slides": [\n    {\n      "title": "Regional Development Council NCR",\n      "subtitle": "Planning a sustainable and resilient Metro Manila",\n      "imageKey": "photo1",\n      "button1": { "text": "View Plans", "link": "/publications" },\n      "button2": { "text": "Latest Reports", "link": "/publications" }\n    }\n  ]\n}',
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

const sectionTypeOptions = [
  { value: "hero_carousel", label: "Hero Carousel" },
  { value: "publication_catalog", label: "Publication Catalog" },
  { value: "document_group", label: "Document/Card Group" },
  { value: "dashboard_teaser", label: "Dashboard Teaser" },
  { value: "news_preview", label: "Latest News Preview" },
  { value: "events_preview", label: "Events Preview" },
  { value: "contact_info", label: "Contact Information" },
  { value: "location_map", label: "Location Map Text" },
  { value: "form_intro", label: "Form Intro / Messages" },
  { value: "text", label: "Text Section" },
  { value: "image_text", label: "Image + Text" },
  { value: "cards", label: "Cards" },
  { value: "faq", label: "FAQ" },
];

const iconOptions = [
  "leaf",
  "file",
  "document",
  "book",
  "scale",
  "target",
  "briefcase",
  "chart-line",
  "chart-bar",
  "clipboard",
  "gear",
  "refresh",
  "trend",
  "building",
  "crown",
  "handshake",
  "lightbulb",
  "search",
];

const sectionTemplate = (type: string): Record<string, unknown> => {
  if (type === "hero_carousel") {
    return {
      slides: [
        {
          title: "Regional Development Council NCR",
          subtitle: "Planning a sustainable and resilient Metro Manila",
          imageKey: "photo1",
          button1: { text: "View Plans", link: "/publications" },
          button2: { text: "Latest Reports", link: "/publications" },
        },
      ],
    };
  }
  if (type === "document_group") {
    return {
      title: "Section title",
      items: [
        {
          id: "",
          title: "Featured document",
          description: "Short public description",
          category: "Category",
          icon: "file",
          link: "/publications",
          fileType: "",
          fileSize: "",
          pages: "",
          quickLinks: [],
        },
      ],
    };
  }
  if (type === "publication_catalog") {
    return {
      title: "Publications & Official Documents",
      subtitle: "Plans, reports, and development programs for the National Capital Region",
      browseTitle: "Browse by Category",
      browseSubtitle: "Select a category to view available documents",
      categories: [
        {
          id: "category-id",
          title: "Publication Category",
          description: "Short public category description",
          icon: "file",
          color: "from-blue-600 to-cyan-500",
          isVisible: true,
          documents: [
            {
              id: "document-id",
              title: "Document title",
              year: "2026",
              fileType: "PDF",
              fileSize: "",
              isVisible: true,
            },
          ],
        },
      ],
    };
  }
  if (type === "dashboard_teaser") {
    return {
      title: "Regional Development Dashboard",
      buttonLabel: "View Full Dashboard ->",
      buttonLink: "/Projects",
    };
  }
  if (type === "news_preview") {
    return {
      title: "Latest Media Releases",
      viewAllLabel: "View all ->",
      viewAllLink: "/news",
    };
  }
  if (type === "events_preview") {
    return {
      title: "Upcoming Events",
      subtitle: "Calendar & Meetings",
      buttonLabel: "View Full Calendar",
      calendarTitle: "Public Events and Meetings",
      calendarSubtitle: "Published schedules from the RDC-NCR public website.",
    };
  }
  if (type === "contact_info") {
    return {
      title: "Main Office Information",
      addressLabel: "Address",
      address:
        "16th Floor, MMDA Head Office, Dofia Julia Vargas Avenue corner Molawe St., Barangay Ugong, Pasig City",
      emailLabel: "Email",
      email: "rdc.ncr@mmda.gov.ph",
      phoneLabel: "Phone",
      phone: "+63 (2) 1234-5678",
      hoursLabel: "Office Hours",
      officeHours: "Monday - Friday: 7:00 AM - 4:00 PM\nSaturday, Sunday & Holidays: Closed",
    };
  }
  if (type === "location_map") {
    return {
      title: "RDC-NCR Location",
      subtitle: "MMDA Head Office, Pasig City",
      badgeLabel: "Live Location",
    };
  }
  if (type === "form_intro") {
    return {
      title: "Send Us a Message",
      subtitle: "Have a question or inquiry? Fill out the form below and we'll get back to you as soon as possible.",
      successTitle: "Thank You!",
      successMessage: "Your inquiry has been received. We'll respond within 24-48 business hours.",
      namePlaceholder: "Your full name",
      emailPlaceholder: "your.email@example.com",
      subjectPlaceholder: "What is your inquiry about?",
      messagePlaceholder: "Please describe your inquiry in detail...",
      submitLabel: "Send Message",
      loadingLabel: "Sending...",
    };
  }
  return {
    title: "",
    subtitle: "",
    body: "",
    buttonText: "",
    buttonLink: "",
  };
};

const formatJson = (value: Record<string, unknown>) => JSON.stringify(value, null, 2);

const parseJsonObject = (value: string): Record<string, unknown> => {
  try {
    const parsed = JSON.parse(value || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
};

const parseRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};

const textValue = (value: unknown) => (typeof value === "string" ? value : "");
const stringValue = (value: unknown) => (value === null || value === undefined ? "" : String(value));

const mediaDisplayName = (item: CMSMediaAsset) =>
  item.caption || item.alt_text || item.file?.split(/[\\/]/).pop() || `Media #${item.id}`;

const formatMediaSize = (bytes: number) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
};

const mediaFileTypeLabel = (item: CMSMediaAsset) => {
  if (item.mime_type === "application/pdf") return "PDF";
  if (item.file_type === "image") return "Image";
  if (item.file_type === "document") return "Document";
  return "File";
};

const mediaTypeClass = (item: CMSMediaAsset) => {
  if (item.mime_type === "application/pdf" || item.file_type === "document") return "bg-red-50 text-red-700";
  if (item.file_type === "image") return "bg-blue-50 text-blue-700";
  return "bg-slate-100 text-slate-700";
};

const quickLinksToText = (value: unknown) =>
  Array.isArray(value)
    ? value
        .map((item) => {
          const row = parseRecord(item);
          const label = textValue(row.label);
          const link = textValue(row.link);
          return label || link ? `${label}|${link}` : "";
        })
        .filter(Boolean)
        .join("\n")
    : "";

const quickLinksFromText = (value: string) =>
  value
    .split(/\r?\n/)
    .map((line) => {
      const [label = "", link = ""] = line.split("|");
      return { label: label.trim(), link: link.trim() };
    })
    .filter((item) => item.label && item.link);

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

const pagePublicPath = (slug: string) => {
  const routeMap: Record<string, string> = {
    home: "/",
    "about-rdc": "/about",
    contact: "/contact",
    news: "/news",
  };
  return routeMap[slug] || `/${slug}`;
};

const articlePublicPath = (slug: string) => `/news/${slug}`;

const absolutePublicUrl = (path: string) => {
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path}`;
};

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
  const [showGuide, setShowGuide] = useState(false);

  const isAdmin = mode === "admin";
  const selectedPage = useMemo(
    () => pages.find((page) => page.id === selectedPageId) || null,
    [pages, selectedPageId],
  );
  const selectedPageSections = selectedPage?.sections || [];
  const sectionContent = useMemo(
    () => parseJsonObject(sectionForm.content_json),
    [sectionForm.content_json],
  );
  const mediaById = useMemo(() => new Map(media.map((item) => [String(item.id), item])), [media]);
  const imageMediaOptions = useMemo(
    () =>
      media
        .filter((item) => item.file_type === "image")
        .map((item) => ({
          label: `${mediaDisplayName(item)}${formatMediaSize(item.size) ? ` (${formatMediaSize(item.size)})` : ""}`,
          value: String(item.id),
        })),
    [media],
  );
  const documentMediaOptions = useMemo(
    () =>
      media
        .filter((item) => item.file_type === "document" || item.mime_type === "application/pdf")
        .map((item) => ({
          label: `${mediaDisplayName(item)}${formatMediaSize(item.size) ? ` (${formatMediaSize(item.size)})` : ""}`,
          value: String(item.id),
        })),
    [media],
  );

  const setSectionContent = (content: Record<string, unknown>) => {
    setSectionForm((prev) => ({ ...prev, content_json: formatJson(content) }));
  };

  const updateSectionContent = (key: string, value: unknown) => {
    setSectionContent({ ...sectionContent, [key]: value });
  };

  const copyPublicUrl = async (path: string) => {
    const url = absolutePublicUrl(path);
    try {
      await navigator.clipboard.writeText(url);
      setNotice(`Copied public URL: ${url}`);
    } catch {
      setNotice(`Public URL: ${url}`);
    }
  };

  const updateHeroSlide = (index: number, updater: (slide: Record<string, unknown>) => Record<string, unknown>) => {
    const slides = Array.isArray(sectionContent.slides) ? [...sectionContent.slides] : [];
    slides[index] = updater(parseRecord(slides[index]));
    setSectionContent({ ...sectionContent, slides });
  };

  const updateDocumentItem = (index: number, updater: (item: Record<string, unknown>) => Record<string, unknown>) => {
    const items = Array.isArray(sectionContent.items) ? [...sectionContent.items] : [];
    items[index] = updater(parseRecord(items[index]));
    setSectionContent({ ...sectionContent, items });
  };

  const addHeroSlide = () => {
    const slides = Array.isArray(sectionContent.slides) ? [...sectionContent.slides] : [];
    slides.push({
      title: "New carousel slide",
      subtitle: "Short supporting message",
      imageKey: "photo1",
      button1: { text: "Learn More", link: "/" },
      button2: { text: "View Details", link: "/" },
    });
    setSectionContent({ ...sectionContent, slides });
  };

  const addDocumentItem = () => {
    const items = Array.isArray(sectionContent.items) ? [...sectionContent.items] : [];
    items.push({
      id: "",
      title: "New item",
      description: "Short public description",
      category: "Category",
      icon: "file",
      link: "/publications",
      fileType: "",
      fileSize: "",
      pages: "",
      quickLinks: [],
    });
    setSectionContent({ ...sectionContent, items });
  };

  const updateArrayItem = (key: string, index: number, value: unknown) => {
    const current = Array.isArray(sectionContent[key]) ? [...sectionContent[key]] : [];
    current[index] = value;
    setSectionContent({ ...sectionContent, [key]: current });
  };

  const removeArrayItem = (key: string, index: number) => {
    const current = Array.isArray(sectionContent[key]) ? [...sectionContent[key]] : [];
    setSectionContent({ ...sectionContent, [key]: current.filter((_, itemIndex) => itemIndex !== index) });
  };

  const addOverviewStat = () => {
    const stats = Array.isArray(sectionContent.stats) ? [...sectionContent.stats] : [];
    stats.push({
      label: "New Stat",
      value: "0",
      subtext: "Short context",
      icon: "people",
      color: "from-blue-500 to-cyan-400",
    });
    setSectionContent({ ...sectionContent, stats });
  };

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
    const publicPath = pagePublicPath(page.slug);
    const confirmed = window.confirm(
      `Publish "${page.title}" to the public website?\n\nPublic URL: ${publicPath}\n\nThis will replace the published snapshot visitors see.`,
    );
    if (!confirmed) return;
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.publishPage(page.id);
      setNotice(`Page published. Public site now uses the new snapshot at ${publicPath}.`);
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
    const publicPath = articlePublicPath(article.slug);
    const confirmed = window.confirm(
      `Publish "${article.title}" to the public News page?\n\nPublic URL: ${publicPath}\n\nThis will update the article visitors see.`,
    );
    if (!confirmed) return;
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.publishArticle(article.id);
      setNotice(`News article published at ${publicPath}.`);
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

  const archiveMedia = async (item: CMSMediaAsset) => {
    if (!item.can_archive) {
      setNotice("This media file is still used by CMS content. Remove or replace it before archiving.");
      return;
    }
    const confirmed = window.confirm(
      `Archive "${mediaDisplayName(item)}"?\n\nArchived files stay stored, but will no longer appear in the active media picker.`,
    );
    if (!confirmed) return;
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.archiveMedia(item.id);
      setNotice("Media archived.");
      await loadAll();
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to archive media."));
    } finally {
      setLoading(false);
    }
  };

  const renderSectionVisualEditor = () => {
    if (sectionForm.section_type === "hero_carousel") {
      const slides = Array.isArray(sectionContent.slides) ? sectionContent.slides : [];
      return (
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="font-bold text-slate-900">Hero Carousel Slides</h4>
              <p className="text-xs text-slate-500">Use image keys like photo1, photo2, or paste a media URL.</p>
            </div>
            <button type="button" className="portal-btn portal-btn-ghost" onClick={addHeroSlide}>
              Add Slide
            </button>
          </div>
          {slides.length === 0 ? (
            <p className="text-sm text-slate-500">No slides yet.</p>
          ) : (
            slides.map((slide, index) => {
              const row = parseRecord(slide);
              const button1 = parseRecord(row.button1);
              const button2 = parseRecord(row.button2);
              return (
                <div key={index} className="rounded-xl border border-slate-200 bg-white p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <strong className="text-sm text-slate-800">Slide {index + 1}</strong>
                    <button
                      type="button"
                      className="text-sm text-red-600"
                      onClick={() => {
                        const next = slides.filter((_, slideIndex) => slideIndex !== index);
                        setSectionContent({ ...sectionContent, slides: next });
                      }}
                    >
                      Remove
                    </button>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Title" value={textValue(row.title)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, title: value }))} />
                    <Field label="Subtitle" value={textValue(row.subtitle)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, subtitle: value }))} />
                    <Field label="Image Key" value={textValue(row.imageKey)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, imageKey: value }))} helper="Built-in carousel image key, e.g. photo1" />
                    <Field label="Image URL" value={textValue(row.imageUrl)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, imageUrl: value }))} helper="Optional uploaded media URL" />
                    <Field label="Primary Button Text" value={textValue(button1.text)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, button1: { ...parseRecord(current.button1), text: value } }))} />
                    <Field label="Primary Button Link" value={textValue(button1.link)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, button1: { ...parseRecord(current.button1), link: value } }))} />
                    <Field label="Secondary Button Text" value={textValue(button2.text)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, button2: { ...parseRecord(current.button2), text: value } }))} />
                    <Field label="Secondary Button Link" value={textValue(button2.link)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, button2: { ...parseRecord(current.button2), link: value } }))} />
                  </div>
                </div>
              );
            })
          )}
        </div>
      );
    }

    if (sectionForm.section_type === "text") {
      return (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
          <Area label="Body Content" value={textValue(sectionContent.body)} onChange={(value) => updateSectionContent("body", value)} rows={5} />
        </div>
      );
    }

    if (sectionForm.section_type === "cards" && sectionForm.section_key === "regional-overview") {
      const paragraphs = Array.isArray(sectionContent.paragraphs) ? sectionContent.paragraphs : [];
      const stats = Array.isArray(sectionContent.stats) ? sectionContent.stats : [];
      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <Field label="Overview Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />

          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
            <div className="flex items-center justify-between gap-3">
              <h4 className="font-bold text-slate-900">Overview Paragraphs</h4>
              <button
                type="button"
                className="portal-btn portal-btn-ghost"
                onClick={() => setSectionContent({ ...sectionContent, paragraphs: [...paragraphs, "New paragraph"] })}
              >
                Add Paragraph
              </button>
            </div>
            {paragraphs.map((paragraph, index) => (
              <div key={index} className="rounded-lg border border-slate-200 p-3">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <strong className="text-sm text-slate-700">Paragraph {index + 1}</strong>
                  <button type="button" className="text-sm text-red-600" onClick={() => removeArrayItem("paragraphs", index)}>
                    Remove
                  </button>
                </div>
                <Area
                  label="Text"
                  value={textValue(paragraph)}
                  onChange={(value) => updateArrayItem("paragraphs", index, value)}
                  rows={3}
                />
              </div>
            ))}
          </div>

          <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
            <div className="flex items-center justify-between gap-3">
              <h4 className="font-bold text-slate-900">Quick Stats</h4>
              <button type="button" className="portal-btn portal-btn-ghost" onClick={addOverviewStat}>
                Add Stat
              </button>
            </div>
            {stats.map((stat, index) => {
              const row = parseRecord(stat);
              return (
                <div key={index} className="rounded-lg border border-slate-200 p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <strong className="text-sm text-slate-700">Stat {index + 1}</strong>
                    <button type="button" className="text-sm text-red-600" onClick={() => removeArrayItem("stats", index)}>
                      Remove
                    </button>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <Field label="Label" value={textValue(row.label)} onChange={(value) => updateArrayItem("stats", index, { ...row, label: value })} />
                    <Field label="Value" value={textValue(row.value)} onChange={(value) => updateArrayItem("stats", index, { ...row, value })} />
                    <Field label="Subtext" value={textValue(row.subtext)} onChange={(value) => updateArrayItem("stats", index, { ...row, subtext: value })} />
                    <Field label="Icon Key" value={textValue(row.icon)} onChange={(value) => updateArrayItem("stats", index, { ...row, icon: value })} helper="Examples: people, gdp, map, building, office" />
                    <Field label="Color Classes" value={textValue(row.color)} onChange={(value) => updateArrayItem("stats", index, { ...row, color: value })} helper="Tailwind gradient classes, e.g. from-blue-500 to-cyan-400" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    if (sectionForm.section_type === "publication_catalog") {
      const categories = Array.isArray(sectionContent.categories) ? sectionContent.categories : [];
      const updateCategory = (categoryIndex: number, nextCategory: Record<string, unknown>) => {
        const next = [...categories];
        next[categoryIndex] = nextCategory;
        setSectionContent({ ...sectionContent, categories: next });
      };
      const updatePublicationDocument = (
        categoryIndex: number,
        documentIndex: number,
        nextDocument: Record<string, unknown>,
      ) => {
        const nextCategories = [...categories];
        const category = parseRecord(nextCategories[categoryIndex]);
        const documents = Array.isArray(category.documents) ? [...category.documents] : [];
        documents[documentIndex] = nextDocument;
        nextCategories[categoryIndex] = { ...category, documents };
        setSectionContent({ ...sectionContent, categories: nextCategories });
      };
      const setPublicationDocumentMedia = (
        categoryIndex: number,
        documentIndex: number,
        document: Record<string, unknown>,
        mediaId: string,
      ) => {
        const selected = mediaById.get(mediaId);
        if (!selected) {
          updatePublicationDocument(categoryIndex, documentIndex, { ...document, mediaAssetId: "", url: "" });
          return;
        }
        updatePublicationDocument(categoryIndex, documentIndex, {
          ...document,
          mediaAssetId: selected.id,
          url: selected.url,
          fileType: mediaFileTypeLabel(selected),
          fileSize: formatMediaSize(selected.size) || textValue(document.fileSize),
        });
      };
      const setPublicationCoverMedia = (
        categoryIndex: number,
        documentIndex: number,
        document: Record<string, unknown>,
        mediaId: string,
      ) => {
        const selected = mediaById.get(mediaId);
        if (!selected) {
          updatePublicationDocument(categoryIndex, documentIndex, { ...document, coverAssetId: "", coverImage: "" });
          return;
        }
        updatePublicationDocument(categoryIndex, documentIndex, {
          ...document,
          coverAssetId: selected.id,
          coverImage: selected.url,
          coverAlt: textValue(document.coverAlt) || selected.alt_text || selected.caption || textValue(document.title),
        });
      };

      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Page Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
            <Field label="Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
            <Field label="Browse Heading" value={textValue(sectionContent.browseTitle)} onChange={(value) => updateSectionContent("browseTitle", value)} />
            <Field label="Browse Helper Text" value={textValue(sectionContent.browseSubtitle)} onChange={(value) => updateSectionContent("browseSubtitle", value)} />
          </div>

          <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
            <p className="font-semibold">Publication media workflow</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              <li>Upload publication PDFs and cover images in the Media Library tab first.</li>
              <li>Return here, then choose the uploaded PDF and cover image in each document row.</li>
              <li>Save the section draft, then publish the page when the changes are ready for the public website.</li>
              <li>If no CMS media is selected, the public page keeps using the built-in fallback file for that document ID.</li>
            </ol>
          </div>

          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="font-bold text-slate-900">Publication Categories</h4>
              <p className="text-xs text-slate-500">Document IDs use built-in PDFs/covers by default. Select CMS Media to override with uploaded PDFs or cover images.</p>
            </div>
            <button
              type="button"
              className="portal-btn portal-btn-ghost"
              onClick={() =>
                setSectionContent({
                  ...sectionContent,
                  categories: [
                    ...categories,
                    {
                      id: "new-category",
                      title: "New Publication Category",
                      description: "Short public category description",
                      icon: "file",
                      color: "from-blue-600 to-cyan-500",
                      isVisible: true,
                      documents: [],
                    },
                  ],
                })
              }
            >
              Add Category
            </button>
          </div>

          {categories.map((categoryEntry, categoryIndex) => {
            const category = parseRecord(categoryEntry);
            const documents = Array.isArray(category.documents) ? category.documents : [];
            return (
              <div key={categoryIndex} className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
                <div className="flex items-center justify-between gap-3">
                  <strong className="text-sm text-slate-800">Category {categoryIndex + 1}</strong>
                  <button
                    type="button"
                    className="text-sm text-red-600"
                    onClick={() => {
                      const next = categories.filter((_, itemIndex) => itemIndex !== categoryIndex);
                      setSectionContent({ ...sectionContent, categories: next });
                    }}
                  >
                    Remove
                  </button>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="Category ID" value={textValue(category.id)} onChange={(value) => updateCategory(categoryIndex, { ...category, id: value })} helper="Use existing IDs like greenprint, rdp, rdip, rdr, res, sdg, rpmes, or rrp to keep built-in files connected." />
                  <Field label="Title" value={textValue(category.title)} onChange={(value) => updateCategory(categoryIndex, { ...category, title: value })} />
                  <Area label="Description" value={textValue(category.description)} onChange={(value) => updateCategory(categoryIndex, { ...category, description: value })} rows={2} />
                  <Field label="Icon" value={textValue(category.icon)} onChange={(value) => updateCategory(categoryIndex, { ...category, icon: value })} />
                  <Field label="Color Classes" value={textValue(category.color)} onChange={(value) => updateCategory(categoryIndex, { ...category, color: value })} helper="Example: from-blue-600 to-cyan-500" />
                  <Select
                    label="Visibility"
                    value={category.isVisible === false ? "false" : "true"}
                    onChange={(value) => updateCategory(categoryIndex, { ...category, isVisible: value === "true" })}
                    options={[
                      { label: "Visible", value: "true" },
                      { label: "Hidden", value: "false" },
                    ]}
                  />
                </div>

                <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
                  <span className="text-sm font-semibold text-slate-700">Documents</span>
                  <button
                    type="button"
                    className="text-sm font-semibold text-blue-600"
                    onClick={() => {
                      const nextDocuments = [
                        ...documents,
                        {
                          id: "",
                          title: "New document",
                          year: "",
                          fileType: "PDF",
                          fileSize: "",
                          isVisible: true,
                        },
                      ];
                      updateCategory(categoryIndex, { ...category, documents: nextDocuments });
                    }}
                  >
                    Add Document
                  </button>
                </div>

                {documents.map((documentEntry, documentIndex) => {
                  const document = parseRecord(documentEntry);
                  const documentSource = textValue(document.url)
                    ? stringValue(document.mediaAssetId)
                      ? "CMS media document selected"
                      : "Custom/manual document URL"
                    : "Built-in fallback file";
                  const coverSource = textValue(document.coverImage)
                    ? stringValue(document.coverAssetId)
                      ? "CMS cover image selected"
                      : "Custom/manual cover URL"
                    : "Built-in fallback cover";
                  return (
                    <div key={documentIndex} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <strong className="text-xs uppercase tracking-wide text-slate-500">Document {documentIndex + 1}</strong>
                        <button
                          type="button"
                          className="text-sm text-red-600"
                          onClick={() => {
                            const nextDocuments = documents.filter((_, itemIndex) => itemIndex !== documentIndex);
                            updateCategory(categoryIndex, { ...category, documents: nextDocuments });
                          }}
                        >
                          Remove
                        </button>
                      </div>
                      <div className="mb-3 grid gap-2 md:grid-cols-2">
                        <div className="rounded-lg border border-blue-100 bg-white px-3 py-2 text-xs text-blue-800">
                          <span className="font-semibold">Document source:</span> {documentSource}
                        </div>
                        <div className="rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs text-emerald-800">
                          <span className="font-semibold">Cover source:</span> {coverSource}
                        </div>
                      </div>
                      <div className="grid gap-3 md:grid-cols-3">
                        <Field label="Document ID" value={textValue(document.id)} onChange={(value) => updatePublicationDocument(categoryIndex, documentIndex, { ...document, id: value })} helper="Use existing IDs like gp1, rdp1, rdip1 to keep local files connected." />
                        <Field label="Title" value={textValue(document.title)} onChange={(value) => updatePublicationDocument(categoryIndex, documentIndex, { ...document, title: value })} />
                        <Field label="Year" value={textValue(document.year)} onChange={(value) => updatePublicationDocument(categoryIndex, documentIndex, { ...document, year: value })} />
                        <Field label="File Type" value={textValue(document.fileType)} onChange={(value) => updatePublicationDocument(categoryIndex, documentIndex, { ...document, fileType: value })} />
                        <Field label="File Size" value={textValue(document.fileSize)} onChange={(value) => updatePublicationDocument(categoryIndex, documentIndex, { ...document, fileSize: value })} />
                        <Select
                          label="Visibility"
                          value={document.isVisible === false ? "false" : "true"}
                          onChange={(value) =>
                            updatePublicationDocument(categoryIndex, documentIndex, {
                              ...document,
                              isVisible: value === "true",
                            })
                          }
                          options={[
                            { label: "Visible", value: "true" },
                            { label: "Hidden", value: "false" },
                          ]}
                        />
                        <Select
                          label="PDF / Document from Media Library"
                          value={stringValue(document.mediaAssetId)}
                          onChange={(value) => setPublicationDocumentMedia(categoryIndex, documentIndex, document, value)}
                          options={documentMediaOptions}
                          emptyLabel={
                            documentMediaOptions.length
                              ? "Use built-in file / custom URL"
                              : "No uploaded documents yet"
                          }
                          helper="Upload PDFs in Media Library first. Selecting one replaces the built-in fallback after Save Section Draft and Publish Page."
                        />
                        <Select
                          label="Cover Image from Media Library"
                          value={stringValue(document.coverAssetId)}
                          onChange={(value) => setPublicationCoverMedia(categoryIndex, documentIndex, document, value)}
                          options={imageMediaOptions}
                          emptyLabel={imageMediaOptions.length ? "Use built-in cover / custom URL" : "No uploaded images yet"}
                          helper="Upload PNG, JPG, WebP, or GIF covers in Media Library first. The selected cover is used on publication cards after publishing."
                        />
                        <Field
                          label="Custom URL (optional)"
                          value={textValue(document.url)}
                          onChange={(value) =>
                            updatePublicationDocument(categoryIndex, documentIndex, {
                              ...document,
                              mediaAssetId: "",
                              url: value,
                            })
                          }
                          helper="Use this for external or manual file links. Leave blank to use the built-in file for this document ID."
                        />
                        <Field
                          label="Custom Cover URL (optional)"
                          value={textValue(document.coverImage)}
                          onChange={(value) =>
                            updatePublicationDocument(categoryIndex, documentIndex, {
                              ...document,
                              coverAssetId: "",
                              coverImage: value,
                            })
                          }
                        />
                        <Field label="Cover Alt Text" value={textValue(document.coverAlt)} onChange={(value) => updatePublicationDocument(categoryIndex, documentIndex, { ...document, coverAlt: value })} />
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      );
    }

    if (sectionForm.section_type === "document_group") {
      const items = Array.isArray(sectionContent.items) ? sectionContent.items : [];
      if (sectionForm.section_key === "lgu-directory") {
        return (
          <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
              <Field label="Directory Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
              <button
                type="button"
                className="portal-btn portal-btn-ghost"
                onClick={() => setSectionContent({ ...sectionContent, items: [...items, { name: "New LGU", website: "https://", type: "website" }] })}
              >
                Add LGU
              </button>
            </div>
            {items.map((item, index) => {
              const row = parseRecord(item);
              return (
                <div key={index} className="rounded-xl border border-slate-200 bg-white p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <strong className="text-sm text-slate-800">LGU {index + 1}</strong>
                    <button type="button" className="text-sm text-red-600" onClick={() => removeArrayItem("items", index)}>
                      Remove
                    </button>
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    <Field label="LGU Name" value={textValue(row.name || row.title)} onChange={(value) => updateArrayItem("items", index, { ...row, name: value })} />
                    <Field label="Official Link" value={textValue(row.website || row.link)} onChange={(value) => updateArrayItem("items", index, { ...row, website: value })} />
                    <Select
                      label="Link Type"
                      value={textValue(row.type, "website")}
                      onChange={(value) => updateArrayItem("items", index, { ...row, type: value })}
                      options={[
                        { label: "Website", value: "website" },
                        { label: "Facebook", value: "facebook" },
                      ]}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        );
      }
      return (
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
            <div className="grid gap-3">
              <Field label="Group Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
              <Field label="Group Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
            </div>
            <button type="button" className="portal-btn portal-btn-ghost" onClick={addDocumentItem}>
              Add Item
            </button>
          </div>
          {items.map((item, index) => {
            const row = parseRecord(item);
            return (
              <div key={index} className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <strong className="text-sm text-slate-800">Card {index + 1}</strong>
                  <button
                    type="button"
                    className="text-sm text-red-600"
                    onClick={() => {
                      const next = items.filter((_, itemIndex) => itemIndex !== index);
                      setSectionContent({ ...sectionContent, items: next });
                    }}
                  >
                    Remove
                  </button>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="Stable ID (optional)" value={textValue(row.id)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, id: value }))} helper="Used by built-in pages to match existing cards, e.g. eo113 or executive." />
                  <Field label="Title" value={textValue(row.title)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, title: value }))} />
                  <Field label="Category Label" value={textValue(row.category)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, category: value }))} />
                  <Field label="Description" value={textValue(row.description)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, description: value }))} />
                  <Select
                    label="Icon"
                    value={textValue(row.icon)}
                    onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, icon: value }))}
                    options={iconOptions.map((icon) => ({ label: icon, value: icon }))}
                  />
                  <Field
                    label="Destination URL / Link"
                    value={textValue(row.url || row.link)}
                    onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, url: value, link: value }))}
                    helper="Use for downloadable legal documents, external files, or page links. Leave blank to use the page fallback when available."
                  />
                  <Field label="File Type (optional)" value={textValue(row.fileType)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, fileType: value }))} />
                  <Field label="File Size (optional)" value={textValue(row.fileSize)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, fileSize: value }))} />
                  <Field label="Pages (optional)" value={row.pages == null ? "" : String(row.pages)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, pages: value }))} />
                </div>
                <label className="mt-3 block">
                  <span className="text-sm font-medium text-slate-700">Quick Links</span>
                  <textarea
                    className="mt-1 h-20 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
                    value={quickLinksToText(row.quickLinks)}
                    onChange={(event) =>
                      updateDocumentItem(index, (current) => ({
                        ...current,
                        quickLinks: quickLinksFromText(event.target.value),
                      }))
                    }
                    placeholder={"RDIP DOCUMENTS|/publications?category=rdip\nRDIP DASHBOARD|/Projects"}
                  />
                  <span className="mt-1 block text-xs text-slate-500">One per line: Label|/link</span>
                </label>
              </div>
            );
          })}
        </div>
      );
    }

    if (sectionForm.section_type === "dashboard_teaser") {
      return (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Dashboard Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Button Label" value={textValue(sectionContent.buttonLabel)} onChange={(value) => updateSectionContent("buttonLabel", value)} />
          <Field label="Button Link" value={textValue(sectionContent.buttonLink)} onChange={(value) => updateSectionContent("buttonLink", value)} />
        </div>
      );
    }

    if (sectionForm.section_type === "news_preview") {
      return (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Section Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="View All Label" value={textValue(sectionContent.viewAllLabel)} onChange={(value) => updateSectionContent("viewAllLabel", value)} />
          <Field label="View All Link" value={textValue(sectionContent.viewAllLink)} onChange={(value) => updateSectionContent("viewAllLink", value)} />
        </div>
      );
    }

    if (sectionForm.section_type === "events_preview") {
      return (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Section Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
          <Field label="Button Label" value={textValue(sectionContent.buttonLabel)} onChange={(value) => updateSectionContent("buttonLabel", value)} />
          <Field label="Calendar Drawer Title" value={textValue(sectionContent.calendarTitle)} onChange={(value) => updateSectionContent("calendarTitle", value)} />
          <Field label="Calendar Drawer Subtitle" value={textValue(sectionContent.calendarSubtitle)} onChange={(value) => updateSectionContent("calendarSubtitle", value)} />
        </div>
      );
    }

    if (sectionForm.section_type === "contact_info") {
      return (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Card Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Address Label" value={textValue(sectionContent.addressLabel)} onChange={(value) => updateSectionContent("addressLabel", value)} />
          <Area label="Address" value={textValue(sectionContent.address)} onChange={(value) => updateSectionContent("address", value)} rows={3} />
          <Field label="Email Label" value={textValue(sectionContent.emailLabel)} onChange={(value) => updateSectionContent("emailLabel", value)} />
          <Field label="Email Address" value={textValue(sectionContent.email)} onChange={(value) => updateSectionContent("email", value)} />
          <Field label="Phone Label" value={textValue(sectionContent.phoneLabel)} onChange={(value) => updateSectionContent("phoneLabel", value)} />
          <Field label="Phone Number" value={textValue(sectionContent.phone)} onChange={(value) => updateSectionContent("phone", value)} />
          <Field label="Office Hours Label" value={textValue(sectionContent.hoursLabel)} onChange={(value) => updateSectionContent("hoursLabel", value)} />
          <Area label="Office Hours" value={textValue(sectionContent.officeHours)} onChange={(value) => updateSectionContent("officeHours", value)} rows={3} />
        </div>
      );
    }

    if (sectionForm.section_type === "location_map") {
      return (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Map Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Map Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
          <Field label="Map Caption" value={textValue(sectionContent.caption)} onChange={(value) => updateSectionContent("caption", value)} />
          <Field label="Badge Label" value={textValue(sectionContent.badgeLabel)} onChange={(value) => updateSectionContent("badgeLabel", value)} />
        </div>
      );
    }

    if (sectionForm.section_type === "form_intro") {
      return (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Form Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Form Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
          <Field label="Success Title" value={textValue(sectionContent.successTitle)} onChange={(value) => updateSectionContent("successTitle", value)} />
          <Field label="Success Message" value={textValue(sectionContent.successMessage)} onChange={(value) => updateSectionContent("successMessage", value)} />
          <Field label="Name Placeholder" value={textValue(sectionContent.namePlaceholder)} onChange={(value) => updateSectionContent("namePlaceholder", value)} />
          <Field label="Email Placeholder" value={textValue(sectionContent.emailPlaceholder)} onChange={(value) => updateSectionContent("emailPlaceholder", value)} />
          <Field label="Subject Placeholder" value={textValue(sectionContent.subjectPlaceholder)} onChange={(value) => updateSectionContent("subjectPlaceholder", value)} />
          <Field label="Message Placeholder" value={textValue(sectionContent.messagePlaceholder)} onChange={(value) => updateSectionContent("messagePlaceholder", value)} />
          <Field label="Submit Button Label" value={textValue(sectionContent.submitLabel)} onChange={(value) => updateSectionContent("submitLabel", value)} />
          <Field label="Loading Label" value={textValue(sectionContent.loadingLabel)} onChange={(value) => updateSectionContent("loadingLabel", value)} />
        </div>
      );
    }

    return (
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-sm text-slate-600">This section type uses the advanced JSON editor for now.</p>
      </div>
    );
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
            <button type="button" onClick={() => setShowGuide((value) => !value)} className="portal-btn portal-btn-ghost">
              CMS Guide
            </button>
          </div>
        </div>
        {notice && (
          <div className="border-t border-slate-200 px-5 py-3 text-sm text-blue-700">
            {notice}
          </div>
        )}
      </div>

      {showGuide && (
        <div className="portal-card border-blue-200 bg-blue-50">
          <div className="portal-card-body grid gap-4 text-sm text-blue-950 lg:grid-cols-3">
            <div>
              <h3 className="font-bold">Safe publishing rule</h3>
              <p className="mt-1">Saving drafts does not change the public website. Public visitors only see content after an Admin clicks Publish.</p>
            </div>
            <div>
              <h3 className="font-bold">Publication media workflow</h3>
              <p className="mt-1">Upload PDFs/covers in Media Library, select them in the Publication Catalog section, save the section, then publish the page.</p>
            </div>
            <div>
              <h3 className="font-bold">Media safety</h3>
              <p className="mt-1">Media used by pages or news cannot be archived until staff remove or replace it from the related content.</p>
            </div>
          </div>
        </div>
      )}

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
                        <div className="min-w-0">
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
                          <p className="text-xs text-slate-500">CMS slug: /{page.slug}</p>
                          <p className="text-xs text-slate-500">Public URL: {pagePublicPath(page.slug)}</p>
                          <p className="text-xs text-slate-500">Published: {formatDate(page.published_at)}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button type="button" className="text-sm text-blue-600" onClick={() => editPage(page)}>
                            Edit
                          </button>
                          <button
                            type="button"
                            className="text-sm text-slate-600"
                            onClick={() => window.open(pagePublicPath(page.slug), "_blank", "noopener,noreferrer")}
                          >
                            View Published
                          </button>
                          <button type="button" className="text-sm text-slate-600" onClick={() => copyPublicUrl(pagePublicPath(page.slug))}>
                            Copy URL
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
                    onChange={(value) =>
                      setSectionForm((prev) => ({
                        ...prev,
                        section_type: value,
                        content_json: prev.id ? prev.content_json : formatJson(sectionTemplate(value)),
                      }))
                    }
                    options={sectionTypeOptions}
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
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2">
                  <p className="text-sm text-blue-800">
                    Use the form below for normal editing. The public site still updates only after publish.
                  </p>
                  <button
                    type="button"
                    className="text-sm font-semibold text-blue-700"
                    onClick={() =>
                      setSectionForm((prev) => ({
                        ...prev,
                        content_json: formatJson(sectionTemplate(prev.section_type)),
                      }))
                    }
                  >
                    Load template
                  </button>
                </div>
                {renderSectionVisualEditor()}
                <details className="rounded-xl border border-slate-200 bg-white">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-700">
                    Advanced JSON editor
                  </summary>
                  <div className="border-t border-slate-200 p-4">
                    <textarea
                      className="h-52 w-full rounded-xl border border-slate-300 px-3 py-2 font-mono text-sm"
                      value={sectionForm.content_json}
                      onChange={(event) => setSectionForm((prev) => ({ ...prev, content_json: event.target.value }))}
                    />
                  </div>
                </details>
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
                              {section.section_type} - {section.is_visible ? "visible" : "hidden"}
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
                        <p className="text-xs text-slate-500">Public URL: {articlePublicPath(article.slug)}</p>
                        <p className="mt-1 text-sm text-slate-600">{article.summary || "No summary yet."}</p>
                      </div>
                      <div className="flex flex-wrap gap-2 text-sm">
                        <button type="button" className="text-blue-600" onClick={() => editArticle(article)}>
                          Edit
                        </button>
                        <button
                          type="button"
                          className="text-slate-600"
                          onClick={() => window.open(articlePublicPath(article.slug), "_blank", "noopener,noreferrer")}
                        >
                          View Published
                        </button>
                        <button type="button" className="text-slate-600" onClick={() => copyPublicUrl(articlePublicPath(article.slug))}>
                          Copy URL
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
              <div className="rounded-xl border border-sky-100 bg-sky-50 p-3 text-sm text-sky-900">
                <p className="font-semibold">Use this for CMS-managed files</p>
                <p className="mt-1">
                  Upload publication PDFs and cover images here, then select them inside Pages - Publications - Publication Catalog.
                  Public pages update only after the page is published.
                </p>
              </div>
              <label className="block">
                <span className="text-sm font-medium text-slate-700">Image or PDF</span>
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif,application/pdf"
                  className="mt-1 block w-full text-sm"
                  onChange={(event) => setMediaFile(event.target.files?.[0] || null)}
                />
                <span className="mt-1 block text-xs text-slate-500">
                  Allowed: PNG, JPG, WebP, GIF, and PDF. Use clear captions such as "RDP 2023 Full PDF" or "Greenprint Cover".
                </span>
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
                  {media.map((item) => {
                    const usageCount = item.usage_count || 0;
                    const usedBy = item.used_by || [];
                    const canArchive = item.can_archive !== false;
                    return (
                      <div key={item.id} className="rounded-xl border border-slate-200 p-3">
                        <div className="aspect-video overflow-hidden rounded-lg bg-slate-100">
                          {item.file_type === "image" ? (
                            <img src={item.url} alt={item.alt_text || item.caption || "CMS media"} className="h-full w-full object-cover" />
                          ) : (
                            <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-500">
                              {mediaFileTypeLabel(item)}
                            </div>
                          )}
                        </div>
                        <div className="mt-2 flex items-start justify-between gap-2">
                          <p className="min-w-0 truncate text-sm font-semibold text-slate-900">{mediaDisplayName(item)}</p>
                          <span className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${mediaTypeClass(item)}`}>
                            {mediaFileTypeLabel(item)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500">
                          {item.mime_type || "Unknown type"} - {formatMediaSize(item.size) || "Unknown size"}
                        </p>

                        <div className={`mt-3 rounded-lg border px-3 py-2 text-xs ${usageCount ? "border-amber-100 bg-amber-50 text-amber-800" : "border-emerald-100 bg-emerald-50 text-emerald-800"}`}>
                          <p className="font-semibold">{usageCount ? `Used in ${usageCount} CMS location(s)` : "Not used by CMS content"}</p>
                          {usedBy.length > 0 && (
                            <ul className="mt-1 space-y-1">
                              {usedBy.slice(0, 3).map((usage, index) => (
                                <li key={`${usage.type}-${usage.slug}-${usage.location}-${index}`}>
                                  {usage.title} - {usage.location}{usage.is_public ? " (public)" : " (draft)"}
                                </li>
                              ))}
                              {usedBy.length > 3 && <li>+{usedBy.length - 3} more location(s)</li>}
                            </ul>
                          )}
                        </div>

                        <div className="mt-2 flex flex-wrap gap-2 text-sm">
                          <a href={item.url} target="_blank" rel="noreferrer" className="text-blue-600">
                            Open
                          </a>
                          <button type="button" className="text-slate-600" onClick={() => navigator.clipboard?.writeText(item.url)}>
                            Copy URL
                          </button>
                          <button
                            type="button"
                            className={canArchive ? "text-red-600" : "cursor-not-allowed text-slate-400"}
                            disabled={!canArchive || loading}
                            title={canArchive ? "Archive this unused media file" : "Remove this file from CMS content before archiving"}
                            onClick={() => archiveMedia(item)}
                          >
                            Archive
                          </button>
                        </div>
                      </div>
                    );
                  })}
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

const Area = ({
  label,
  value,
  onChange,
  rows = 4,
  helper,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  helper?: string;
}) => (
  <label className="block">
    <span className="text-sm font-medium text-slate-700">{label}</span>
    <textarea
      className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2"
      value={value}
      rows={rows}
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
  helper,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  emptyLabel?: string;
  helper?: string;
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
    {helper && <span className="mt-1 block text-xs text-slate-500">{helper}</span>}
  </label>
);

export default CmsManager;
