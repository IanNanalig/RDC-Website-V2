import { useState } from "react";
import PortalLayout from "../../components/portal/PortalLayout";
import CmsManager from "../../components/portal/CmsManager";
import PublicEventsManager from "../../components/portal/PublicEventsManager";

type PortalUser = {
  username?: string;
  full_name?: string;
  role?: "admin" | "validator" | "employee" | "content_editor";
};

const ContentManagement = () => {
  const [activeTab, setActiveTab] = useState<"cms" | "events">("cms");
  const userRaw = localStorage.getItem("user");
  const user: PortalUser = userRaw ? JSON.parse(userRaw) : {};
  const role = user.role === "content_editor" ? "content_editor" : "admin";
  const displayName = user.full_name || user.username || "Content User";

  return (
    <PortalLayout
      title="Content Management"
      subtitle="Draft, review, and publish public website content"
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
            Website CMS
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

      {activeTab === "cms" ? (
        <CmsManager mode={role === "admin" ? "admin" : "editor"} />
      ) : (
        <PublicEventsManager mode={role === "admin" ? "admin" : "editor"} />
      )}
    </PortalLayout>
  );
};

export default ContentManagement;
