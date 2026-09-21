import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import cmsApi, {
  type CMSArticle,
  type CMSMediaAsset,
  type CMSPage,
  type CMSReviewQueue,
  type CMSRevision,
  type CMSSection,
  type CMSSiteSetting,
} from "../../services/cmsApi";
import { ORGANIZATION_NODE_DEFAULTS, RESOLUTIONS_BY_YEAR } from "../../pages/About_RDC";
const RichTextEditor = React.lazy(() => import("./RichTextEditor"));
const ContributorFormsManager = React.lazy(() => import("./ContributorFormsManager"));
const AIScoringManager = React.lazy(() => import("./AIScoringManager"));

type ResourceTab = "pages" | "news" | "forms" | "media" | "review" | "revisions" | "settings" | "ai";
type PaginatedResourceTab = "pages" | "news" | "media" | "revisions";

const CMS_LIST_PAGE_SIZE = 30;

type Props = {
  mode: "admin" | "editor";
  initialTab?: ResourceTab;
};

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
  publication_date: string;
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
  publication_date: new Date().toISOString().slice(0, 10),
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

const sectionTypeLabels = new Map(sectionTypeOptions.map((option) => [option.value, option.label]));

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

const colorOptions = [
  { value: "from-blue-500 to-cyan-400", label: "Blue" },
  { value: "from-blue-600 to-cyan-500", label: "Deep Blue" },
  { value: "from-green-500 to-emerald-400", label: "Green" },
  { value: "from-teal-600 to-green-500", label: "Teal" },
  { value: "from-orange-500 to-red-400", label: "Orange" },
  { value: "from-purple-500 to-indigo-400", label: "Violet" },
  { value: "from-pink-500 to-rose-400", label: "Rose" },
  { value: "from-slate-600 to-slate-400", label: "Slate" },
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
  if (type === "image_text") {
    return {
      title: "Image and text section",
      subtitle: "",
      body: "",
      imageUrl: "",
      imageAlt: "",
      mediaAssetId: "",
      buttonText: "",
      buttonLink: "",
    };
  }
  if (type === "cards") {
    return {
      title: "Card section",
      subtitle: "",
      items: [],
    };
  }
  if (type === "faq") {
    return {
      title: "Frequently Asked Questions",
      subtitle: "",
      items: [],
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

const CMS_MEDIA_TYPE_LABELS: Record<string, string> = {
  "image/png": "PNG image",
  "image/jpeg": "JPG image",
  "image/webp": "WebP image",
  "application/pdf": "PDF document",
  "application/msword": "Word document",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word document",
  "application/vnd.ms-excel": "Excel workbook",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Excel workbook",
};

const validateSelectedMediaFile = (file: File, allowedTypes: string[]) =>
  allowedTypes.includes(file.type)
    ? ""
    : "This file type is not allowed by the current database upload policy.";

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

const stringListToText = (value: unknown) =>
  Array.isArray(value)
    ? value.map((item) => textValue(item)).filter(Boolean).join("\n")
    : "";

const stringListFromText = (value: string) =>
  value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);

const statusClass = (status: string) => {
  if (status === "published") return "bg-emerald-100 text-emerald-700";
  if (status === "submitted") return "bg-blue-100 text-blue-700";
  if (status === "rejected") return "bg-rose-100 text-rose-700";
  if (status === "archived") return "bg-slate-200 text-slate-700";
  return "bg-amber-100 text-amber-700";
};

const statusLabel = (status: string) => status ? status.charAt(0).toUpperCase() + status.slice(1) : "Draft";

const friendlySettingNames: Record<string, string> = {
  "site-logo": "Website Logo",
  "footer-text": "Footer Description",
  "contact-details": "Contact Details",
  "social-links": "Social Media Links",
  "office-address": "Office Address",
  "quick-links": "Footer Quick Links",
  "chatbot-contact-fallback-link": "Chatbot Contact Link",
  "homepage-announcement-banner": "Homepage Announcement",
  "media-upload-allowed-types": "Allowed Upload Types",
  "media-upload-max-bytes": "Upload Size Limits",
};

const sectionContentSummary = (section: CMSSection) => {
  const content = parseRecord(section.content_json);
  const slides = Array.isArray(content.slides) ? content.slides.length : 0;
  const categories = Array.isArray(content.categories) ? content.categories : [];
  const documents = categories.reduce((total, value) => {
    const rows = parseRecord(value).documents;
    return total + (Array.isArray(rows) ? rows.length : 0);
  }, 0);
  const items = Array.isArray(content.items) ? content.items.length : 0;
  const years = Array.isArray(content.years) ? content.years : [];
  const resolutions = years.reduce((total, value) => {
    const rows = parseRecord(value).resolutions;
    return total + (Array.isArray(rows) ? rows.length : 0);
  }, 0);
  const nodes = Array.isArray(content.nodes) ? content.nodes.length : 0;
  const stats = Array.isArray(content.stats) ? content.stats.length : 0;

  if (slides) return `${slides} carousel slide${slides === 1 ? "" : "s"}`;
  if (categories.length) return `${categories.length} categor${categories.length === 1 ? "y" : "ies"} · ${documents} document${documents === 1 ? "" : "s"}`;
  if (years.length) return `${years.length} year group${years.length === 1 ? "" : "s"} · ${resolutions} resolution${resolutions === 1 ? "" : "s"}`;
  if (nodes) return `${nodes} organization position${nodes === 1 ? "" : "s"}`;
  if (stats) return `${stats} profile statistic${stats === 1 ? "" : "s"}`;
  if (items) return `${items} ${section.section_type === "faq" ? "question" : "card"}${items === 1 ? "" : "s"}`;
  return textValue(content.title) || textValue(content.heading) || "Editable page content";
};

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
      if (parsed?.reason === "file_too_large") {
        return `${parsed.detail || "File is too large."} Current limit: ${formatMediaSize(Number(parsed.current_limit || 0))}.`;
      }
      if (parsed?.reason === "file_type_not_allowed") {
        return parsed.detail || "This file type is not allowed by the current CMS upload policy.";
      }
      if (typeof parsed?.detail === "string") return parsed.detail;
      const firstMessage = parsed && typeof parsed === "object"
        ? Object.values(parsed).flat().find((value) => typeof value === "string")
        : null;
      return typeof firstMessage === "string" ? firstMessage : fallback;
    } catch {
      const message = err.message.trim();
      const looksTechnical = /(?:traceback|typeerror|referenceerror|syntaxerror|<!doctype|<html|\{.*\}| at \w+|\\|\/src\/)/i.test(message);
      return !looksTechnical && message.length <= 240 ? message : fallback;
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

const nextUniqueId = (values: unknown[], prefix: string) => {
  const used = new Set(values.map((value) => textValue(parseRecord(value).id)).filter(Boolean));
  let sequence = 1;
  while (used.has(`${prefix}-${sequence}`)) sequence += 1;
  return `${prefix}-${sequence}`;
};

const corePublicPages = [
  { slug: "home", label: "Home", path: "/", scope: "Hero, public resource groups, dashboard teaser, latest news, and upcoming events" },
  { slug: "about-rdc", label: "About RDC", path: "/about", scope: "Hero, legal basis, committees, organization structure, and resolutions archive headings" },
  { slug: "regional-profile", label: "Region Profile", path: "/regional-profile", scope: "Hero, regional overview and statistics, geographic coverage, and LGU directory" },
  { slug: "publications", label: "Publications", path: "/publications", scope: "Page introduction, publication categories, documents, covers, and download links" },
  { slug: "news", label: "News", path: "/news", scope: "News landing-page hero and listing introduction; individual articles are managed in the News tab" },
  { slug: "projects-dashboard", label: "Projects Dashboard", path: "/projects", scope: "Dashboard headings and explanatory copy; project figures remain sourced from endorsed portal data" },
  { slug: "contact", label: "Contact", path: "/contact", scope: "Hero, office details, location text, and public contact-form labels and messages" },
] as const;

const corePageIndex = new Map<string, number>(
  corePublicPages.map((page, index) => [page.slug, index]),
);
const corePageDetails = new Map<string, (typeof corePublicPages)[number]>(
  corePublicPages.map((page) => [page.slug, page]),
);

const pagePublicPath = (slug: string) => {
  return corePageDetails.get(slug)?.path || `/${slug}`;
};

const articlePublicPath = (slug: string) => `/news/${slug}`;

const portableMediaUrl = (value: string) => {
  try {
    const parsed = new URL(value, window.location.origin);
    if (parsed.pathname.startsWith("/media/")) {
      return `${parsed.pathname}${parsed.search}`;
    }
  } catch {
    return value;
  }
  return value;
};

const publishedSlug = (item: CMSPage | CMSArticle) => {
  if (item.published_slug?.trim()) return item.published_slug.trim();
  const snapshotSlug = item.published_snapshot_json?.slug;
  return typeof snapshotSlug === "string" && snapshotSlug.trim()
    ? snapshotSlug.trim()
    : item.slug;
};

const absolutePublicUrl = (path: string) => {
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path}`;
};

const CmsManager: React.FC<Props> = ({ mode, initialTab = "pages" }) => {
  const [activeTab, setActiveTab] = useState<ResourceTab>(initialTab);
  const [pages, setPages] = useState<CMSPage[]>([]);
  const [articles, setArticles] = useState<CMSArticle[]>([]);
  const [media, setMedia] = useState<CMSMediaAsset[]>([]);
  const [settingsRows, setSettingsRows] = useState<CMSSiteSetting[]>([]);
  const [settingDrafts, setSettingDrafts] = useState<Record<number, unknown>>({});
  const [settingSourceDrafts, setSettingSourceDrafts] = useState<Record<number, string>>({});
  const [revisions, setRevisions] = useState<CMSRevision[]>([]);
  const [reviewQueue, setReviewQueue] = useState<CMSReviewQueue>({ pages: [], sections: [], news: [], forms: [], events: [] });
  const [selectedPageId, setSelectedPageId] = useState<number | null>(null);
  const [pageForm, setPageForm] = useState<PageForm>(emptyPageForm);
  const [sectionForm, setSectionForm] = useState<SectionForm>(emptySectionForm);
  const [sectionReadOnly, setSectionReadOnly] = useState(false);
  const [articleForm, setArticleForm] = useState<ArticleForm>(emptyArticleForm);
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaAlt, setMediaAlt] = useState("");
  const [mediaCaption, setMediaCaption] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [showGuide, setShowGuide] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [listPages, setListPages] = useState<Record<PaginatedResourceTab, number>>({
    pages: 1,
    news: 1,
    media: 1,
    revisions: 1,
  });
  const [hasMoreRows, setHasMoreRows] = useState<Record<PaginatedResourceTab, boolean>>({
    pages: false,
    news: false,
    media: false,
    revisions: false,
  });
  const developerMode = false;
  const [pageFormBaseline, setPageFormBaseline] = useState(JSON.stringify(emptyPageForm));
  const [sectionFormBaseline, setSectionFormBaseline] = useState("");
  const [articleFormBaseline, setArticleFormBaseline] = useState(JSON.stringify(emptyArticleForm));
  const loadedTabsRef = useRef<Set<ResourceTab>>(new Set());
  const mediaLoadedRef = useRef(false);
  const mediaLoadPromiseRef = useRef<Promise<CMSMediaAsset[]> | null>(null);
  const tabLoadRequestRef = useRef(0);
  const searchTimerRef = useRef<number | null>(null);

  const isAdmin = mode === "admin";

  const sectionFormSerialized = JSON.stringify(sectionForm);
  const articleFormSerialized = JSON.stringify(articleForm);
  const settingsHaveChanges = settingsRows.some(
    (row) => JSON.stringify(settingDrafts[row.id]) !== JSON.stringify(row.value_json),
  );
  const pageFormHasChanges = JSON.stringify(pageForm) !== pageFormBaseline;
  const sectionFormHasChanges = Boolean(sectionFormBaseline && sectionFormSerialized !== sectionFormBaseline);
  const articleFormHasChanges = articleFormSerialized !== articleFormBaseline;
  const hasUnsavedChanges = pageFormHasChanges || sectionFormHasChanges || articleFormHasChanges || settingsHaveChanges || Boolean(mediaFile);

  useEffect(() => setActiveTab(initialTab), [initialTab]);
  useEffect(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [hasUnsavedChanges]);
  const selectedPage = useMemo(
    () => pages.find((page) => page.id === selectedPageId) || null,
    [pages, selectedPageId],
  );
  const sortedPages = useMemo(
    () =>
      [...pages].sort((left, right) => {
        const leftOrder = corePageIndex.get(left.slug) ?? Number.MAX_SAFE_INTEGER;
        const rightOrder = corePageIndex.get(right.slug) ?? Number.MAX_SAFE_INTEGER;
        return leftOrder - rightOrder || left.title.localeCompare(right.title);
      }),
    [pages],
  );
  const selectedPageSections = selectedPage?.sections || [];
  const nextSectionKey = (sectionType: string) => {
    const base = slugify(sectionTypeLabels.get(sectionType) || sectionType || "section") || "section";
    const used = new Set(selectedPageSections.map((section) => section.section_key));
    if (!used.has(base)) return base;
    let suffix = 2;
    while (used.has(`${base}-${suffix}`)) suffix += 1;
    return `${base}-${suffix}`;
  };
  const sectionContent = useMemo(
    () => parseJsonObject(sectionForm.content_json),
    [sectionForm.content_json],
  );
  const mediaById = useMemo(() => new Map(media.map((item) => [String(item.id), item])), [media]);
  const mediaUploadLimits = useMemo(() => {
    const row = settingsRows.find((item) => item.key === "media-upload-max-bytes");
    const values = parseRecord(row?.value_json);
    return {
      image: Number(values.image || 5 * 1024 * 1024),
      document: Number(values.document || 20 * 1024 * 1024),
    };
  }, [settingsRows]);
  const allowedMediaTypes = useMemo(() => {
    const row = settingsRows.find((item) => item.key === "media-upload-allowed-types");
    const values = parseRecord(row?.value_json);
    const configured = [...(Array.isArray(values.image) ? values.image : []), ...(Array.isArray(values.document) ? values.document : [])]
      .filter((value): value is string => typeof value === "string");
    return configured.length ? configured : Object.keys(CMS_MEDIA_TYPE_LABELS);
  }, [settingsRows]);

  const setSectionContent = (content: Record<string, unknown>) => {
    setSectionForm((prev) => ({ ...prev, content_json: formatJson(content) }));
  };

  const setSettingValue = (id: number, value: unknown) => {
    setSettingDrafts((current) => ({ ...current, [id]: value }));
    setSettingSourceDrafts((current) => ({ ...current, [id]: JSON.stringify(value, null, 2) }));
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
    if (sectionForm.section_key === "committees") {
      items.push({
        id: nextUniqueId(items, "committee"),
        title: "New Committee",
        description: "Short public description",
        icon: "building",
        overview: "Committee overview",
        functions: [],
        members: [],
        url: "",
      });
    } else {
      const idPrefix = sectionForm.section_key === "legal-basis"
        ? "legal-document"
        : sectionForm.section_key === "investment-programming"
          ? "investment-card"
          : "card";
      items.push({
        id: nextUniqueId(items, idPrefix),
        title: sectionForm.section_key === "legal-basis" ? "New Legal Document" : "New Card",
        description: "Short public description",
        category: "Category",
        icon: "file",
        link: sectionForm.section_key === "investment-programming" ? "/publications?category=rdip" : "",
        fileType: "",
        fileSize: "",
        pages: "",
      });
    }
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

  const applySettingsRows = useCallback((rows: CMSSiteSetting[]) => {
    setSettingsRows(rows);
    setSettingDrafts(Object.fromEntries(rows.map((row) => [row.id, row.value_json])));
    setSettingSourceDrafts(Object.fromEntries(rows.map((row) => [row.id, JSON.stringify(row.value_json, null, 2)])));
  }, []);

  const loadMediaAssets = useCallback(async (force = false) => {
    if (!force && mediaLoadedRef.current) return;
    if (mediaLoadPromiseRef.current) {
      await mediaLoadPromiseRef.current;
      return;
    }
    const request = cmsApi.listMedia();
    mediaLoadPromiseRef.current = request;
    try {
      const rows = await request;
      setMedia(rows);
      setListPages((current) => ({ ...current, media: 1 }));
      setHasMoreRows((current) => ({ ...current, media: rows.length === CMS_LIST_PAGE_SIZE }));
      mediaLoadedRef.current = true;
    } finally {
      if (mediaLoadPromiseRef.current === request) mediaLoadPromiseRef.current = null;
    }
  }, []);

  const loadPageDetail = useCallback(async (pageId: number) => {
    const detail = await cmsApi.getPage(pageId);
    setPages((current) => current.map((page) => (page.id === detail.id ? detail : page)));
    return detail;
  }, []);

  const loadTab = useCallback(async (tab: ResourceTab, force = false, search = "") => {
    if (!force && loadedTabsRef.current.has(tab)) return;
    if (tab === "forms" || tab === "ai") {
      loadedTabsRef.current.add(tab);
      return;
    }

    const requestId = ++tabLoadRequestRef.current;
    setLoading(true);
    try {
      if (tab === "pages") {
        const pageRows = await cmsApi.listPages(search);
        setPages(pageRows);
        setListPages((current) => ({ ...current, pages: 1 }));
        setHasMoreRows((current) => ({ ...current, pages: pageRows.length === CMS_LIST_PAGE_SIZE }));
        const initialPage = pageRows.find((page) => page.slug === "home") || pageRows[0];
        if (initialPage) {
          setSelectedPageId((current) => current && pageRows.some((page) => page.id === current) ? current : initialPage.id);
          const initialSectionForm = { ...emptySectionForm, page: initialPage.id };
          setSectionForm((current) => current.page ? current : initialSectionForm);
          setSectionFormBaseline((current) => current || JSON.stringify(initialSectionForm));
          void loadPageDetail(initialPage.id).catch((error) => {
            console.error("Failed to load the selected CMS page.", error);
            setNotice(getErrorDetail(error, "The page list loaded, but its section details could not be opened."));
          });
        }
      } else if (tab === "news") {
        const articleRows = await cmsApi.listArticles(search);
        setArticles(articleRows);
        setListPages((current) => ({ ...current, news: 1 }));
        setHasMoreRows((current) => ({ ...current, news: articleRows.length === CMS_LIST_PAGE_SIZE }));
        void loadMediaAssets().catch((error) => console.error("Failed to load CMS media picker.", error));
      } else if (tab === "media") {
        const [, settingRows] = await Promise.all([
          loadMediaAssets(force),
          cmsApi.listSettings(),
        ]);
        applySettingsRows(settingRows);
      } else if (tab === "review") {
        const queue = await cmsApi.getReviewQueue();
        setReviewQueue({ ...queue, forms: Array.isArray(queue.forms) ? queue.forms : [] });
      } else if (tab === "revisions") {
        const revisionRows = await cmsApi.listRevisions(search);
        setRevisions(revisionRows);
        setListPages((current) => ({ ...current, revisions: 1 }));
        setHasMoreRows((current) => ({ ...current, revisions: revisionRows.length === CMS_LIST_PAGE_SIZE }));
      } else if (tab === "settings") {
        applySettingsRows(await cmsApi.listSettings());
        void loadMediaAssets().catch((error) => console.error("Failed to load CMS media picker.", error));
      }
      loadedTabsRef.current.add(tab);
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, `Failed to load the ${tab} CMS workspace.`));
    } finally {
      if (tabLoadRequestRef.current === requestId) setLoading(false);
    }
  }, [applySettingsRows, loadMediaAssets, loadPageDetail]);

  const updateSearch = (value: string) => {
    setSearchText(value);
    if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current);
    searchTimerRef.current = window.setTimeout(() => {
      void loadTab(activeTab, true, value.trim());
    }, 300);
  };

  useEffect(() => () => {
    if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current);
  }, []);

  const loadMoreRows = async (tab: PaginatedResourceTab) => {
    if (loading || !hasMoreRows[tab]) return;
    const nextPage = listPages[tab] + 1;
    setLoading(true);
    try {
      let rowCount = 0;
      if (tab === "pages") {
        const rows = await cmsApi.listPages(searchText.trim(), nextPage);
        rowCount = rows.length;
        setPages((current) => [...current, ...rows]);
      } else if (tab === "news") {
        const rows = await cmsApi.listArticles(searchText.trim(), nextPage);
        rowCount = rows.length;
        setArticles((current) => [...current, ...rows]);
      } else if (tab === "media") {
        const rows = await cmsApi.listMedia("", nextPage);
        rowCount = rows.length;
        setMedia((current) => [...current, ...rows]);
      } else {
        const rows = await cmsApi.listRevisions(searchText.trim(), nextPage);
        rowCount = rows.length;
        setRevisions((current) => [...current, ...rows]);
      }
      setListPages((current) => ({ ...current, [tab]: nextPage }));
      setHasMoreRows((current) => ({ ...current, [tab]: rowCount === CMS_LIST_PAGE_SIZE }));
    } catch (error) {
      setNotice(getErrorDetail(error, `Failed to load more ${tab}.`));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTab(activeTab);
  }, [activeTab, loadTab]);

  useEffect(() => {
    if (!sectionForm.id || sectionReadOnly) return;
    const timer = window.setInterval(() => {
      cmsApi.heartbeatSection(sectionForm.id!).catch(() => {
        setSectionReadOnly(true);
        setNotice("Your section editing lock expired or is no longer available. Reopen the section to continue.");
      });
    }, 120_000);
    return () => window.clearInterval(timer);
  }, [sectionForm.id, sectionReadOnly]);

  const editPage = async (page: CMSPage) => {
    if (pageFormHasChanges && pageForm.id !== page.id && !window.confirm("Discard the unsaved page changes and open another page?")) return;
    if (sectionFormHasChanges && sectionForm.page !== page.id) {
      setNotice("Save or discard the open section changes before switching to another page.");
      return;
    }
    setLoading(true);
    let fullPage = page;
    try {
      if (!Array.isArray(page.sections)) fullPage = await loadPageDetail(page.id);
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to open the page draft."));
      return;
    } finally {
      setLoading(false);
    }
    const nextForm = { id: fullPage.id, title: fullPage.title, slug: fullPage.slug };
    setPageForm(nextForm);
    setPageFormBaseline(JSON.stringify(nextForm));
    setSelectedPageId(fullPage.id);
    setSectionForm((prev) => ({ ...prev, page: fullPage.id }));
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
      setPageFormBaseline(JSON.stringify(emptyPageForm));
      await loadTab("pages", true);
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to save page."));
    } finally {
      setLoading(false);
    }
  };

  const publishPage = async (page: CMSPage) => {
    if (!isAdmin) return;
    if (sectionFormHasChanges && sectionForm.page === page.id) {
      setNotice("Save or discard the open section changes before publishing this page.");
      return;
    }
    const publicPath = pagePublicPath(page.slug);
    const currentPublicPath = pagePublicPath(publishedSlug(page));
    const slugWarning =
      page.status === "published" && currentPublicPath !== publicPath
        ? `\n\nURL change warning: the live URL will change from ${currentPublicPath} to ${publicPath}. Existing saved links may stop working.`
        : "";
    const confirmed = window.confirm(
      `Publish "${page.title}" to the public website?\n\nPublic URL: ${publicPath}\n\nThis will replace the published snapshot visitors see.${slugWarning}`,
    );
    if (!confirmed) return;
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.publishPage(page.id);
      setNotice(`Page published. Public site now uses the new snapshot at ${publicPath}.`);
      await loadTab("pages", true);
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to publish page."));
    } finally {
      setLoading(false);
    }
  };

  const populateSectionForm = (section: CMSSection) => {
    const nextForm: SectionForm = {
      id: section.id,
      page: section.page,
      section_key: section.section_key,
      section_type: section.section_type,
      order: String(section.order),
      schema_version: String(section.schema_version),
      is_visible: section.is_visible,
      content_json: JSON.stringify(section.content_json || {}, null, 2),
    };
    setSelectedPageId(section.page);
    setSectionForm(nextForm);
    setSectionFormBaseline(JSON.stringify(nextForm));
  };

  const editSection = async (section: CMSSection) => {
    if (sectionFormHasChanges && sectionForm.id !== section.id && !window.confirm("Discard the unsaved section changes and open another section?")) return;
    void loadMediaAssets().catch((error) => console.error("Failed to load CMS media picker.", error));
    populateSectionForm(section);
    if (section.is_locked && !section.locked_by_me) {
      setSectionReadOnly(true);
      setNotice(`Currently being edited by ${section.lock_owner_name || "another editor"}. This section is read-only.`);
      return;
    }
    try {
      const locked = (await cmsApi.lockSection(section.id)) as CMSSection;
      populateSectionForm(locked);
      setSectionReadOnly(false);
      setNotice("Section lock acquired for 10 minutes. It will stay active while this editor is open.");
    } catch (error) {
      setSectionReadOnly(true);
      setNotice(getErrorDetail(error, "This section is currently locked by another editor."));
      await loadTab("pages", true);
    }
  };

  const closeSectionEditor = async () => {
    if (sectionFormHasChanges && !window.confirm("Discard the unsaved changes in this section?")) return;
    const sectionId = sectionForm.id;
    const nextForm = { ...emptySectionForm, page: selectedPageId || "" };
    setSectionForm(nextForm);
    setSectionFormBaseline(JSON.stringify(nextForm));
    setSectionReadOnly(false);
    if (sectionId && !sectionReadOnly) {
      try {
        await cmsApi.unlockSection(sectionId);
      } catch {
        // An expired lock is already effectively released.
      }
      await loadTab("pages", true);
    }
  };

  const saveSection = async (event: React.FormEvent) => {
    event.preventDefault();
    if (sectionReadOnly) {
      setNotice("This section is read-only while another editor holds the lock.");
      return;
    }
    if (!sectionForm.page || !sectionForm.section_type.trim()) {
      setNotice("Choose a page and section type before saving.");
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
        section_key: slugify(sectionForm.section_key || nextSectionKey(sectionForm.section_type)),
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
      const nextForm = { ...emptySectionForm, page: Number(sectionForm.page) };
      setSectionForm(nextForm);
      setSectionFormBaseline(JSON.stringify(nextForm));
      setSectionReadOnly(false);
      await loadTab("pages", true);
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
      await loadTab("pages", true);
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to reorder sections."));
    } finally {
      setLoading(false);
    }
  };

  const editArticle = async (article: CMSArticle) => {
    if (articleFormHasChanges && articleForm.id !== article.id && !window.confirm("Discard the unsaved news changes and open another article?")) return;
    void loadMediaAssets().catch((error) => console.error("Failed to load CMS media picker.", error));
    setLoading(true);
    let fullArticle = article;
    try {
      if (typeof article.body !== "string") fullArticle = await cmsApi.getArticle(article.id);
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to open the news draft."));
      return;
    } finally {
      setLoading(false);
    }
    const nextForm: ArticleForm = {
      id: fullArticle.id,
      title: fullArticle.title,
      slug: fullArticle.slug,
      category: fullArticle.category,
      summary: fullArticle.summary,
      body: fullArticle.body,
      thumbnail: fullArticle.thumbnail || "",
      author: fullArticle.author,
      publication_date: fullArticle.publication_date || "",
      featured: fullArticle.featured,
    };
    setArticleForm(nextForm);
    setArticleFormBaseline(JSON.stringify(nextForm));
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
        publication_date: articleForm.publication_date || null,
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
      setArticleFormBaseline(JSON.stringify(emptyArticleForm));
      await loadTab("news", true);
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to save article."));
    } finally {
      setLoading(false);
    }
  };

  const publishArticle = async (article: CMSArticle) => {
    if (!isAdmin) return;
    if (articleFormHasChanges && articleForm.id === article.id) {
      setNotice("Save or discard the open article changes before publishing it.");
      return;
    }
    const publicPath = articlePublicPath(article.slug);
    const currentPublicPath = articlePublicPath(publishedSlug(article));
    const slugWarning =
      article.status === "published" && currentPublicPath !== publicPath
        ? `\n\nURL change warning: the live URL will change from ${currentPublicPath} to ${publicPath}. Existing saved links may stop working.`
        : "";
    const confirmed = window.confirm(
      `Publish "${article.title}" to the public News page?\n\nPublic URL: ${publicPath}\n\nThis will update the article visitors see.${slugWarning}`,
    );
    if (!confirmed) return;
    setLoading(true);
    setNotice("");
    try {
      await cmsApi.publishArticle(article.id);
      setNotice(`News article published at ${publicPath}.`);
      await loadTab("news", true);
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
    const fileError = validateSelectedMediaFile(mediaFile, allowedMediaTypes);
    if (fileError) {
      setNotice(fileError);
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
      await loadTab("media", true);
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
      await loadTab("media", true);
    } catch (error) {
      console.error(error);
      setNotice(getErrorDetail(error, "Failed to archive media."));
    } finally {
      setLoading(false);
    }
  };

  const runWorkflowAction = async (
    kind: "page" | "article" | "section",
    id: number,
    action: "submit" | "publish" | "reject" | "archive",
    label: string,
  ) => {
    if (kind === "section" && sectionForm.id === id && sectionFormHasChanges) {
      setNotice("Save or discard the open section changes before continuing with its workflow.");
      return;
    }
    if (kind === "article" && articleForm.id === id && articleFormHasChanges) {
      setNotice("Save or discard the open article changes before continuing with its workflow.");
      return;
    }
    if (action === "publish" && !window.confirm(`Publish "${label}" to the public website now?`)) return;
    if (action === "archive" && !window.confirm(`Archive "${label}"? It will be removed from public CMS responses.`)) return;
    const remarks = action === "reject" ? window.prompt("Reason for rejection:", "Changes requested by administrator.") : "";
    if (action === "reject" && remarks === null) return;
    setLoading(true);
    setNotice("");
    try {
      if (kind === "page") {
        if (action === "submit") await cmsApi.submitPage(id);
        if (action === "publish") await cmsApi.publishPage(id);
        if (action === "reject") await cmsApi.rejectPage(id, remarks || "");
        if (action === "archive") await cmsApi.archivePage(id);
      } else if (kind === "article") {
        if (action === "submit") await cmsApi.submitArticle(id);
        if (action === "publish") await cmsApi.publishArticle(id);
        if (action === "reject") await cmsApi.rejectArticle(id, remarks || "");
        if (action === "archive") await cmsApi.archiveArticle(id);
      } else {
        if (action === "submit") await cmsApi.submitSection(id);
        if (action === "publish") await cmsApi.publishSection(id);
        if (action === "reject") await cmsApi.rejectSection(id, remarks || "");
        if (action === "archive") await cmsApi.archiveSection(id);
      }
      setNotice(`${label}: ${action} completed.`);
      if (kind === "section" && sectionForm.id === id) {
        const nextForm = { ...emptySectionForm, page: selectedPageId || "" };
        setSectionForm(nextForm);
        setSectionFormBaseline(JSON.stringify(nextForm));
        setSectionReadOnly(false);
      }
      const refreshTab: ResourceTab = activeTab === "review"
        ? "review"
        : kind === "article"
          ? "news"
          : "pages";
      await loadTab(refreshTab, true);
    } catch (error) {
      setNotice(getErrorDetail(error, `Failed to ${action} ${label}.`));
    } finally {
      setLoading(false);
    }
  };

  const requestSectionAccess = async (section: CMSSection) => {
    try {
      await cmsApi.requestSectionAccess(section.id);
      setNotice(`Access request sent to ${section.lock_owner_name || "the current editor"}.`);
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to request access."));
    }
  };

  const releaseOwnSectionLock = async (section: CMSSection) => {
    try {
      await cmsApi.unlockSection(section.id);
      if (sectionForm.id === section.id) {
        setSectionForm({ ...emptySectionForm, page: selectedPageId || "" });
        setSectionReadOnly(false);
      }
      setNotice(`Editing lock released for ${section.section_key}.`);
      await loadTab("pages", true);
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to release the section lock."));
    }
  };

  const saveSetting = async (row: CMSSiteSetting) => {
    if (!isAdmin) return;
    try {
      const updated = (await cmsApi.updateSetting(row.key, { value_json: settingDrafts[row.id], description: row.description })) as CMSSiteSetting;
      setSettingsRows((current) => current.map((item) => item.id === row.id ? { ...item, ...updated } : item));
      setSettingDrafts((current) => ({ ...current, [row.id]: updated.value_json }));
      setSettingSourceDrafts((current) => ({ ...current, [row.id]: JSON.stringify(updated.value_json, null, 2) }));
      setNotice(`Setting "${row.key}" updated. Upload policy changes take effect immediately.`);
    } catch (error) {
      setNotice(getErrorDetail(error, "This setting could not be saved. Check the fields and try again."));
    }
  };

  const applySettingSource = (row: CMSSiteSetting) => {
    try {
      const parsed = JSON.parse(settingSourceDrafts[row.id] || "null") as unknown;
      setSettingDrafts((current) => ({ ...current, [row.id]: parsed }));
      setNotice(`Developer source applied to ${friendlySettingNames[row.key] || row.key}. Select Save Setting to keep it.`);
    } catch {
      setNotice("The developer source is not valid JSON. Correct it before applying.");
    }
  };

  const restoreRevision = async (revision: CMSRevision) => {
    if (!isAdmin || !window.confirm(`Restore ${revision.content_type} revision v${revision.version_number}?`)) return;
    try {
      await cmsApi.restoreRevision(revision.id);
      setNotice(`Revision v${revision.version_number} restored.`);
      await loadTab("revisions", true);
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to restore revision."));
    }
  };

  const renderSectionVisualEditor = () => {
    if (sectionForm.section_type === "hero_carousel") {
      const slides = Array.isArray(sectionContent.slides) ? sectionContent.slides : [];
      return (
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
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
                  <div className="grid min-w-0 gap-3 md:grid-cols-2">
                    <Field label="Title" value={textValue(row.title)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, title: value }))} />
                    <Field label="Subtitle" value={textValue(row.subtitle)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, subtitle: value }))} />
                    {developerMode && isAdmin && <Field label="Developer: Built-in Image Key" value={textValue(row.imageKey)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, imageKey: value }))} />}
                    <MediaAssetPicker
                      label="Uploaded Image"
                      assets={media.filter((item) => item.file_type === "image")}
                      value={stringValue(row.mediaAssetId || row.imageAssetId)}
                      onChange={(value) => {
                        const selected = mediaById.get(value);
                        updateHeroSlide(index, (current) => {
                          if (!selected) {
                            return { ...current, mediaAssetId: "", imageAssetId: "" };
                          }
                          return {
                            ...current,
                            mediaAssetId: selected.id,
                            imageAssetId: selected.id,
                            imageUrl: portableMediaUrl(selected.url),
                            imageAlt: textValue(current.imageAlt) || selected.alt_text || selected.caption || textValue(current.title),
                          };
                        });
                      }}
                      helper="Choose a CMS image to fill the image URL automatically."
                    />
                    {developerMode && isAdmin && <Field label="Developer: Manual Image URL" value={textValue(row.imageUrl)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, imageUrl: value }))} />}
                    <Field label="Image Alt Text" value={textValue(row.imageAlt)} onChange={(value) => updateHeroSlide(index, (current) => ({ ...current, imageAlt: value }))} helper="Short description for accessibility." />
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

    if (sectionForm.section_key === "organization-structure") {
      const configuredNodes = Array.isArray(sectionContent.nodes) ? sectionContent.nodes : [];
      const configuredById = new Map(
        configuredNodes.map((value) => {
          const row = parseRecord(value);
          return [textValue(row.id), row];
        }),
      );
      const nodes = ORGANIZATION_NODE_DEFAULTS.map((defaults) => ({
        ...defaults,
        ...configuredById.get(defaults.id),
      }));
      const updateNode = (index: number, nextNode: Record<string, unknown>) => {
        const next = nodes.map((node) => ({ ...node }));
        next[index] = nextNode as (typeof next)[number];
        setSectionContent({ ...sectionContent, nodes: next });
      };
      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid min-w-0 gap-3 md:grid-cols-2">
            <Field label="Section Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
            <Field label="Section Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
          </div>
          <div>
            <h4 className="font-bold text-slate-900">Organization Framework</h4>
            <p className="text-xs text-slate-500">Change the displayed role names, office names, descriptions, and member labels without changing the approved chart layout.</p>
          </div>
          <div className="grid gap-3 xl:grid-cols-2">
            {nodes.map((node, index) => {
              const row = parseRecord(node);
              return (
                <div key={textValue(row.id) || index} className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="mb-3 text-xs font-bold uppercase tracking-wide text-blue-700">{textValue(row.label) || `Organization Position ${index + 1}`}</p>
                  <div className="grid min-w-0 gap-3 md:grid-cols-2">
                    {developerMode && isAdmin && <Field label="Developer: Position ID" value={textValue(row.id)} onChange={(value) => updateNode(index, { ...row, id: value })} />}
                    <Field label="Group Label" value={textValue(row.label)} onChange={(value) => updateNode(index, { ...row, label: value })} />
                    <Field label="Name / Role" value={textValue(row.title)} onChange={(value) => updateNode(index, { ...row, title: value })} />
                    <Field label="Description / Office" value={textValue(row.subtitle)} onChange={(value) => updateNode(index, { ...row, subtitle: value })} />
                    {Array.isArray(row.items) && row.items.length > 0 && (
                      <Area label="Child Labels (one per line)" value={stringListToText(row.items)} onChange={(value) => updateNode(index, { ...row, items: stringListFromText(value) })} rows={4} />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    if (sectionForm.section_key === "resolutions-archive") {
      const years = Array.isArray(sectionContent.years) ? sectionContent.years : [];
      const updateYear = (yearIndex: number, nextYear: Record<string, unknown>) => {
        const next = [...years];
        next[yearIndex] = nextYear;
        setSectionContent({ ...sectionContent, years: next });
      };
      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid min-w-0 gap-3 md:grid-cols-2">
            <Field label="Section Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
            <Field label="Section Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
            <Field label="Document Legend Heading" value={textValue(sectionContent.legendTitle)} onChange={(value) => updateSectionContent("legendTitle", value)} />
            <Field label="Category Summary Heading" value={textValue(sectionContent.categoryTitle)} onChange={(value) => updateSectionContent("categoryTitle", value)} />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 className="font-bold text-slate-900">Resolution Years and Documents</h4>
              <p className="text-xs text-slate-500">Add a year, then add editable resolution titles and optional document links.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {years.length === 0 && (
                <button
                  type="button"
                  className="portal-btn portal-btn-ghost"
                  onClick={() =>
                    setSectionContent({
                      ...sectionContent,
                      years: RESOLUTIONS_BY_YEAR.map((year) => ({
                        year: year.year,
                        replaceExisting: true,
                        resolutions: year.content.map((title) => ({ title, url: "" })),
                      })),
                    })
                  }
                >
                  Load Current Public Archive
                </button>
              )}
              <button
                type="button"
                className="portal-btn portal-btn-ghost"
                onClick={() => setSectionContent({
                  ...sectionContent,
                  years: [
                    ...years,
                    { year: `Final Year ${new Date().getFullYear()}`, replaceExisting: false, resolutions: [] },
                  ],
                })}
              >
                Add Archive Year
              </button>
            </div>
          </div>
          {years.length === 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              The current hardcoded archive remains public. Select “Load Current Public Archive” to bring every existing resolution into this editor before changing or removing older entries.
            </div>
          )}
          {years.map((yearValue, yearIndex) => {
            const year = parseRecord(yearValue);
            const resolutions = Array.isArray(year.resolutions)
              ? year.resolutions
              : Array.isArray(year.items)
                ? year.items
                : [];
            return (
              <div key={yearIndex} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div className="min-w-[220px] flex-1">
                    <Field label="Archive Year Label" value={textValue(year.year)} onChange={(value) => updateYear(yearIndex, { ...year, year: value })} />
                  </div>
                  <div className="flex gap-3 text-sm">
                    <button
                      type="button"
                      className="font-semibold text-blue-600"
                      onClick={() => updateYear(yearIndex, {
                        ...year,
                        resolutions: [...resolutions, { title: "New RDC-NCR Resolution", url: "" }],
                      })}
                    >
                      Add Resolution
                    </button>
                    <button type="button" className="font-semibold text-red-600" onClick={() => setSectionContent({ ...sectionContent, years: years.filter((_, index) => index !== yearIndex) })}>
                      Remove Year
                    </button>
                  </div>
                </div>
                {resolutions.map((resolutionValue, resolutionIndex) => {
                  const resolution = typeof resolutionValue === "string"
                    ? { title: resolutionValue, url: "" }
                    : parseRecord(resolutionValue);
                  const updateResolution = (nextResolution: Record<string, unknown>) => {
                    const next = [...resolutions];
                    next[resolutionIndex] = nextResolution;
                    updateYear(yearIndex, { ...year, resolutions: next });
                  };
                  return (
                    <div key={resolutionIndex} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,0.45fr)_auto] md:items-end">
                        <Area label={`Resolution ${resolutionIndex + 1} Title`} value={textValue(resolution.title)} onChange={(value) => updateResolution({ ...resolution, title: value })} rows={3} />
                        <Field label="Document URL (optional)" value={textValue(resolution.url)} onChange={(value) => updateResolution({ ...resolution, url: value })} />
                        <button type="button" className="pb-2 text-sm font-semibold text-red-600" onClick={() => updateYear(yearIndex, { ...year, resolutions: resolutions.filter((_, index) => index !== resolutionIndex) })}>
                          Remove
                        </button>
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

    if (sectionForm.section_type === "text") {
      return (
        <div className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
          <Area label="Body Content" value={textValue(sectionContent.body)} onChange={(value) => updateSectionContent("body", value)} rows={5} />
          {sectionForm.section_key === "resolutions-archive" && (
            <>
              <Field label="Document Legend Heading" value={textValue(sectionContent.legendTitle)} onChange={(value) => updateSectionContent("legendTitle", value)} />
              <Field label="Category Summary Heading" value={textValue(sectionContent.categoryTitle)} onChange={(value) => updateSectionContent("categoryTitle", value)} />
            </>
          )}
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
            <div className="flex flex-wrap items-center justify-between gap-3">
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
            <div className="flex flex-wrap items-center justify-between gap-3">
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
                  <div className="grid min-w-0 gap-3 md:grid-cols-2">
                    <Field label="Label" value={textValue(row.label)} onChange={(value) => updateArrayItem("stats", index, { ...row, label: value })} />
                    <Field label="Value" value={textValue(row.value)} onChange={(value) => updateArrayItem("stats", index, { ...row, value })} />
                    <Field label="Subtext" value={textValue(row.subtext)} onChange={(value) => updateArrayItem("stats", index, { ...row, subtext: value })} />
                    <Select label="Icon" value={textValue(row.icon)} onChange={(value) => updateArrayItem("stats", index, { ...row, icon: value })} options={["people", "gdp", "map", "building", "office"].map((icon) => ({ label: icon.charAt(0).toUpperCase() + icon.slice(1), value: icon }))} />
                    <Select label="Color" value={textValue(row.color)} onChange={(value) => updateArrayItem("stats", index, { ...row, color: value })} options={colorOptions} emptyLabel="Use the current page color" />
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
          url: portableMediaUrl(selected.url),
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
          coverImage: portableMediaUrl(selected.url),
          coverAlt: textValue(document.coverAlt) || selected.alt_text || selected.caption || textValue(document.title),
        });
      };

      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid min-w-0 gap-3 md:grid-cols-2">
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

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 className="font-bold text-slate-900">Publication Categories</h4>
              <p className="text-xs text-slate-500">Document IDs use built-in PDFs/covers by default. Select CMS Media to override with uploaded PDFs or cover images.</p>
            </div>
            <button
              type="button"
              className="portal-btn portal-btn-ghost"
              onClick={() => {
                const categoryId = nextUniqueId(categories, "category");
                setSectionContent({
                  ...sectionContent,
                  categories: [
                    {
                      id: categoryId,
                      title: "New Publication Category",
                      description: "Short public category description",
                      icon: "file",
                      color: "from-blue-600 to-cyan-500",
                      isVisible: true,
                      documents: [],
                    },
                    ...categories,
                  ],
                });
                setNotice("New publication category card added at the top. Complete its details, add documents, then select Save Section.");
              }}
            >
              Add Category Card
            </button>
          </div>

          {categories.map((categoryEntry, categoryIndex) => {
            const category = parseRecord(categoryEntry);
            const documents = Array.isArray(category.documents) ? category.documents : [];
            return (
              <div key={categoryIndex} className="space-y-3 rounded-xl border border-slate-200 bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
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
                <div className="grid min-w-0 gap-3 md:grid-cols-2">
                  {developerMode && isAdmin && <Field label="Developer: Category ID" value={textValue(category.id)} onChange={(value) => updateCategory(categoryIndex, { ...category, id: value })} />}
                  <Field label="Title" value={textValue(category.title)} onChange={(value) => updateCategory(categoryIndex, { ...category, title: value })} />
                  <Area label="Description" value={textValue(category.description)} onChange={(value) => updateCategory(categoryIndex, { ...category, description: value })} rows={2} />
                  <Select label="Icon" value={textValue(category.icon)} onChange={(value) => updateCategory(categoryIndex, { ...category, icon: value })} options={iconOptions.map((icon) => ({ label: icon.replace(/-/g, " "), value: icon }))} />
                  <Select label="Color" value={textValue(category.color)} onChange={(value) => updateCategory(categoryIndex, { ...category, color: value })} options={colorOptions} emptyLabel="Use the current category color" />
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
                      const categoryId = textValue(category.id) || `category-${categoryIndex + 1}`;
                      const nextDocuments = [
                        {
                          id: nextUniqueId(documents, `${categoryId}-document`),
                          title: "New document",
                          year: String(new Date().getFullYear()),
                          fileType: "PDF",
                          fileSize: "",
                          isVisible: true,
                        },
                        ...documents,
                      ];
                      updateCategory(categoryIndex, { ...category, documents: nextDocuments });
                      setNotice(`New document added at the top of ${textValue(category.title) || `Category ${categoryIndex + 1}`}. Complete its details, then select Save Section.`);
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
                      <div className="grid min-w-0 gap-3 md:grid-cols-3">
                        {developerMode && isAdmin && <Field label="Developer: Document ID" value={textValue(document.id)} onChange={(value) => updatePublicationDocument(categoryIndex, documentIndex, { ...document, id: value })} />}
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
                        <MediaAssetPicker
                          label="PDF / Document from Media Library"
                          assets={media.filter((item) => item.file_type === "document" || item.mime_type === "application/pdf")}
                          value={stringValue(document.mediaAssetId)}
                          onChange={(value) => setPublicationDocumentMedia(categoryIndex, documentIndex, document, value)}
                          helper="Upload PDFs in Media Library first. Selecting one replaces the built-in fallback after Save Section Draft and Publish Page."
                        />
                        <MediaAssetPicker
                          label="Cover Image from Media Library"
                          assets={media.filter((item) => item.file_type === "image")}
                          value={stringValue(document.coverAssetId)}
                          onChange={(value) => setPublicationCoverMedia(categoryIndex, documentIndex, document, value)}
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
            <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
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
                  <div className="grid min-w-0 gap-3 md:grid-cols-3">
                    <Field label="LGU Name" value={textValue(row.name || row.title)} onChange={(value) => updateArrayItem("items", index, { ...row, name: value })} />
                    <Field label="Official Link" value={textValue(row.website || row.link)} onChange={(value) => updateArrayItem("items", index, { ...row, website: value })} />
                    <Select
                      label="Link Type"
                      value={textValue(row.type) || "website"}
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
          <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <div className="grid gap-3">
              <Field label="Group Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
              <Field label="Group Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
            </div>
            <button type="button" className="portal-btn portal-btn-ghost" onClick={addDocumentItem}>
              {sectionForm.section_key === "legal-basis"
                ? "Add Legal Document"
                : sectionForm.section_key === "committees"
                  ? "Add Committee"
                  : "Add Card"}
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
                <div className="grid min-w-0 gap-3 md:grid-cols-2">
                  {developerMode && isAdmin && <Field label="Developer: Stable ID" value={textValue(row.id)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, id: value }))} />}
                  <Field label="Title" value={textValue(row.title)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, title: value }))} />
                  <Field label="Category Label" value={textValue(row.category)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, category: value }))} />
                  <Field label="Description" value={textValue(row.description)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, description: value }))} />
                  <Select
                    label="Icon"
                    value={textValue(row.icon)}
                    onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, icon: value }))}
                    options={iconOptions.map((icon) => ({ label: icon, value: icon }))}
                  />
                  <MediaAssetPicker
                    label="CMS Document / PDF"
                    assets={media.filter((item) => item.file_type === "document" || item.mime_type === "application/pdf")}
                    value={stringValue(row.mediaAssetId || row.documentAssetId)}
                    onChange={(value) => {
                      const selected = mediaById.get(value);
                      updateDocumentItem(index, (current) => {
                        if (!selected) {
                          return { ...current, mediaAssetId: "", documentAssetId: "" };
                        }
                        return {
                          ...current,
                          mediaAssetId: selected.id,
                          documentAssetId: selected.id,
                          url: portableMediaUrl(selected.url),
                          link: portableMediaUrl(selected.url),
                          fileType: mediaFileTypeLabel(selected),
                          fileSize: formatMediaSize(selected.size) || textValue(current.fileSize),
                        };
                      });
                    }}
                    helper="Choose an uploaded PDF/document to fill the card link and file metadata."
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
                  <Select
                    label="Card Visibility"
                    value={row.isVisible === false ? "false" : "true"}
                    onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, isVisible: value === "true" }))}
                    options={[{ label: "Visible", value: "true" }, { label: "Hidden", value: "false" }]}
                  />
                </div>
                {sectionForm.section_key === "committees" && (
                  <div className="mt-3 grid min-w-0 gap-3 md:grid-cols-2">
                    <Area label="Committee Overview" value={textValue(row.overview || parseRecord(row.content).overview)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, overview: value }))} rows={3} />
                    <Area label="Functions (one per line)" value={stringListToText(row.functions || parseRecord(row.content).functions)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, functions: stringListFromText(value) }))} rows={4} />
                    <Area label="Members (one per line)" value={stringListToText(row.members || parseRecord(row.content).members)} onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, members: stringListFromText(value) }))} rows={4} />
                  </div>
                )}
                {sectionForm.section_key !== "investment-programming" && sectionForm.section_key !== "committees" && (
                  <div className="mt-3">
                    <QuickLinksEditor
                      title="Quick Links"
                      value={row.quickLinks}
                      onChange={(value) => updateDocumentItem(index, (current) => ({ ...current, quickLinks: value }))}
                    />
                  </div>
                )}
              </div>
            );
          })}
          {sectionForm.section_key === "investment-programming" && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <QuickLinksEditor
                title="Quick Access (always displayed after all cards)"
                value={sectionContent.quickLinks || parseRecord(items[0]).quickLinks}
                onChange={(value) => updateSectionContent("quickLinks", value)}
                helper="Add and edit cards above. Quick Access remains a single bottom block on the public Home page."
              />
            </div>
          )}
        </div>
      );
    }

    if (sectionForm.section_type === "image_text") {
      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid min-w-0 gap-3 md:grid-cols-2">
            <Field label="Heading" value={textValue(sectionContent.title || sectionContent.heading)} onChange={(value) => updateSectionContent(sectionContent.heading !== undefined ? "heading" : "title", value)} />
            <Field label="Supporting Text" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
            <Area label="Main Content" value={textValue(sectionContent.body || sectionContent.description)} onChange={(value) => updateSectionContent(sectionContent.description !== undefined ? "description" : "body", value)} rows={6} />
            <div className="space-y-3">
              <MediaAssetPicker
                label="Section Image"
                assets={media.filter((item) => item.file_type === "image")}
                value={stringValue(sectionContent.mediaAssetId || sectionContent.imageAssetId)}
                onChange={(value) => {
                  const selected = mediaById.get(value);
                  setSectionContent({
                    ...sectionContent,
                    mediaAssetId: selected?.id || "",
                    imageAssetId: selected?.id || "",
                    imageUrl: selected ? portableMediaUrl(selected.url) : textValue(sectionContent.imageUrl),
                    imageAlt: selected ? textValue(sectionContent.imageAlt) || selected.alt_text || selected.caption : textValue(sectionContent.imageAlt),
                  });
                }}
                helper="Choose an uploaded image. Existing manual image addresses are preserved automatically."
              />
              <Field label="Image Description" value={textValue(sectionContent.imageAlt)} onChange={(value) => updateSectionContent("imageAlt", value)} helper="Briefly describe meaningful images for visitors using assistive technology." />
            </div>
            <Field label="Button Text" value={textValue(sectionContent.buttonText)} onChange={(value) => updateSectionContent("buttonText", value)} />
            <Field label="Button Destination" value={textValue(sectionContent.buttonLink)} onChange={(value) => updateSectionContent("buttonLink", value)} />
          </div>
        </div>
      );
    }

    if (sectionForm.section_type === "cards") {
      const items = Array.isArray(sectionContent.items) ? sectionContent.items : [];
      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Section Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
              <Field label="Section Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
            </div>
            <button
              type="button"
              className="portal-btn portal-btn-ghost"
              onClick={() => setSectionContent({ ...sectionContent, items: [...items, { id: nextUniqueId(items, "card"), title: "New card", description: "", icon: "file", link: "", isVisible: true }] })}
            >
              Add Card
            </button>
          </div>
          {items.length === 0 && <EmptyEditorState title="No cards yet" detail="Select Add Card to create the first card in this section." />}
          {items.map((item, index) => {
            const row = parseRecord(item);
            return (
              <div key={textValue(row.id) || index} className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <strong className="text-sm text-slate-800">Card {index + 1}</strong>
                  <button type="button" className="text-sm text-red-600" onClick={() => removeArrayItem("items", index)}>Remove</button>
                </div>
                <div className="grid min-w-0 gap-3 md:grid-cols-2">
                  {developerMode && isAdmin && <Field label="Developer: Stable ID" value={textValue(row.id)} onChange={(value) => updateArrayItem("items", index, { ...row, id: value })} />}
                  <Field label="Card Title" value={textValue(row.title)} onChange={(value) => updateArrayItem("items", index, { ...row, title: value })} />
                  <Area label="Description" value={textValue(row.description || row.body)} onChange={(value) => updateArrayItem("items", index, { ...row, description: value })} rows={3} />
                  <Select label="Icon" value={textValue(row.icon)} onChange={(value) => updateArrayItem("items", index, { ...row, icon: value })} options={iconOptions.map((icon) => ({ label: icon.replace(/-/g, " "), value: icon }))} />
                  <Field label="Button Text" value={textValue(row.buttonText || row.linkLabel)} onChange={(value) => updateArrayItem("items", index, { ...row, buttonText: value })} />
                  <Field label="Button Destination" value={textValue(row.link || row.buttonLink)} onChange={(value) => updateArrayItem("items", index, { ...row, link: value })} />
                  <Select label="Card Visibility" value={row.isVisible === false ? "false" : "true"} onChange={(value) => updateArrayItem("items", index, { ...row, isVisible: value === "true" })} options={[{ label: "Visible", value: "true" }, { label: "Hidden", value: "false" }]} />
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    if (sectionForm.section_type === "faq") {
      const items = Array.isArray(sectionContent.items) ? sectionContent.items : [];
      return (
        <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Section Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
              <Field label="Section Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
            </div>
            <button type="button" className="portal-btn portal-btn-ghost" onClick={() => setSectionContent({ ...sectionContent, items: [...items, { id: nextUniqueId(items, "question"), question: "New question", answer: "" }] })}>
              Add Question
            </button>
          </div>
          {items.length === 0 && <EmptyEditorState title="No questions yet" detail="Select Add Question to create the first answer." />}
          {items.map((item, index) => {
            const row = parseRecord(item);
            return (
              <div key={textValue(row.id) || index} className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <strong className="text-sm text-slate-800">Question {index + 1}</strong>
                  <button type="button" className="text-sm text-red-600" onClick={() => removeArrayItem("items", index)}>Remove</button>
                </div>
                <div className="grid min-w-0 gap-3">
                  {developerMode && isAdmin && <Field label="Developer: Stable ID" value={textValue(row.id)} onChange={(value) => updateArrayItem("items", index, { ...row, id: value })} />}
                  <Field label="Question" value={textValue(row.question)} onChange={(value) => updateArrayItem("items", index, { ...row, question: value })} />
                  <Area label="Answer" value={textValue(row.answer)} onChange={(value) => updateArrayItem("items", index, { ...row, answer: value })} rows={4} />
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    if (sectionForm.section_type === "dashboard_teaser") {
      return (
        <div className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Dashboard Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Button Label" value={textValue(sectionContent.buttonLabel)} onChange={(value) => updateSectionContent("buttonLabel", value)} />
          <Field label="Button Link" value={textValue(sectionContent.buttonLink)} onChange={(value) => updateSectionContent("buttonLink", value)} />
        </div>
      );
    }

    if (sectionForm.section_type === "news_preview") {
      return (
        <div className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Section Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="View All Label" value={textValue(sectionContent.viewAllLabel)} onChange={(value) => updateSectionContent("viewAllLabel", value)} />
          <Field label="View All Link" value={textValue(sectionContent.viewAllLink)} onChange={(value) => updateSectionContent("viewAllLink", value)} />
        </div>
      );
    }

    if (sectionForm.section_type === "events_preview") {
      return (
        <div className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
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
        <div className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
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
        <div className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <Field label="Map Title" value={textValue(sectionContent.title)} onChange={(value) => updateSectionContent("title", value)} />
          <Field label="Map Subtitle" value={textValue(sectionContent.subtitle)} onChange={(value) => updateSectionContent("subtitle", value)} />
          <Field label="Map Caption" value={textValue(sectionContent.caption)} onChange={(value) => updateSectionContent("caption", value)} />
          <Field label="Badge Label" value={textValue(sectionContent.badgeLabel)} onChange={(value) => updateSectionContent("badgeLabel", value)} />
        </div>
      );
    }

    if (sectionForm.section_type === "form_intro") {
      return (
        <div className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
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
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
        <h4 className="font-bold text-amber-900">Unsupported Section</h4>
        <p className="mt-1 text-sm text-amber-800">
          This section type does not have a visual editor yet. Its existing content is preserved unchanged. Ask an administrator or developer for help before modifying it.
        </p>
        <p className="mt-2 text-xs text-amber-700">You can still change its visibility or close this editor without losing any stored fields.</p>
      </div>
    );
  };

  return (
    <div className="min-w-0 space-y-4">
      <div className="portal-card min-w-0 overflow-hidden">
        <div className="portal-card-body flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-900">Content CMS</h2>
            <p className="text-sm text-slate-500">
              Manage public content and contributor form drafts. Live content changes only after Admin publishes.
            </p>
            {hasUnsavedChanges && <p className="mt-1 text-xs font-semibold text-amber-700">You have unsaved changes.</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {(["pages", "news", "forms", "media", "review", "revisions", "settings", "ai"] as ResourceTab[]).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => {
                  if (tab !== activeTab && searchText) loadedTabsRef.current.delete(activeTab);
                  if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current);
                  setSearchText("");
                  setActiveTab(tab);
                }}
                className={`portal-btn ${activeTab === tab ? "portal-btn-primary" : "portal-btn-ghost"}`}
              >
                {{
                  pages: "Pages",
                  news: "News",
                  forms: "Contributor Forms",
                  media: "Media Library",
                  review: "Review Queue",
                  revisions: "Revision History",
                  settings: "Site Settings",
                  ai: "AI Scoring",
                }[tab]}
              </button>
            ))}
            {["pages", "news", "revisions"].includes(activeTab) && (
              <input
                type="search"
                value={searchText}
                onChange={(event) => updateSearch(event.target.value)}
                placeholder={`Search ${activeTab === "pages" ? "pages" : activeTab === "news" ? "news" : "history"}`}
                aria-label={`Search ${activeTab}`}
                className="min-w-48 rounded-xl border border-slate-300 px-3 py-2 text-sm"
              />
            )}
            <button type="button" onClick={() => {
              if (hasUnsavedChanges && !window.confirm("Reload CMS data and discard all unsaved changes?")) return;
              void loadTab(activeTab, true);
            }} className="portal-btn portal-btn-ghost" disabled={loading}>
              {loading ? "Working..." : "Refresh"}
            </button>
            <button type="button" onClick={() => setShowGuide((value) => !value)} className="portal-btn portal-btn-ghost">
              CMS Guide
            </button>
          </div>
        </div>
        {notice && (
          <div role="status" aria-live="polite" className="border-t border-slate-200 px-5 py-3 text-sm text-blue-700">
            {notice}
          </div>
        )}
        {loading && <div className="h-1 w-full animate-pulse bg-gradient-to-r from-blue-600 via-cyan-400 to-blue-600" role="progressbar" aria-label="CMS operation in progress" />}
      </div>

      {showGuide && (
        <div className="portal-card min-w-0 overflow-hidden border-blue-200 bg-blue-50">
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
        <div className="grid min-w-0 gap-4 2xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-4">
            <form onSubmit={savePage} className="portal-card min-w-0 overflow-hidden">
              <div className="portal-card-header min-w-0">
                <h3 className="font-bold text-slate-900">{pageForm.id ? "Edit Page Draft" : "Create Page Draft"}</h3>
              </div>
              <div className="portal-card-body min-w-0 space-y-3">
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
                {developerMode && isAdmin && (
                  <Field
                    label="Developer: Page Slug"
                    value={pageForm.slug}
                    onChange={(value) => setPageForm((prev) => ({ ...prev, slug: value }))}
                    helper={pages.find((page) => page.id === pageForm.id)?.published_at ? "Locked after first publish to protect shared links." : "Internal URL name, such as about-rdc."}
                    disabled={Boolean(pages.find((page) => page.id === pageForm.id)?.published_at)}
                  />
                )}
                <div className="flex flex-wrap gap-2">
                  <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                    {pageForm.id ? "Save Page Draft" : "Create Page"}
                  </button>
                  {pageForm.id && (
                    <button type="button" className="portal-btn portal-btn-ghost" onClick={() => {
                      if (pageFormHasChanges && !window.confirm("Discard the unsaved page changes?")) return;
                      setPageForm(emptyPageForm);
                      setPageFormBaseline(JSON.stringify(emptyPageForm));
                    }}>
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            </form>

            <div className="portal-card min-w-0 overflow-hidden">
              <div className="portal-card-header min-w-0">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="font-bold text-slate-900">Public Website Pages</h3>
                    <p className="text-xs text-slate-500">All seven core public pages are managed here. Select Edit to manage that page and its section blocks.</p>
                  </div>
                  <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                    {corePublicPages.filter((definition) => pages.some((page) => page.slug === definition.slug)).length}/{corePublicPages.length} core pages
                  </span>
                </div>
              </div>
              <div className="portal-card-body min-w-0 space-y-3">
                {pages.length === 0 ? (
                  <p className="text-sm text-slate-500">No CMS pages yet.</p>
                ) : (
                  sortedPages.map((page) => (
                    <div
                      key={page.id}
                      data-cms-page-id={page.id}
                      className={`rounded-xl border p-3 ${selectedPageId === page.id ? "border-blue-400 bg-blue-50" : "border-slate-200"}`}
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <strong className="break-words">{page.title}</strong>
                            <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(page.status)}`}>
                              {statusLabel(page.status)}
                            </span>
                            {page.has_unpublished_changes && (
                              <span className="rounded-full bg-orange-100 px-2 py-1 text-xs font-semibold text-orange-700">
                                unpublished changes
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500">Public URL: {pagePublicPath(publishedSlug(page))}</p>
                          {corePageDetails.get(page.slug) && (
                            <p className="mt-1 text-xs leading-relaxed text-slate-600">
                              <span className="font-semibold">Editable parts:</span> {corePageDetails.get(page.slug)?.scope}
                            </p>
                          )}
                          {page.status === "published" && publishedSlug(page) !== page.slug && (
                            <p className="text-xs font-medium text-orange-700">
                              Draft URL after publish: {pagePublicPath(page.slug)}
                            </p>
                          )}
                          <p className="text-xs text-slate-500">Published: {formatDate(page.published_at)}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {page.status !== "archived" && (
                            <button type="button" className="text-sm text-blue-600" onClick={() => editPage(page)}>Edit</button>
                          )}
                          <button
                            type="button"
                            className="text-sm text-slate-600"
                            onClick={() => window.open(pagePublicPath(publishedSlug(page)), "_blank", "noopener,noreferrer")}
                          >
                            View Published
                          </button>
                          <button type="button" className="text-sm text-slate-600" onClick={() => copyPublicUrl(pagePublicPath(publishedSlug(page)))}>
                            Copy URL
                          </button>
                          {isAdmin && page.status !== "archived" && (
                            <button type="button" className="text-sm text-emerald-700" onClick={() => publishPage(page)}>
                              Publish
                            </button>
                          )}
                          {!isAdmin && page.status !== "submitted" && page.status !== "archived" && (
                            <button type="button" className="text-sm text-blue-700" onClick={() => runWorkflowAction("page", page.id, "submit", page.title)}>
                              Submit
                            </button>
                          )}
                          {isAdmin && page.status === "submitted" && (
                            <button type="button" className="text-sm text-rose-700" onClick={() => runWorkflowAction("page", page.id, "reject", page.title)}>
                              Reject
                            </button>
                          )}
                          {isAdmin && page.status !== "archived" && (
                            <button type="button" className="text-sm text-slate-600" onClick={() => runWorkflowAction("page", page.id, "archive", page.title)}>
                              Archive
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

          <div className="min-w-0 space-y-4">
            <form onSubmit={saveSection} className="portal-card min-w-0 overflow-hidden">
              <div className="portal-card-header flex min-w-0 items-center justify-between gap-3">
                <div>
                  <h3 className="font-bold text-slate-900">{sectionForm.id ? sectionReadOnly ? "View Locked Section" : "Edit Section Block" : "Add Section Block"}</h3>
                  {sectionForm.id && <p className="text-xs text-slate-500">Locks expire after 10 minutes; this editor refreshes them every 2 minutes.</p>}
                </div>
                {sectionForm.id && <button type="button" className="portal-btn portal-btn-ghost" onClick={closeSectionEditor}>Close</button>}
              </div>
              {sectionReadOnly && (
                <div className="border-b border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-800">
                  Another editor currently holds this section lock. Fields are read-only until the lock is released or expires.
                </div>
              )}
              <fieldset disabled={sectionReadOnly} className="portal-card-body min-w-0 space-y-4 disabled:opacity-70">
                <div className="grid min-w-0 gap-3 md:grid-cols-2">
                  <Select
                    label="Page"
                    value={String(sectionForm.page)}
                    onChange={(value) => {
                      const pageId = value ? Number(value) : "";
                      setSelectedPageId(pageId || null);
                      setSectionForm((prev) => ({ ...prev, page: pageId }));
                      if (pageId) {
                        const page = pages.find((item) => item.id === pageId);
                        if (page && !Array.isArray(page.sections)) {
                          void loadPageDetail(pageId).catch((error) => {
                            setNotice(getErrorDetail(error, "Failed to load this page's sections."));
                          });
                        }
                      }
                    }}
                    options={sortedPages.map((page) => ({ label: page.title, value: String(page.id) }))}
                  />
                  <Select
                    label="Section Type"
                    value={sectionForm.section_type}
                    onChange={(value) =>
                      setSectionForm((prev) => ({
                        ...prev,
                        section_type: value,
                        section_key: prev.id ? prev.section_key : nextSectionKey(value),
                        content_json: prev.id ? prev.content_json : formatJson(sectionTemplate(value)),
                      }))
                    }
                    options={sectionTypeOptions}
                  />
                </div>
                {developerMode && isAdmin && (
                  <div className="grid min-w-0 gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 md:grid-cols-3">
                    <Field label="Developer: Section Key" value={sectionForm.section_key} onChange={(value) => setSectionForm((prev) => ({ ...prev, section_key: value }))} helper="Unique internal key for this page." />
                    <Field label="Developer: Order" value={sectionForm.order} onChange={(value) => setSectionForm((prev) => ({ ...prev, order: value }))} />
                    <Field label="Developer: Schema Version" value={sectionForm.schema_version} onChange={(value) => setSectionForm((prev) => ({ ...prev, schema_version: value }))} />
                  </div>
                )}
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
                    onClick={() => {
                      if (!window.confirm("Replace the current section fields with a fresh template? Existing unsaved values in this editor will be discarded.")) return;
                      setSectionForm((prev) => ({ ...prev, content_json: formatJson(sectionTemplate(prev.section_type)) }));
                    }}
                  >
                    Load template
                  </button>
                </div>
                <div className="min-w-0 space-y-4">
                  {renderSectionVisualEditor()}
                  {developerMode && isAdmin && (
                    <details className="overflow-hidden rounded-xl border border-amber-200 bg-white">
                      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-amber-800">Developer: Section JSON source</summary>
                      <div className="border-t border-amber-200 p-4">
                        <textarea aria-label="Section JSON source" className="h-52 min-w-0 w-full rounded-xl border border-amber-300 px-3 py-2 font-mono text-sm" value={sectionForm.content_json} onChange={(event) => setSectionForm((prev) => ({ ...prev, content_json: event.target.value }))} />
                      </div>
                    </details>
                  )}
                </div>
                <div className="sticky bottom-0 z-10 flex flex-wrap gap-2 border-t border-slate-200 bg-white/95 py-3 backdrop-blur">
                  <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                    {sectionForm.id ? "Save Section Draft" : "Add Section"}
                  </button>
                  {sectionForm.id && (
                    <button
                      type="button"
                      className="portal-btn portal-btn-ghost"
                      onClick={closeSectionEditor}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </fieldset>
            </form>

            <div className="portal-card min-w-0 overflow-hidden">
              <div className="portal-card-header min-w-0">
                <h3 className="font-bold text-slate-900">Sections {selectedPage ? `for ${selectedPage.title}` : ""}</h3>
              </div>
              <div className="portal-card-body min-w-0 space-y-3">
                {!selectedPage ? (
                  <p className="text-sm text-slate-500">Select or create a page to manage sections.</p>
                ) : selectedPageSections.length === 0 ? (
                  <p className="text-sm text-slate-500">No sections yet.</p>
                ) : (
                  [...selectedPageSections]
                    .filter((section) => section.status !== "archived")
                    .sort((a, b) => a.order - b.order || a.id - b.id)
                    .map((section, index, list) => (
                      <div data-cms-section-id={section.id} key={section.id} className={`rounded-xl border bg-white p-3 ${sectionForm.id === section.id ? "border-blue-400 ring-2 ring-blue-100" : "border-slate-200"}`}>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <strong>{section.order}. {textValue(parseRecord(section.content_json).title) || sectionTypeLabels.get(section.section_type) || "Page Section"}</strong>
                              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(section.status)}`}>{statusLabel(section.status)}</span>
                              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${section.is_visible ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                                {section.is_visible ? "Visible" : "Hidden"}
                              </span>
                            </div>
                            <p className="mt-1 text-xs font-medium text-slate-600">{sectionTypeLabels.get(section.section_type) || "Unsupported Section"}</p>
                            <p className="text-xs text-slate-500">{sectionContentSummary(section)} · Updated {formatDate(section.updated_at)}</p>
                            {section.is_locked && !section.locked_by_me && (
                              <p className="text-xs font-semibold text-amber-700">
                                Editing locked by {section.lock_owner_name || "another editor"}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-2 text-sm">
                            <button type="button" className="text-slate-600" disabled={index === 0} onClick={() => moveSection(section, -1)}>
                              Up
                            </button>
                            <button type="button" className="text-slate-600" disabled={index === list.length - 1} onClick={() => moveSection(section, 1)}>
                              Down
                            </button>
                            <button type="button" className="text-blue-600" onClick={() => editSection(section)}>
                              {section.is_locked && !section.locked_by_me ? "View" : "Edit"}
                            </button>
                            {section.is_locked && !section.locked_by_me && (
                              <button type="button" className="text-amber-700" onClick={() => requestSectionAccess(section)}>Request Access</button>
                            )}
                            {section.is_locked && section.locked_by_me && (
                              <button type="button" className="text-amber-700" onClick={() => releaseOwnSectionLock(section)}>Release Edit Lock</button>
                            )}
                            {!isAdmin && section.status !== "submitted" && section.status !== "archived" && (
                              <button type="button" className="text-blue-700" onClick={() => runWorkflowAction("section", section.id, "submit", section.section_key)}>Submit</button>
                            )}
                            {isAdmin && section.status !== "archived" && (
                              <button type="button" className="text-emerald-700" onClick={() => runWorkflowAction("section", section.id, "publish", section.section_key)}>Publish</button>
                            )}
                            {isAdmin && section.status === "submitted" && (
                              <button type="button" className="text-rose-700" onClick={() => runWorkflowAction("section", section.id, "reject", section.section_key)}>Reject</button>
                            )}
                            {isAdmin && section.status !== "archived" && (
                              <button type="button" className="text-slate-600" onClick={() => runWorkflowAction("section", section.id, "archive", section.section_key)}>Archive</button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "news" && (
        <div className="grid min-w-0 gap-4 2xl:grid-cols-[minmax(320px,460px)_minmax(0,1fr)]">
          <form onSubmit={saveArticle} className="portal-card min-w-0 overflow-hidden">
            <div className="portal-card-header min-w-0">
              <h3 className="font-bold text-slate-900">{articleForm.id ? "Edit News Draft" : "Create News Draft"}</h3>
            </div>
            <div className="portal-card-body min-w-0 space-y-3">
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
              {developerMode && isAdmin && (
                <Field
                  label="Developer: Article Slug"
                  value={articleForm.slug}
                  onChange={(value) => setArticleForm((prev) => ({ ...prev, slug: value }))}
                  helper={articles.find((article) => article.id === articleForm.id)?.published_at ? "Locked after first publish to protect shared links." : "Automatically generated from the title."}
                  disabled={Boolean(articles.find((article) => article.id === articleForm.id)?.published_at)}
                />
              )}
              <div className="grid min-w-0 gap-3 md:grid-cols-2">
                <Field
                  label="Category"
                  value={articleForm.category}
                  onChange={(value) => setArticleForm((prev) => ({ ...prev, category: value }))}
                />
                <MediaAssetPicker
                  label="Thumbnail"
                  assets={media.filter((item) => item.file_type === "image")}
                  value={String(articleForm.thumbnail || "")}
                  onChange={(value) => setArticleForm((prev) => ({ ...prev, thumbnail: value ? Number(value) : "" }))}
                  helper="Upload images in Media Library first, then select one as the public news thumbnail."
                />
              </div>
              <Field
                label="Short Summary"
                value={articleForm.summary}
                onChange={(value) => setArticleForm((prev) => ({ ...prev, summary: value }))}
              />
              <label className="block min-w-0">
                <span className="text-sm font-medium text-slate-700">Article Body</span>
                <div className="mt-1">
                  <React.Suspense fallback={<div className="rounded-xl border border-slate-200 p-4 text-sm text-slate-500">Loading article editor...</div>}>
                    <RichTextEditor
                      value={articleForm.body}
                      onChange={(value) => setArticleForm((prev) => ({ ...prev, body: value }))}
                    />
                  </React.Suspense>
                </div>
              </label>
              {developerMode && isAdmin && (
                <details className="overflow-hidden rounded-xl border border-amber-200 bg-white">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-amber-800">Developer: Article HTML source</summary>
                  <div className="border-t border-amber-200 p-4">
                    <textarea
                      aria-label="Article HTML source"
                      className="h-48 min-w-0 w-full rounded-xl border border-amber-300 px-3 py-2 font-mono text-sm"
                      value={articleForm.body}
                      onChange={(event) => setArticleForm((prev) => ({ ...prev, body: event.target.value }))}
                    />
                  </div>
                </details>
              )}
              <Field
                label="Author"
                value={articleForm.author}
                onChange={(value) => setArticleForm((prev) => ({ ...prev, author: value }))}
              />
              <label className="block min-w-0">
                <span className="text-sm font-medium text-slate-700">Publication Date</span>
                <input
                  type="date"
                  className="mt-1 min-w-0 w-full rounded-xl border border-slate-300 px-3 py-2"
                  value={articleForm.publication_date}
                  onChange={(event) => setArticleForm((prev) => ({ ...prev, publication_date: event.target.value }))}
                />
                <span className="mt-1 block text-xs text-slate-500">This is the date shown to public readers. Publishing time is still recorded separately.</span>
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={articleForm.featured}
                  onChange={(event) => setArticleForm((prev) => ({ ...prev, featured: event.target.checked }))}
                />
                Feature this article
              </label>
              <div className="flex flex-wrap gap-2">
                <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                  {articleForm.id ? "Save News Draft" : "Create News"}
                </button>
                {articleForm.id && (
                  <button
                    type="button"
                    className="portal-btn portal-btn-ghost"
                    onClick={() => {
                      if (articleFormHasChanges && !window.confirm("Discard the unsaved changes to this article?")) return;
                      setArticleForm(emptyArticleForm);
                      setArticleFormBaseline(JSON.stringify(emptyArticleForm));
                    }}
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          </form>

          <div className="portal-card min-w-0 overflow-hidden">
            <div className="portal-card-header min-w-0">
              <h3 className="font-bold text-slate-900">News Articles</h3>
            </div>
            <div className="portal-card-body min-w-0 space-y-3">
              {articles.length === 0 ? (
                <p className="text-sm text-slate-500">No CMS news articles yet.</p>
              ) : (
                articles.map((article) => (
                  <div key={article.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="break-words">{article.title}</strong>
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(article.status)}`}>
                            {statusLabel(article.status)}
                          </span>
                          {article.has_unpublished_changes && (
                            <span className="rounded-full bg-orange-100 px-2 py-1 text-xs font-semibold text-orange-700">
                              unpublished changes
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500">Public URL: {articlePublicPath(publishedSlug(article))}</p>
                        {article.status === "published" && publishedSlug(article) !== article.slug && (
                          <p className="text-xs font-medium text-orange-700">
                            Draft URL after publish: {articlePublicPath(article.slug)}
                          </p>
                        )}
                        <p className="mt-1 text-sm text-slate-600">{article.summary || "No summary yet."}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Publication date: {article.publication_date || "Uses publishing date"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 text-sm">
                        {article.status !== "archived" && (
                          <button type="button" className="text-blue-600" onClick={() => editArticle(article)}>Edit</button>
                        )}
                        <button
                          type="button"
                          className="text-slate-600"
                          onClick={() => window.open(articlePublicPath(publishedSlug(article)), "_blank", "noopener,noreferrer")}
                        >
                          View Published
                        </button>
                        <button type="button" className="text-slate-600" onClick={() => copyPublicUrl(articlePublicPath(publishedSlug(article)))}>
                          Copy URL
                        </button>
                        {isAdmin && article.status !== "archived" && (
                          <button type="button" className="text-emerald-700" onClick={() => publishArticle(article)}>
                            Publish
                          </button>
                        )}
                        {!isAdmin && article.status !== "submitted" && article.status !== "archived" && (
                          <button type="button" className="text-blue-700" onClick={() => runWorkflowAction("article", article.id, "submit", article.title)}>Submit</button>
                        )}
                        {isAdmin && article.status === "submitted" && (
                          <button type="button" className="text-rose-700" onClick={() => runWorkflowAction("article", article.id, "reject", article.title)}>Reject</button>
                        )}
                        {isAdmin && article.status !== "archived" && (
                          <button type="button" className="text-slate-600" onClick={() => runWorkflowAction("article", article.id, "archive", article.title)}>Archive</button>
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
        <div className="grid min-w-0 gap-4 2xl:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
          <form onSubmit={uploadMedia} className="portal-card min-w-0 overflow-hidden">
            <div className="portal-card-header min-w-0">
              <h3 className="font-bold text-slate-900">Upload Media</h3>
            </div>
            <div className="portal-card-body min-w-0 space-y-3">
              <div className="rounded-xl border border-sky-100 bg-sky-50 p-3 text-sm text-sky-900">
                <p className="font-semibold">Use this for CMS-managed files</p>
                <p className="mt-1">
                  Upload publication PDFs and cover images here, then select them inside Pages - Publications - Publication Catalog.
                  Public pages update only after the page is published.
                </p>
              </div>
              <label className="block min-w-0">
                <span className="text-sm font-medium text-slate-700">Image or document</span>
                <input
                  type="file"
                  accept={allowedMediaTypes.join(",")}
                  className="mt-1 block w-full text-sm"
                  onChange={(event) => {
                    const nextFile = event.target.files?.[0] || null;
                    if (!nextFile) {
                      setMediaFile(null);
                      return;
                    }
                    const fileError = validateSelectedMediaFile(nextFile, allowedMediaTypes);
                    if (fileError) {
                      event.target.value = "";
                      setMediaFile(null);
                      setNotice(fileError);
                      return;
                    }
                    setNotice("");
                    setMediaFile(nextFile);
                  }}
                />
                <span className="mt-1 block text-xs text-slate-500">
                  The current database policy allows {allowedMediaTypes.length} MIME type{allowedMediaTypes.length === 1 ? "" : "s"}.
                  Image limit: {formatMediaSize(mediaUploadLimits.image)}; document limit: {formatMediaSize(mediaUploadLimits.document)}.
                  Admins can change the policy in Site Settings.
                </span>
              </label>
              {mediaFile && (
                <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                  <p className="font-semibold">Ready to upload: {mediaFile.name}</p>
                  <p>
                    {CMS_MEDIA_TYPE_LABELS[mediaFile.type] || mediaFile.type} - {formatMediaSize(mediaFile.size)}
                  </p>
                </div>
              )}
              <Field
                label="Alt Text"
                value={mediaAlt}
                onChange={setMediaAlt}
                helper="Required for meaningful images; leave blank for decorative files or PDFs."
              />
              <Field
                label="Caption"
                value={mediaCaption}
                onChange={setMediaCaption}
                helper="Use a clear library name so staff can find this asset later."
              />
              <button type="submit" className="portal-btn portal-btn-primary" disabled={loading}>
                Upload Media
              </button>
            </div>
          </form>

          <div className="portal-card min-w-0 overflow-hidden">
            <div className="portal-card-header flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="font-bold text-slate-900">Media Library</h3>
                <p className="text-xs text-slate-500">Active CMS assets. Files in use are protected from archiving.</p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {media.length} active asset{media.length === 1 ? "" : "s"}
              </span>
            </div>
            <div className="portal-card-body min-w-0">
              {media.length === 0 ? (
                <p className="text-sm text-slate-500">No uploaded media yet.</p>
              ) : (
                <div className="grid min-w-0 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {media.map((item) => {
                    const usageKnown = typeof item.usage_count === "number";
                    const usageCount = item.usage_count || 0;
                    const usedBy = item.used_by || [];
                    const canArchive = usageKnown ? item.can_archive !== false : true;
                    return (
                      <div key={item.id} className="rounded-xl border border-slate-200 p-3">
                        <div className="aspect-video overflow-hidden rounded-lg bg-slate-100">
                          {item.file_type === "image" ? (
                            <img src={item.url} alt={item.alt_text || item.caption || "CMS media"} width={320} height={180} loading="lazy" decoding="async" className="h-full w-full object-cover" />
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
                          {mediaFileTypeLabel(item)} - {formatMediaSize(item.size) || "Unknown size"}
                        </p>

                        <div className={`mt-3 rounded-lg border px-3 py-2 text-xs ${usageCount ? "border-amber-100 bg-amber-50 text-amber-800" : usageKnown ? "border-emerald-100 bg-emerald-50 text-emerald-800" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
                          <p className="font-semibold">
                            {usageKnown
                              ? usageCount ? `Used in ${usageCount} CMS location(s)` : "Not used by CMS content"
                              : "References are checked safely when you archive"}
                          </p>
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
                          <button
                            type="button"
                            className="text-slate-600"
                            onClick={async () => {
                              try {
                                await navigator.clipboard?.writeText(item.url);
                                setNotice(`Copied media URL for ${mediaDisplayName(item)}.`);
                              } catch {
                                setNotice(`Media URL: ${item.url}`);
                              }
                            }}
                          >
                            Copy URL
                          </button>
                          <button
                            type="button"
                            className={canArchive ? "text-red-600" : "cursor-not-allowed text-slate-400"}
                            disabled={!canArchive || loading}
                            title={canArchive ? "Archive this unused media file" : "This file is protected because it is referenced by CMS content"}
                            onClick={() => archiveMedia(item)}
                          >
                            {canArchive ? "Archive" : "Protected"}
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

      {activeTab === "forms" && (
        <React.Suspense fallback={<div className="portal-card p-5 text-sm text-slate-600">Loading contributor forms...</div>}>
          <ContributorFormsManager mode={mode} />
        </React.Suspense>
      )}

      {activeTab === "ai" && (
        <React.Suspense fallback={<div className="portal-card p-5 text-sm text-slate-600">Loading AI scoring workspace...</div>}>
          <AIScoringManager mode={mode} />
        </React.Suspense>
      )}

      {activeTab === "review" && (
        <div className="grid min-w-0 gap-4 xl:grid-cols-2">
          <div className="portal-card min-w-0 overflow-hidden">
            <div className="portal-card-header"><h3 className="font-bold text-slate-900">Pages and Sections Awaiting Review</h3></div>
            <div className="portal-card-body space-y-3">
              {reviewQueue.pages.length === 0 && reviewQueue.sections.length === 0 && <p className="text-sm text-slate-500">No submitted pages or sections.</p>}
              {reviewQueue.pages.map((page) => (
                <div key={`page-${page.id}`} className="rounded-xl border border-slate-200 p-3">
                  <strong>{page.title}</strong><p className="text-xs text-slate-500">Page submitted for review</p>
                  {isAdmin && <div className="mt-2 flex gap-3 text-sm"><button className="text-emerald-700" onClick={() => runWorkflowAction("page", page.id, "publish", page.title)}>Publish</button><button className="text-rose-700" onClick={() => runWorkflowAction("page", page.id, "reject", page.title)}>Reject</button></div>}
                </div>
              ))}
              {reviewQueue.sections.map((section) => (
                <div key={`section-${section.id}`} className="rounded-xl border border-slate-200 p-3">
                  <strong>{section.section_key}</strong><p className="text-xs text-slate-500">Page section submitted for review</p>
                  {isAdmin && <div className="mt-2 flex gap-3 text-sm"><button className="text-emerald-700" onClick={() => runWorkflowAction("section", section.id, "publish", section.section_key)}>Publish</button><button className="text-rose-700" onClick={() => runWorkflowAction("section", section.id, "reject", section.section_key)}>Reject</button></div>}
                </div>
              ))}
            </div>
          </div>
          <div className="portal-card min-w-0 overflow-hidden">
            <div className="portal-card-header"><h3 className="font-bold text-slate-900">News, Forms, and Events Awaiting Review</h3></div>
            <div className="portal-card-body space-y-3">
              {reviewQueue.news.length === 0 && reviewQueue.forms.length === 0 && reviewQueue.events.length === 0 && <p className="text-sm text-slate-500">No submitted news, contributor forms, or events.</p>}
              {reviewQueue.news.map((article) => (
                <div key={`article-${article.id}`} className="rounded-xl border border-slate-200 p-3">
                  <strong>{article.title}</strong><p className="text-xs text-slate-500">News article submitted for review</p>
                  {isAdmin && <div className="mt-2 flex gap-3 text-sm"><button className="text-emerald-700" onClick={() => runWorkflowAction("article", article.id, "publish", article.title)}>Publish</button><button className="text-rose-700" onClick={() => runWorkflowAction("article", article.id, "reject", article.title)}>Reject</button></div>}
                </div>
              ))}
              {reviewQueue.forms.map((form) => (
                <div key={`form-${form.id}`} className="rounded-xl border border-slate-200 p-3">
                  <strong>{form.name}</strong><p className="text-xs text-slate-500">Contributor form submitted for review</p>
                  {isAdmin && <button type="button" className="mt-2 text-sm font-semibold text-blue-700" onClick={() => setActiveTab("forms")}>Review changes</button>}
                </div>
              ))}
              {reviewQueue.events.map((event) => (
                <div key={`event-${String(event.id)}`} className="rounded-xl border border-slate-200 p-3">
                  <strong>{String(event.title || "Submitted event")}</strong><p className="text-xs text-slate-500">Review this item in the Events Calendar workspace.</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === "revisions" && (
        <div className="portal-card min-w-0 overflow-hidden">
          <div className="portal-card-header"><h3 className="font-bold text-slate-900">Revision History</h3><p className="text-xs text-slate-500">Historical snapshots remain available after their target is deleted.</p></div>
          <div className="portal-card-body space-y-3">
            {revisions.length === 0 ? <p className="text-sm text-slate-500">No CMS revisions yet.</p> : revisions.map((revision) => (
              <div key={revision.id} className="flex flex-col justify-between gap-3 rounded-xl border border-slate-200 p-3 md:flex-row md:items-center">
                <div><strong>{revision.content_type === "page" ? "Page" : revision.content_type === "article" ? "News Article" : revision.content_type === "section" ? "Page Section" : revision.content_type === "form" ? "Contributor Form" : "Media File"} · Revision {revision.version_number}{revision.is_target_deleted ? " (deleted)" : ""}</strong><p className="text-xs text-slate-500">{statusLabel(revision.action)} by {revision.changed_by_name || "system"} · {formatDate(revision.created_at)}</p></div>
                {isAdmin && !["media", "form"].includes(revision.content_type) && <button type="button" className="portal-btn portal-btn-ghost" onClick={() => restoreRevision(revision)}>Restore</button>}
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "settings" && (
        <div className="space-y-5">
          {[
            { title: "Branding and Contact", detail: "Public logo, footer wording, office address, and contact information.", keys: ["site-logo", "footer-text", "contact-details", "office-address"] },
            { title: "Navigation and Messages", detail: "Public links, homepage announcement, and chatbot contact destination.", keys: ["social-links", "quick-links", "homepage-announcement-banner", "chatbot-contact-fallback-link"] },
            { title: "Media Upload Rules", detail: "File types and size limits accepted by the CMS Media Library.", keys: ["media-upload-allowed-types", "media-upload-max-bytes"] },
          ].map((group) => {
            const rows = group.keys.map((key) => settingsRows.find((row) => row.key === key)).filter((row): row is CMSSiteSetting => Boolean(row));
            if (!rows.length) return null;
            return (
              <section key={group.title} className="space-y-3">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">{group.title}</h3>
                  <p className="text-sm text-slate-500">{group.detail}</p>
                </div>
                <div className="grid min-w-0 gap-4 xl:grid-cols-2">
                  {rows.map((row) => (
                    <div data-cms-setting-key={row.key} key={row.id} className="portal-card min-w-0 overflow-hidden">
                      <div className="portal-card-header"><h4 className="font-bold text-slate-900">{friendlySettingNames[row.key] || row.key}</h4><p className="text-xs text-slate-500">{row.description}</p></div>
                      <div className="portal-card-body space-y-3">
                        <SiteSettingFields row={row} value={settingDrafts[row.id]} onChange={(value) => setSettingValue(row.id, value)} media={media} disabled={!isAdmin} />
                        {developerMode && isAdmin && (
                          <details className="overflow-hidden rounded-xl border border-amber-200 bg-white">
                            <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-amber-800">Developer: Setting JSON source</summary>
                            <div className="space-y-2 border-t border-amber-200 p-3">
                              <textarea aria-label={`${row.key} JSON source`} className="h-36 w-full rounded-xl border border-amber-300 px-3 py-2 font-mono text-sm" value={settingSourceDrafts[row.id] || ""} onChange={(event) => setSettingSourceDrafts((current) => ({ ...current, [row.id]: event.target.value }))} />
                              <button type="button" className="portal-btn portal-btn-ghost" onClick={() => applySettingSource(row)}>Apply Developer Source</button>
                            </div>
                          </details>
                        )}
                        {isAdmin && <button type="button" className="portal-btn portal-btn-primary" disabled={loading} onClick={() => saveSetting(row)}>Save Setting</button>}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
          {settingsRows.some((row) => !friendlySettingNames[row.key]) && (
            <section className="space-y-3">
              <div><h3 className="text-lg font-bold text-slate-900">Other Settings</h3><p className="text-sm text-slate-500">Unrecognized settings are preserved until a visual editor is added.</p></div>
              {settingsRows.filter((row) => !friendlySettingNames[row.key]).map((row) => (
                <div key={row.id} className="portal-card min-w-0 overflow-hidden">
                  <div className="portal-card-body">
                    <h4 className="font-bold text-slate-900">Unsupported Setting</h4>
                    <p className="mt-1 text-sm text-slate-600">{row.description || "This setting does not have a visual editor yet."}</p>
                    {developerMode && isAdmin && (
                      <details className="mt-3 overflow-hidden rounded-xl border border-amber-200 bg-white">
                        <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-amber-800">Developer: {row.key}</summary>
                        <div className="space-y-2 border-t border-amber-200 p-3">
                          <textarea aria-label={`${row.key} JSON source`} className="h-36 w-full rounded-xl border border-amber-300 px-3 py-2 font-mono text-sm" value={settingSourceDrafts[row.id] || ""} onChange={(event) => setSettingSourceDrafts((current) => ({ ...current, [row.id]: event.target.value }))} />
                          <button type="button" className="portal-btn portal-btn-ghost" onClick={() => applySettingSource(row)}>Apply Developer Source</button>
                          <button type="button" className="portal-btn portal-btn-primary" onClick={() => saveSetting(row)}>Save Setting</button>
                        </div>
                      </details>
                    )}
                  </div>
                </div>
              ))}
            </section>
          )}
        </div>
      )}

      {(["pages", "news", "media", "revisions"] as ResourceTab[]).includes(activeTab)
        && hasMoreRows[activeTab as PaginatedResourceTab] && (
          <div className="flex justify-center">
            <button
              type="button"
              className="portal-btn portal-btn-ghost"
              disabled={loading}
              onClick={() => void loadMoreRows(activeTab as PaginatedResourceTab)}
            >
              {loading ? "Loading..." : "Load more"}
            </button>
          </div>
        )}
    </div>
  );
};

const EmptyEditorState = ({ title, detail }: { title: string; detail: string }) => (
  <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center">
    <p className="font-semibold text-slate-700">{title}</p>
    <p className="mt-1 text-sm text-slate-500">{detail}</p>
  </div>
);

const QuickLinksEditor = ({
  title,
  value,
  onChange,
  helper,
}: {
  title: string;
  value: unknown;
  onChange: (value: Array<Record<string, unknown>>) => void;
  helper?: string;
}) => {
  const links = Array.isArray(value) ? value : [];
  const update = (index: number, next: Record<string, unknown>) => {
    const values = [...links];
    values[index] = next;
    onChange(values.map(parseRecord));
  };
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-slate-800">{title}</p>
          {helper && <p className="mt-1 text-xs text-slate-600">{helper}</p>}
        </div>
        <button type="button" className="portal-btn portal-btn-ghost" onClick={() => onChange([...links.map(parseRecord), { label: "New link", link: "/" }])}>Add Link</button>
      </div>
      {links.length === 0 && <EmptyEditorState title="No links yet" detail="Select Add Link to create one." />}
      {links.map((item, index) => {
        const link = parseRecord(item);
        return (
          <div key={index} className="rounded-xl border border-slate-200 bg-white p-3">
            <div className="mb-2 flex items-center justify-between gap-3"><strong className="text-sm">Link {index + 1}</strong><button type="button" className="text-sm text-red-600" onClick={() => onChange(links.filter((_, itemIndex) => itemIndex !== index).map(parseRecord))}>Remove</button></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Label" value={textValue(link.label)} onChange={(next) => update(index, { ...link, label: next })} />
              <Field label="Destination" value={textValue(link.link || link.url)} onChange={(next) => update(index, { ...link, link: next })} />
            </div>
          </div>
        );
      })}
    </div>
  );
};

const MediaAssetPicker = ({
  label,
  assets,
  value,
  onChange,
  helper,
}: {
  label: string;
  assets: CMSMediaAsset[];
  value: string;
  onChange: (value: string) => void;
  helper?: string;
}) => {
  const selected = assets.find((asset) => String(asset.id) === value);
  return (
    <label className="block min-w-0">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <div className="mt-1 overflow-hidden rounded-xl border border-slate-300 bg-white">
        {selected && (
          <div className="flex items-center gap-3 border-b border-slate-200 bg-slate-50 p-2">
            {selected.file_type === "image" ? (
              <img src={selected.url} alt={selected.alt_text || selected.caption || "Selected media"} width={80} height={56} loading="lazy" decoding="async" className="h-14 w-20 rounded-lg object-cover" />
            ) : (
              <div className="flex h-14 w-20 items-center justify-center rounded-lg bg-red-50 text-xs font-bold text-red-700">{mediaFileTypeLabel(selected)}</div>
            )}
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-800">{mediaDisplayName(selected)}</p>
              <p className="text-xs text-slate-500">{mediaFileTypeLabel(selected)}{formatMediaSize(selected.size) ? ` · ${formatMediaSize(selected.size)}` : ""}</p>
            </div>
          </div>
        )}
        <select className="min-w-0 w-full px-3 py-2" value={value} onChange={(event) => onChange(event.target.value)}>
          <option value="">{assets.length ? "No library file selected" : "No matching media uploaded yet"}</option>
          {assets.map((asset) => (
            <option key={asset.id} value={String(asset.id)}>{mediaDisplayName(asset)}{formatMediaSize(asset.size) ? ` (${formatMediaSize(asset.size)})` : ""}</option>
          ))}
        </select>
      </div>
      {helper && <span className="mt-1 block text-xs text-slate-500">{helper}</span>}
    </label>
  );
};

const SiteSettingFields = ({
  row,
  value,
  onChange,
  media,
  disabled,
}: {
  row: CMSSiteSetting;
  value: unknown;
  onChange: (value: unknown) => void;
  media: CMSMediaAsset[];
  disabled: boolean;
}) => {
  const objectValue = parseRecord(value);
  const listValue = Array.isArray(value) ? value : [];
  const updateListItem = (index: number, next: Record<string, unknown>) => {
    const values = [...listValue];
    values[index] = next;
    onChange(values);
  };

  let fields: React.ReactNode;

  if (["footer-text", "office-address", "chatbot-contact-fallback-link"].includes(row.key)) {
    fields = row.key === "footer-text" || row.key === "office-address"
      ? <Area label={friendlySettingNames[row.key]} value={textValue(value)} onChange={onChange} rows={3} />
      : <Field label="Contact Page Destination" value={textValue(value)} onChange={onChange} helper="Example: /contact" />;
  } else if (row.key === "site-logo") {
    const imageAssets = media.filter((item) => item.file_type === "image");
    const selectedId = stringValue(objectValue.mediaAssetId) || String(imageAssets.find((item) => portableMediaUrl(item.url) === textValue(objectValue.url))?.id || "");
    fields = (
      <div className="space-y-3">
        <MediaAssetPicker
          label="Logo Image"
          assets={imageAssets}
          value={selectedId}
          onChange={(selectedValue) => {
            const selected = imageAssets.find((item) => String(item.id) === selectedValue);
            onChange({
              ...objectValue,
              mediaAssetId: selected?.id || "",
              url: selected ? portableMediaUrl(selected.url) : "",
              alt: selected ? textValue(objectValue.alt) || selected.alt_text || selected.caption || "RDC-NCR" : textValue(objectValue.alt),
            });
          }}
          helper="Upload the image in Media Library first, then select it here."
        />
        <Field label="Logo Description" value={textValue(objectValue.alt)} onChange={(next) => onChange({ ...objectValue, alt: next })} />
      </div>
    );
  } else if (row.key === "contact-details") {
    fields = (
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Public Email" value={textValue(objectValue.email)} onChange={(next) => onChange({ ...objectValue, email: next })} />
        <Field label="Public Phone" value={textValue(objectValue.phone)} onChange={(next) => onChange({ ...objectValue, phone: next })} />
      </div>
    );
  } else if (row.key === "homepage-announcement-banner") {
    fields = (
      <div className="space-y-3">
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" checked={objectValue.enabled === true} onChange={(event) => onChange({ ...objectValue, enabled: event.target.checked })} />
          Show the announcement on the homepage
        </label>
        <Area label="Announcement Text" value={textValue(objectValue.text)} onChange={(next) => onChange({ ...objectValue, text: next })} rows={3} />
        <Field label="Optional Destination" value={textValue(objectValue.link)} onChange={(next) => onChange({ ...objectValue, link: next })} helper="Leave blank when the announcement should not link anywhere." />
      </div>
    );
  } else if (row.key === "social-links" || row.key === "quick-links") {
    const isSocial = row.key === "social-links";
    fields = (
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-slate-600">Links appear in the order shown.</p>
          <button type="button" className="portal-btn portal-btn-ghost" onClick={() => onChange([...listValue, isSocial ? { label: "New social link", url: "https://" } : { label: "New quick link", link: "/" }])}>Add Link</button>
        </div>
        {listValue.length === 0 && <EmptyEditorState title="No links yet" detail="Select Add Link to create one." />}
        {listValue.map((item, index) => {
          const link = parseRecord(item);
          const destinationKey = isSocial ? "url" : "link";
          return (
            <div key={index} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="mb-2 flex items-center justify-between gap-3"><strong className="text-sm">Link {index + 1}</strong><button type="button" className="text-sm text-red-600" onClick={() => onChange(listValue.filter((_, itemIndex) => itemIndex !== index))}>Remove</button></div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={isSocial ? "Platform / Label" : "Link Label"} value={textValue(link.label || link.platform)} onChange={(next) => updateListItem(index, { ...link, label: next })} />
                <Field label="Destination" value={textValue(link[destinationKey] || link.link || link.url)} onChange={(next) => updateListItem(index, { ...link, [destinationKey]: next })} />
              </div>
            </div>
          );
        })}
      </div>
    );
  } else if (row.key === "media-upload-allowed-types") {
    fields = (
      <div className="grid gap-4 sm:grid-cols-2">
        {(["image", "document"] as const).map((group) => {
          const configured = Array.isArray(objectValue[group]) ? objectValue[group].filter((item): item is string => typeof item === "string") : [];
          const known = Object.entries(CMS_MEDIA_TYPE_LABELS).filter(([mime]) => group === "image" ? mime.startsWith("image/") : !mime.startsWith("image/"));
          return (
            <div key={group}>
              <p className="mb-2 text-sm font-semibold capitalize text-slate-800">{group} files</p>
              <div className="space-y-2">
                {known.map(([mime, label]) => (
                  <label key={mime} className="flex items-start gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={configured.includes(mime)}
                      onChange={(event) => {
                        const nextValues = event.target.checked ? [...configured, mime] : configured.filter((item) => item !== mime);
                        onChange({ ...objectValue, [group]: nextValues });
                      }}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    );
  } else if (row.key === "media-upload-max-bytes") {
    fields = (
      <div className="grid gap-3 sm:grid-cols-2">
        {(["image", "document"] as const).map((group) => (
          <Field
            key={group}
            label={`${group === "image" ? "Image" : "Document"} Limit (MB)`}
            value={(Number(objectValue[group] || 0) / (1024 * 1024)).toFixed(1)}
            onChange={(next) => {
              const megabytes = Number(next);
              if (!Number.isFinite(megabytes) || megabytes < 0) return;
              onChange({ ...objectValue, [group]: Math.round(megabytes * 1024 * 1024) });
            }}
          />
        ))}
      </div>
    );
  } else {
    fields = <p className="text-sm text-slate-600">This value is preserved, but it does not have a visual editor yet.</p>;
  }

  return <fieldset disabled={disabled} className="min-w-0 disabled:opacity-70">{fields}</fieldset>;
};

const Field = ({
  label,
  value,
  onChange,
  helper,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  helper?: string;
  disabled?: boolean;
}) => (
  <label className="block min-w-0">
    <span className="text-sm font-medium text-slate-700">{label}</span>
    <input
      className="mt-1 min-w-0 w-full rounded-xl border border-slate-300 px-3 py-2"
      value={value}
      disabled={disabled}
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
  <label className="block min-w-0">
    <span className="text-sm font-medium text-slate-700">{label}</span>
    <textarea
      className="mt-1 min-w-0 w-full rounded-xl border border-slate-300 px-3 py-2"
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
  <label className="block min-w-0">
    <span className="text-sm font-medium text-slate-700">{label}</span>
    <select
      className="mt-1 min-w-0 w-full rounded-xl border border-slate-300 px-3 py-2"
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
