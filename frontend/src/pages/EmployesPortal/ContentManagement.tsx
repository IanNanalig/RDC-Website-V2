import PortalLayout from "../../components/portal/PortalLayout";
import PublicEventsManager from "../../components/portal/PublicEventsManager";

type PortalUser = {
  username?: string;
  full_name?: string;
  role?: "admin" | "validator" | "employee" | "content_editor";
};

const ContentManagement = () => {
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
      <PublicEventsManager mode={role === "admin" ? "admin" : "editor"} />
    </PortalLayout>
  );
};

export default ContentManagement;
