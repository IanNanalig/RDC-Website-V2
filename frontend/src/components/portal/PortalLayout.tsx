import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEncodingWindow } from "../../hooks/useEncodingWindow";
import { api } from "../../services/api";

type Role = "admin" | "validator" | "employee" | "content_editor";

type Props = {
  title: string;
  subtitle?: string;
  role: Role;
  userName: string;
  children: React.ReactNode;
  topActions?: React.ReactNode;
};

type NavItem = { label: string; to: string };

type StoredPortalUser = {
  agency?: string | null;
};

type PortalNotification = {
  id: number;
  title: string;
  message: string;
  link_path?: string;
  read_at?: string | null;
  is_read?: boolean;
  created_at?: string;
  project_title?: string;
};

const roleLabel: Record<Role, string> = {
  admin: "Administrator",
  validator: "Validator",
  employee: "Contributor",
  content_editor: "Content Editor",
};

const roleAccent: Record<Role, string> = {
  admin: "portal-chip-admin",
  validator: "portal-chip-validator",
  employee: "portal-chip-employee",
  content_editor: "portal-chip-validator",
};

const navByRole: Record<Role, NavItem[]> = {
  admin: [
    { label: "Dashboard", to: "/admin/dashboard" },
    { label: "Projects", to: "/admin/projects" },
    { label: "Validator Tracker", to: "/admin/validator-diffs" },
    { label: "Content Management", to: "/admin/content" },
    { label: "Users & Access", to: "/admin/users" },
  ],
  validator: [
    { label: "Dashboard", to: "/validator/dashboard" },
    { label: "Review Queue", to: "/validator/projects" },
    { label: "Reviewed & Endorsed", to: "/validator/projects/history" },
  ],
  employee: [
    { label: "Dashboard", to: "/employee/dashboard" },
    { label: "My Projects", to: "/employee/projects" },
    { label: "New Submission", to: "/employee/projects/new" },
  ],
  content_editor: [
    { label: "Content Management", to: "/content/dashboard" },
  ],
};

const iconFor = (label: string) => {
  const common = "w-4 h-4";
  if (label.toLowerCase().includes("dashboard")) {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M3 13h8V3H3zM13 21h8v-6h-8zM13 3v8h8V3zM3 21h8v-6H3z" />
      </svg>
    );
  }
  if (label.toLowerCase().includes("project")) {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M9 4h11v16H4V9z" />
        <path d="M9 4v5H4" />
      </svg>
    );
  }
  if (label.toLowerCase().includes("user") || label.toLowerCase().includes("access")) {
    return (
      <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M16 11a4 4 0 1 0-8 0 4 4 0 0 0 8 0Z" />
        <path d="M3 20a7 7 0 0 1 14 0" />
      </svg>
    );
  }
  return (
    <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
};

const PortalLayout: React.FC<Props> = ({ title, subtitle, role, userName, children, topActions }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState<PortalNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const location = useLocation();
  const navigate = useNavigate();
  const navItems = useMemo(() => navByRole[role], [role]);
  const encodingWindow = useEncodingWindow(role === "employee");
  const workspaceLabel = useMemo(() => {
    try {
      const raw = localStorage.getItem("user");
      if (!raw) return "NCR Workspace";
      const user = JSON.parse(raw) as StoredPortalUser;
      const agency = String(user.agency || "").trim();
      return agency ? `${agency} Workspace` : "NCR Workspace";
    } catch {
      return "NCR Workspace";
    }
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const loadNotifications = useCallback(async () => {
    try {
      const [items, unread] = await Promise.all([
        api.get("notifications/?limit=10"),
        api.get("notifications/unread-count/"),
      ]);
      setNotifications(Array.isArray(items) ? items : []);
      setUnreadCount(Number(unread?.unread_count || 0));
    } catch {
      setNotifications([]);
      setUnreadCount(0);
    }
  }, []);

  useEffect(() => {
    loadNotifications();
    const id = window.setInterval(loadNotifications, 15000);
    const onStorage = (event: StorageEvent) => {
      if (event.key === "projects_last_update") loadNotifications();
    };
    window.addEventListener("storage", onStorage);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("storage", onStorage);
    };
  }, [loadNotifications]);

  useEffect(() => {
    setNotificationsOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 768px)");
    const onChange = (event: MediaQueryListEvent) => {
      if (event.matches) setMobileOpen(false);
    };
    if (media.matches) setMobileOpen(false);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const logout = () => {
    localStorage.removeItem("user");
    localStorage.removeItem("isLoggedIn");
    localStorage.removeItem("username");
    localStorage.removeItem("token");
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    navigate("/login");
  };

  const markRead = async (notification: PortalNotification) => {
    if (!notification.is_read && !notification.read_at) {
      try {
        await api.post(`notifications/${notification.id}/mark-read/`, {});
      } catch {
        // Navigation should not fail because a read receipt failed.
      }
    }
    await loadNotifications();
  };

  const markAllRead = async () => {
    try {
      await api.post("notifications/mark-all-read/", {});
      await loadNotifications();
    } catch {
      // Keep the dropdown usable even if the server rejects the action.
    }
  };

  return (
    <div className="portal-bg min-h-screen">
      <div className="portal-shell w-full mx-auto p-2 md:p-4 xl:p-5">
        {mobileOpen && <div className="fixed inset-0 bg-black/30 z-20 md:hidden" onClick={() => setMobileOpen(false)} />}
        <div className="grid grid-cols-1 md:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)] 2xl:grid-cols-[260px_minmax(0,1fr)] gap-2 md:gap-4">
          <aside
            className={`portal-sidebar fixed top-2 left-2 bottom-2 w-[84vw] max-w-[300px] z-30 overflow-y-auto ${
              mobileOpen ? "block" : "hidden"
            } md:static md:w-auto md:max-w-none md:block`}
          >
            <div className="portal-brand">
              <div className="portal-brand-dot" />
              <div>
                <p className="portal-brand-title">RDC Portal</p>
                <p className="portal-brand-sub">{workspaceLabel}</p>
              </div>
            </div>

            <p className="portal-side-label">Navigation</p>
            <nav className="space-y-1">
              {navItems.map((item) => {
                const active = location.pathname.startsWith(item.to);
                const encodingDisabled =
                  role === "employee" && item.to === "/employee/projects/new" && !encodingWindow.can_encode;
                return (
                  <Link
                    key={item.to}
                    to={encodingDisabled ? "#" : item.to}
                    aria-disabled={encodingDisabled}
                    title={encodingDisabled ? encodingWindow.message : undefined}
                    className={`portal-nav-item ${active ? "portal-nav-item-active" : ""} ${
                      encodingDisabled ? "opacity-50 cursor-not-allowed" : ""
                    }`}
                    onClick={(event) => {
                      if (encodingDisabled) event.preventDefault();
                      else setMobileOpen(false);
                    }}
                  >
                    <span className="portal-nav-icon">{iconFor(item.label)}</span>
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="mt-auto pt-6">
              <p className="portal-side-label">Account</p>
              <div className="portal-account">
                <div>
                  <p className="portal-account-name">{userName}</p>
                  <span className={`portal-chip ${roleAccent[role]}`}>{roleLabel[role]}</span>
                </div>
                <button onClick={logout} className="portal-logout-btn">
                  Logout
                </button>
              </div>
            </div>
          </aside>

          <main className="space-y-3 md:space-y-5 min-w-0">
            <header className="portal-topbar">
              <div className="flex items-center gap-2 md:gap-3 min-w-0">
                <button onClick={() => setMobileOpen((v) => !v)} className="portal-menu-btn md:hidden">
                  Menu
                </button>
                <div className="min-w-0">
                  <h1 className="portal-title">{title}</h1>
                  {subtitle && <p className="portal-subtitle">{subtitle}</p>}
                </div>
              </div>
              <div className="portal-top-actions">
                <div className="relative">
                  <button
                    type="button"
                    className="portal-btn portal-btn-ghost relative px-3"
                    title="Notifications"
                    aria-label="Notifications"
                    onClick={() => setNotificationsOpen((value) => !value)}
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
                      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                    </svg>
                    {unreadCount > 0 && (
                      <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                        {unreadCount > 9 ? "9+" : unreadCount}
                      </span>
                    )}
                  </button>
                  {notificationsOpen && (
                    <div className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-slate-200 bg-white shadow-xl">
                      <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
                        <p className="text-sm font-semibold text-slate-900">Notifications</p>
                        <button type="button" onClick={markAllRead} className="text-xs font-medium text-blue-700 hover:underline">
                          Mark all read
                        </button>
                      </div>
                      <div className="max-h-96 overflow-y-auto">
                        {notifications.length === 0 ? (
                          <p className="px-3 py-4 text-sm text-slate-500">No notifications yet.</p>
                        ) : (
                          notifications.map((notification) => {
                            const unread = !notification.is_read && !notification.read_at;
                            const body = (
                              <div className={`border-b border-slate-100 px-3 py-3 text-left last:border-b-0 ${unread ? "bg-blue-50/70" : "bg-white"}`}>
                                <div className="flex items-start gap-2">
                                  {unread && <span className="mt-1.5 h-2 w-2 rounded-full bg-blue-600" />}
                                  <div className="min-w-0 flex-1">
                                    <p className="text-sm font-semibold text-slate-900">{notification.title}</p>
                                    {notification.message && <p className="mt-1 line-clamp-2 text-xs text-slate-600">{notification.message}</p>}
                                    <p className="mt-1 text-[11px] text-slate-400">
                                      {notification.created_at ? new Date(notification.created_at).toLocaleString() : ""}
                                    </p>
                                  </div>
                                </div>
                              </div>
                            );
                            return notification.link_path ? (
                              <Link
                                key={notification.id}
                                to={notification.link_path}
                                onClick={() => markRead(notification)}
                                className="block hover:bg-slate-50"
                              >
                                {body}
                              </Link>
                            ) : (
                              <button key={notification.id} type="button" onClick={() => markRead(notification)} className="block w-full hover:bg-slate-50">
                                {body}
                              </button>
                            );
                          })
                        )}
                      </div>
                    </div>
                  )}
                </div>
                {topActions}
              </div>
            </header>

            <section>{children}</section>
          </main>
        </div>
      </div>
    </div>
  );
};

export default PortalLayout;
