import React, { useState, useMemo } from "react";
import { Link } from "react-router-dom";

type NewsCategory =
  | "Press Release"
  | "Event"
  | "Resolution"
  | "Committee Announcement";

type NewsItem = {
  id: string;
  title: string;
  category: NewsCategory;
  date: string;
  summary: string;
  thumbnail: string;
  slug: string;
};

const SAMPLE_NEWS: NewsItem[] = [
  {
    id: "news-001",
    title: "RDC-NCR Elects New Chairperson for 2025-2026",
    category: "Press Release",
    date: "2024-11-17",
    summary:
      "The Regional Development Council elected a new chairperson during its fourth quarter meeting, marking a new chapter in regional governance.",
    thumbnail:
      "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?q=80&w=800&auto=format&fit=crop",
    slug: "new-chairperson-2025",
  },
  {
    id: "news-002",
    title: "NCR Backs Call for Digital Transformation Initiative",
    category: "Committee Announcement",
    date: "2024-11-12",
    summary:
      "The Infrastructure Development Committee endorsed support for digital initiatives across the region to modernize public services.",
    thumbnail:
      "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=800&auto=format&fit=crop",
    slug: "digital-transformation",
  },
  {
    id: "news-003",
    title: "Quarterly Economic Report Released: Q3 2024",
    category: "Press Release",
    date: "2024-11-08",
    summary:
      "The latest economic indicators show positive growth trends in the National Capital Region with 6.2% GDP increase.",
    thumbnail:
      "https://images.unsplash.com/photo-1460925895917-adf4e7d5e7a1?q=80&w=800&auto=format&fit=crop",
    slug: "q3-economic-report",
  },
  {
    id: "news-004",
    title: "RDC Full Council Meeting - December 15, 2024",
    category: "Event",
    date: "2024-11-05",
    summary:
      "Save the date! The RDC Full Council Meeting will convene to discuss regional development priorities and review ongoing projects.",
    thumbnail:
      "https://images.unsplash.com/photo-1511578314322-379afb476865?q=80&w=800&auto=format&fit=crop",
    slug: "council-meeting-dec",
  },
  {
    id: "news-005",
    title: "Resolution No. 2024-15: Infrastructure Investment Approval",
    category: "Resolution",
    date: "2024-10-28",
    summary:
      "RDC-NCR approves PHP 12.5 billion infrastructure investment program for 2025, focusing on transport and flood control.",
    thumbnail:
      "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=800&auto=format&fit=crop",
    slug: "resolution-2024-15",
  },
  {
    id: "news-006",
    title: "Public Consultation on Greenprint 2030 Extended",
    category: "Press Release",
    date: "2024-10-22",
    summary:
      "Due to public demand, the consultation period for Greenprint 2030 has been extended until November 30, 2024.",
    thumbnail:
      "https://images.unsplash.com/photo-1497436072909-60f360e1d4b1?q=80&w=800&auto=format&fit=crop",
    slug: "greenprint-consultation",
  },
  {
    id: "news-007",
    title: "Innovation Summit 2024: Smart Cities Forum",
    category: "Event",
    date: "2024-10-15",
    summary:
      "Join us for a two-day summit exploring smart city solutions and digital governance innovations for Metro Manila.",
    thumbnail:
      "https://images.unsplash.com/photo-1540575467063-178a50c2df87?q=80&w=800&auto=format&fit=crop",
    slug: "innovation-summit",
  },
  {
    id: "news-008",
    title: "Housing Committee Announces New Affordable Housing Program",
    category: "Committee Announcement",
    date: "2024-10-10",
    summary:
      "New program aims to provide 50,000 affordable housing units across NCR by 2026 through public-private partnerships.",
    thumbnail:
      "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=800&auto=format&fit=crop",
    slug: "housing-program",
  },
  {
    id: "news-009",
    title: "Resolution No. 2024-14: Climate Action Plan Adopted",
    category: "Resolution",
    date: "2024-09-30",
    summary:
      "RDC-NCR formally adopts comprehensive climate action plan aligned with national and international commitments.",
    thumbnail:
      "https://images.unsplash.com/photo-1569163139394-de4798aa62b6?q=80&w=800&auto=format&fit=crop",
    slug: "resolution-2024-14",
  },
  {
    id: "news-010",
    title: "Regional Development Forum: Stakeholder Engagement Success",
    category: "Event",
    date: "2024-09-25",
    summary:
      "Over 500 stakeholders participated in the successful Regional Development Forum discussing NCR's future priorities.",
    thumbnail:
      "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?q=80&w=800&auto=format&fit=crop",
    slug: "development-forum",
  },
  {
    id: "news-011",
    title: "Transportation Committee Updates on Metro Manila Subway",
    category: "Committee Announcement",
    date: "2024-09-18",
    summary:
      "Latest progress report shows subway project is 45% complete, on track for 2025 partial operations target.",
    thumbnail:
      "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?q=80&w=800&auto=format&fit=crop",
    slug: "subway-update",
  },
  {
    id: "news-012",
    title: "RDC-NCR Launches Open Data Portal",
    category: "Press Release",
    date: "2024-09-10",
    summary:
      "New transparency initiative provides public access to regional development data, statistics, and project information.",
    thumbnail:
      "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=800&auto=format&fit=crop",
    slug: "open-data-portal",
  },
];

const categoryColors: Record<NewsCategory, { bg: string; text: string }> = {
  "Press Release": { bg: "bg-blue-100", text: "text-blue-700" },
  Event: { bg: "bg-green-100", text: "text-green-700" },
  Resolution: { bg: "bg-purple-100", text: "text-purple-700" },
  "Committee Announcement": { bg: "bg-orange-100", text: "text-orange-700" },
};

const ITEMS_PER_PAGE = 9;

export default function NewsPage() {
  const [selectedYear, setSelectedYear] = useState<string>("All");
  const [selectedCategory, setSelectedCategory] = useState<
    NewsCategory | "All"
  >("All");
  const [currentPage, setCurrentPage] = useState(1);
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  // Extract unique years
  const years = useMemo(() => {
    const yearSet = new Set<string>();
    SAMPLE_NEWS.forEach((news) => {
      yearSet.add(new Date(news.date).getFullYear().toString());
    });
    return [
      "All",
      ...Array.from(yearSet).sort((a, b) => Number(b) - Number(a)),
    ];
  }, []);

  // Filter news
  const filteredNews = useMemo(() => {
    return SAMPLE_NEWS.filter((news) => {
      const newsYear = new Date(news.date).getFullYear().toString();
      const yearMatch = selectedYear === "All" || newsYear === selectedYear;
      const categoryMatch =
        selectedCategory === "All" || news.category === selectedCategory;
      return yearMatch && categoryMatch;
    });
  }, [selectedYear, selectedCategory]);

  // Pagination
  const totalPages = Math.ceil(filteredNews.length / ITEMS_PER_PAGE);
  const paginatedNews = filteredNews.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  // Reset to page 1 when filters change
  useMemo(() => {
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

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="bg-gradient-to-r from-[#012a5a] via-[#0b6fb7] to-[#0d8fb3] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
              News & Announcements
            </h1>
            <p className="text-lg text-white/90">Latest updates from RDC-NCR</p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
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
                    {(Object.keys(categoryColors) as NewsCategory[]).map(
                      (category) => (
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
                      )
                    )}
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
            {paginatedNews.length > 0 ? (
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
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      {/* Category Badge */}
                      <div className="absolute top-3 right-3">
                        <span
                          className={`text-xs font-semibold px-3 py-1 rounded-full ${
                            categoryColors[news.category].bg
                          } ${categoryColors[news.category].text}`}
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
                    )
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
