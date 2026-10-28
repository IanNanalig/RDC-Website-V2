import { useEffect, useMemo, useState, type SyntheticEvent } from "react";
import { Link } from "react-router-dom";
import { useParams } from "react-router-dom";
import cmsApi, {
  type CMSArticleSnapshot,
  type CMSPageSnapshot,
} from "../services/cmsApi";

type NewsItem = {
  id: string;
  title: string;
  category: string;
  date: string;
  summary: string;
  thumbnail: string;
  slug: string;
  body?: string;
  source: "cms";
};


const categoryColors: Record<string, { bg: string; text: string }> = {
  "Press Release": { bg: "bg-blue-100", text: "text-blue-700" },
  Event: { bg: "bg-green-100", text: "text-green-700" },
  Resolution: { bg: "bg-purple-100", text: "text-purple-700" },
  "Committee Announcement": { bg: "bg-orange-100", text: "text-orange-700" },
};

const ITEMS_PER_PAGE = 9;

const fallbackThumbnail =
  "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=800&auto=format&fit=crop";

const useFallbackThumbnail = (event: SyntheticEvent<HTMLImageElement>) => {
  const image = event.currentTarget;
  if (image.src === fallbackThumbnail) return;
  image.src = fallbackThumbnail;
};

const mapCmsArticle = (article: CMSArticleSnapshot): NewsItem => ({
  id: article.slug,
  title: article.title,
  category: article.category || "Updates",
  date: article.publicationDate || article.publishedAt,
  summary: article.summary || "Read the latest RDC-NCR public update.",
  thumbnail: article.thumbnailUrl || fallbackThumbnail,
  slug: article.slug,
  body: article.body,
  source: "cms",
});

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const asString = (value: unknown, fallback = "") =>
  typeof value === "string" && value.trim() ? value.trim() : fallback;

const getPageSection = (page: CMSPageSnapshot | null, sectionKey: string) =>
  asRecord(
    page?.sections.find((section) => section.sectionKey === sectionKey)?.content,
  );

export default function NewsPage() {
  const { slug } = useParams();
  const [cmsPage, setCmsPage] = useState<CMSPageSnapshot | null>(null);
  const [cmsNews, setCmsNews] = useState<NewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(true);
  const [newsError, setNewsError] = useState("");
  const [selectedYear, setSelectedYear] = useState<string>("All");
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [currentPage, setCurrentPage] = useState(1);
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  useEffect(() => {
    let cancelled = false;
    cmsApi
      .getPublicPage("news")
      .then((page) => {
        if (!cancelled) setCmsPage(page);
      })
      .catch(() => {
        if (!cancelled) setCmsPage(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadNews = async () => {
      try {
        setNewsLoading(true);
        setNewsError("");
        const rows = await cmsApi.listPublicNews(100);
        if (!cancelled) {
          setCmsNews(rows.map(mapCmsArticle));
        }
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          setCmsNews([]);
          setNewsError("Published news is temporarily unavailable.");
        }
      } finally {
        if (!cancelled) setNewsLoading(false);
      }
    };
    loadNews();
    return () => {
      cancelled = true;
    };
  }, []);

  const newsItems = cmsNews;
  const selectedArticle = slug ? newsItems.find((item) => item.slug === slug || item.id === slug) : null;
  const heroContent = getPageSection(cmsPage, "news-hero");
  const listingContent = getPageSection(cmsPage, "news-listing");

  // Extract unique years
  const years = useMemo(() => {
    const yearSet = new Set<string>();
    newsItems.forEach((news) => {
      yearSet.add(new Date(news.date).getFullYear().toString());
    });
    return [
      "All",
      ...Array.from(yearSet).sort((a, b) => Number(b) - Number(a)),
    ];
  }, [newsItems]);

  const categories = useMemo(() => {
    return ["All", ...Array.from(new Set(newsItems.map((news) => news.category))).sort()];
  }, [newsItems]);

  // Filter news
  const filteredNews = useMemo(() => {
    return newsItems.filter((news) => {
      const newsYear = new Date(news.date).getFullYear().toString();
      const yearMatch = selectedYear === "All" || newsYear === selectedYear;
      const categoryMatch =
        selectedCategory === "All" || news.category === selectedCategory;
      return yearMatch && categoryMatch;
    });
  }, [newsItems, selectedYear, selectedCategory]);

  // Pagination
  const totalPages = Math.ceil(filteredNews.length / ITEMS_PER_PAGE);
  const paginatedNews = filteredNews.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE,
  );

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedYear, selectedCategory]);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  };

  if (selectedArticle) {
    const colors = categoryColors[selectedArticle.category] || { bg: "bg-slate-100", text: "text-slate-700" };
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
        <header className="bg-gradient-to-r from-[#012a5a] via-[#0b6fb7] to-[#0d8fb3] text-white">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
            <div className="flex flex-wrap items-center gap-3">
              <Link
                to="/news"
                className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/20"
              >
                <span aria-hidden="true">←</span>
                Back to all news
              </Link>
              <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-semibold ${colors.bg} ${colors.text}`}>
                {selectedArticle.category}
              </span>
            </div>
            <h1 className="mt-7 max-w-4xl text-4xl font-extrabold leading-tight md:text-5xl">{selectedArticle.title}</h1>
            <p className="mt-4 text-white/85">{formatDate(selectedArticle.date)}</p>
          </div>
        </header>
        <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <img
            src={selectedArticle.thumbnail}
            alt={selectedArticle.title}
            onError={useFallbackThumbnail}
            width={1200}
            height={525}
            decoding="async"
            className="mb-8 aspect-[16/7] w-full rounded-2xl bg-slate-200 object-cover shadow-lg"
          />
          <p className="mb-8 text-xl leading-relaxed text-slate-700">{selectedArticle.summary}</p>
          {selectedArticle.source === "cms" && selectedArticle.body ? (
            <article
              className="prose max-w-none rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
              dangerouslySetInnerHTML={{ __html: selectedArticle.body }}
            />
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-slate-700 shadow-sm">
              Full article content will be available once this item is published through the CMS.
            </div>
          )}
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="bg-gradient-to-r from-[#012a5a] via-[#0b6fb7] to-[#0d8fb3] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
              {asString(heroContent.title, "News & Announcements")}
            </h1>
            <p className="text-lg text-white/90">
              {asString(heroContent.subtitle, "Latest updates from RDC-NCR")}
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <section className="mb-8 rounded-2xl border border-blue-100 bg-white p-6 shadow-sm">
          <h2 className="text-2xl font-bold text-slate-900">
            {asString(listingContent.title, "Published News and Announcements")}
          </h2>
          <p className="mt-2 text-slate-600">
            {asString(
              listingContent.subtitle,
              "Browse official updates, resolutions, committee announcements, and events.",
            )}
          </p>
          {asString(listingContent.body) && (
            <p className="mt-2 text-sm text-slate-500">
              {asString(listingContent.body)}
            </p>
          )}
        </section>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar Filters */}
          <aside className="lg:col-span-1">
            <div className="lg:sticky lg:top-6">
              {/* Mobile Filter Toggle */}
              <button
                onClick={() => setShowMobileFilters(!showMobileFilters)}
                className="lg:hidden w-full mb-4 px-4 py-3 bg-white rounded-xl shadow-md border border-slate-200 font-medium flex items-center justify-between"
              >
                <span>Filters</span>
                <svg
                  className={`w-5 h-5 transition-transform ${
                    showMobileFilters ? "rotate-180" : ""
                  }`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                >
                  <path d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Filter Panel */}
              <div
                className={`space-y-6 ${
                  showMobileFilters ? "block" : "hidden lg:block"
                }`}
              >
                {/* Year Filter */}
                {newsError && (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                    {newsError}
                  </div>
                )}
                <div className="bg-white rounded-xl shadow-md p-6 border border-slate-100">
                  <h3 className="text-lg font-bold text-slate-900 mb-4">
                    Filter by Year
                  </h3>
                  <div className="space-y-2">
                    {years.map((year) => (
                      <button
                        key={year}
                        onClick={() => setSelectedYear(year)}
                        className={`w-full text-left px-4 py-2 rounded-lg transition ${
                          selectedYear === year
                            ? "bg-blue-600 text-white"
                            : "bg-slate-50 text-slate-700 hover:bg-slate-100"
                        }`}
                      >
                        {year}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Category Filter */}
                <div className="bg-white rounded-xl shadow-md p-6 border border-slate-100">
                  <h3 className="text-lg font-bold text-slate-900 mb-4">
                    Filter by Category
                  </h3>
                  <div className="space-y-2">
                    <button
                      onClick={() => setSelectedCategory("All")}
                      className={`w-full text-left px-4 py-2 rounded-lg transition ${
                        selectedCategory === "All"
                          ? "bg-blue-600 text-white"
                          : "bg-slate-50 text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      All Categories
                    </button>
                    {categories
                      .filter((category) => category !== "All")
                      .map((category) => (
                        <button
                          key={category}
                          onClick={() => setSelectedCategory(category)}
                          className={`w-full text-left px-4 py-2 rounded-lg transition ${
                            selectedCategory === category
                              ? "bg-blue-600 text-white"
                              : "bg-slate-50 text-slate-700 hover:bg-slate-100"
                          }`}
                        >
                          {category}
                        </button>
                      ))}
                  </div>
                </div>

                {/* Results Info */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-100">
                  <h4 className="text-sm font-bold text-slate-900 mb-2">
                    Search Results
                  </h4>
                  <div className="text-3xl font-extrabold text-blue-600 mb-1">
                    {filteredNews.length}
                  </div>
                  <div className="text-sm text-slate-600">
                    article{filteredNews.length !== 1 ? "s" : ""} found
                  </div>
                </div>

                {/* Reset Button */}
                <button
                  onClick={() => {
                    setSelectedYear("All");
                    setSelectedCategory("All");
                    setCurrentPage(1);
                  }}
                  className="w-full px-4 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium rounded-lg transition"
                >
                  Reset All Filters
                </button>
              </div>
            </div>
          </aside>

          {/* News Grid */}
          <section className="lg:col-span-3">
            {/* Results Summary */}
            <div className="mb-6 flex items-center justify-between">
              <div className="text-sm text-slate-600">
                Showing {paginatedNews.length} of {filteredNews.length} results
              </div>
              <div className="text-sm text-slate-600">
                Page {currentPage} of {totalPages}
              </div>
            </div>

            {/* News Cards Grid */}
            {newsLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
                {[1, 2, 3, 4, 5, 6].map((item) => (
                  <div key={item} className="h-80 animate-pulse rounded-xl border border-slate-100 bg-white shadow-md">
                    <div className="h-48 rounded-t-xl bg-slate-200" />
                    <div className="space-y-3 p-5">
                      <div className="h-4 w-2/3 rounded bg-slate-200" />
                      <div className="h-3 w-full rounded bg-slate-100" />
                      <div className="h-3 w-4/5 rounded bg-slate-100" />
                    </div>
                  </div>
                ))}
              </div>
            ) : paginatedNews.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
                {paginatedNews.map((news) => (
                  <article
                    key={news.id}
                    className="bg-white rounded-xl shadow-md hover:shadow-xl transition-all transform hover:-translate-y-1 overflow-hidden border border-slate-100 flex flex-col group"
                  >
                    {/* Thumbnail */}
                    <div className="relative h-48 overflow-hidden bg-slate-200">
                      <img
                        src={news.thumbnail}
                        alt={news.title}
                        onError={useFallbackThumbnail}
                        width={640}
                        height={384}
                        loading="lazy"
                        decoding="async"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      {/* Category Badge */}
                      <div className="absolute top-3 right-3">
                        <span
                          className={`text-xs font-semibold px-3 py-1 rounded-full ${
                            (categoryColors[news.category] || { bg: "bg-slate-100", text: "text-slate-700" }).bg
                          } ${(categoryColors[news.category] || { bg: "bg-slate-100", text: "text-slate-700" }).text}`}
                        >
                          {news.category}
                        </span>
                      </div>
                    </div>

                    {/* Content */}
                    <div className="p-5 flex flex-col flex-1">
                      {/* Date */}
                      <div className="flex items-center gap-2 text-sm text-slate-500 mb-3">
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <rect
                            x="3"
                            y="4"
                            width="18"
                            height="18"
                            rx="2"
                            ry="2"
                          />
                          <line x1="16" y1="2" x2="16" y2="6" />
                          <line x1="8" y1="2" x2="8" y2="6" />
                          <line x1="3" y1="10" x2="21" y2="10" />
                        </svg>
                        {formatDate(news.date)}
                      </div>

                      {/* Title */}
                      <h3 className="text-lg font-bold text-slate-900 mb-2 line-clamp-2 group-hover:text-blue-600 transition">
                        {news.title}
                      </h3>

                      {/* Summary */}
                      <p className="text-sm text-slate-600 mb-4 line-clamp-3 flex-1">
                        {news.summary}
                      </p>

                      {/* Read More Button */}
                      <Link
                        to={`/news/${news.slug}`}
                        className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium text-sm group-hover:gap-3 transition-all"
                      >
                        Read More
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M9 5l7 7-7 7" />
                        </svg>
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="text-center py-16">
                <svg
                  className="mx-auto h-16 w-16 text-slate-400 mb-4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  viewBox="0 0 24 24"
                >
                  <path d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                </svg>
                <h3 className="text-xl font-bold text-slate-900 mb-2">
                  No articles found
                </h3>
                <p className="text-slate-600 mb-4">
                  Try adjusting your filters to see more results
                </p>
                <button
                  onClick={() => {
                    setSelectedYear("All");
                    setSelectedCategory("All");
                    setCurrentPage(1);
                  }}
                  className="px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition"
                >
                  Clear Filters
                </button>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() =>
                    setCurrentPage((prev) => Math.max(1, prev - 1))
                  }
                  disabled={currentPage === 1}
                  className="px-4 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 font-medium hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Previous
                </button>

                <div className="flex items-center gap-2">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                    (page) => (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`w-10 h-10 rounded-lg font-medium transition ${
                          currentPage === page
                            ? "bg-blue-600 text-white"
                            : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        {page}
                      </button>
                    ),
                  )}
                </div>

                <button
                  onClick={() =>
                    setCurrentPage((prev) => Math.min(totalPages, prev + 1))
                  }
                  disabled={currentPage === totalPages}
                  className="px-4 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 font-medium hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Next
                </button>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
