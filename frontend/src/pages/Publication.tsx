import { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import cmsApi, { type CMSPageSnapshot } from "../services/cmsApi";

const publicDocument = (fileName: string) => `/assets/Documents/${encodeURIComponent(fileName)}`;
const publicationCover = (fileName: string) => `/assets/PublicationCovers/${encodeURIComponent(fileName)}`;

const greenprintFull = publicDocument("GREENPRINT-2.pdf");
const greenprintBrochure = publicDocument("Greeprint-brochure.pdf");
const rdp2023Full = publicDocument("Full_Version_RDP-NCR_2023-2028.pdf");
const rdp2023Abridged = publicDocument("Abridged_Version_RDP-NCR_2023-2028.pdf");
const rdp2023Brochure = publicDocument("Brochure_RDP-NCR_2023-2028.pdf");
const rdp2017Full = publicDocument("NCR-Regional-Development-Plan-2017-2022-resize (2).pdf");
const rdp2017Abridged = publicDocument("Abridged-Final-resize.pdf");
const rdp2017Brochure = publicDocument("RDP-Brochure-Final.pdf");
const rdip2023 = publicDocument("Regional Development Investment Program 2023-2028_1.pdf");
const rdip2020 = publicDocument("For_Concurrence_RDIP-NCR_Pre-final_2022.pdf");
const rdipUpdated2023 = publicDocument("[FY 2023] List of Updated Investment Program.pdf");
const rdr2023 = publicDocument("RDRNCR2023.pdf");
const res2021 = publicDocument("res layout_jan 3.pdf");
const res2022 = publicDocument("RES_2022_v8.pdf");
const res2023 = publicDocument("Res_2023_Final_Last_version.pdf");
const rpmesGuidelines = publicDocument("20231016_RPMES-Operational-Guidelines.pdf");
const rrpFull = publicDocument("RRP-NCR_with_Investment_Program_for_posting.pdf");
const rrpAbridged = publicDocument("RRP-NCR_Abridged_version_for_posting.pdf");
const coverGreenprint2030 = publicationCover("Greenprint 2030.png");
const coverGreenprintBrochure = publicationCover("GP2030 Brochure Cover_page-0001.jpg");
const coverRdp2023 = publicationCover("Regional Development Plans 2023-2028.png");
const coverRdpLegacy = publicationCover("Regional Development Plans.png");
const coverRdip = publicationCover("Regional Development Investment Program .png");
const coverRdr = publicationCover("Regional Development Report .png");
const coverRes = publicationCover("Regional Economic Situationer .png");

type DocumentItem = {
  id: string;
  title: string;
  year: string;
  fileType: string;
  fileSize: string;
  url: string;
  coverImage?: string;
  coverAlt?: string;
};

type Category = {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  documents: DocumentItem[];
};

const CATEGORIES: Category[] = [
  {
    id: "greenprint",
    title: "Greenprint 2030",
    description:
      "Strategic environmental and sustainability framework for Metro Manila",
    icon: "🌱",
    color: "from-green-600 to-emerald-500",
    documents: [
      {
        id: "gp1",
        title: "Greenprint 2030 Full Document",
        year: "2023",
        fileType: "PDF",
        fileSize: "6.9 MB",
        url: greenprintFull,
        coverImage: coverGreenprint2030,
        coverAlt: "Greenprint 2030 cover",
      },
      {
        id: "gp2",
        title: "Green Print Brochure",
        year: "2023",
        fileType: "PDF",
        fileSize: "2.8 MB",
        url: greenprintBrochure,
        coverImage: coverGreenprintBrochure,
        coverAlt: "Greenprint 2030 brochure cover",
      },
    ],
  },
  {
    id: "rdp",
    title: "Regional Development Plans (RDP-NCR)",
    description: "Comprehensive development blueprints and strategic plans",
    icon: "📋",
    color: "from-blue-600 to-cyan-500",
    documents: [
      {
        id: "rdp1",
        title: "RDP-NCR 2023–2028 (Full Version)",
        year: "2023",
        fileType: "PDF",
        fileSize: "36.4 MB",
        url: rdp2023Full,
        coverImage: coverRdp2023,
        coverAlt: "RDP-NCR 2023-2028 cover",
      },
      {
        id: "rdp2",
        title: "RDP-NCR 2023–2028 (Abridged Version)",
        year: "2023",
        fileType: "PDF",
        fileSize: "10.6 MB",
        url: rdp2023Abridged,
        coverImage: coverRdp2023,
        coverAlt: "RDP-NCR 2023-2028 cover",
      },
      {
        id: "rdp3",
        title: "RDP-NCR 2023–2028 Brochure",
        year: "2023",
        fileType: "PDF",
        fileSize: "2.2 MB",
        url: rdp2023Brochure,
        coverImage: coverRdp2023,
        coverAlt: "RDP-NCR 2023-2028 cover",
      },
      {
        id: "rdp4",
        title: "RDP-NCR 2017- 2022 (Full Version)",
        year: "2023",
        fileType: "PDF",
        fileSize: "8.0 MB",
        url: rdp2017Full,
        coverImage: coverRdpLegacy,
        coverAlt: "RDP-NCR 2017-2022 cover",
      },
      {
        id: "rdp5",
        title: "RDP-NCR 2017- 2022 (Abridged Version)",
        year: "2023",
        fileType: "PDF",
        fileSize: "1.1 MB",
        url: rdp2017Abridged,
        coverImage: coverRdpLegacy,
        coverAlt: "RDP-NCR 2017-2022 cover",
      },
      {
        id: "rdp6",
        title: "RDP-NCR 2017- 2022 Brochure",
        year: "2023",
        fileType: "PDF",
        fileSize: "5.3 MB",
        url: rdp2017Brochure,
        coverImage: coverRdpLegacy,
        coverAlt: "RDP-NCR 2017-2022 cover",
      },
    ],
  },
  {
    id: "rdip",
    title: "Regional Development Investment Program (RDIP)",
    description: "Priority investment programs and infrastructure projects",
    icon: "💼",
    color: "from-purple-600 to-indigo-500",
    documents: [
      {
        id: "rdip1",
        title: "RDIP-NCR 2023–2028",
        year: "2023",
        fileType: "PDF",
        fileSize: "12.4 MB",
        url: rdip2023,
        coverImage: coverRdip,
        coverAlt: "RDIP-NCR cover",
      },
      {
        id: "rdip2",
        title: "RDIP-NCR 2020–2022",
        year: "2020",
        fileType: "PDF",
        fileSize: "10.4 MB",
        url: rdip2020,
        coverImage: coverRdip,
        coverAlt: "RDIP-NCR cover",
      },
      {
        id: "rdip3",
        title: "RDIP Updated List 2024",
        year: "2024",
        fileType: "PDF",
        fileSize: "1.9 MB",
        url: "https://docs.google.com/document/d/1UlpfePYCH1r_M041K3PaUqnlq0rqLNJ5_EEsPFKf8eQ/edit?tab=t.5yre1br7hyj2",
        coverImage: coverRdip,
        coverAlt: "RDIP-NCR cover",
      },
      {
        id: "rdip4",
        title: "RDIP Updated List 2023",
        year: "2023",
        fileType: "PDF",
        fileSize: "7.3 MB",
        url: rdipUpdated2023,
        coverImage: coverRdip,
        coverAlt: "RDIP-NCR cover",
      },
    ],
  },
  {
    id: "rdr",
    title: "Regional Development Report (RDR)",
    description: "Annual progress reports and development outcomes",
    icon: "📊",
    color: "from-orange-600 to-red-500",
    documents: [
      {
        id: "rdr1",
        title: "RDR 2023",
        year: "2023",
        fileType: "PDF",
        fileSize: "43.6 MB",
        url: rdr2023,
        coverImage: coverRdr,
        coverAlt: "Regional Development Report cover",
      },
    ],
  },
  {
    id: "res",
    title: "Regional Economic Situationer (RES)",
    description: "Economic performance and trends analysis",
    icon: "📈",
    color: "from-teal-600 to-green-500",
    documents: [
      {
        id: "res1",
        title: "RES Annual 2021",
        year: "2024",
        fileType: "PDF",
        fileSize: "7.9 MB",
        url: res2021,
        coverImage: coverRes,
        coverAlt: "Regional Economic Situationer cover",
      },
      {
        id: "res2",
        title: "RES Annual 2022",
        year: "2024",
        fileType: "PDF",
        fileSize: "10.5 MB",
        url: res2022,
        coverImage: coverRes,
        coverAlt: "Regional Economic Situationer cover",
      },
      {
        id: "res4",
        title: "RES Annual 2023",
        year: "2023",
        fileType: "PDF",
        fileSize: "17.8 MB",
        url: res2023,
        coverImage: coverRes,
        coverAlt: "Regional Economic Situationer cover",
      },
    ],
  },
  {
    id: "sdg",
    title: "SDG Catch-Up Plan",
    description: "Sustainable Development Goals acceleration strategies",
    icon: "🎯",
    color: "from-pink-600 to-rose-500",
    documents: [
      {
        id: "sdg1",
        title: "SDG Catch-Up Plan 2023–2028",
        year: "2023",
        fileType: "PDF",
        fileSize: "3.1 MB",
        url: "https://your-actual-link.com/sdg-catch-up-plan-2023-2028.pdf",
      },
      {
        id: "sdg2",
        title: "SDG Progress Report 2023",
        year: "2023",
        fileType: "PDF",
        fileSize: "2.4 MB",
        url: "https://your-actual-link.com/sdg-progress-report-2023.pdf",
      },
      {
        id: "sdg3",
        title: "SDG Monitoring Framework",
        year: "2024",
        fileType: "PDF",
        fileSize: "1.5 MB",
        url: "https://your-actual-link.com/sdg-monitoring-framework-2024.pdf",
      },
    ],
  },
  {
    id: "rpmes",
    title: "Regional Project Monitoring and Evaluation System (RPMES)",
    description: "Regional Project Monitoring and Evaluation System",
    icon: "⚙️",
    color: "from-slate-600 to-gray-500",
    documents: [
      {
        id: "rpmes3",
        title: "RPMES Operational Guidelines",
        year: "2024",
        fileType: "PDF",
        fileSize: "8.4 MB",
        url: rpmesGuidelines,
      },
    ],
  },
  {
    id: "rrp",
    title:
      "Rehabilitation & Recovery Plan for the National Capital Region (RRP-NCR)",
    description: "Post-disaster recovery and resilience strategies",
    icon: "🔄",
    color: "from-yellow-600 to-orange-500",
    documents: [
      {
        id: "rrp1",
        title: "RRP-NCR with Investment Program (Full Document)",
        year: "2024",
        fileType: "PDF",
        fileSize: "31.5 MB",
        url: rrpFull,
      },
      {
        id: "rrp2",
        title: "RRP-NCR (Abridge Version)",
        year: "2023",
        fileType: "PDF",
        fileSize: "2.5 MB",
        url: rrpAbridged,
      },
    ],
  },
];

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const asString = (value: unknown, fallback = "") =>
  typeof value === "string" && value.trim() ? value.trim() : fallback;

const publicationIcon = (value: string) => {
  const icons: Record<string, string> = {
    briefcase: "\u{1F4BC}",
    "chart-bar": "\u{1F4CA}",
    "chart-line": "\u{1F4C8}",
    clipboard: "\u{1F4CB}",
    document: "\u{1F4C4}",
    file: "\u{1F4C4}",
    gear: "\u2699\uFE0F",
    leaf: "\u{1F331}",
    refresh: "\u{1F504}",
    target: "\u{1F3AF}",
    trend: "\u{1F4C8}",
  };
  const key = value.toLowerCase();
  return icons[key] || value || icons.document;
};

const isVisible = (value: unknown) => {
  const row = asRecord(value);
  return row.isVisible !== false && row.visible !== false;
};

const getPublicationCatalog = (page: CMSPageSnapshot | null) =>
  page?.sections.find((section) => section.sectionKey === "publication-catalog")?.content ?? null;

const cloneCategory = (category: Category): Category => ({
  ...category,
  documents: category.documents.map((document) => ({ ...document })),
});

const mergeDocuments = (cmsDocuments: unknown[], baseCategory?: Category): DocumentItem[] => {
  const result = baseCategory?.documents.map((document) => ({ ...document })) ?? [];

  cmsDocuments.forEach((documentEntry, documentIndex) => {
    const documentRow = asRecord(documentEntry);
    const documentId = asString(documentRow.id);
    const title = asString(documentRow.title);
    const matchIndex = result.findIndex(
      (document) =>
        (!!documentId && document.id === documentId) ||
        (!!title && document.title.toLowerCase() === title.toLowerCase()),
    );
    const baseDocument = matchIndex >= 0 ? result[matchIndex] : undefined;
    if (!isVisible(documentRow)) {
      if (matchIndex >= 0) result.splice(matchIndex, 1);
      return;
    }

    const id = documentId || baseDocument?.id || `${baseCategory?.id ?? "publication"}-${documentIndex + 1}`;
    const url = asString(documentRow.url, baseDocument?.url ?? "");
    if (!url) return;

    const coverImage = asString(documentRow.coverImage, baseDocument?.coverImage ?? "");
    const nextDocument: DocumentItem = {
      id,
      title: asString(documentRow.title, baseDocument?.title ?? "Untitled publication"),
      year: asString(documentRow.year, baseDocument?.year ?? ""),
      fileType: asString(documentRow.fileType, baseDocument?.fileType ?? "PDF"),
      fileSize: asString(documentRow.fileSize, baseDocument?.fileSize ?? ""),
      url,
      coverImage: coverImage || undefined,
      coverAlt: asString(documentRow.coverAlt, baseDocument?.coverAlt ?? ""),
    };

    if (matchIndex >= 0) result[matchIndex] = nextDocument;
    else result.push(nextDocument);
  });

  return result.filter((document) => Boolean(document.url));
};

const buildCategoriesFromCms = (page: CMSPageSnapshot | null): Category[] => {
  const catalog = getPublicationCatalog(page);
  const cmsCategories = asArray(catalog?.categories);
  if (!cmsCategories.length) return CATEGORIES;

  const result = CATEGORIES.map(cloneCategory);

  cmsCategories.forEach((entry, categoryIndex) => {
    const row = asRecord(entry);
    const id = asString(row.id);
    const title = asString(row.title);
    const matchIndex = result.findIndex(
      (category) =>
        (!!id && category.id === id) ||
        (!!title && category.title.toLowerCase() === title.toLowerCase()),
    );
    const baseCategory = matchIndex >= 0 ? result[matchIndex] : undefined;

    if (!isVisible(row)) {
      if (matchIndex >= 0) result.splice(matchIndex, 1);
      return;
    }

    const nextId = id || baseCategory?.id || `category-${categoryIndex + 1}`;
    const cmsDocuments = asArray(row.documents);
    const documents = mergeDocuments(cmsDocuments, baseCategory);
    if (documents.length === 0) return;

    const nextCategory: Category = {
      id: nextId,
      title: asString(row.title, baseCategory?.title ?? "Publication Category"),
      description: asString(row.description, baseCategory?.description ?? ""),
      icon: asString(row.icon, baseCategory?.icon ?? "document"),
      color: asString(row.color, baseCategory?.color ?? "from-slate-600 to-slate-500"),
      documents,
    };

    if (matchIndex >= 0) result[matchIndex] = nextCategory;
    else result.push(nextCategory);
  });

  return result.length ? result : CATEGORIES;
};

export default function Publications() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const categoryParam = searchParams.get("category");
  const [cmsPage, setCmsPage] = useState<CMSPageSnapshot | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    categoryParam || null,
  );

  const categories = useMemo(() => buildCategoriesFromCms(cmsPage), [cmsPage]);
  const catalogContent = getPublicationCatalog(cmsPage);
  const activeCategory = categories.find((c) => c.id === selectedCategory);
  const headerTitle = asString(catalogContent?.title, "Publications & Official Documents");
  const headerSubtitle = asString(
    catalogContent?.subtitle,
    "Plans, reports, and development programs for the National Capital Region",
  );
  const browseTitle = asString(catalogContent?.browseTitle, "Browse by Category");
  const browseSubtitle = asString(catalogContent?.browseSubtitle, "Select a category to view available documents");

  // Update selected category when URL parameter changes
  useEffect(() => {
    setSelectedCategory(categoryParam || null);
  }, [categoryParam]);

  useEffect(() => {
    let cancelled = false;

    const loadCmsPage = async () => {
      try {
        const page = await cmsApi.getPublicPage("publications");
        if (!cancelled) setCmsPage(page);
      } catch (error) {
        console.error(error);
        if (!cancelled) setCmsPage(null);
      }
    };

    loadCmsPage();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedCategory && !categories.some((category) => category.id === selectedCategory)) {
      setSelectedCategory(null);
    }
  }, [selectedCategory, categories]);

  const handleCategorySelect = (categoryId: string) => {
    setSelectedCategory(categoryId);
    navigate(`/publications?category=${categoryId}`);
  };

  const handleBackToCategories = () => {
    setSelectedCategory(null);
    navigate("/publications");
  };

  // Download action removed — view-only interface

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="bg-gradient-to-r from-[#012a5a] via-[#0b6fb7] to-[#0d8fb3] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
              {headerTitle}
            </h1>
            <p className="text-lg text-white/90">
              {headerSubtitle}
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {!selectedCategory || !activeCategory ? (
          // Category Selection View
          <div>
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-slate-900 mb-2">
                {browseTitle}
              </h2>
              <p className="text-slate-600">
                {browseSubtitle}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {categories.map((category) => (
                <button
                  key={category.id}
                  onClick={() => handleCategorySelect(category.id)}
                  className="bg-white rounded-2xl shadow-md hover:shadow-xl transition-all transform hover:-translate-y-1 p-6 text-left group border border-slate-100 h-full flex flex-col justify-between"
                >
                  <div
                    className={`w-16 h-16 rounded-xl bg-gradient-to-br ${category.color} flex items-center justify-center text-3xl mb-4 group-hover:scale-110 transition-transform leading-none text-center`}
                  >
                    <span className="leading-none align-middle">
                      {publicationIcon(category.icon)}
                    </span>
                  </div>
                  <h3 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-blue-600 transition">
                    {category.title}
                  </h3>
                  <p className="text-sm text-slate-600 line-clamp-2">
                    {category.description}
                  </p>
                  <div className="mt-4 flex items-center text-sm text-blue-600 font-medium">
                    <span>View documents</span>
                    <svg
                      className="w-4 h-4 ml-1 group-hover:translate-x-1 transition"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          // Document Listing View
          <div>
            {/* Back Button & Category Header */}
            <button
              onClick={handleBackToCategories}
              className="mb-6 flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium transition"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                viewBox="0 0 24 24"
              >
                <path d="M15 19l-7-7 7-7" />
              </svg>
              Back to Categories
            </button>

            <div
              className={`bg-gradient-to-br ${activeCategory?.color} rounded-2xl p-8 mb-8 text-white shadow-lg`}
            >
              <div className="flex items-start gap-4">
                <div className="text-5xl leading-none text-center">
                  {publicationIcon(activeCategory?.icon || "document")}
                </div>
                <div>
                  <h2 className="text-3xl font-bold mb-2">
                    {activeCategory?.title}
                  </h2>
                  <p className="text-white/90 text-lg">
                    {activeCategory?.description}
                  </p>
                  <div className="mt-4 text-sm text-white/80">
                    {activeCategory?.documents.length} document(s) available
                  </div>
                </div>
              </div>
            </div>

            {/* Document Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {activeCategory?.documents.map((doc) => (
                <div
                  key={doc.id}
                  className="bg-white rounded-xl shadow-md hover:shadow-lg transition-all border border-slate-100 overflow-hidden group"
                >
                  <div
                    className={`h-2 bg-gradient-to-r ${activeCategory.color}`}
                  />

                  <div className="p-6">
                    {/* Cover */}
                    <div className="mb-4">
                      <div className="w-full aspect-[3/4] rounded-lg overflow-hidden border border-slate-100 bg-slate-50">
                        {doc.coverImage ? (
                          <img
                            src={doc.coverImage}
                            alt={doc.coverAlt || doc.title}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div
                            className={`w-full h-full bg-gradient-to-br ${activeCategory.color} flex flex-col items-center justify-center text-white/90 px-4 text-center`}
                          >
                            <p className="text-xs uppercase tracking-wider font-semibold text-white/80">
                              Publication Cover
                            </p>
                            <p className="mt-2 text-sm font-semibold line-clamp-4">
                              {doc.title}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Document Info */}
                    <h3 className="font-bold text-slate-900 mb-2 line-clamp-2 group-hover:text-blue-600 transition">
                      {doc.title}
                    </h3>

                    {/* File Type Badge */}
                    <div className="mb-4">
                      <span className="inline-block px-3 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded-full">
                        {doc.fileType}
                      </span>
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2">
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition text-center"
                      >
                        View
                      </a>
                      <a
                        href={doc.url}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg transition text-center"
                      >
                        Download
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
