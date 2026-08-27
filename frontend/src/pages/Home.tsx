import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  getPublicProjects,
  getPublicProjectsStats,
} from "../services/publicProjectsApi";
import { getPublicEvents, type PublicEvent } from "../services/publicEventsApi";
import cmsApi, {
  type CMSArticleSnapshot,
  type CMSPageSnapshot,
} from "../services/cmsApi";
import type { PublicProjectsStats } from "../types/api";
import photo1 from "../assets/Photo-Corousel/Photos/photo1.jpg";
import photo2 from "../assets/Photo-Corousel/Photos/photo2.jpg";
import photo3 from "../assets/Photo-Corousel/Photos/photo3.jpg";
import photo4 from "../assets/Photo-Corousel/Photos/photo4.jpg";
import photo5 from "../assets/Photo-Corousel/Photos/photo5.jpg";
import photo6 from "../assets/Photo-Corousel/Photos/photo6.jpg";
import photo7 from "../assets/Photo-Corousel/Photos/photo7.jpg";
import photo8 from "../assets/Photo-Corousel/Photos/photo8.jpg";
import photo9 from "../assets/Photo-Corousel/Photos/photo9.jpg";
import {
  FaLeaf,
  FaFileAlt,
  FaBullseye,
  FaChartLine,
  FaChartBar,
  FaClipboardList,
} from "react-icons/fa";

type HomeNewsArticle = {
  id: string;
  title: string;
  excerpt: string;
  date: string;
  image: string;
  category: string;
  slug: string;
};

type HomeButton = {
  text: string;
  link: string;
};

type HomeSlide = {
  src: string;
  title: string;
  subtitle: string;
  button1: HomeButton;
  button2: HomeButton;
};

type DocCard = {
  title: string;
  link: string;
  icon?: React.ReactNode;
  category?: string;
  quickLinks?: Array<{ label: string; link: string }>;
};

const imageByKey: Record<string, string> = {
  photo1,
  photo2,
  photo3,
  photo4,
  photo5,
  photo6,
  photo7,
  photo8,
  photo9,
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const asString = (value: unknown, fallback = "") =>
  typeof value === "string" && value.trim() ? value.trim() : fallback;

const asArray = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];

const isVisible = (value: unknown) => {
  const row = asRecord(value);
  return row.isVisible !== false && row.visible !== false;
};

const getHomeSection = (
  page: CMSPageSnapshot | null,
  sectionKey: string | string[],
) => {
  const sectionKeys = Array.isArray(sectionKey) ? sectionKey : [sectionKey];
  return (
    page?.sections.find((section) => sectionKeys.includes(section.sectionKey))
      ?.content ?? null
  );
};

const iconForCms = (icon: unknown, fallback = "file") => {
  const key = asString(icon, fallback).toLowerCase();
  if (key === "leaf") return <FaLeaf className="w-8 h-8 text-green-500" />;
  if (key === "target" || key === "bullseye")
    return <FaBullseye className="w-8 h-8 text-indigo-600" />;
  if (key === "chart-line")
    return <FaChartLine className="w-8 h-8 text-green-600" />;
  if (key === "chart-bar")
    return <FaChartBar className="w-8 h-8 text-purple-600" />;
  if (key === "clipboard")
    return <FaClipboardList className="w-8 h-8 text-purple-500" />;
  return <FaFileAlt className="w-8 h-8 text-gray-700" />;
};

const mapCmsDocItems = (
  content: Record<string, unknown> | null,
  fallback: DocCard[],
) => {
  const baseItems = fallback.map((item) => ({ ...item }));
  const result = [...baseItems];

  asArray(content?.items).forEach((item) => {
    const row = asRecord(item);
    const title = asString(row.title);
    const link = asString(row.link);
    if (!title && !link) return;
    const matchIndex = result.findIndex(
      (candidate) =>
        (!!link && candidate.link === link) ||
        (!!title && candidate.title.toLowerCase() === title.toLowerCase()),
    );
    const fallbackItem = matchIndex >= 0 ? result[matchIndex] : undefined;
    if (!isVisible(row)) {
      if (matchIndex >= 0) result.splice(matchIndex, 1);
      return;
    }
    const quickLinks = asArray(row.quickLinks)
      .map((quickLink) => {
        const quick = asRecord(quickLink);
        const label = asString(quick.label);
        const quickLinkUrl = asString(quick.link);
        return label && quickLinkUrl ? { label, link: quickLinkUrl } : null;
      })
      .filter(Boolean) as Array<{ label: string; link: string }>;

    const nextItem: DocCard = {
      title: asString(row.title, fallbackItem?.title ?? "Featured Document"),
      link: asString(row.link, fallbackItem?.link ?? ""),
      category: asString(row.category, fallbackItem?.category ?? "Featured"),
      icon: row.icon ? iconForCms(row.icon) : fallbackItem?.icon ?? iconForCms(row.icon),
      quickLinks: quickLinks.length ? quickLinks : fallbackItem?.quickLinks,
    };

    if (!nextItem.link) return;
    if (matchIndex >= 0) result[matchIndex] = nextItem;
    else result.push(nextItem);
  });

  return result.length > 0 ? result : fallback;
};

const formatArticleDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "Recently published";
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
};

const mapHomeArticle = (article: CMSArticleSnapshot): HomeNewsArticle => ({
  id: article.slug,
  title: article.title,
  excerpt: article.summary || "Read the latest public update from RDC-NCR.",
  date: formatArticleDate(article.publishedAt),
  image: article.thumbnailUrl || photo2,
  category: article.category || "Updates",
  slug: article.slug,
});

const EVENT_TIME_ZONE = "Asia/Manila";

const eventDayKey = (date: Date) =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: EVENT_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);

const formatEventMoment = (date: Date, now: Date) => {
  const time = date.toLocaleTimeString("en-US", {
    timeZone: EVENT_TIME_ZONE,
    hour: "numeric",
    minute: "2-digit",
  });
  const todayKey = eventDayKey(now);
  const dateKey = eventDayKey(date);
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);

  if (dateKey === todayKey) return `today at ${time}`;
  if (dateKey === eventDayKey(tomorrow)) return `tomorrow at ${time}`;

  const day = date.toLocaleDateString("en-US", {
    timeZone: EVENT_TIME_ZONE,
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
  return `${day} at ${time}`;
};

const formatTimeRemaining = (milliseconds: number) => {
  const totalMinutes = Math.max(1, Math.ceil(milliseconds / 60_000));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) {
    return `${days} day${days === 1 ? "" : "s"}${hours ? ` ${hours} hr` : ""}`;
  }
  if (hours > 0) {
    return `${hours} hr${minutes ? ` ${minutes} min` : ""}`;
  }
  return `${minutes} min`;
};

const getEventTiming = (event: PublicEvent) => {
  const start = new Date(event.start_at);
  const end = event.end_at
    ? new Date(event.end_at)
    : new Date(start.getTime() + 2 * 60 * 60 * 1000);
  const now = new Date();

  if (Number.isNaN(start.getTime())) {
    return {
      rank: 1,
      label: "Scheduled",
      message: "This event is scheduled.",
      className: "bg-blue-50 text-blue-700 ring-1 ring-blue-100",
      messageClassName: "border-blue-100 bg-blue-50 text-blue-700",
    };
  }

  if (now >= start && now < end) {
    return {
      rank: 0,
      label: "Happening now",
      message: `Ends ${formatEventMoment(end, now)} · ${formatTimeRemaining(end.getTime() - now.getTime())} remaining.`,
      className: "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200",
      messageClassName: "border-emerald-100 bg-emerald-50 text-emerald-800",
    };
  }

  if (now >= end) {
    return {
      rank: 2,
      label: "Ended",
      message: `Ended ${formatEventMoment(end, now)}.`,
      className: "bg-slate-100 text-slate-600 ring-1 ring-slate-200",
      messageClassName: "border-slate-200 bg-slate-50 text-slate-600",
    };
  }

  return {
    rank: 1,
    label: "Upcoming",
    message: `Starts ${formatEventMoment(start, now)} · Ends ${formatEventMoment(end, now)}.`,
    className: "bg-blue-50 text-blue-700 ring-1 ring-blue-100",
    messageClassName: "border-blue-100 bg-blue-50 text-blue-700",
  };
};

const sortEventsForDisplay = (events: PublicEvent[]) =>
  [...events].sort((a, b) => {
    const aTiming = getEventTiming(a);
    const bTiming = getEventTiming(b);
    if (aTiming.rank !== bTiming.rank) return aTiming.rank - bTiming.rank;
    const aStart = new Date(a.start_at).getTime() || 0;
    const bStart = new Date(b.start_at).getTime() || 0;
    if (aTiming.rank === 2) return bStart - aStart;
    return aStart - bStart;
  });

const HOME_EVENT_PREVIEW_LIMIT = 3;

const Home: React.FC = () => {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [upcomingEvents, setUpcomingEvents] = useState<PublicEvent[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<PublicEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState("");
  const [showCalendar, setShowCalendar] = useState(false);
  const [calendarFilter, setCalendarFilter] = useState("all");
  const [publicStats, setPublicStats] = useState<PublicProjectsStats | null>(
    null,
  );
  const [publicStatsError, setPublicStatsError] = useState<string>("");
  const [homeCmsPage, setHomeCmsPage] = useState<CMSPageSnapshot | null>(null);
  const [cmsNewsArticles, setCmsNewsArticles] = useState<HomeNewsArticle[]>([]);
  const navigate = useNavigate();

  const buildStatsFromProjects = useCallback(
    (
      projects: Awaited<ReturnType<typeof getPublicProjects>>,
    ): PublicProjectsStats => {
      const by_status: Record<string, number> = {};
      const by_agency: Record<string, number> = {};
      const by_lgu: Record<string, number> = {};
      const by_year: Record<string, number> = {};
      let total_budget = 0;
      let unspecified_location_count = 0;
      let last_updated_at: string | null = null;

      projects.forEach((p) => {
        total_budget += Number(p.budget || 0);
        const status = canonicalStatus(
          p.implementation_status || "Unspecified",
        );
        by_status[status] = (by_status[status] || 0) + 1;

        const agency = String(p.agency || "Other").trim() || "Other";
        by_agency[agency] = (by_agency[agency] || 0) + 1;

        if (p.lgu) by_lgu[p.lgu] = (by_lgu[p.lgu] || 0) + 1;
        else unspecified_location_count += 1;

        if (typeof p.year === "number")
          by_year[String(p.year)] = (by_year[String(p.year)] || 0) + 1;
        if (
          !last_updated_at ||
          (p.updated_at && new Date(p.updated_at) > new Date(last_updated_at))
        ) {
          last_updated_at = p.updated_at || last_updated_at;
        }
      });

      return {
        total_projects: projects.length,
        total_budget,
        by_status,
        by_agency,
        by_lgu,
        by_year,
        unspecified_location_count,
        last_updated_at,
      };
    },
    [],
  );

  const fallbackCarouselImages = useMemo<HomeSlide[]>(
    () => [
      {
        src: photo1,
        title: "Regional Development Council NCR",
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
    ],
    [],
  );

  const heroSection = getHomeSection(homeCmsPage, [
    "hero-carousel",
    "carousel",
  ]);
  const carouselImages = useMemo(() => {
    const slides = asArray(heroSection?.slides)
      .map((slide, index) => {
        const row = asRecord(slide);
        const imageKey = asString(row.imageKey);
        const imageUrl = asString(row.imageUrl);
        const button1 = asRecord(row.button1);
        const button2 = asRecord(row.button2);
        const fallback =
          fallbackCarouselImages[index % fallbackCarouselImages.length];
        return {
          src: imageUrl || imageByKey[imageKey] || fallback.src,
          title: asString(row.title, fallback.title),
          subtitle: asString(row.subtitle, fallback.subtitle),
          button1: {
            text: asString(button1.text, fallback.button1.text),
            link: asString(button1.link, fallback.button1.link),
          },
          button2: {
            text: asString(button2.text, fallback.button2.text),
            link: asString(button2.link, fallback.button2.link),
          },
        };
      })
      .filter((slide) => slide.title && slide.src);

    return slides.length > 0 ? slides : fallbackCarouselImages;
  }, [heroSection, fallbackCarouselImages]);

  const fallbackNewsArticles: HomeNewsArticle[] = [
    {
      id: "home-news-1",
      title: "RDC-NCR ELECTS NEW CHAIRPERSON FOR 2025-2026",
      excerpt:
        "The Regional Development Council elected a new chairperson during its fourth quarter meeting...",
      date: "November 17, 2025",
      image: photo2,
      category: "Announcement",
      slug: "new-chairperson-2025",
    },
    {
      id: "home-news-2",
      title: "NCR BACKS CALL FOR DIGITAL TRANSFORMATION",
      excerpt:
        "The Infrastructure Development Committee endorsed support for digital initiatives across the region...",
      date: "November 12, 2025",
      image: photo3,
      category: "Technology",
      slug: "digital-transformation",
    },
    {
      id: "home-news-3",
      title: "QUARTERLY ECONOMIC REPORT RELEASED",
      excerpt:
        "The latest economic indicators show positive growth trends in the National Capital Region...",
      date: "November 8, 2025",
      image: photo4,
      category: "Report",
      slug: "q3-economic-report",
    },
    {
      id: "home-news-4",
      title: "METRO MANILA TRANSPORTATION PLAN UPDATE",
      excerpt:
        "New initiatives to improve public transportation and reduce congestion in Metro Manila...",
      date: "November 5, 2025",
      image: photo5,
      category: "Infrastructure",
      slug: "transportation-plan-update",
    },
  ];

  const newsArticles =
    cmsNewsArticles.length > 0 ? cmsNewsArticles : fallbackNewsArticles;

  const fallbackDevelopmentPlans: DocCard[] = [
    {
      title: "Metro Manila Greenprint 2030",
      category: "Sustainability Framework",
      icon: <FaLeaf className="w-8 h-8 text-green-500" />,
      link: "/publications?category=greenprint",
    },
    {
      title: "Regional Development Plan",
      category: "Comprehensive Plan",
      icon: <FaFileAlt className="w-8 h-8 text-gray-700" />,
      link: "/publications?category=rdp",
    },
    {
      title: "SDG Catch-up Plan",
      category: "Development Goals",
      icon: <FaBullseye className="w-8 h-8 text-indigo-600" />,
      link: "/publications?category=sdg",
    },
  ];

  const fallbackInvestmentProgramming: DocCard[] = [
    {
      title: "Regional Development Investment Program",
      category: "Investment Portfolio",
      icon: <FaChartLine className="w-8 h-8 text-green-600" />,
      link: "/publications?category=rdip",
      quickLinks: [
        { label: "RDIP DOCUMENTS", link: "/publications?category=rdip" },
        { label: "RDIP DASHBOARD", link: "/Projects" },
      ],
    },
  ];

  const fallbackMonitoringEvaluation: DocCard[] = [
    {
      title: "Regional Development Report",
      category: "Annual Report",
      icon: <FaChartBar className="w-8 h-8 text-purple-600" />,
      link: "/publications?category=rdr",
    },
    {
      title: "Regional Project Monitoring and Evaluation System",
      category: "Monitoring System",
      icon: <FaClipboardList className="w-8 h-8 text-purple-500" />,
      link: "/publications?category=rpmes",
    },
  ];

  const developmentPlansSection = getHomeSection(
    homeCmsPage,
    "development-plans",
  );
  const investmentProgrammingSection = getHomeSection(
    homeCmsPage,
    "investment-programming",
  );
  const monitoringEvaluationSection = getHomeSection(
    homeCmsPage,
    "monitoring-evaluation",
  );
  const dashboardSection = getHomeSection(homeCmsPage, "dashboard-teaser");
  const latestMediaSection = getHomeSection(homeCmsPage, "latest-media");
  const upcomingEventsSection = getHomeSection(homeCmsPage, "upcoming-events");

  const developmentPlansTitle = asString(
    developmentPlansSection?.title,
    "Development Plans and Frameworks",
  );
  const investmentProgrammingTitle = asString(
    investmentProgrammingSection?.title,
    "Investment Programming",
  );
  const monitoringEvaluationTitle = asString(
    monitoringEvaluationSection?.title,
    "Monitoring and Evaluation",
  );
  const dashboardTitle = asString(
    dashboardSection?.title,
    "Regional Development Dashboard",
  );
  const dashboardButtonLabel = asString(
    dashboardSection?.buttonLabel,
    "View Full Dashboard ->",
  );
  const dashboardButtonLink = asString(
    dashboardSection?.buttonLink,
    "/Projects",
  );
  const latestMediaTitle = asString(
    latestMediaSection?.title,
    "Latest Media Releases",
  );
  const latestMediaViewAllLabel = asString(
    latestMediaSection?.viewAllLabel,
    "View all ->",
  );
  const latestMediaViewAllLink = asString(
    latestMediaSection?.viewAllLink,
    "/news",
  );
  const upcomingEventsTitle = asString(
    upcomingEventsSection?.title,
    "Upcoming Events",
  );
  const upcomingEventsSubtitle = asString(
    upcomingEventsSection?.subtitle,
    "Calendar & Meetings",
  );
  const upcomingEventsButtonLabel = asString(
    upcomingEventsSection?.buttonLabel,
    "View Full Calendar",
  );
  const calendarTitle = asString(
    upcomingEventsSection?.calendarTitle,
    "Public Events and Meetings",
  );
  const calendarSubtitle = asString(
    upcomingEventsSection?.calendarSubtitle,
    "Published schedules from the RDC-NCR public website.",
  );

  const developmentPlans = mapCmsDocItems(
    developmentPlansSection,
    fallbackDevelopmentPlans,
  );
  const investmentProgramming = mapCmsDocItems(
    investmentProgrammingSection,
    fallbackInvestmentProgramming,
  );
  const monitoringEvaluation = mapCmsDocItems(
    monitoringEvaluationSection,
    fallbackMonitoringEvaluation,
  );

  const formatMoneyCompact = (n: number) => {
    const value = Number(n || 0);
    if (!Number.isFinite(value)) return "PHP 0";
    if (value >= 1000000000) return `PHP ${(value / 1000000000).toFixed(1)}B`;
    if (value >= 1000000) return `PHP ${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `PHP ${(value / 1000).toFixed(1)}K`;
    return `PHP ${Math.round(value).toLocaleString("en-US")}`;
  };

  const canonicalStatus = (raw: string) => {
    const s = String(raw || "").trim();
    if (!s) return "Unspecified";
    const key = s.toLowerCase();
    const map: Record<string, string> = {
      completed: "Completed",
      ongoing: "Ongoing",
      new: "New",
      updated: "Updated",
      discontinued: "Discontinued",
      dropped: "Dropped",
      "not implemented": "Not Implemented",
      "n/a": "N/A",
      na: "N/A",
      unspecified: "Unspecified",
    };
    return map[key] || s;
  };

  const statusCount = useCallback(
    (label: string) => {
      const by = publicStats?.by_status || {};
      const target = canonicalStatus(label).toLowerCase();
      let total = 0;
      Object.entries(by).forEach(([k, v]) => {
        if (canonicalStatus(k).toLowerCase() === target)
          total += Number(v || 0);
      });
      return total;
    },
    [publicStats?.by_status],
  );

  const dashboardStats = useMemo(() => {
    const ongoing = statusCount("Ongoing");
    const completed = statusCount("Completed");
    const totalBudget = Number(publicStats?.total_budget || 0);
    const agencies = Object.keys(publicStats?.by_agency || {}).length;
    return [
      { label: "Ongoing Projects", value: String(ongoing) },
      { label: "Completed Projects", value: String(completed) },
      { label: "Total Investment", value: formatMoneyCompact(totalBudget) },
      { label: "Agencies Covered", value: String(agencies) },
    ];
  }, [publicStats, statusCount]);

  const projectStatusData = useMemo(() => {
    const by = (publicStats?.by_status || {}) as Record<string, number>;
    const entries = Object.entries(by).map(([k, v]) => ({
      status: canonicalStatus(k),
      count: Number(v || 0),
    }));
    entries.sort((a, b) => b.count - a.count);

    const colorOf = (s: string) => {
      switch (canonicalStatus(s)) {
        case "Completed":
          return "bg-green-500";
        case "Ongoing":
          return "bg-yellow-500";
        case "New":
          return "bg-blue-500";
        case "Updated":
          return "bg-indigo-500";
        default:
          return "bg-slate-500";
      }
    };

    return entries.slice(0, 5).map((e) => ({
      status: e.status,
      count: e.count,
      color: colorOf(e.status),
    }));
  }, [publicStats]);

  const investmentData = useMemo(() => {
    const by = (publicStats?.by_agency || {}) as Record<string, number>;
    const total = Math.max(
      1,
      Object.values(by).reduce((s, n) => s + Number(n || 0), 0),
    );
    const top = Object.entries(by)
      .map(([k, v]) => ({ sector: k, count: Number(v || 0) }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    return top.map((t) => ({
      sector: t.sector,
      amount: `${t.count} project(s)`,
      percentage: Math.round((t.count / total) * 100),
    }));
  }, [publicStats]);

  const timelineData = useMemo(() => {
    const byYear = (publicStats?.by_year || {}) as Record<string, number>;
    const years = Object.keys(byYear)
      .map((y) => Number(y))
      .filter((y) => Number.isFinite(y))
      .sort((a, b) => a - b);
    const last = years.slice(-6);
    return last.map((y) => ({
      quarter: String(y),
      projects: Number(byYear[String(y)] || 0),
    }));
  }, [publicStats]);

  useEffect(() => {
    let cancelled = false;

    const loadHomeCmsPage = async () => {
      try {
        const page = await cmsApi.getPublicPage("home");
        if (!cancelled) setHomeCmsPage(page);
      } catch (error) {
        console.error(error);
        if (!cancelled) setHomeCmsPage(null);
      }
    };

    loadHomeCmsPage();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadPublicStats = async () => {
      try {
        setPublicStatsError("");
        const st = await getPublicProjectsStats({ cacheBust: true });
        if (!cancelled) setPublicStats(st);
      } catch (err: unknown) {
        try {
          const list = await getPublicProjects({
            limit: 500,
            offset: 0,
            cacheBust: true,
          });
          if (!cancelled) {
            setPublicStats(buildStatsFromProjects(list));
            setPublicStatsError("");
          }
        } catch (fallbackErr: unknown) {
          if (!cancelled) {
            const msg =
              fallbackErr instanceof Error
                ? fallbackErr.message
                : String(fallbackErr || err);
            setPublicStatsError(msg || "Failed to load dashboard stats.");
          }
        }
      }
    };

    loadPublicStats();
    const timer = window.setInterval(loadPublicStats, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [buildStatsFromProjects]);

  useEffect(() => {
    let cancelled = false;
    const loadCmsNews = async () => {
      try {
        const rows = await cmsApi.listPublicNews(4);
        if (!cancelled) {
          setCmsNewsArticles(rows.map(mapHomeArticle));
        }
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          setCmsNewsArticles([]);
        }
      }
    };
    loadCmsNews();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (isPaused) return;

    const timer = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % carouselImages.length);
    }, 5000);

    return () => clearInterval(timer);
  }, [isPaused, carouselImages.length]);

  useEffect(() => {
    let cancelled = false;

    const loadEvents = async () => {
      try {
        setEventsLoading(true);
        setEventsError("");
        const fullRows = await getPublicEvents({
          limit: 50,
          includePast: true,
        });
        const displayRows = sortEventsForDisplay(fullRows);
        if (!cancelled) {
          setUpcomingEvents(displayRows.slice(0, HOME_EVENT_PREVIEW_LIMIT));
          setCalendarEvents(displayRows);
        }
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          setUpcomingEvents([]);
          setCalendarEvents([]);
          setEventsError("Events calendar is temporarily unavailable.");
        }
      } finally {
        if (!cancelled) setEventsLoading(false);
      }
    };

    loadEvents();
    const timer = window.setInterval(loadEvents, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const eventTone = (type: string) => {
    if (type === "meeting") return "bg-blue-100 text-blue-700";
    if (type === "forum" || type === "consultation")
      return "bg-green-100 text-green-700";
    if (type === "deadline") return "bg-amber-100 text-amber-700";
    return "bg-purple-100 text-purple-700";
  };

  const eventPillTone = (type: string) => {
    if (type === "meeting") return "bg-blue-50 text-blue-600";
    if (type === "forum" || type === "consultation")
      return "bg-green-50 text-green-600";
    if (type === "deadline") return "bg-amber-50 text-amber-700";
    return "bg-purple-50 text-purple-600";
  };

  const filteredCalendarEvents = useMemo(
    () =>
      calendarEvents.filter((event) =>
        calendarFilter === "all" ? true : event.event_type === calendarFilter,
      ),
    [calendarEvents, calendarFilter],
  );

  const remainingEventCount = Math.max(
    0,
    calendarEvents.length - upcomingEvents.length,
  );

  const goToSlide = (index: number) => {
    setCurrentSlide(index);
  };

  const nextSlide = () => {
    setCurrentSlide((prev) => (prev + 1) % carouselImages.length);
  };

  const prevSlide = () => {
    setCurrentSlide(
      (prev) => (prev - 1 + carouselImages.length) % carouselImages.length,
    );
  };

  const handleDocumentClick = (link: string) => {
    navigate(link);
  };

  type DocCard = {
    title: string;
    link: string;
    icon?: React.ReactNode;
    category?: string;
  };

  const renderDocumentCard = (doc: DocCard) => (
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

  type StatProps = {
    label: string;
    value: string;
    change?: string;
    trend?: "up" | "down";
  };

  const StatCard = ({ label, value, change, trend }: StatProps) => (
    <div className="bg-gray-800 rounded-xl p-5">
      <div className="text-3xl font-bold text-white mb-2">{value}</div>
      <div className="text-sm text-gray-300 mb-3">{label}</div>
      {change ? (
        <div
          className={`text-sm ${
            trend === "down" ? "text-red-400" : "text-green-400"
          } flex items-center gap-1`}
        >
          <span>{change}</span>
          <svg
            className={`w-4 h-4 ${
              trend === "down" ? "text-red-400" : "text-green-400"
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            {trend === "down" ? (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            ) : (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 15l7-7 7 7"
              />
            )}
          </svg>
        </div>
      ) : null}
    </div>
  );

  const lastUpdatedLabel = useMemo(() => {
    const raw = publicStats?.last_updated_at;
    if (!raw) return "N/A";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return "N/A";
    const now = new Date();
    const sameDay =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    const time = d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
    return sameDay ? `Today, ${time}` : d.toLocaleString("en-US");
  }, [publicStats?.last_updated_at]);

  const statusTotal = useMemo(() => {
    const sum = (projectStatusData || []).reduce(
      (s: number, i: { count: number }) => s + Number(i.count || 0),
      0,
    );
    return Math.max(1, sum);
  }, [projectStatusData]);

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
                      to={slide.button1.link}
                      className="bg-white text-green-800 hover:bg-gray-100 px-6 py-3 rounded-lg font-semibold text-lg shadow-lg hover:shadow-xl transition-all duration-300"
                    >
                      {slide.button1.text}
                    </Link>
                    <Link
                      to={slide.button2.link}
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
                <h2 className="text-xl font-bold">{developmentPlansTitle}</h2>
              </div>
              <div className="p-5 space-y-5">
                {developmentPlans.map(renderDocumentCard)}
              </div>
            </div>

            {/* Investment Programming */}
            <div className="bg-white rounded-xl shadow-md overflow-hidden">
              <div className="bg-gradient-to-r from-green-600 to-green-700 text-white px-6 py-4">
                <h2 className="text-xl font-bold">
                  {investmentProgrammingTitle}
                </h2>
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

                    {(doc.quickLinks?.length ?? 0) > 0 ? (
                      <div className="border-t pt-5">
                        <h5 className="font-semibold text-gray-700 mb-3">
                          Quick Access:
                        </h5>
                        <div className="space-y-2">
                          {(doc.quickLinks || []).map((quickLink, idx) => (
                            <div
                              key={idx}
                              className="flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors group cursor-pointer"
                              onClick={() =>
                                handleDocumentClick(quickLink.link)
                              }
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
                    ) : null}
                  </div>
                ))}
              </div>
            </div>

            {/* Monitoring and Evaluation */}
            <div className="bg-white rounded-xl shadow-md overflow-hidden">
              <div className="bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-4">
                <h2 className="text-xl font-bold">
                  {monitoringEvaluationTitle}
                </h2>
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
                <h2 className="text-2xl font-bold">{dashboardTitle}</h2>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-300">
                    Last updated: {lastUpdatedLabel}
                  </span>
                  <Link
                    to={dashboardButtonLink}
                    className="bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors"
                  >
                    {dashboardButtonLabel}
                  </Link>
                </div>
              </div>
            </div>

            <div className="p-6">
              {publicStatsError ? (
                <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {publicStatsError}
                </div>
              ) : null}

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
                              style={{
                                width: `${(item.count / statusTotal) * 100}%`,
                              }}
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
                        ...timelineData.map((d) => d.projects),
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
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-3">
          {/* Latest Media Releases */}
          <div className="lg:col-span-2">
            <section className="overflow-hidden rounded-xl bg-white shadow-md">
              <div className="bg-gray-800 text-white px-5 py-3">
                <div className="flex justify-between items-center">
                  <h2 className="text-xl font-bold">{latestMediaTitle}</h2>
                  <Link
                    to={latestMediaViewAllLink}
                    className="text-xs text-blue-300 hover:text-white transition-colors"
                  >
                    {latestMediaViewAllLabel}
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
                            onError={(event) => {
                              event.currentTarget.src = photo2;
                            }}
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
                            to={`/news/${article.slug}`}
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
                <h3 className="text-lg font-bold">{upcomingEventsTitle}</h3>
                <p className="text-sm opacity-90 mt-0.5">
                  {upcomingEventsSubtitle}
                </p>
              </div>
              <div className="p-5">
                {eventsLoading ? (
                  <div className="space-y-4">
                    {[1, 2, 3].map((item) => (
                      <div
                        key={item}
                        className="h-24 animate-pulse rounded-lg bg-slate-100"
                      />
                    ))}
                  </div>
                ) : eventsError ? (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                    Events are temporarily unavailable.
                  </div>
                ) : upcomingEvents.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-600">
                    No public events are posted yet.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {upcomingEvents.map((event) => {
                      const timing = getEventTiming(event);
                      return (
                        <div
                          key={event.id}
                          className="flex items-start gap-3 p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors"
                        >
                          <div className="flex-shrink-0">
                            <div
                              className={`${eventTone(event.event_type)} p-3 rounded-lg text-center min-w-[60px]`}
                            >
                              <div className="text-lg font-bold">
                                {event.day}
                              </div>
                              <div className="text-xs font-semibold">
                                {event.month}
                              </div>
                            </div>
                          </div>
                          <div className="min-w-0 flex-1">
                            <h4 className="font-bold text-gray-800 text-sm mb-1 line-clamp-2">
                              {event.title}
                            </h4>
                            <p className="text-xs text-gray-600">
                              <span className="font-medium">{event.time}</span>
                              <span className="px-1.5">-</span>
                              {event.location ||
                                (event.is_virtual
                                  ? "Virtual"
                                  : "Location to be announced")}
                            </p>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <span
                                className={`text-xs px-2 py-1 rounded-full ${eventPillTone(event.event_type)}`}
                              >
                                {event.event_type}
                              </span>
                              <span
                                className={`text-xs px-2 py-1 rounded-full font-semibold ${timing.className}`}
                              >
                                {timing.label}
                              </span>
                            </div>
                            <p
                              className={`mt-2 rounded-md border px-2 py-1.5 text-xs font-medium leading-5 ${timing.messageClassName || "border-slate-200 bg-slate-50 text-slate-600"}`}
                            >
                              {timing.message}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
                <div className="mt-6 pt-4 border-t">
                  {remainingEventCount > 0 && (
                    <div className="mb-3 rounded-lg border border-purple-100 bg-purple-50 px-3 py-2 text-center text-xs font-medium text-purple-700">
                      {remainingEventCount} more event
                      {remainingEventCount === 1 ? "" : "s"} available in the
                      full calendar.
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => setShowCalendar(true)}
                    className="w-full text-center block bg-purple-600 hover:bg-purple-700 text-white font-medium text-sm py-3 rounded-lg transition-colors"
                  >
                    {upcomingEventsButtonLabel}
                  </button>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </main>
      {showCalendar && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <button
            type="button"
            className="absolute inset-0 h-full w-full bg-slate-950/60"
            aria-label="Close calendar"
            onClick={() => setShowCalendar(false)}
          />
          <section className="relative ml-auto flex h-full w-full max-w-4xl flex-col bg-white shadow-2xl">
            <div className="border-b border-slate-200 bg-gradient-to-r from-purple-700 to-fuchsia-600 px-5 py-5 text-white">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.25em] text-purple-100">
                    RDC-NCR Calendar
                  </p>
                  <h2 className="mt-1 text-2xl font-black">{calendarTitle}</h2>
                  <p className="mt-1 text-sm text-purple-50">
                    {calendarSubtitle}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowCalendar(false)}
                  className="rounded-full bg-white/15 px-4 py-2 text-sm font-semibold text-white hover:bg-white/25"
                >
                  Close
                </button>
              </div>
            </div>
            <div className="border-b border-slate-200 bg-white px-5 py-4">
              <label className="block text-sm font-semibold text-slate-700">
                Filter by event type
              </label>
              <select
                value={calendarFilter}
                onChange={(event) => setCalendarFilter(event.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm sm:max-w-xs"
              >
                <option value="all">All events</option>
                <option value="meeting">Meetings</option>
                <option value="forum">Forums</option>
                <option value="consultation">Consultations</option>
                <option value="deadline">Deadlines</option>
                <option value="summit">Summits</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="flex-1 overflow-y-auto bg-slate-50 p-5">
              {filteredCalendarEvents.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">
                  No events match this filter.
                </div>
              ) : (
                <div className="grid gap-4">
                  {filteredCalendarEvents.map((event) => {
                    const timing = getEventTiming(event);
                    return (
                      <article
                        key={event.id}
                        className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
                      >
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                          <div
                            className={`${eventTone(event.event_type)} rounded-2xl px-4 py-3 text-center sm:w-24`}
                          >
                            <div className="text-2xl font-black">
                              {event.day}
                            </div>
                            <div className="text-xs font-bold uppercase tracking-wide">
                              {event.month}
                            </div>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${eventPillTone(event.event_type)}`}
                              >
                                {event.event_type}
                              </span>
                              <span
                                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${timing.className}`}
                              >
                                {timing.label}
                              </span>
                              <span className="text-xs text-slate-500">
                                {event.time}
                                {event.end_time ? ` - ${event.end_time}` : ""}
                              </span>
                            </div>
                            <h3 className="mt-2 text-lg font-black text-slate-900">
                              {event.title}
                            </h3>
                            <p className="mt-1 text-sm font-medium text-slate-600">
                              {event.location ||
                                (event.is_virtual
                                  ? "Virtual event"
                                  : "Location to be announced")}
                            </p>
                            <p
                              className={`mt-3 rounded-lg border px-3 py-2 text-sm font-semibold ${timing.messageClassName || "border-slate-200 bg-slate-50 text-slate-600"}`}
                            >
                              {timing.message}
                            </p>
                            {event.description && (
                              <p className="mt-3 text-sm leading-6 text-slate-600">
                                {event.description}
                              </p>
                            )}
                            {event.meeting_link && (
                              <a
                                href={event.meeting_link}
                                target="_blank"
                                rel="noreferrer"
                                className="mt-3 inline-flex rounded-full bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-700"
                              >
                                Open event link
                              </a>
                            )}
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
};

export default Home;
