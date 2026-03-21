import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import photo1 from "../assets/Photo-Corousel/Photos/photo1.jpg";
import photo2 from "../assets/Photo-Corousel/Photos/photo2.jpg";
import photo3 from "../assets/Photo-Corousel/Photos/photo3.jpg";
import photo4 from "../assets/Photo-Corousel/Photos/photo4.jpg";
import photo5 from "../assets/Photo-Corousel/Photos/photo5.jpg";
import photo6 from "../assets/Photo-Corousel/Photos/photo6.jpg";
import photo7 from "../assets/Photo-Corousel/Photos/photo7.jpg";
import photo8 from "../assets/Photo-Corousel/Photos/photo8.jpg";
import photo9 from "../assets/Photo-Corousel/Photos/photo9.jpg";
import rdcLogo from "../assets/Photo-Corousel/Photos/RDC-NCR LOGO.png";

const Home: React.FC = () => {
  const [visitorCount, setVisitorCount] = useState(0);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [pageViews, setPageViews] = useState(0);
  const [averageDailyViews, setAverageDailyViews] = useState(0);
  const [todayViews, setTodayViews] = useState(0);
  const navigate = useNavigate();

  const carouselImages = [
    {
      src: photo1,
      title: "Regional Development Council – NCR",
      subtitle: "Planning a sustainable and resilient Metro Manila",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo2,
      title: "Building a Better Future",
      subtitle: "Collaborative governance for Metro Manila's growth",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo3,
      title: "Strategic Development",
      subtitle: "Empowering communities through effective planning",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo4,
      title: "Infrastructure Excellence",
      subtitle: "Modern solutions for urban challenges",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo5,
      title: "Sustainable Growth",
      subtitle: "Balancing progress with environmental care",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo6,
      title: "Urban Innovation Hub",
      subtitle: "Transforming Metro Manila into a smart metropolis",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo7,
      title: "Community Engagement",
      subtitle: "Working together for inclusive development",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo8,
      title: "Economic Resilience",
      subtitle: "Strengthening NCR's economic foundations",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
    {
      src: photo9,
      title: "Future-Ready Infrastructure",
      subtitle: "Building for tomorrow's needs today",
      button1: { text: "View Plans", link: "/plans" },
      button2: { text: "Latest Reports", link: "/reports" },
    },
  ];

  const newsArticles = [
    {
      id: 1,
      title: "RDC-NCR ELECTS NEW CHAIRPERSON FOR 2025-2026",
      excerpt:
        "The Regional Development Council elected a new chairperson during its fourth quarter meeting...",
      date: "November 17, 2025",
      image: photo2,
      category: "Announcement",
    },
    {
      id: 2,
      title: "NCR BACKS CALL FOR DIGITAL TRANSFORMATION",
      excerpt:
        "The Infrastructure Development Committee endorsed support for digital initiatives across the region...",
      date: "November 12, 2025",
      image: photo3,
      category: "Technology",
    },
    {
      id: 3,
      title: "QUARTERLY ECONOMIC REPORT RELEASED",
      excerpt:
        "The latest economic indicators show positive growth trends in the National Capital Region...",
      date: "November 8, 2025",
      image: photo4,
      category: "Report",
    },
    {
      id: 4,
      title: "METRO MANILA TRANSPORTATION PLAN UPDATE",
      excerpt:
        "New initiatives to improve public transportation and reduce congestion in Metro Manila...",
      date: "November 5, 2025",
      image: photo5,
      category: "Infrastructure",
    },
  ];

  const developmentPlans = [
    {
      title: "Metro Manila Greenprint 2030",
      category: "Sustainability Framework",
      icon: "🌿",
      link: "/publications?category=greenprint",
    },
    {
      title: "Regional Development Plan",
      category: "Comprehensive Plan",
      icon: "📋",
      link: "/publications?category=rdp",
    },
    {
      title: "SDG Catch-up Plan",
      category: "Development Goals",
      icon: "🎯",
      link: "/publications?category=sdg",
    },
  ];

  const investmentProgramming = [
    {
      title: "Regional Development Investment Program",
      category: "Investment Portfolio",
      icon: "💰",
      link: "/publications?category=rdip",
      quickLinks: [
        { label: "RDIP DOCUMENTS", link: "/publications?category=rdip" },
        { label: "RDIP DASHBOARD", link: "/Projects" },
      ],
    },
  ];

  const monitoringEvaluation = [
    {
      title: "Regional Development Report",
      category: "Annual Report",
      icon: "📊",
      link: "/publications?category=rdr",
    },
    {
      title: "Regional Project Monitoring and Evaluation System",
      category: "Monitoring System",
      icon: "📈",
      link: "/publications?category=rpmes",
    },
  ];

  const upcomingEvents = [
    {
      day: 15,
      month: "DEC",
      title: "RDC Full Council Meeting",
      time: "9:00 AM",
      location: "NEDA Conference Room",
      type: "meeting",
    },
    {
      day: 20,
      month: "DEC",
      title: "Public Consultation Forum",
      time: "2:00 PM",
      location: "Virtual",
      type: "forum",
    },
    {
      day: 10,
      month: "JAN",
      title: "Private Sector Partnership Summit",
      time: "10:00 AM",
      location: "Manila Hotel",
      type: "summit",
    },
    {
      day: 25,
      month: "JAN",
      title: "Infrastructure Committee Meeting",
      time: "1:30 PM",
      location: "MMDA Building",
      type: "meeting",
    },
  ];

  const dashboardStats = [
    { label: "Ongoing Projects", value: "142", change: "+5%", trend: "up" },
    { label: "Completed Projects", value: "89", change: "+12%", trend: "up" },
    { label: "Total Investment", value: "₱2.4B", change: "+8%", trend: "up" },
    { label: "Community Impact", value: "1.2M", change: "+15%", trend: "up" },
  ];

  const projectStatusData = [
    { status: "Planning", count: 45, color: "bg-blue-500" },
    { status: "In Progress", count: 67, color: "bg-yellow-500" },
    { status: "Completed", count: 89, color: "bg-green-500" },
  ];

  const investmentData = [
    { sector: "Infrastructure", amount: "₱1.2B", percentage: 50 },
    { sector: "Social Services", amount: "₱480M", percentage: 20 },
    { sector: "Economic Development", amount: "₱360M", percentage: 15 },
    { sector: "Environment", amount: "₱240M", percentage: 10 },
    { sector: "Governance", amount: "₱120M", percentage: 5 },
  ];

  const timelineData = [
    { quarter: "Q1 2024", projects: 25 },
    { quarter: "Q2 2024", projects: 32 },
    { quarter: "Q3 2024", projects: 45 },
    { quarter: "Q4 2024", projects: 40 },
    { quarter: "Q1 2025", projects: 38 },
    { quarter: "Q2 2025", projects: 42 },
  ];

  // Google Maps URL for the address
  const googleMapsUrl =
    "https://www.google.com/maps/dir/?api=1&destination=MMDA+Head+Office,+Julia+Vargas+Avenue,+Pasig,+Metro+Manila";

  // Email URL
  const emailUrl = "mailto:rdc.ncr@mmda.gov.ph";

  useEffect(() => {
    const local = localStorage.getItem("visitorCount");
    const next = local ? parseInt(local) + 1 : 1;
    localStorage.setItem("visitorCount", next.toString());
    setVisitorCount(next);

    // Simulate analytics data
    setPageViews(15432);
    setAverageDailyViews(387);
    setTodayViews(123);
  }, []);

  useEffect(() => {
    if (isPaused) return;

    const timer = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % carouselImages.length);
    }, 5000);

    return () => clearInterval(timer);
  }, [isPaused, carouselImages.length]);

  const goToSlide = (index: number) => {
    setCurrentSlide(index);
  };

  const nextSlide = () => {
    setCurrentSlide((prev) => (prev + 1) % carouselImages.length);
  };

  const prevSlide = () => {
    setCurrentSlide(
      (prev) => (prev - 1 + carouselImages.length) % carouselImages.length
    );
  };

  const handleDocumentClick = (link: string) => {
    navigate(link);
  };

  const renderDocumentCard = (doc: any) => (
    <div
      key={doc.title}
      className="bg-white rounded-lg border border-gray-200 hover:border-green-500 hover:shadow-lg transition-all duration-300 group cursor-pointer"
      onClick={() => handleDocumentClick(doc.link)}
    >
      <div className="p-5">
        <div className="flex items-start gap-4">
          <div className="text-3xl mt-1">{doc.icon}</div>
          <div className="flex-1">
            <span className="inline-block px-3 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full mb-3">
              {doc.category}
            </span>
            <h4 className="font-bold text-gray-800 text-lg group-hover:text-green-700 transition-colors">
              {doc.title}
            </h4>
            <div className="inline-flex items-center gap-2 text-green-600 hover:text-green-800 font-medium mt-4 transition-colors">
              View Details
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const StatCard = ({ label, value, change, trend }: any) => (
    <div className="bg-gray-800 rounded-xl p-5">
      <div className="text-3xl font-bold text-white mb-2">{value}</div>
      <div className="text-sm text-gray-300 mb-3">{label}</div>
      <div
        className={`text-sm ${
          trend === "up" ? "text-green-400" : "text-red-400"
        } flex items-center gap-1`}
      >
        <span>{change}</span>
        <svg
          className={`w-4 h-4 ${
            trend === "up" ? "text-green-400" : "text-red-400"
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          {trend === "up" ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 15l7-7 7 7"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          )}
        </svg>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      {/* Hero Carousel Section - Clean Rectangle */}
      <section
        className="relative overflow-hidden"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div className="relative h-[70vh] min-h-[500px]">
          {carouselImages.map((slide, index) => (
            <div
              key={index}
              className={`absolute inset-0 transition-opacity duration-1000 ease-in-out ${
                index === currentSlide ? "opacity-100" : "opacity-0"
              }`}
              style={{
                backgroundImage: `url(${slide.src})`,
                backgroundSize: "cover",
                backgroundPosition: "center",
                backgroundRepeat: "no-repeat",
              }}
            >
              {/* Dark overlay for better text readability */}
              <div className="absolute inset-0 bg-black/50"></div>

              <div className="container mx-auto px-4 sm:px-6 lg:px-8 relative h-full flex items-center">
                <div className="max-w-3xl text-white">
                  <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight mb-4">
                    {slide.title}
                  </h1>
                  <p className="text-xl md:text-2xl text-gray-200 mb-8">
                    {slide.subtitle}
                  </p>

                  <div className="flex flex-wrap gap-4">
                    <Link
                      to="/publications"
                      className="bg-white text-green-800 hover:bg-gray-100 px-6 py-3 rounded-lg font-semibold text-lg shadow-lg hover:shadow-xl transition-all duration-300"
                    >
                      {slide.button1.text}
                    </Link>
                    <Link
                      to="/publications?category=rdr"
                      className="bg-transparent border-2 border-white hover:bg-white/10 text-white px-6 py-3 rounded-lg font-semibold text-lg transition-all duration-300"
                    >
                      {slide.button2.text}
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Carousel Controls */}
        <button
          onClick={prevSlide}
          className="absolute left-4 top-1/2 -translate-y-1/2 z-20 bg-white/20 hover:bg-white/30 text-white p-3 rounded-full transition-all duration-300 backdrop-blur-sm hover:scale-110"
          aria-label="Previous slide"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>

        <button
          onClick={nextSlide}
          className="absolute right-4 top-1/2 -translate-y-1/2 z-20 bg-white/20 hover:bg-white/30 text-white p-3 rounded-full transition-all duration-300 backdrop-blur-sm hover:scale-110"
          aria-label="Next slide"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>

        {/* Carousel Indicators */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex gap-2">
          {carouselImages.map((_, index) => (
            <button
              key={index}
              onClick={() => goToSlide(index)}
              className={`w-3 h-3 rounded-full transition-all duration-300 ${
                index === currentSlide
                  ? "bg-white scale-125"
                  : "bg-white/50 hover:bg-white/75"
              }`}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>
      </section>

      {/* Announcement Banner */}
      <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white py-2 px-4 text-center"></div>

      {/* Main Content Area */}
      <main className="container mx-auto px-4 pb-8 pt-6">
        {/* Featured Documents Section */}
        <section className="mb-8">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Development Plans and Frameworks */}
            <div className="bg-white rounded-xl shadow-md overflow-hidden">
              <div className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-4">
                <h2 className="text-xl font-bold">
                  Development Plans and Frameworks
                </h2>
              </div>
              <div className="p-5 space-y-5">
                {developmentPlans.map(renderDocumentCard)}
              </div>
            </div>

            {/* Investment Programming */}
            <div className="bg-white rounded-xl shadow-md overflow-hidden">
              <div className="bg-gradient-to-r from-green-600 to-green-700 text-white px-6 py-4">
                <h2 className="text-xl font-bold">Investment Programming</h2>
              </div>
              <div className="p-5 space-y-5">
                {investmentProgramming.map((doc, index) => (
                  <div key={index} className="space-y-5">
                    <div
                      className="bg-white rounded-lg border border-gray-200 hover:border-green-500 hover:shadow-lg transition-all duration-300 group cursor-pointer"
                      onClick={() => handleDocumentClick(doc.link)}
                    >
                      <div className="p-5">
                        <div className="flex items-start gap-4">
                          <div className="text-3xl mt-1">{doc.icon}</div>
                          <div className="flex-1">
                            <span className="inline-block px-3 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full mb-3">
                              {doc.category}
                            </span>
                            <h4 className="font-bold text-gray-800 text-lg group-hover:text-green-700 transition-colors">
                              {doc.title}
                            </h4>
                            <div className="inline-flex items-center gap-2 text-green-600 hover:text-green-800 font-medium mt-4 transition-colors">
                              View Details
                              <svg
                                className="w-4 h-4"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M9 5l7 7-7 7"
                                />
                              </svg>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Quick Links inside Investment Programming */}
                    <div className="border-t pt-5">
                      <h5 className="font-semibold text-gray-700 mb-3">
                        Quick Access:
                      </h5>
                      <div className="space-y-2">
                        {doc.quickLinks.map((quickLink: any, idx: number) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors group cursor-pointer"
                            onClick={() => handleDocumentClick(quickLink.link)}
                          >
                            <span className="font-medium text-gray-800">
                              {quickLink.label}
                            </span>
                            <svg
                              className="w-4 h-4 text-gray-400 group-hover:text-green-600 transition-colors"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 5l7 7-7 7"
                              />
                            </svg>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Monitoring and Evaluation */}
            <div className="bg-white rounded-xl shadow-md overflow-hidden">
              <div className="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-4">
                <h2 className="text-xl font-bold">Monitoring and Evaluation</h2>
              </div>
              <div className="p-5 space-y-5">
                {monitoringEvaluation.map(renderDocumentCard)}
              </div>
            </div>
          </div>
        </section>

        {/* Enhanced Dashboard Section with Graphs */}
        <section className="mb-8">
          <div className="bg-white rounded-xl shadow-lg overflow-hidden">
            <div className="bg-gradient-to-r from-gray-900 to-black text-white px-6 py-4">
              <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold">
                  Regional Development Dashboard
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-300">
                    Last updated: Today
                  </span>
                  <Link
                    to="/Projects"
                    className="bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors"
                  >
                    View Full Dashboard →
                  </Link>
                </div>
              </div>
            </div>

            <div className="p-6">
              {/* Top Stats Row */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {dashboardStats.map((stat, index) => (
                  <StatCard key={index} {...stat} />
                ))}
              </div>

              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
                {/* Project Status Chart */}
                <div className="bg-gray-50 rounded-xl p-5">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">
                    Project Status Distribution
                  </h3>
                  <div className="space-y-3">
                    {projectStatusData.map((item, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-3 h-3 rounded-full ${item.color}`}
                          ></div>
                          <span className="text-sm text-gray-700">
                            {item.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="w-32 bg-gray-200 rounded-full h-2">
                            <div
                              className={`h-full ${item.color} rounded-full`}
                              style={{ width: `${(item.count / 216) * 100}%` }}
                            ></div>
                          </div>
                          <span className="text-sm font-semibold text-gray-800">
                            {item.count}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Investment Distribution */}
                <div className="bg-gray-50 rounded-xl p-5">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">
                    Investment Distribution
                  </h3>
                  <div className="space-y-3">
                    {investmentData.map((item, index) => (
                      <div key={index} className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-700">{item.sector}</span>
                          <span className="font-semibold text-gray-800">
                            {item.amount}
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-green-600 h-full rounded-full"
                            style={{ width: `${item.percentage}%` }}
                          ></div>
                        </div>
                        <div className="text-xs text-gray-500 text-right">
                          {item.percentage}%
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Project Timeline */}
                <div className="bg-gray-50 rounded-xl p-5">
                  <h3 className="text-lg font-bold text-gray-800 mb-4">
                    Projects Timeline (Last 6 Quarters)
                  </h3>
                  <div className="flex items-end h-32 gap-2 pt-4">
                    {timelineData.map((item, index) => {
                      const maxProjects = Math.max(
                        ...timelineData.map((d) => d.projects)
                      );
                      const height = (item.projects / maxProjects) * 80;
                      return (
                        <div
                          key={index}
                          className="flex-1 flex flex-col items-center"
                        >
                          <div
                            className="w-full bg-gradient-to-t from-blue-500 to-blue-600 rounded-t-lg"
                            style={{ height: `${height}px` }}
                          ></div>
                          <div className="text-xs text-gray-600 mt-2 text-center">
                            <div>{item.quarter}</div>
                            <div className="font-semibold">{item.projects}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* News and Events Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Latest Media Releases */}
          <div className="lg:col-span-2">
            <section className="bg-white rounded-xl shadow-md overflow-hidden h-full">
              <div className="bg-gray-800 text-white px-5 py-3">
                <div className="flex justify-between items-center">
                  <h2 className="text-xl font-bold">Latest Media Releases</h2>
                  <Link
                    to="/news"
                    className="text-xs text-blue-300 hover:text-white transition-colors"
                  >
                    View all →
                  </Link>
                </div>
              </div>
              <div className="p-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {newsArticles.map((article) => (
                    <article
                      key={article.id}
                      className="border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow duration-300"
                    >
                      <div className="md:flex">
                        <div className="md:w-2/5 relative">
                          <img
                            src={article.image}
                            alt={article.title}
                            className="w-full h-48 md:h-full object-cover"
                          />
                          <div className="absolute top-2 left-2">
                            <span className="bg-blue-600 text-white text-xs px-2 py-1 rounded">
                              {article.category}
                            </span>
                          </div>
                        </div>
                        <div className="md:w-3/5 p-5">
                          <p className="text-xs text-gray-500 mb-2">
                            {article.date}
                          </p>
                          <h3 className="font-bold text-gray-800 text-lg mb-3 line-clamp-2">
                            {article.title}
                          </h3>
                          <p className="text-sm text-gray-600 mb-4 line-clamp-3">
                            {article.excerpt}
                          </p>
                          <Link
                            to={`/news/${article.id}`}
                            className="text-green-700 font-semibold text-sm hover:text-green-800 transition-colors inline-flex items-center gap-1"
                          >
                            Read more
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 5l7 7-7 7"
                              />
                            </svg>
                          </Link>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            </section>
          </div>

          {/* Upcoming Events */}
          <aside>
            <div className="bg-white rounded-xl shadow-md overflow-hidden h-full">
              <div className="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-5 py-4">
                <h3 className="text-lg font-bold">Upcoming Events</h3>
                <p className="text-sm opacity-90 mt-0.5">Calendar & Meetings</p>
              </div>
              <div className="p-5">
                <div className="space-y-4">
                  {upcomingEvents.map((event, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-3 p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex-shrink-0">
                        <div
                          className={`${
                            event.type === "meeting"
                              ? "bg-blue-100 text-blue-700"
                              : event.type === "forum"
                              ? "bg-green-100 text-green-700"
                              : "bg-purple-100 text-purple-700"
                          } p-3 rounded-lg text-center min-w-[60px]`}
                        >
                          <div className="text-lg font-bold">{event.day}</div>
                          <div className="text-xs font-semibold">
                            {event.month}
                          </div>
                        </div>
                      </div>
                      <div className="flex-1">
                        <h4 className="font-bold text-gray-800 text-sm mb-1">
                          {event.title}
                        </h4>
                        <p className="text-xs text-gray-600">
                          <span className="font-medium">{event.time}</span> •{" "}
                          {event.location}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <span
                            className={`text-xs px-2 py-1 rounded-full ${
                              event.type === "meeting"
                                ? "bg-blue-50 text-blue-600"
                                : event.type === "forum"
                                ? "bg-green-50 text-green-600"
                                : "bg-purple-50 text-purple-600"
                            }`}
                          >
                            {event.type}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-6 pt-4 border-t">
                  <Link
                    to="/events"
                    className="w-full text-center block bg-purple-600 hover:bg-purple-700 text-white font-medium text-sm py-3 rounded-lg transition-colors"
                  >
                    View Full Calendar
                  </Link>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
};

export default Home;
