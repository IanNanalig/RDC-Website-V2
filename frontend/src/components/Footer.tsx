import React from "react";
// Link not used here
import rdcLogo from "../assets/optimized/rdc-logo-256.webp";
import api from "../services/api";
import cmsApi, { resolveCmsMediaUrl } from "../services/cmsApi";

interface FooterProps {
  showVisitorCount?: boolean;
}

const Footer: React.FC<FooterProps> = ({ showVisitorCount = true }) => {
  const [visitorCount, setVisitorCount] = React.useState(0);
  const [pageViews, setPageViews] = React.useState(0);
  const [averageDailyViews, setAverageDailyViews] = React.useState(0);
  const [todayViews, setTodayViews] = React.useState(0);
  const [siteSettings, setSiteSettings] = React.useState<Record<string, unknown>>({});

  const logoSetting = siteSettings["site-logo"] && typeof siteSettings["site-logo"] === "object"
    ? siteSettings["site-logo"] as Record<string, unknown>
    : {};
  const contactSetting = siteSettings["contact-details"] && typeof siteSettings["contact-details"] === "object"
    ? siteSettings["contact-details"] as Record<string, unknown>
    : {};
  const officeAddress = typeof siteSettings["office-address"] === "string" && siteSettings["office-address"]
    ? String(siteSettings["office-address"])
    : "16th Floor, MMDA Head Office, Doña Julia Vargas Avenue corner Molave St., Barangay Ugong, Pasig City";
  const contactEmail = typeof contactSetting.email === "string" && contactSetting.email ? contactSetting.email : "rdc.ncr@mmda.gov.ph";
  const contactPhone = typeof contactSetting.phone === "string" && contactSetting.phone ? contactSetting.phone : "8898-4200 local 1604-1606";
  const footerText = typeof siteSettings["footer-text"] === "string" && siteSettings["footer-text"]
    ? String(siteSettings["footer-text"])
    : "Planning and coordinating sustainable development for Metro Manila.";

  // Google Maps URL for the address
  const googleMapsUrl =
    `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(officeAddress)}`;

  // Email URL
  const emailUrl = `mailto:${contactEmail}`;

  React.useEffect(() => {
    let mounted = true;
    cmsApi.getPublicSettings().then((data) => {
      if (mounted && data && typeof data === "object") setSiteSettings(data as Record<string, unknown>);
    }).catch(() => undefined);
    return () => { mounted = false; };
  }, []);

  React.useEffect(() => {
    let mounted = true;
    const register = async () => {
      try {
        // register visit and get updated counts
        const data = await api.post("analytics/", { action: "visit" });
        if (!mounted) return;
        setPageViews(Number(data.pageviews || 0));
        setAverageDailyViews(Number(data.avg_daily || 0));
        setTodayViews(Number(data.today || 0));
        setVisitorCount(Number(data.total_visitors || 0));
        return;
      } catch {
        // fallback: try to GET analytics without registering visit
      }

      try {
        const data = await api.get("analytics/");
        if (!mounted) return;
        setPageViews(Number(data.pageviews || 0));
        setAverageDailyViews(Number(data.avg_daily || 0));
        setTodayViews(Number(data.today || 0));
        setVisitorCount(Number(data.total_visitors || 0));
      } catch {
        // keep defaults on error
      }
    };
    let idleId: number;
    if ("requestIdleCallback" in window) idleId = window.requestIdleCallback(register, { timeout: 2500 });
    else idleId = window.setTimeout(register, 0);
    return () => {
      mounted = false;
      if ("cancelIdleCallback" in window) window.cancelIdleCallback(idleId);
      else window.clearTimeout(idleId);
    };
  }, []);

  return (
    <footer className="bg-gray-900 text-white pt-8 pb-6">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Logo and Description */}
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              {/* RDC Logo without background */}
              <img
                src={typeof logoSetting.url === "string" && logoSetting.url ? resolveCmsMediaUrl(logoSetting.url) : rdcLogo}
                alt={typeof logoSetting.alt === "string" && logoSetting.alt ? logoSetting.alt : "RDC-NCR Logo"}
                width={256}
                height={256}
                loading="lazy"
                decoding="async"
                className="w-24 h-24 object-contain"
              />
              <div>
                <h2 className="text-lg font-bold">
                  Regional Development Council
                </h2>
                <p className="text-sm font-semibold text-blue-300">
                  National Capital Region
                </p>
              </div>
            </div>

            <p className="text-xs text-gray-300">
              {footerText}
            </p>

            {/* Connect with us */}
            <div className="pt-2">
              <p className="text-sm font-medium mb-2">Connect with us:</p>
              <div className="flex gap-2">
                <a
                  href="https://www.facebook.com/RDCNCR"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs transition-colors"
                >
                  Facebook
                </a>
                <a
                  href="https://mmda.gov.ph"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-xs transition-colors"
                >
                  MMDA
                </a>
              </div>
            </div>
          </div>

          {/* Contact Information */}
          <div>
            <h3 className="text-sm font-bold mb-4 pb-2 border-b border-gray-700">
              CONTACT INFORMATION
            </h3>
            <div className="space-y-3 text-xs">
              <div>
                <p className="font-medium mb-1">Address:</p>
                <a
                  href={googleMapsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-300 hover:text-blue-200 hover:underline transition-colors flex items-start gap-1"
                >
                  <svg
                    className="w-3 h-3 mt-0.5 flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                  <span>
                    {officeAddress}
                  </span>
                </a>
              </div>

              <div>
                <p className="font-medium mb-1">Telephone No.:</p>
                <p className="text-gray-300">{contactPhone}</p>
              </div>

              <div>
                <p className="font-medium mb-1">E-mail Address:</p>
                <a
                  href={emailUrl}
                  className="text-blue-300 hover:text-blue-200 hover:underline transition-colors flex items-center gap-1"
                >
                  <svg
                    className="w-3 h-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                    />
                  </svg>
                  <span>{contactEmail}</span>
                </a>
              </div>
            </div>
          </div>

          {/* Analytics Section */}
          <div className="col-span-1 md:col-span-2">
            <h3 className="text-sm font-bold mb-4 pb-2 border-b border-gray-700">
              WEBSITE ANALYTICS
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-400">
                  {pageViews.toLocaleString()}
                </div>
                <div className="text-xs text-gray-300 mt-1">Pageviews</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-green-400">
                  {averageDailyViews.toLocaleString()}
                </div>
                <div className="text-xs text-gray-300 mt-1">
                  Avg Daily Views
                </div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-purple-400">
                  {todayViews.toLocaleString()}
                </div>
                <div className="text-xs text-gray-300 mt-1">Today</div>
              </div>
            </div>

            {/* Visitor Counter */}
            {showVisitorCount && (
              <div className="mt-6 pt-4 border-t border-gray-700">
                <div className="text-center">
                  <div className="text-4xl font-bold text-yellow-400">
                    {visitorCount.toLocaleString()}
                  </div>
                  <div className="text-sm text-gray-300">
                    Total Website Visitors
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Copyright */}
        <div className="mt-8 pt-6 border-t border-gray-800 text-center">
          <div className="text-xs text-gray-400">
            <p>
              &copy; {new Date().getFullYear()} Regional Development Council -
              National Capital Region. All rights reserved.
            </p>
            <p className="mt-1">Republic of the Philippines</p>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
