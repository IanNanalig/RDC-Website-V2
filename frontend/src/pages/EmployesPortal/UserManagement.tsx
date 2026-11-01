import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";
import RefreshButton from "../../components/portal/RefreshButton";
import { MobileSortControls, SortableTableHeader } from "../../components/portal/TableSortControls";
import { sortRows } from "../../utils/tableSort";
import { userDisplayName } from "../../utils/userDisplayName";
import type { SortDirection } from "../../utils/tableSort";
import BatchRegistrationPanel from "../../components/portal/BatchRegistrationPanel";
import AgencyManagementPanel from "../../components/portal/AgencyManagementPanel";

type UserRow = {
  id: number;
  username: string;
  first_name?: string;
  last_name?: string;
  email: string;
  role: string;
  agency?: string;
  agency_code?: string;
  is_active: boolean;
  account_state?: "pending_activation" | "active" | "disabled";
};

type AgencyCapacityOption = {
  code: string;
  name: string;
  accepting_contributors?: boolean;
  contributor_capacity?: {
    limit: number;
    active: number;
    reserved: number;
    used: number;
    available: number;
  };
};

type AccountCapacitySummary = {
  limit: number;
  active: number;
  reserved: number;
  used: number;
  available: number;
};

const userAccountState = (user: UserRow) =>
  user.account_state || (user.is_active ? "active" : "disabled");

const accountStateLabel = (user: UserRow) => {
  const state = userAccountState(user);
  if (state === "pending_activation") return "Pending Activation";
  if (state === "disabled") return "Disabled";
  return "Active";
};

const accountStateClass = (user: UserRow) => {
  const state = userAccountState(user);
  if (state === "pending_activation") return "bg-amber-100 text-amber-800";
  if (state === "disabled") return "bg-slate-100 text-slate-700";
  return "bg-emerald-100 text-emerald-700";
};

const displayRole = (role: string) => {
  if (role === "staff" || role === "employee" || role === "contributor") return "Contributor";
  if (role === "validator") return "Validator";
  if (role === "admin") return "Admin";
  if (role === "content_editor") return "Content Editor";
  if (role === "unauthenticated") return "Unauthenticated";
  return role;
};

const userRoleFilterValue = (role: string) =>
  role === "staff" || role === "employee" || role === "contributor"
    ? "contributor"
    : role;

type ChatKnowledgeGap = {
  id: number;
  question_sample: string;
  language: string;
  count: number;
  last_asked: string;
  status: "pending" | "approved" | "rejected";
  suggested_title: string;
  suggested_summary: string;
  suggested_body: string;
  suggested_tags: string[];
  matched_content_title?: string;
  reviewed_by_name?: string;
  reviewed_at?: string;
};

type ChatGapDraft = {
  title: string;
  summary: string;
  body: string;
  tags: string;
  url: string;
};

type PublicEventRow = {
  id: number;
  title: string;
  description: string;
  event_type: string;
  start_at: string;
  end_at?: string;
  day?: number;
  month?: string;
  time?: string;
  end_time?: string;
  location: string;
  is_virtual: boolean;
  meeting_link: string;
  status: "draft" | "submitted" | "published" | "rejected" | "archived";
  review_notes?: string;
  published_at?: string;
  updated_at: string;
};

type PublicEventForm = {
  id?: number;
  title: string;
  description: string;
  event_type: string;
  start_at: string;
  end_at: string;
  location: string;
  is_virtual: boolean;
  meeting_link: string;
};

type AdminUsersTab =
  | "create-account"
  | "encoding-window"
  | "agencies"
  | "system-users"
  | "system-audit-log"
  | "chatbot-learning";

type EncodingWindowState = {
  enabled: boolean;
  start_at: string;
  end_at: string;
  is_open: boolean;
  can_encode?: boolean;
  status_code: string;
  message: string;
  server_now?: string;
};

const parseTab = (value: string | null): AdminUsersTab => {
  if (
    value === "create-account" ||
    value === "encoding-window" ||
    value === "agencies" ||
    value === "system-users" ||
    value === "system-audit-log"
  )
    return value;
  return "create-account";
};

const emptyEventForm: PublicEventForm = {
  title: "",
  description: "",
  event_type: "meeting",
  start_at: "",
  end_at: "",
  location: "",
  is_virtual: false,
  meeting_link: "",
};

const UserManagement = () => {
  const navigate = useNavigate();
  const showLegacyEventsPanel =
    import.meta.env.VITE_SHOW_LEGACY_EVENTS_PANEL === "true";
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = parseTab(searchParams.get("tab"));
  useEffect(() => { if (searchParams.get("tab") === "system-audit-log") navigate("/admin/audit-log", { replace: true }); }, [navigate, searchParams]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [accountAgencies, setAccountAgencies] = useState<AgencyCapacityOption[]>([]);
  const [administratorCapacity, setAdministratorCapacity] = useState<AccountCapacitySummary | null>(null);
  const [agencyEditUser, setAgencyEditUser] = useState<UserRow | null>(null);
  const [agencyEditCode, setAgencyEditCode] = useState("");
  const [agencyEditBusy, setAgencyEditBusy] = useState(false);
  useEffect(() => {
    if (!agencyEditUser) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !agencyEditBusy) setAgencyEditUser(null);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [agencyEditBusy, agencyEditUser]);
  const [usersRefreshing, setUsersRefreshing] = useState(false);
  const [usersError, setUsersError] = useState("");
  const [userFilters, setUserFilters] = useState({
    search: "",
    agency: "",
    role: "",
    status: "",
    limit: "10",
  });
  const [userPage, setUserPage] = useState(1);
  const [userSortKey, setUserSortKey] = useState<string | null>(null);
  const [userSortDirection, setUserSortDirection] = useState<SortDirection>("asc");
  const userAgencies = useMemo(() => [...new Set(users.map((user) => user.agency?.trim() || ""))]
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: "base" })), [users]);
  const hasUsersWithoutAgency = users.some((user) => !user.agency?.trim());
  const filteredUsers = useMemo(() => users.filter((user) => {
    const search = userFilters.search.trim().toLocaleLowerCase();
    if (search && ![userDisplayName(user), user.username, user.email]
      .some((value) => String(value || "").toLocaleLowerCase().includes(search))) return false;
    if (userFilters.agency === "__none__" && user.agency?.trim()) return false;
    if (userFilters.agency && userFilters.agency !== "__none__" &&
      user.agency?.trim() !== userFilters.agency) return false;
    if (userFilters.role && userRoleFilterValue(user.role) !== userFilters.role) return false;
    if (userFilters.status && userAccountState(user) !== userFilters.status) return false;
    return true;
  }), [users, userFilters]);
  const userSortOptions = [
    { key: "username", label: "Username" },
    { key: "email", label: "Email" },
    { key: "agency", label: "Agency" },
    { key: "role", label: "Role" },
    { key: "status", label: "Status" },
  ];
  const changeUserSort = (key: string) => {
    setUserPage(1);
    if (userSortKey === key) setUserSortDirection((direction) => direction === "asc" ? "desc" : "asc");
    else { setUserSortKey(key); setUserSortDirection("asc"); }
  };
  const toggleUserSortDirection = () => {
    setUserPage(1);
    setUserSortDirection((direction) => direction === "asc" ? "desc" : "asc");
  };
  const sortedUsers = useMemo(() => sortRows(filteredUsers, userSortKey, userSortDirection, (user, key) => {
    switch (key) {
      case "username": return userDisplayName(user);
      case "email": return user.email || "";
      case "agency": return user.agency || "";
      case "role": return displayRole(user.role);
      case "status": return accountStateLabel(user);
      default: return "";
    }
  }), [filteredUsers, userSortKey, userSortDirection]);
  const userLimit = Number(userFilters.limit) || 10;
  const userPageCount = Math.max(1, Math.ceil(filteredUsers.length / userLimit));
  const currentUserPage = Math.min(userPage, userPageCount);
  const userStart = filteredUsers.length ? (currentUserPage - 1) * userLimit + 1 : 0;
  const userEnd = Math.min(currentUserPage * userLimit, filteredUsers.length);
  const visibleUsers = sortedUsers.slice((currentUserPage - 1) * userLimit, currentUserPage * userLimit);
  const updateUserFilter = (key: keyof typeof userFilters, value: string) => {
    setUserPage(1);
    setUserFilters((previous) => ({ ...previous, [key]: value }));
  };
  const clearUserFilters = () => {
    setUserPage(1);
    setUserFilters({ search: "", agency: "", role: "", status: "", limit: "10" });
  };
  useEffect(() => {
    setUserPage((page) => Math.min(page, userPageCount));
  }, [userPageCount]);
  const [chatGaps, setChatGaps] = useState<ChatKnowledgeGap[]>([]);
  const [chatGapsLoading, setChatGapsLoading] = useState(false);
  const [chatGapDrafts, setChatGapDrafts] = useState<
    Record<number, ChatGapDraft>
  >({});
  const [chatGapStatus, setChatGapStatus] = useState("pending");
  const [expandedChatGapIds, setExpandedChatGapIds] = useState<
    Record<number, boolean>
  >({});
  const [events, setEvents] = useState<PublicEventRow[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventForm, setEventForm] = useState<PublicEventForm>(emptyEventForm);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [form, setForm] = useState({
    email: "",
    role: "contributor",
  });
  const [invitationSending, setInvitationSending] = useState(false);
  const invitationInFlight = React.useRef(false);
  const [windowForm, setWindowForm] = useState({
    enabled: false,
    start_at: "",
    end_at: "",
  });
  const [windowState, setWindowState] = useState<EncodingWindowState | null>(
    null,
  );
  const userRaw = localStorage.getItem("user");
  const user = userRaw ? JSON.parse(userRaw) : { username: "admin" };
  const displayName = userDisplayName(user, "Admin");

  const labelRole = displayRole;

  const getErrorDetail = (err: unknown, fallback: string) => {
    if (err instanceof Error && err.message) {
      try {
        const parsed = JSON.parse(err.message);
        return parsed?.detail || err.message;
      } catch {
        return err.message;
      }
    }
    return fallback;
  };

  const setActiveTab = (tab: AdminUsersTab) => {
    const next = new URLSearchParams(searchParams);
    next.set("tab", tab);
    setSearchParams(next);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [usersResult, winResult, agencyResult] = await Promise.allSettled([
        api.get("admin/users/"),
        api.get("encoding-window/"),
        api.get("admin/users/batch-invitations/options/"),
      ]);
      if (usersResult.status === "fulfilled") {
        setUsers(Array.isArray(usersResult.value) ? usersResult.value : []);
        setUsersError("");
      } else {
        setUsersError("Unable to load system users. Please refresh to try again.");
      }
      if (winResult.status === "fulfilled") {
        const winRes = winResult.value;
        setWindowForm({
          enabled: Boolean(winRes?.enabled),
          start_at: winRes?.start_at || "",
          end_at: winRes?.end_at || "",
        });
        setWindowState(winRes || null);
      }
      if (agencyResult.status === "fulfilled") {
        setAccountAgencies(
          Array.isArray(agencyResult.value?.agencies)
            ? agencyResult.value.agencies
            : [],
        );
        setAdministratorCapacity(agencyResult.value?.administrator_capacity || null);
      }
    } catch (error) {
      console.error(error);
      setUsersError("Unable to load system users. Please refresh to try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshUsers = async () => {
    if (usersRefreshing) return;
    setUsersRefreshing(true);
    setUsersError("");
    try {
      const data = await api.get("admin/users/");
      setUsers(Array.isArray(data) ? data : []);
    } catch (error) {
      setUsersError(getErrorDetail(error, "Unable to refresh system users. Please try again."));
    } finally {
      setUsersRefreshing(false);
    }
  };

  const loadChatGaps = useCallback(async () => {
    setChatGapsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("status", chatGapStatus);
      params.set("limit", "25");
      const data = await api.get(
        `admin/chat/knowledge-gaps/?${params.toString()}`,
      );
      const rows: ChatKnowledgeGap[] = Array.isArray(data?.results)
        ? data.results
        : [];
      setChatGaps(rows);
      setChatGapDrafts((previous) => {
        const next = { ...previous };
        rows.forEach((gap) => {
          if (next[gap.id]) return;
          next[gap.id] = {
            title:
              gap.suggested_title || `Public question: ${gap.question_sample}`,
            summary: gap.suggested_summary || gap.question_sample,
            body: gap.suggested_body || gap.question_sample,
            tags: Array.isArray(gap.suggested_tags)
              ? gap.suggested_tags.join(", ")
              : "chatbot-approved",
            url: "",
          };
        });
        return next;
      });
    } catch (error) {
      console.error(error);
      setChatGaps([]);
    } finally {
      setChatGapsLoading(false);
    }
  }, [chatGapStatus]);

  const loadEvents = useCallback(async () => {
    setEventsLoading(true);
    try {
      const data = await api.get("admin/events/");
      setEvents(
        Array.isArray(data)
          ? data
          : Array.isArray(data?.results)
            ? data.results
            : [],
      );
    } catch (error) {
      console.error(error);
      setEvents([]);
    } finally {
      setEventsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (activeTab === "chatbot-learning") {
      loadChatGaps();
    }
    if (
      showLegacyEventsPanel &&
      ["system-users", "chatbot-learning"].includes(
        activeTab,
      )
    ) {
      loadEvents();
    }
  }, [activeTab, loadChatGaps, loadEvents, showLegacyEventsPanel]);

  const createAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (invitationInFlight.current) return;
    setNotice("");
    const email = form.email.trim();
    const role = form.role === "contributor" ? "staff" : form.role;
    if (!window.confirm(`Send a registration link to ${email} for the ${form.role.replace("_", " ")} role?\n\nContinue?`)) return;
    invitationInFlight.current = true;
    setInvitationSending(true);
    try {
      await api.post("admin/users/", {
        email,
        role,
      });
      setForm({ email: "", role: "contributor" });
      setNotice("Registration invitation sent. The account will appear in System Users after registration and remain inactive until an administrator activates it.");
      await load();
    } catch (err) {
      let message = "Failed to create account. Check email/role.";
      if (err instanceof Error && err.message) {
        try {
          const parsed = JSON.parse(err.message);
          message = parsed?.detail || err.message;
        } catch {
          message = err.message;
        }
      }
      setNotice(message);
    } finally {
      invitationInFlight.current = false;
      setInvitationSending(false);
    }
  };

  const setUserActive = async (id: number, active: boolean) => {
    setNotice("");
    try {
      await api.post(`admin/users/${id}/set_active/`, { active });
      setNotice(active ? "User activated." : "User deactivated.");
      await load();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to update user status."));
    }
  };

  const openAgencyEditor = (user: UserRow) => {
    setAgencyEditUser(user);
    setAgencyEditCode(user.agency_code || user.agency || "");
    setNotice("");
  };

  const saveUserAgency = async () => {
    if (!agencyEditUser || !agencyEditCode || agencyEditBusy) return;
    setAgencyEditBusy(true);
    setNotice("");
    try {
      await api.patch(`admin/users/${agencyEditUser.id}/`, {
        agency_code: agencyEditCode,
      });
      setNotice("Contributor agency updated. Existing project records were not transferred.");
      setAgencyEditUser(null);
      await load();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to update the contributor agency."));
    } finally {
      setAgencyEditBusy(false);
    }
  };

  const updateChatGapDraft = (
    id: number,
    key: keyof ChatGapDraft,
    value: string,
  ) => {
    setChatGapDrafts((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] || {
          title: "",
          summary: "",
          body: "",
          tags: "",
          url: "",
        }),
        [key]: value,
      },
    }));
  };

  const toggleChatGap = (id: number) => {
    setExpandedChatGapIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const approveChatGap = async (gap: ChatKnowledgeGap) => {
    const draft = chatGapDrafts[gap.id];
    if (!draft?.title.trim() || !draft?.body.trim()) {
      setNotice(
        "Title and approved answer are required before approving chatbot knowledge.",
      );
      return;
    }
    try {
      await api.post(`admin/chat/knowledge-gaps/${gap.id}/approve/`, {
        title: draft.title.trim(),
        summary: draft.summary.trim(),
        body: draft.body.trim(),
        tags: draft.tags,
        url: draft.url.trim(),
        language: gap.language,
      });
      setNotice("Chatbot knowledge approved and added to public content.");
      await loadChatGaps();
    } catch (error) {
      setNotice(
        getErrorDetail(error, "Failed to approve chatbot knowledge gap."),
      );
    }
  };

  const rejectChatGap = async (gap: ChatKnowledgeGap) => {
    try {
      await api.post(`admin/chat/knowledge-gaps/${gap.id}/reject/`, {
        notes: "Rejected from admin chatbot learning review.",
      });
      setNotice("Chatbot knowledge gap rejected.");
      await loadChatGaps();
    } catch (error) {
      setNotice(
        getErrorDetail(error, "Failed to reject chatbot knowledge gap."),
      );
    }
  };

  const toDateTimeLocal = (value?: string) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  };

  const editEvent = (event: PublicEventRow) => {
    setEventForm({
      id: event.id,
      title: event.title || "",
      description: event.description || "",
      event_type: event.event_type || "meeting",
      start_at: toDateTimeLocal(event.start_at),
      end_at: toDateTimeLocal(event.end_at),
      location: event.location || "",
      is_virtual: Boolean(event.is_virtual),
      meeting_link: event.meeting_link || "",
    });
  };

  const saveEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    if (!eventForm.title.trim() || !eventForm.start_at) {
      setNotice("Event title and start date/time are required.");
      return;
    }
    try {
      const payload = {
        title: eventForm.title.trim(),
        description: eventForm.description.trim(),
        event_type: eventForm.event_type,
        start_at: eventForm.start_at,
        end_at: eventForm.end_at || null,
        location: eventForm.location.trim(),
        is_virtual: eventForm.is_virtual,
        meeting_link: eventForm.meeting_link.trim(),
      };
      if (eventForm.id) {
        await api.put(`admin/events/${eventForm.id}/`, payload);
        setNotice("Event draft updated.");
      } else {
        await api.post("admin/events/", payload);
        setNotice("Event draft created.");
      }
      setEventForm(emptyEventForm);
      await loadEvents();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to save event."));
    }
  };

  const runEventAction = async (
    event: PublicEventRow,
    action: "submit" | "publish" | "reject" | "archive",
  ) => {
    setNotice("");
    try {
      await api.post(`admin/events/${event.id}/${action}/`, {});
      const labels: Record<typeof action, string> = {
        submit: "Event submitted for review.",
        publish: "Event published to the public website.",
        reject: "Event rejected.",
        archive: "Event archived.",
      };
      setNotice(labels[action]);
      await loadEvents();
    } catch (error) {
      setNotice(getErrorDetail(error, `Failed to ${action} event.`));
    }
  };

  const saveEncodingWindow = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    if (windowForm.enabled && (!windowForm.start_at || !windowForm.end_at)) {
      setNotice(
        "Start and end date are required for a scheduled encoding window.",
      );
      return;
    }
    if (
      windowForm.enabled &&
      new Date(windowForm.start_at).getTime() >=
        new Date(windowForm.end_at).getTime()
    ) {
      setNotice("Start date must be earlier than end date.");
      return;
    }
    try {
      const state = await api.post("encoding-window/", windowForm);
      setWindowState(state || null);
      setWindowForm({
        enabled: Boolean(state?.enabled),
        start_at: state?.start_at || "",
        end_at: state?.end_at || "",
      });
      setNotice("Encoding schedule updated.");
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to update encoding schedule."));
    }
  };

  const scheduleIncomplete =
    windowForm.enabled && (!windowForm.start_at || !windowForm.end_at);
  const scheduleRangeInvalid =
    windowForm.enabled &&
    Boolean(windowForm.start_at) &&
    Boolean(windowForm.end_at) &&
    new Date(windowForm.start_at).getTime() >=
      new Date(windowForm.end_at).getTime();
  const formatWindowDate = (value?: string) =>
    value
      ? new Date(value).toLocaleString("en-PH", {
          timeZone: "Asia/Manila",
          year: "numeric",
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
        })
      : "Not set";
  const windowStatusLabel: Record<string, string> = {
    schedule_not_configured: "Schedule not configured",
    closed_by_admin: "Closed by administrator",
    scheduled_not_started: "Scheduled - not started",
    scheduled_open: "Open for contributor encoding",
    scheduled_ended: "Schedule ended",
    schedule_invalid: "Invalid schedule",
  };

  return (
    <PortalLayout
      title="Users & Access Control"
      subtitle="Account provisioning, request approvals, and encoding schedule"
      role="admin"
      userName={displayName}
      topActions={
        <RefreshButton
          loading={loading}
          onClick={() => void load()}
        />
      }
    >
      {notice && (
        <div className="portal-card p-3 mb-3 text-sm bg-blue-50 border-blue-200 text-blue-800">
          {notice}
        </div>
      )}

      <div className="portal-card mb-4">
        <div className="portal-card-body">
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <button
              type="button"
              onClick={() => setActiveTab("create-account")}
              className={`portal-btn min-h-11 min-w-0 whitespace-normal sm:min-h-0 ${activeTab === "create-account" ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              Create Account
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("encoding-window")}
              className={`portal-btn min-h-11 min-w-0 whitespace-normal sm:min-h-0 ${activeTab === "encoding-window" ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              Encoding Window
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("system-users")}
              className={`portal-btn min-h-11 min-w-0 whitespace-normal sm:min-h-0 ${activeTab === "system-users" ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              System Users
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("agencies")}
              className={`portal-btn min-h-11 min-w-0 whitespace-normal sm:min-h-0 ${activeTab === "agencies" ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              Agencies
            </button>
          </div>
        </div>
      </div>

      {activeTab === "create-account" && (
        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Create Account</h2>
          </div>
          <div className="portal-card-body">
          <form
            onSubmit={createAccount}
            className="grid grid-cols-1 xl:grid-cols-2 gap-3"
          >
            <label className="block">
              <span className="text-sm text-slate-700">Email</span>
              <input
                className="mt-1 border rounded-xl px-3 py-2 w-full"
                type="email"
                placeholder="Email"
                value={form.email}
                onChange={(e) =>
                  setForm((p) => ({ ...p, email: e.target.value }))
                }
                required
              />
            </label>
            <label className="block">
              <span className="text-sm text-slate-700">User Type</span>
              <select
                className="mt-1 border rounded-xl px-3 py-2 w-full"
                value={form.role}
                onChange={(e) =>
                  setForm((p) => ({ ...p, role: e.target.value }))
                }
              >
                <option value="contributor">Contributor</option>
                <option value="validator">Validator</option>
                <option value="content_editor">Content Editor</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <button
              type="submit"
              className="portal-btn portal-btn-primary xl:col-span-2"
              disabled={invitationSending || (form.role === "admin" && administratorCapacity?.available === 0)}
            >
              {invitationSending ? "Sending Registration Form..." : "Send Registration Form"}
            </button>
            {form.role === "admin" && administratorCapacity && (
              <p className={`text-sm xl:col-span-2 ${administratorCapacity.available > 0 ? "text-slate-600" : "text-rose-700"}`}>
                Administrator capacity: {administratorCapacity.active} active + {administratorCapacity.reserved} reserved / {administratorCapacity.limit}. {administratorCapacity.available} slot{administratorCapacity.available === 1 ? "" : "s"} available.
              </p>
            )}
          </form>
          <BatchRegistrationPanel onComplete={load} />
          </div>
        </div>
      )}

      {activeTab === "agencies" && <AgencyManagementPanel />}

      {activeTab === "encoding-window" && (
        <>
          <div className="portal-card mb-4">
            <div className="portal-card-header">
              <h2 className="text-lg font-semibold">
                Contributor Encoding Window
              </h2>
            </div>
            <form
              onSubmit={saveEncodingWindow}
              className="portal-card-body space-y-4"
            >
              <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">
                      Current Contributor Access
                    </p>
                    <p className="mt-1 text-lg font-semibold text-slate-900">
                      {windowStatusLabel[
                        windowState?.status_code || "schedule_not_configured"
                      ] || "Unavailable"}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      {windowState?.message ||
                        "Contributor encoding is closed until an administrator sets a schedule."}
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      windowState?.is_open
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {windowState?.is_open ? "Encoding Open" : "View-Only Mode"}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                  <div>
                    <p className="text-xs text-slate-500">Timezone</p>
                    <p className="font-medium">
                      Philippine Standard Time (UTC+8)
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Opening Date</p>
                    <p className="font-medium">
                      {formatWindowDate(windowState?.start_at)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Closing Deadline</p>
                    <p className="font-medium">
                      {formatWindowDate(windowState?.end_at)}
                    </p>
                  </div>
                </div>
              </div>

              <label className="block">
                <span className="text-sm text-slate-700">Encoding Mode</span>
                <select
                  className="mt-1 w-full border rounded-xl px-3 py-2"
                  value={windowForm.enabled ? "open" : "closed"}
                  onChange={(e) =>
                    setWindowForm((previous) =>
                      e.target.value === "open"
                        ? { ...previous, enabled: true }
                        : { enabled: false, start_at: "", end_at: "" },
                    )
                  }
                >
                  <option value="open">Open by schedule</option>
                  <option value="closed">Closed (view-only)</option>
                </select>
              </label>

              {windowForm.enabled && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                  <label className="block">
                    <span className="text-sm text-slate-700">
                      Opening Date and Time *
                    </span>
                    <input
                      type="datetime-local"
                      required
                      className="mt-1 w-full border rounded-xl px-3 py-2"
                      value={
                        windowForm.start_at
                          ? windowForm.start_at.slice(0, 16)
                          : ""
                      }
                      onChange={(e) =>
                        setWindowForm((p) => ({
                          ...p,
                          start_at: e.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="block">
                    <span className="text-sm text-slate-700">
                      Closing Deadline *
                    </span>
                    <input
                      type="datetime-local"
                      required
                      className="mt-1 w-full border rounded-xl px-3 py-2"
                      value={
                        windowForm.end_at ? windowForm.end_at.slice(0, 16) : ""
                      }
                      onChange={(e) =>
                        setWindowForm((p) => ({ ...p, end_at: e.target.value }))
                      }
                    />
                  </label>
                </div>
              )}

              {(scheduleIncomplete || scheduleRangeInvalid) && (
                <p className="text-sm text-rose-600">
                  {scheduleIncomplete
                    ? "Set both opening and closing dates."
                    : "Opening date must be earlier than the closing deadline."}
                </p>
              )}
              <button
                type="submit"
                disabled={scheduleIncomplete || scheduleRangeInvalid}
                className="portal-btn portal-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save Encoding Window
              </button>
            </form>
          </div>
        </>
      )}

      {activeTab === "system-users" && (
        <div className="portal-card mb-4 portal-table-wrap">
          <div className="portal-card-header flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">System Users</h2>
              <p className="text-xs text-slate-500">
                Find accounts, review lifecycle state, and manage agency access.
              </p>
            </div>
            <RefreshButton
              loading={usersRefreshing}
              onClick={refreshUsers}
              label="Refresh Users"
              disabled={loading || usersRefreshing}
              className="portal-btn portal-btn-ghost disabled:cursor-wait disabled:opacity-60"
            />
          </div>
          <div className="portal-card-body border-b border-slate-200 bg-slate-50/60">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <label className="block min-w-0">
                <span className="text-xs font-semibold text-slate-600">Search User</span>
                <input
                  type="search"
                  className="mt-1 w-full rounded-lg border bg-white px-2 py-1.5 text-sm"
                  placeholder="Name, username, or email"
                  value={userFilters.search}
                  onChange={(event) => updateUserFilter("search", event.target.value)}
                />
              </label>
              <label className="block min-w-0">
                <span className="text-xs font-semibold text-slate-600">Agency</span>
                <select
                  aria-label="Agency"
                  className="mt-1 w-full rounded-lg border bg-white px-2 py-1.5 text-sm"
                  value={userFilters.agency}
                  onChange={(event) => updateUserFilter("agency", event.target.value)}
                >
                  <option value="">All agencies</option>
                  {userAgencies.map((agency) => <option key={agency} value={agency}>{agency}</option>)}
                  {hasUsersWithoutAgency && <option value="__none__">No agency</option>}
                </select>
              </label>
              <label className="block min-w-0">
                <span className="text-xs font-semibold text-slate-600">Role</span>
                <select
                  aria-label="Role"
                  className="mt-1 w-full rounded-lg border bg-white px-2 py-1.5 text-sm"
                  value={userFilters.role}
                  onChange={(event) => updateUserFilter("role", event.target.value)}
                >
                  <option value="">All roles</option>
                  <option value="admin">Admin</option>
                  <option value="validator">Validator</option>
                  <option value="contributor">Contributor</option>
                  <option value="content_editor">Content Editor</option>
                </select>
              </label>
              <label className="block min-w-0">
                <span className="text-xs font-semibold text-slate-600">Status</span>
                <select
                  aria-label="Status"
                  className="mt-1 w-full rounded-lg border bg-white px-2 py-1.5 text-sm"
                  value={userFilters.status}
                  onChange={(event) => updateUserFilter("status", event.target.value)}
                >
                  <option value="">All statuses</option>
                  <option value="active">Active</option>
                  <option value="pending_activation">Pending Activation</option>
                  <option value="disabled">Disabled</option>
                </select>
              </label>
              <label className="block min-w-0">
                <span className="text-xs font-semibold text-slate-600">Rows Per Page</span>
                <select
                  className="mt-1 w-full rounded-lg border bg-white px-2 py-1.5 text-sm"
                  value={userFilters.limit}
                  onChange={(event) => updateUserFilter("limit", event.target.value)}
                >
                  <option value="10">10</option>
                  <option value="20">20</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                </select>
              </label>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-slate-500">
                {filteredUsers.length} of {users.length} system users match the filters.
              </p>
              <MobileSortControls
                className="w-full xl:hidden"
                options={userSortOptions}
                sortKey={userSortKey}
                direction={userSortDirection}
                onSortKeyChange={changeUserSort}
                onToggleDirection={toggleUserSortDirection}
              />
              <button type="button" onClick={clearUserFilters} className="portal-btn portal-btn-ghost">
                Clear Filters
              </button>
            </div>
          </div>
          {usersError && (
            <div role="alert" className="border-b border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {usersError}
            </div>
          )}
          {loading ? (
            <div className="portal-card-body text-slate-500">
              Loading users...
            </div>
          ) : users.length === 0 ? (
            <div className="portal-card-body text-slate-500">
              {usersError ? "No users to display until the list loads." : "No users found."}
            </div>
          ) : filteredUsers.length === 0 ? (
            <div className="portal-card-body text-slate-500">
              No users match the selected filters.
            </div>
          ) : (
            <>
              <ul className="divide-y divide-slate-100 xl:hidden" aria-label="System users">
                {visibleUsers.map((u) => (
                  <li key={u.id} className="min-w-0 p-4">
                    <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                      <p className="min-w-0 break-words font-semibold text-slate-900">
                        {userDisplayName(u)}
                      </p>
                      <span
                        className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${accountStateClass(u)}`}
                      >
                        {accountStateLabel(u)}
                      </span>
                    </div>
                    <dl className="mt-3 grid min-w-0 gap-3 text-sm sm:grid-cols-2">
                      <div className="min-w-0">
                        <dt className="text-xs font-medium text-slate-500">Email</dt>
                        <dd className="break-all text-slate-800">{u.email || "-"}</dd>
                      </div>
                      <div className="min-w-0">
                        <dt className="text-xs font-medium text-slate-500">Agency</dt>
                        <dd className="break-words text-slate-800">{u.agency || "-"}</dd>
                      </div>
                      <div className="min-w-0">
                        <dt className="text-xs font-medium text-slate-500">Role</dt>
                        <dd className="break-words text-slate-800">{labelRole(u.role)}</dd>
                      </div>
                    </dl>
                    <div className="mt-4 grid gap-2">
                      <Link to={`/admin/profiles/${u.id}`} className="portal-btn portal-btn-ghost col-span-2 text-center">View Profile</Link>
                      <button
                        type="button"
                        onClick={() => setUserActive(u.id, !u.is_active)}
                        className="portal-btn portal-btn-ghost min-h-11 min-w-0 whitespace-normal text-blue-700"
                      >
                        {u.is_active ? "Deactivate" : "Activate"}
                      </button>
                      {userRoleFilterValue(u.role) === "contributor" && (
                        <button
                          type="button"
                          onClick={() => openAgencyEditor(u)}
                          className="portal-btn portal-btn-ghost min-h-11 min-w-0 whitespace-normal text-indigo-700"
                        >
                          Change Agency
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              <table className="portal-table hidden xl:table">
              <thead>
                <tr>
                  <SortableTableHeader label="Username" sortKey="username" activeKey={userSortKey} direction={userSortDirection} onSort={changeUserSort} />
                  <SortableTableHeader label="Email" sortKey="email" activeKey={userSortKey} direction={userSortDirection} onSort={changeUserSort} />
                  <SortableTableHeader label="Agency" sortKey="agency" activeKey={userSortKey} direction={userSortDirection} onSort={changeUserSort} />
                  <SortableTableHeader label="Role" sortKey="role" activeKey={userSortKey} direction={userSortDirection} onSort={changeUserSort} />
                  <SortableTableHeader label="Status" sortKey="status" activeKey={userSortKey} direction={userSortDirection} onSort={changeUserSort} />
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleUsers.map((u) => (
                  <tr key={u.id}>
                    <td>{userDisplayName(u)}</td>
                    <td>{u.email || "-"}</td>
                    <td>{u.agency || "-"}</td>
                    <td>{labelRole(u.role)}</td>
                    <td>
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-semibold ${accountStateClass(u)}`}
                      >
                        {accountStateLabel(u)}
                      </span>
                    </td>
                    <td className="space-x-2">
                      <Link to={`/admin/profiles/${u.id}`} className="text-slate-700 hover:underline">Profile</Link>
                      <button
                        onClick={() => setUserActive(u.id, !u.is_active)}
                        className="text-blue-600 hover:underline"
                      >
                        {u.is_active ? "Deactivate" : "Activate"}
                      </button>
                      {userRoleFilterValue(u.role) === "contributor" && (
                        <button
                          type="button"
                          onClick={() => openAgencyEditor(u)}
                          className="text-indigo-600 hover:underline"
                        >
                          Change Agency
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              </table>
              <div className="portal-card-body flex flex-col gap-3 border-t border-slate-200 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-600" aria-live="polite">
                  Showing <span className="font-semibold">{userStart}</span>–<span className="font-semibold">{userEnd}</span> of {filteredUsers.length} matching users
                  {filteredUsers.length !== users.length ? ` (${users.length} total)` : ""}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setUserPage((page) => Math.max(1, page - 1))}
                    disabled={currentUserPage <= 1}
                    className="portal-btn portal-btn-ghost disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-slate-600">Page {currentUserPage} of {userPageCount}</span>
                  <button
                    type="button"
                    onClick={() => setUserPage((page) => Math.min(userPageCount, page + 1))}
                    disabled={currentUserPage >= userPageCount}
                    className="portal-btn portal-btn-ghost disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {agencyEditUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !agencyEditBusy) setAgencyEditUser(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="change-user-agency-title"
            className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-2xl"
          >
            <h2 id="change-user-agency-title" className="text-lg font-semibold text-slate-900">
              Change Contributor Agency
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Reassign {userDisplayName(agencyEditUser)}. This changes account authorization only; it does not transfer project ownership.
            </p>
            <label className="mt-4 block">
              <span className="text-sm font-medium text-slate-700">Active agency</span>
              <select
                autoFocus
                value={agencyEditCode}
                onChange={(event) => setAgencyEditCode(event.target.value)}
                disabled={agencyEditBusy}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Select an agency</option>
                {accountAgencies.map((agency) => {
                  const current = agency.code === (agencyEditUser.agency_code || agencyEditUser.agency);
                  const available = Number(agency.contributor_capacity?.available ?? 0);
                  const disabled = !current && agency.accepting_contributors === false;
                  return (
                    <option key={agency.code} value={agency.code} disabled={disabled}>
                      {agency.code} - {agency.name} ({available} slot{available === 1 ? "" : "s"} available)
                    </option>
                  );
                })}
              </select>
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                className="portal-btn portal-btn-ghost"
                disabled={agencyEditBusy}
                onClick={() => setAgencyEditUser(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="portal-btn portal-btn-primary"
                disabled={agencyEditBusy || !agencyEditCode}
                onClick={saveUserAgency}
              >
                {agencyEditBusy ? "Saving..." : "Save Agency"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showLegacyEventsPanel && activeTab === "chatbot-learning" && (
        <div className="portal-card mb-4">
          <div className="portal-card-header flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Public Events Calendar</h2>
              <p className="text-xs text-slate-500">
                Manage Home page events. Only published events appear on the
                public website.
              </p>
            </div>
            <RefreshButton loading={eventsLoading} onClick={loadEvents} label="Refresh Events" />
          </div>
          <form
            onSubmit={saveEvent}
            className="portal-card-body border-b border-slate-200"
          >
            <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
              <label className="block">
                <span className="text-sm text-slate-700">Event Title *</span>
                <input
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                  value={eventForm.title}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      title: e.target.value,
                    }))
                  }
                  placeholder="RDC Full Council Meeting"
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Event Type</span>
                <select
                  className="mt-1 w-full rounded-lg border px-3 py-2 bg-white"
                  value={eventForm.event_type}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      event_type: e.target.value,
                    }))
                  }
                >
                  <option value="meeting">Meeting</option>
                  <option value="forum">Forum</option>
                  <option value="consultation">Consultation</option>
                  <option value="deadline">Deadline</option>
                  <option value="summit">Summit</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">
                  Start Date and Time *
                </span>
                <input
                  type="datetime-local"
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                  value={eventForm.start_at}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      start_at: e.target.value,
                    }))
                  }
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">
                  End Date and Time
                </span>
                <input
                  type="datetime-local"
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                  value={eventForm.end_at}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      end_at: e.target.value,
                    }))
                  }
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Location / Venue</span>
                <input
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                  value={eventForm.location}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      location: e.target.value,
                    }))
                  }
                  placeholder="MMDA Building or Virtual"
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Meeting Link</span>
                <input
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                  value={eventForm.meeting_link}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      meeting_link: e.target.value,
                    }))
                  }
                  placeholder="https://..."
                />
              </label>
              <label className="flex items-center gap-2 xl:col-span-2">
                <input
                  type="checkbox"
                  checked={eventForm.is_virtual}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      is_virtual: e.target.checked,
                    }))
                  }
                />
                <span className="text-sm text-slate-700">
                  This is a virtual or online event.
                </span>
              </label>
              <label className="block xl:col-span-2">
                <span className="text-sm text-slate-700">
                  Public Description
                </span>
                <textarea
                  className="mt-1 min-h-[90px] w-full rounded-lg border px-3 py-2"
                  value={eventForm.description}
                  onChange={(e) =>
                    setEventForm((prev) => ({
                      ...prev,
                      description: e.target.value,
                    }))
                  }
                  placeholder="Brief public-facing details, agenda note, or participation instructions."
                />
              </label>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="submit" className="portal-btn portal-btn-primary">
                {eventForm.id ? "Save Event Draft" : "Create Event Draft"}
              </button>
              {eventForm.id && (
                <button
                  type="button"
                  onClick={() => setEventForm(emptyEventForm)}
                  className="portal-btn portal-btn-ghost"
                >
                  Cancel Edit
                </button>
              )}
            </div>
          </form>
          <div className="portal-card-body">
            {eventsLoading ? (
              <p className="text-sm text-slate-500">Loading public events...</p>
            ) : events.length === 0 ? (
              <p className="text-sm text-slate-500">No events created yet.</p>
            ) : (
              <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
                {events.map((event) => (
                  <div
                    key={event.id}
                    className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-full px-2 py-1 text-xs font-semibold ${
                              event.status === "published"
                                ? "bg-emerald-100 text-emerald-700"
                                : event.status === "submitted"
                                  ? "bg-blue-100 text-blue-700"
                                  : event.status === "rejected"
                                    ? "bg-rose-100 text-rose-700"
                                    : event.status === "archived"
                                      ? "bg-slate-200 text-slate-700"
                                      : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            {event.status}
                          </span>
                          <span className="rounded-full bg-purple-100 px-2 py-1 text-xs font-semibold text-purple-700">
                            {event.event_type}
                          </span>
                        </div>
                        <h3 className="mt-2 font-semibold text-slate-900">
                          {event.title}
                        </h3>
                        <p className="mt-1 text-sm text-slate-600">
                          {event.start_at
                            ? new Date(event.start_at).toLocaleString("en-PH", {
                                timeZone: "Asia/Manila",
                              })
                            : "No date"}
                        </p>
                        <p className="mt-1 text-sm text-slate-500">
                          {event.location ||
                            (event.is_virtual ? "Virtual" : "Location not set")}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => editEvent(event)}
                        className="portal-btn portal-btn-ghost w-fit"
                      >
                        Edit
                      </button>
                    </div>
                    {event.description && (
                      <p className="mt-3 line-clamp-2 text-sm text-slate-600">
                        {event.description}
                      </p>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2">
                      {event.status !== "published" &&
                        event.status !== "archived" && (
                          <button
                            type="button"
                            onClick={() => runEventAction(event, "publish")}
                            className="text-sm font-semibold text-emerald-600 hover:underline"
                          >
                            Publish
                          </button>
                        )}
                      {(event.status === "submitted" ||
                        event.status === "draft") && (
                        <button
                          type="button"
                          onClick={() => runEventAction(event, "reject")}
                          className="text-sm font-semibold text-rose-600 hover:underline"
                        >
                          Reject
                        </button>
                      )}
                      {event.status !== "archived" && (
                        <button
                          type="button"
                          onClick={() => runEventAction(event, "archive")}
                          className="text-sm font-semibold text-slate-500 hover:underline"
                        >
                          Archive
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "chatbot-learning" && (
        <div className="portal-card mb-4">
          <div className="portal-card-header flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Chatbot Learning</h2>
              <p className="text-xs text-slate-500">
                Review repeated low-confidence public questions and convert them
                into approved website knowledge.
              </p>
              <p className="mt-2 w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                {chatGapsLoading
                  ? "Loading questions..."
                  : `${chatGaps.length} question${chatGaps.length === 1 ? "" : "s"} shown`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <select
                className="border rounded-lg px-2 py-1.5 text-sm bg-white"
                value={chatGapStatus}
                onChange={(e) => setChatGapStatus(e.target.value)}
              >
                <option value="pending">Pending gaps</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="all">All statuses</option>
              </select>
              <RefreshButton loading={chatGapsLoading} onClick={loadChatGaps} />
            </div>
          </div>
          <div className="portal-card-body space-y-4">
            {chatGapsLoading ? (
              <p className="text-sm text-slate-500">
                Loading chatbot learning signals...
              </p>
            ) : chatGaps.length === 0 ? (
              <p className="text-sm text-slate-500">
                No chatbot knowledge gaps found for this filter.
              </p>
            ) : (
              chatGaps.map((gap) => {
                const draft = chatGapDrafts[gap.id] || {
                  title: "",
                  summary: "",
                  body: "",
                  tags: "",
                  url: "",
                };
                const isExpanded = Boolean(expandedChatGapIds[gap.id]);
                return (
                  <div
                    key={gap.id}
                    className="rounded-2xl border border-slate-200 bg-white shadow-sm"
                  >
                    <div className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">
                            Asked {gap.count}x
                          </span>
                          <span className="rounded-full bg-slate-200 px-2 py-1 text-xs font-semibold text-slate-700">
                            {gap.language === "tl"
                              ? "Tagalog/Taglish"
                              : "English"}
                          </span>
                          <span
                            className={`rounded-full px-2 py-1 text-xs font-semibold ${
                              gap.status === "approved"
                                ? "bg-emerald-100 text-emerald-700"
                                : gap.status === "rejected"
                                  ? "bg-rose-100 text-rose-700"
                                  : "bg-blue-100 text-blue-700"
                            }`}
                          >
                            {gap.status}
                          </span>
                          <span className="text-xs text-slate-500">
                            Last asked{" "}
                            {new Date(gap.last_asked).toLocaleString()}
                          </span>
                        </div>
                        <p
                          className="mt-2 truncate font-semibold text-slate-900"
                          title={gap.question_sample}
                        >
                          {gap.question_sample}
                        </p>
                        {gap.matched_content_title && (
                          <p className="mt-1 text-xs text-slate-500">
                            Possibly related to: {gap.matched_content_title}
                          </p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => toggleChatGap(gap.id)}
                        className="portal-btn portal-btn-ghost w-fit"
                        aria-expanded={isExpanded}
                      >
                        {isExpanded
                          ? "Hide details"
                          : gap.status === "pending"
                            ? "Review"
                            : "View details"}
                      </button>
                    </div>

                    {isExpanded && gap.status === "pending" ? (
                      <div className="grid grid-cols-1 gap-3 border-t border-slate-200 bg-slate-50/70 px-4 pb-4 pt-4 xl:grid-cols-2">
                        <label className="block">
                          <span className="text-xs font-semibold text-slate-600">
                            Approved Public Title
                          </span>
                          <input
                            className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                            value={draft.title}
                            onChange={(e) =>
                              updateChatGapDraft(
                                gap.id,
                                "title",
                                e.target.value,
                              )
                            }
                          />
                        </label>
                        <label className="block">
                          <span className="text-xs font-semibold text-slate-600">
                            Source URL
                          </span>
                          <input
                            className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                            placeholder="/about-rdc or /contact"
                            value={draft.url}
                            onChange={(e) =>
                              updateChatGapDraft(gap.id, "url", e.target.value)
                            }
                          />
                        </label>
                        <label className="block xl:col-span-2">
                          <span className="text-xs font-semibold text-slate-600">
                            Short Summary
                          </span>
                          <input
                            className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                            value={draft.summary}
                            onChange={(e) =>
                              updateChatGapDraft(
                                gap.id,
                                "summary",
                                e.target.value,
                              )
                            }
                          />
                        </label>
                        <label className="block xl:col-span-2">
                          <span className="text-xs font-semibold text-slate-600">
                            Approved Answer / Knowledge Body
                          </span>
                          <textarea
                            className="mt-1 min-h-[96px] w-full rounded-lg border px-3 py-2 text-sm"
                            value={draft.body}
                            onChange={(e) =>
                              updateChatGapDraft(gap.id, "body", e.target.value)
                            }
                          />
                        </label>
                        <label className="block xl:col-span-2">
                          <span className="text-xs font-semibold text-slate-600">
                            Tags
                          </span>
                          <input
                            className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                            placeholder="dashboard, publications, contact"
                            value={draft.tags}
                            onChange={(e) =>
                              updateChatGapDraft(gap.id, "tags", e.target.value)
                            }
                          />
                        </label>
                        <div className="flex flex-wrap gap-2 xl:col-span-2">
                          <button
                            type="button"
                            onClick={() => approveChatGap(gap)}
                            className="portal-btn portal-btn-primary"
                          >
                            Approve as Knowledge
                          </button>
                          <button
                            type="button"
                            onClick={() => rejectChatGap(gap)}
                            className="portal-btn portal-btn-ghost text-rose-600"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    ) : isExpanded ? (
                      <p className="border-t border-slate-200 px-4 pb-4 pt-3 text-sm text-slate-500">
                        Reviewed{" "}
                        {gap.reviewed_at
                          ? new Date(gap.reviewed_at).toLocaleString()
                          : ""}{" "}
                        {gap.reviewed_by_name
                          ? `by ${gap.reviewed_by_name}`
                          : ""}
                      </p>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

    </PortalLayout>
  );
};

export default UserManagement;
