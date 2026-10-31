import { Link, useLocation } from "react-router-dom";

const tabs = [
  { label: "Projects", to: "/admin/projects", active: (path: string) => path === "/admin/projects" },
  { label: "Update Older Forms", to: "/admin/projects/update-forms", active: (path: string) => path.startsWith("/admin/projects/update-forms") },
  { label: "Project Update Period", to: "/admin/project-update-period", active: (path: string) => path.startsWith("/admin/project-update-period") },
  { label: "Concern Reports", to: "/admin/project-concerns", active: (path: string) => path.startsWith("/admin/project-concerns") },
];

export default function ProjectManagementTabs() {
  const location = useLocation();

  return (
    <nav className="portal-card mb-4" aria-label="Project management sections">
      <div className="portal-card-body flex flex-wrap gap-2" role="tablist">
        {tabs.map((tab) => {
          const selected = tab.active(location.pathname);
          return (
            <Link
              key={tab.to}
              to={tab.to}
              role="tab"
              aria-selected={selected}
              aria-current={selected ? "page" : undefined}
              className={`portal-btn ${selected ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
