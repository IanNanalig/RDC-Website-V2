import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import PortalLayout from "../../components/portal/PortalLayout";

const CmsManager = lazy(() => import("../../components/portal/CmsManager"));
const PublicEventsManager = lazy(() => import("../../components/portal/PublicEventsManager"));

type PortalUser = {
  username?: string;
  full_name?: string;
  role?: "admin" | "validator" | "employee" | "content_editor";
};

const ContentManagement = () => {
  const location = useLocation();
  const routeTab = useMemo(() => {
    const path = location.pathname.toLowerCase();
    if (path.includes("/events")) return "events";
    return "cms";
  }, [location.pathname]);
  const cmsInitialTab = useMemo(() => {
    const path = location.pathname.toLowerCase();
    if (path.includes("/news")) return "news" as const;
    if (path.includes("/forms")) return "forms" as const;
    if (path.includes("/media")) return "media" as const;
    if (path.includes("/settings")) return "settings" as const;
    if (path.includes("/revisions")) return "revisions" as const;
    if (path.includes("/review")) return "review" as const;
    if (path.includes("/ai-scoring")) return "ai" as const;
    return "pages" as const;
  }, [location.pathname]);
  const [activeTab, setActiveTab] = useState<"cms" | "events">(routeTab);
  useEffect(() => setActiveTab(routeTab), [routeTab]);
  const userRaw = localStorage.getItem("user");
  const user: PortalUser = userRaw ? JSON.parse(userRaw) : {};
  const role = user.role === "content_editor" ? "content_editor" : "admin";
  const displayName = user.full_name || user.username || "Content User";

  return (
    <PortalLayout
      title="Content Management"
      subtitle="Draft, review, and publish public content and contributor forms"
      role={role}
      userName={displayName}
    >
      <div className="portal-card mb-4">
        <div className="portal-card-body flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("cms")}
            className={`portal-btn ${activeTab === "cms" ? "portal-btn-primary" : "portal-btn-ghost"}`}
          >
            Content CMS
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("events")}
            className={`portal-btn ${activeTab === "events" ? "portal-btn-primary" : "portal-btn-ghost"}`}
          >
            Events Calendar
          </button>
        </div>
      </div>

      <Suspense fallback={<div className="portal-card p-5 text-sm text-slate-600">Loading content workspace...</div>}>
        {activeTab === "cms" ? (
          <CmsManager mode={role === "admin" ? "admin" : "editor"} initialTab={cmsInitialTab} />
        ) : (
          <PublicEventsManager mode={role === "admin" ? "admin" : "editor"} />
        )}
      </Suspense>
    </PortalLayout>
  );
};

export default ContentManagement;
