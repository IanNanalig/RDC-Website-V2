import { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import cmsApi, { type CMSPageSnapshot } from "../services/cmsApi";
import { canDownloadDocument, downloadDocument } from "../utils/documentDownload";



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

  return result;
};

const buildCategoriesFromCms = (page: CMSPageSnapshot | null): Category[] => {
  const catalog = getPublicationCatalog(page);
  const cmsCategories = asArray(catalog?.categories);
  const result: Category[] = [];

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

  return result;
};

export default function Publications() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const categoryParam = searchParams.get("category");
  const [cmsPage, setCmsPage] = useState<CMSPageSnapshot | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(
    categoryParam || null,
  );
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<string | null>(null);

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

  const handleDownload = async (document: DocumentItem) => {
    setDownloadingDocumentId(document.id);
    try {
      await downloadDocument({
        url: document.url,
        title: document.title,
        fileType: document.fileType,
      });
    } catch (error) {
      console.error(error);
      alert(`The file for "${document.title}" is not available for direct download.`);
    } finally {
      setDownloadingDocumentId(null);
    }
  };

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
            {categories.length === 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-600">
                No publication categories are currently published.
              </div>
            )}
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
              {activeCategory?.documents.length === 0 && (
                <div className="col-span-full rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
                  <h3 className="font-semibold text-slate-800">No documents added yet</h3>
                  <p className="mt-2 text-sm text-slate-500">Documents for this publication category will appear here once added through the CMS.</p>
                </div>
              )}
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
                            width={600}
                            height={800}
                            loading="lazy"
                            decoding="async"
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
                    {doc.url ? (
                      <div className="flex gap-2">
                        <a
                          href={doc.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition text-center"
                        >
                          View
                        </a>
                        <button
                          type="button"
                          onClick={() => handleDownload(doc)}
                          disabled={
                            downloadingDocumentId === doc.id ||
                            !canDownloadDocument(doc.url)
                          }
                          className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed text-slate-700 text-sm font-medium rounded-lg transition text-center"
                          title={
                            canDownloadDocument(doc.url)
                              ? `Download ${doc.title}`
                              : "A direct download file has not been provided"
                          }
                        >
                          {downloadingDocumentId === doc.id
                            ? "Downloading..."
                            : canDownloadDocument(doc.url)
                              ? "Download"
                              : "Unavailable"}
                        </button>
                      </div>
                    ) : (
                      <div className="rounded-lg bg-amber-50 px-4 py-2 text-center text-sm font-medium text-amber-700">
                        Document file not yet available
                      </div>
                    )}
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
