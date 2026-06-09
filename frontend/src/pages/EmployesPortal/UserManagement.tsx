import React, { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";

type UserRow = {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
};

type ActivityItem = {
  id: number;
  username: string;
  full_name?: string;
  role: string;
  event: string;
  project_title?: string;
  ip_address?: string;
  location_hint?: string;
  created_at: string;
  details?: Record<string, unknown>;
};

type PasswordResetRequestRow = {
  id: number;
  email: string;
  status: "pending" | "approved" | "rejected";
  user_email?: string;
  user_username?: string;
  requested_ip?: string;
  requested_user_agent?: string;
  created_at: string;
  reviewed_at?: string;
};

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

type AdminUsersTab = "create-account" | "encoding-window" | "operations";

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
  if (value === "create-account" || value === "encoding-window" || value === "operations") return value;
  return "operations";
};

const UserManagement = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = parseTab(searchParams.get("tab"));
  const [users, setUsers] = useState<UserRow[]>([]);
  const [resetRequests, setResetRequests] = useState<PasswordResetRequestRow[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activityTotal, setActivityTotal] = useState(0);
  const [activityOffset, setActivityOffset] = useState(0);
  const [chatGaps, setChatGaps] = useState<ChatKnowledgeGap[]>([]);
  const [chatGapsLoading, setChatGapsLoading] = useState(false);
  const [chatGapDrafts, setChatGapDrafts] = useState<Record<number, ChatGapDraft>>({});
  const [chatGapStatus, setChatGapStatus] = useState("pending");
  const [expandedChatGapIds, setExpandedChatGapIds] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [toast, setToast] = useState<{ message: string; type: "info" | "success" | "warn" | "error" } | null>(null);
  const [resetActionLoading, setResetActionLoading] = useState<Record<number, boolean>>({});
  const [form, setForm] = useState({
    email: "",
    role: "contributor",
  });
  const [windowForm, setWindowForm] = useState({
    enabled: false,
    start_at: "",
    end_at: "",
  });
  const [windowState, setWindowState] = useState<EncodingWindowState | null>(null);
  const [progressWindowForm, setProgressWindowForm] = useState({
    enabled: false,
    start_at: "",
    end_at: "",
  });
  const [progressWindowState, setProgressWindowState] = useState<EncodingWindowState | null>(null);
  const [activityFilters, setActivityFilters] = useState({
    role: "",
    event: "",
    user: "",
    limit: "10",
    dateFrom: "",
    dateTo: "",
  });

  const userRaw = localStorage.getItem("user");
  const user = userRaw ? JSON.parse(userRaw) : { username: "admin" };
  const displayName = user?.full_name || user?.username || "Admin";

  const labelRole = (role: string) => {
    if (role === "staff" || role === "employee" || role === "contributor") return "Contributor";
    if (role === "validator") return "Validator";
    if (role === "admin") return "Admin";
    return role;
  };

  const eventLabels: Record<string, string> = {
    login: "Auth Login",
    auth_reset_request: "Auth Reset Request",
    auth_reset_approve: "Auth Reset Approved",
    auth_reset_reject: "Auth Reset Rejected",
    user_create: "User Created",
    project_create: "Project Created",
    project_update: "Project Updated",
    project_submit: "Project Submitted",
    project_approve: "Project Approved",
    project_reject: "Project Rejected",
    project_archive: "Project Archived",
    project_comment: "Project Comment",
    validator_draft: "Validator Draft Saved",
    validator_reviewed: "Validator Reviewed",
    validator_endorsed: "Validator Endorsed",
    public_summary_overridden: "Public Summary Updated",
    priority_analysis_run: "Priority Analysis Run",
    priority_analysis_reused: "Priority Analysis Reused",
    priority_analysis_confirmed: "Priority Analysis Confirmed",
    priority_analysis_overridden: "Priority Analysis Overridden",
    encoding_window_updated: "Encoding Window Updated",
    progress_window_updated: "Progress Update Window Updated",
    project_revision_created: "Project Revision Created",
    project_revision_updated: "Project Revision Updated",
    project_revision_submitted: "Project Revision Submitted",
    project_revision_reviewed: "Project Revision Reviewed",
    project_revision_endorsed: "Project Revision Endorsed",
    project_revision_rejected: "Project Revision Rejected",
    chat_knowledge_approved: "Chat Knowledge Approved",
    chat_knowledge_rejected: "Chat Knowledge Rejected",
    chat_content_updated: "Chat Content Updated",
  };

  const eventSeverity: Record<string, "info" | "warn" | "error"> = {
    login: "info",
    auth_reset_request: "warn",
    auth_reset_approve: "info",
    auth_reset_reject: "warn",
    user_create: "info",
    project_create: "info",
    project_update: "info",
    project_submit: "info",
    project_approve: "info",
    project_reject: "warn",
    project_archive: "warn",
    project_comment: "info",
    validator_draft: "info",
    validator_reviewed: "info",
    validator_endorsed: "info",
    public_summary_overridden: "info",
    priority_analysis_run: "info",
    priority_analysis_reused: "info",
    priority_analysis_confirmed: "info",
    priority_analysis_overridden: "warn",
    encoding_window_updated: "info",
    progress_window_updated: "info",
    project_revision_created: "info",
    project_revision_updated: "info",
    project_revision_submitted: "info",
    project_revision_reviewed: "info",
    project_revision_endorsed: "info",
    project_revision_rejected: "warn",
    chat_knowledge_approved: "info",
    chat_knowledge_rejected: "warn",
    chat_content_updated: "info",
  };

  const severityClass = (event: string) => {
    const level = eventSeverity[event] || "info";
    if (level === "error") return "bg-rose-100 text-rose-700";
    if (level === "warn") return "bg-amber-100 text-amber-700";
    return "bg-emerald-100 text-emerald-700";
  };

  const detailLabelOverrides: Record<string, string> = {
    email: "Email",
    role: "Role",
    status: "Status",
    review_status: "Review Status",
    edited_fields_count: "Edited Fields",
    warning: "Warning",
    action: "Action",
    project_id: "Project ID",
    project_title: "Project",
    reviewed_by: "Reviewed By",
    reviewed_at: "Reviewed At",
    requested_ip: "Requested IP",
    ip: "IP",
    user_agent: "User Agent",
    method: "Method",
    previous_mode: "Previous Mode",
    previous_start_at: "Previous Start",
    previous_end_at: "Previous End",
    previous_status: "Previous State",
    new_mode: "New Mode",
    new_start_at: "New Start",
    new_end_at: "New End",
    new_status: "New State",
    revision_number: "Revision",
    revision_state: "Revision State",
    revision_type: "Revision Type",
  };

  const formatDetailLabel = (key: string) => {
    const override = detailLabelOverrides[key];
    if (override) return override;
    return key
      .replace(/_/g, " ")
      .replace(/\b\w/g, (m) => m.toUpperCase());
  };

  const formatDetailValue = (value: unknown) => {
    if (value === null || value === undefined || value === "") return "-";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  const formatReviewStatus = (value: unknown) => {
    const status = String(value || "").toLowerCase();
    if (status === "draft") return "Draft";
    if (status === "reviewed") return "Reviewed";
    if (status === "endorsed" || status === "validated") return "Endorsed";
    if (status === "rejected") return "Rejected";
    return status ? status : "-";
  };

  const formatProjectStatus = (value: unknown) => {
    const status = String(value || "").toLowerCase();
    if (status === "planning") return "Draft";
    if (status === "proposed") return "Submitted";
    if (status === "completed") return "Endorsed";
    if (status === "ongoing") return "Ongoing";
    if (status === "rejected") return "Rejected";
    return status ? status : "-";
  };

  const buildDetailEntries = (item: ActivityItem): Array<[string, string]> => {
    const details = item.details || {};
    const entries: Array<[string, string]> = [];
    const used = new Set<string>();

    const push = (key: string, label: string, value: string) => {
      if (!value || value === "-") return;
      entries.push([label, value]);
      used.add(key);
    };

    if (item.event.startsWith("validator_")) {
      if ("review_status" in details) {
        push("review_status", "Review Status", formatReviewStatus(details.review_status));
      }
      if ("edited_fields_count" in details) {
        push("edited_fields_count", "Edited Fields", String(details.edited_fields_count ?? 0));
      } else if ("edited" in details) {
        push("edited", "Edited", String(details.edited ? "Yes" : "No"));
      }
      if ("warning" in details) {
        push("warning", "Warning", String(details.warning));
      }
    } else {
      if ("status" in details) {
        push("status", "Status", formatProjectStatus(details.status));
      }
      if ("review_status" in details) {
        push("review_status", "Review Status", formatReviewStatus(details.review_status));
      }
      if ("role" in details) {
        push("role", "Role", labelRole(String(details.role)));
      }
    }

    Object.entries(details)
      .filter(([key, value]) => !used.has(key) && value !== undefined && value !== null && value !== "")
      .forEach(([key, value]) => {
        if (entries.length >= 3) return;
        const label = formatDetailLabel(key);
        const formatted =
          key === "status"
            ? formatProjectStatus(value)
            : key === "review_status"
            ? formatReviewStatus(value)
            : formatDetailValue(value);
        push(key, label, formatted);
      });

    return entries.slice(0, 3);
  };

  const showToast = (message: string, type: "info" | "success" | "warn" | "error" = "info") => {
    setToast({ message, type });
  };

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
      const [usersRes, resetRes, winRes, progressWinRes] = await Promise.all([
        api.get("admin/users/"),
        api.get("password-reset-requests/"),
        api.get("encoding-window/"),
        api.get("progress-update-window/"),
      ]);
      setUsers(Array.isArray(usersRes) ? usersRes : []);
      setResetRequests(Array.isArray(resetRes) ? resetRes : []);
      setWindowForm({
        enabled: Boolean(winRes?.enabled),
        start_at: winRes?.start_at || "",
        end_at: winRes?.end_at || "",
      });
      setWindowState(winRes || null);
      setProgressWindowForm({
        enabled: Boolean(progressWinRes?.enabled),
        start_at: progressWinRes?.start_at || "",
        end_at: progressWinRes?.end_at || "",
      });
      setProgressWindowState(progressWinRes || null);
    } catch (error) {
      console.error(error);
      setUsers([]);
      setResetRequests([]);
      setActivity([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadActivity = useCallback(async () => {
    setActivityLoading(true);
    try {
      const params = new URLSearchParams();
      if (activityFilters.role) params.set("role", activityFilters.role);
      if (activityFilters.event) params.set("event", activityFilters.event);
      if (activityFilters.user) params.set("user", activityFilters.user);
      if (activityFilters.limit) params.set("limit", activityFilters.limit);
      if (activityFilters.dateFrom) params.set("date_from", activityFilters.dateFrom);
      if (activityFilters.dateTo) params.set("date_to", activityFilters.dateTo);
      params.set("offset", String(activityOffset));
      params.set("include_meta", "1");
      const qs = params.toString();
      const data = await api.get(`admin/activity/${qs ? `?${qs}` : ""}`);
      if (Array.isArray(data)) {
        setActivity(data);
        setActivityTotal(data.length);
      } else {
        setActivity(Array.isArray(data?.results) ? data.results : []);
        setActivityTotal(Number(data?.count || 0));
      }
    } catch (error) {
      console.error(error);
      setActivity([]);
      setActivityTotal(0);
    } finally {
      setActivityLoading(false);
    }
  }, [
    activityFilters.role,
    activityFilters.event,
    activityFilters.user,
    activityFilters.limit,
    activityFilters.dateFrom,
    activityFilters.dateTo,
    activityOffset,
  ]);

  const loadChatGaps = useCallback(async () => {
    setChatGapsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("status", chatGapStatus);
      params.set("limit", "25");
      const data = await api.get(`admin/chat/knowledge-gaps/?${params.toString()}`);
      const rows: ChatKnowledgeGap[] = Array.isArray(data?.results) ? data.results : [];
      setChatGaps(rows);
      setChatGapDrafts((previous) => {
        const next = { ...previous };
        rows.forEach((gap) => {
          if (next[gap.id]) return;
          next[gap.id] = {
            title: gap.suggested_title || `Public question: ${gap.question_sample}`,
            summary: gap.suggested_summary || gap.question_sample,
            body: gap.suggested_body || gap.question_sample,
            tags: Array.isArray(gap.suggested_tags) ? gap.suggested_tags.join(", ") : "chatbot-approved",
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

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadActivity();
  }, [loadActivity]);

  useEffect(() => {
    if (activeTab !== "operations") return;
    loadChatGaps();
  }, [activeTab, loadChatGaps]);

  useEffect(() => {
    if (!toast) return undefined;
    const timer = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const createAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    try {
      await api.post("admin/users/", {
        email: form.email.trim(),
        role: form.role === "contributor" ? "staff" : form.role,
      });
      setForm({ email: "", role: "contributor" });
      setNotice("Account created. Setup link sent to email.");
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
    }
  };

  const setUserActive = async (id: number, active: boolean) => {
    setNotice("");
    try {
      await api.post(`admin/users/${id}/set_active/`, { active });
      setNotice(active ? "User activated." : "User deactivated.");
      await load();
    } catch {
      setNotice("Failed to update user status.");
    }
  };

  const resetUserPassword = async (id: number) => {
    setNotice("");
    try {
      await api.post(`admin/users/${id}/reset_password/`, {});
      setNotice("Password reset link sent to the user's email.");
    } catch {
      setNotice("Failed to reset password.");
    }
  };

  const reviewResetRequest = async (id: number, action: "approve" | "reject") => {
    setNotice("");
    try {
      setResetActionLoading((prev) => ({ ...prev, [id]: true }));
      await api.post(`password-reset-requests/${id}/${action}/`, {});
      setNotice(action === "approve" ? "Password reset approved." : "Password reset rejected.");
      await load();
      await loadActivity();
    } catch (err) {
      const detail = getErrorDetail(err, "Failed to update password reset request.");
      if (detail.toLowerCase().includes("already reviewed")) {
        showToast(detail, "warn");
      } else {
        setNotice(detail);
      }
    } finally {
      setResetActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const updateChatGapDraft = (id: number, key: keyof ChatGapDraft, value: string) => {
    setChatGapDrafts((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] || { title: "", summary: "", body: "", tags: "", url: "" }),
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
      setNotice("Title and approved answer are required before approving chatbot knowledge.");
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
      await loadActivity();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to approve chatbot knowledge gap."));
    }
  };

  const rejectChatGap = async (gap: ChatKnowledgeGap) => {
    try {
      await api.post(`admin/chat/knowledge-gaps/${gap.id}/reject/`, {
        notes: "Rejected from admin chatbot learning review.",
      });
      setNotice("Chatbot knowledge gap rejected.");
      await loadChatGaps();
      await loadActivity();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to reject chatbot knowledge gap."));
    }
  };

  const saveEncodingWindow = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    if (windowForm.enabled && (!windowForm.start_at || !windowForm.end_at)) {
      setNotice("Start and end date are required for a scheduled encoding window.");
      return;
    }
    if (
      windowForm.enabled &&
      new Date(windowForm.start_at).getTime() >= new Date(windowForm.end_at).getTime()
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
      await loadActivity();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to update encoding schedule."));
    }
  };

  const saveProgressWindow = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    if (progressWindowForm.enabled && (!progressWindowForm.start_at || !progressWindowForm.end_at)) {
      setNotice("Start and end date are required for a scheduled progress update window.");
      return;
    }
    if (
      progressWindowForm.enabled &&
      new Date(progressWindowForm.start_at).getTime() >= new Date(progressWindowForm.end_at).getTime()
    ) {
      setNotice("Progress update start date must be earlier than end date.");
      return;
    }
    try {
      const state = await api.post("progress-update-window/", progressWindowForm);
      setProgressWindowState(state || null);
      setProgressWindowForm({
        enabled: Boolean(state?.enabled),
        start_at: state?.start_at || "",
        end_at: state?.end_at || "",
      });
      setNotice("Progress update schedule updated.");
      await loadActivity();
    } catch (error) {
      setNotice(getErrorDetail(error, "Failed to update progress update schedule."));
    }
  };

  const scheduleIncomplete = windowForm.enabled && (!windowForm.start_at || !windowForm.end_at);
  const scheduleRangeInvalid =
    windowForm.enabled &&
    Boolean(windowForm.start_at) &&
    Boolean(windowForm.end_at) &&
    new Date(windowForm.start_at).getTime() >= new Date(windowForm.end_at).getTime();
  const progressScheduleIncomplete =
    progressWindowForm.enabled && (!progressWindowForm.start_at || !progressWindowForm.end_at);
  const progressScheduleRangeInvalid =
    progressWindowForm.enabled &&
    Boolean(progressWindowForm.start_at) &&
    Boolean(progressWindowForm.end_at) &&
    new Date(progressWindowForm.start_at).getTime() >= new Date(progressWindowForm.end_at).getTime();
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

  const updateActivityFilter = (key: keyof typeof activityFilters, value: string) => {
    setActivityOffset(0);
    setActivityFilters((prev) => ({ ...prev, [key]: value }));
  };

  const clearActivityFilters = () => {
    setActivityOffset(0);
    setActivityFilters({
      role: "",
      event: "",
      user: "",
      limit: "10",
      dateFrom: "",
      dateTo: "",
    });
  };

  const activityLimit = Math.max(1, Number(activityFilters.limit) || 10);
  const activityStart = activityTotal > 0 ? activityOffset + 1 : 0;
  const activityEnd = Math.min(activityOffset + activity.length, activityTotal);
  const hasPreviousActivity = activityOffset > 0;
  const hasNextActivity = activityOffset + activity.length < activityTotal;

  return (
    <PortalLayout
      title="Users & Access Control"
      subtitle="Account provisioning, request approvals, and encoding schedule"
      role="admin"
      userName={displayName}
      topActions={<button onClick={() => { load(); loadActivity(); }} className="portal-btn portal-btn-ghost">Refresh</button>}
    >
      {toast && (
        <div className="fixed top-24 right-6 z-50">
          <div
            className={`rounded-lg shadow-lg px-4 py-3 text-sm font-medium ${
              toast.type === "error"
                ? "bg-rose-50 text-rose-700 border border-rose-200"
                : toast.type === "warn"
                ? "bg-amber-50 text-amber-700 border border-amber-200"
                : toast.type === "success"
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-slate-50 text-slate-700 border border-slate-200"
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}
      {notice && <div className="portal-card p-3 mb-3 text-sm bg-blue-50 border-blue-200 text-blue-800">{notice}</div>}

      <div className="portal-card mb-4">
        <div className="portal-card-body">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("create-account")}
              className={`portal-btn ${activeTab === "create-account" ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              Create Account
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("encoding-window")}
              className={`portal-btn ${activeTab === "encoding-window" ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              Encoding Window
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("operations")}
              className={`portal-btn ${activeTab === "operations" ? "portal-btn-primary" : "portal-btn-ghost"}`}
            >
              Operations
            </button>
          </div>
        </div>
      </div>

      {activeTab === "create-account" && (
        <div className="portal-card">
          <div className="portal-card-header"><h2 className="text-lg font-semibold">Create Account</h2></div>
          <form onSubmit={createAccount} className="portal-card-body grid grid-cols-1 xl:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm text-slate-700">Email</span>
              <input
                className="mt-1 border rounded-xl px-3 py-2 w-full"
                type="email"
                placeholder="Email"
                value={form.email}
                onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
                required
              />
            </label>
            <label className="block">
              <span className="text-sm text-slate-700">User Type</span>
              <select
                className="mt-1 border rounded-xl px-3 py-2 w-full"
                value={form.role}
                onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))}
              >
                <option value="contributor">Contributor</option>
                <option value="validator">Validator</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <button type="submit" className="portal-btn portal-btn-primary xl:col-span-2">Create User</button>
          </form>
        </div>
      )}

      {activeTab === "encoding-window" && (
        <>
        <div className="portal-card mb-4">
          <div className="portal-card-header"><h2 className="text-lg font-semibold">Contributor Encoding Window</h2></div>
          <form onSubmit={saveEncodingWindow} className="portal-card-body space-y-4">
            <div className="rounded-xl border border-blue-100 bg-blue-50/60 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Current Contributor Access</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {windowStatusLabel[windowState?.status_code || "schedule_not_configured"] || "Unavailable"}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {windowState?.message || "Contributor encoding is closed until an administrator sets a schedule."}
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  windowState?.is_open ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                }`}>
                  {windowState?.is_open ? "Encoding Open" : "View-Only Mode"}
                </span>
              </div>
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div><p className="text-xs text-slate-500">Timezone</p><p className="font-medium">Philippine Standard Time (UTC+8)</p></div>
                <div><p className="text-xs text-slate-500">Opening Date</p><p className="font-medium">{formatWindowDate(windowState?.start_at)}</p></div>
                <div><p className="text-xs text-slate-500">Closing Deadline</p><p className="font-medium">{formatWindowDate(windowState?.end_at)}</p></div>
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
                  <span className="text-sm text-slate-700">Opening Date and Time *</span>
                  <input type="datetime-local" required className="mt-1 w-full border rounded-xl px-3 py-2" value={windowForm.start_at ? windowForm.start_at.slice(0, 16) : ""} onChange={(e) => setWindowForm((p) => ({ ...p, start_at: e.target.value }))} />
                </label>
                <label className="block">
                  <span className="text-sm text-slate-700">Closing Deadline *</span>
                  <input type="datetime-local" required className="mt-1 w-full border rounded-xl px-3 py-2" value={windowForm.end_at ? windowForm.end_at.slice(0, 16) : ""} onChange={(e) => setWindowForm((p) => ({ ...p, end_at: e.target.value }))} />
                </label>
              </div>
            )}

            {(scheduleIncomplete || scheduleRangeInvalid) && (
              <p className="text-sm text-rose-600">
                {scheduleIncomplete ? "Set both opening and closing dates." : "Opening date must be earlier than the closing deadline."}
              </p>
            )}
            <button type="submit" disabled={scheduleIncomplete || scheduleRangeInvalid} className="portal-btn portal-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed">
              Save Encoding Window
            </button>
          </form>
        </div>
        <div className="portal-card">
          <div className="portal-card-header"><h2 className="text-lg font-semibold">Project Progress Update Window</h2></div>
          <form onSubmit={saveProgressWindow} className="portal-card-body space-y-4">
            <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Current Progress Update Access</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {windowStatusLabel[progressWindowState?.status_code || "schedule_not_configured"] || "Unavailable"}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    {progressWindowState?.message || "Contributor progress updates are closed until an administrator sets a schedule."}
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  progressWindowState?.is_open ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                }`}>
                  {progressWindowState?.is_open ? "Updates Open" : "View-Only Mode"}
                </span>
              </div>
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div><p className="text-xs text-slate-500">Timezone</p><p className="font-medium">Philippine Standard Time (UTC+8)</p></div>
                <div><p className="text-xs text-slate-500">Opening Date</p><p className="font-medium">{formatWindowDate(progressWindowState?.start_at)}</p></div>
                <div><p className="text-xs text-slate-500">Closing Deadline</p><p className="font-medium">{formatWindowDate(progressWindowState?.end_at)}</p></div>
              </div>
            </div>

            <label className="block">
              <span className="text-sm text-slate-700">Progress Update Mode</span>
              <select
                className="mt-1 w-full border rounded-xl px-3 py-2"
                value={progressWindowForm.enabled ? "open" : "closed"}
                onChange={(e) =>
                  setProgressWindowForm((previous) =>
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

            {progressWindowForm.enabled && (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-sm text-slate-700">Opening Date and Time *</span>
                  <input type="datetime-local" required className="mt-1 w-full border rounded-xl px-3 py-2" value={progressWindowForm.start_at ? progressWindowForm.start_at.slice(0, 16) : ""} onChange={(e) => setProgressWindowForm((p) => ({ ...p, start_at: e.target.value }))} />
                </label>
                <label className="block">
                  <span className="text-sm text-slate-700">Closing Deadline *</span>
                  <input type="datetime-local" required className="mt-1 w-full border rounded-xl px-3 py-2" value={progressWindowForm.end_at ? progressWindowForm.end_at.slice(0, 16) : ""} onChange={(e) => setProgressWindowForm((p) => ({ ...p, end_at: e.target.value }))} />
                </label>
              </div>
            )}

            {(progressScheduleIncomplete || progressScheduleRangeInvalid) && (
              <p className="text-sm text-rose-600">
                {progressScheduleIncomplete ? "Set both opening and closing dates." : "Opening date must be earlier than the closing deadline."}
              </p>
            )}
            <button type="submit" disabled={progressScheduleIncomplete || progressScheduleRangeInvalid} className="portal-btn portal-btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed">
              Save Progress Update Window
            </button>
          </form>
        </div>
        </>
      )}

      {activeTab === "operations" && (
        <>
          <div className="portal-card mb-4 portal-table-wrap">
            <div className="portal-card-header"><h2 className="text-lg font-semibold">Password Reset Requests</h2></div>
            {loading ? (
              <div className="portal-card-body text-slate-500">Loading password reset requests...</div>
            ) : resetRequests.length === 0 ? (
              <div className="portal-card-body text-slate-500">No reset requests found.</div>
            ) : (
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th className="hidden md:table-cell">User</th>
                    <th>Status</th>
                    <th className="hidden lg:table-cell">Requested At</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {resetRequests.map((r) => (
                    <tr key={r.id}>
                      <td>{r.email}</td>
                      <td className="hidden md:table-cell">{r.user_username || "-"}</td>
                      <td>
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                          r.status === "approved"
                            ? "bg-emerald-100 text-emerald-700"
                            : r.status === "rejected"
                            ? "bg-rose-100 text-rose-700"
                            : "bg-amber-100 text-amber-700"
                        }`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="hidden lg:table-cell">{new Date(r.created_at).toLocaleString()}</td>
                      <td className="space-x-2">
                        {r.status === "pending" ? (
                          <>
                            <button
                              onClick={() => reviewResetRequest(r.id, "approve")}
                              className={`text-emerald-600 hover:underline ${resetActionLoading[r.id] ? "opacity-50 pointer-events-none" : ""}`}
                            >
                              {resetActionLoading[r.id] ? "Approving..." : "Approve"}
                            </button>
                            <button
                              onClick={() => reviewResetRequest(r.id, "reject")}
                              className={`text-rose-600 hover:underline ${resetActionLoading[r.id] ? "opacity-50 pointer-events-none" : ""}`}
                            >
                              {resetActionLoading[r.id] ? "Rejecting..." : "Reject"}
                            </button>
                          </>
                        ) : (
                          <span className="text-slate-400">Reviewed</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="portal-card mb-4 portal-table-wrap">
            <div className="portal-card-header"><h2 className="text-lg font-semibold">System Users</h2></div>
            {loading ? (
              <div className="portal-card-body text-slate-500">Loading users...</div>
            ) : users.length === 0 ? (
              <div className="portal-card-body text-slate-500">No users found.</div>
            ) : (
              <table className="portal-table">
                <thead>
                  <tr><th>Username</th><th>Email</th><th>Agency</th><th>Role</th><th>Status</th><th>Actions</th></tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td>{u.username}</td>
                      <td>{u.email || "-"}</td>
                      <td>{(u as any).agency || "-"}</td>
                      <td>{labelRole(u.role)}</td>
                      <td>
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${u.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-700"}`}>
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="space-x-2">
                        <button onClick={() => setUserActive(u.id, !u.is_active)} className="text-blue-600 hover:underline">
                          {u.is_active ? "Deactivate" : "Activate"}
                        </button>
                        <button onClick={() => resetUserPassword(u.id)} className="text-indigo-600 hover:underline">Reset Password</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="portal-card mb-4">
            <div className="portal-card-header flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Chatbot Learning</h2>
                <p className="text-xs text-slate-500">
                  Review repeated low-confidence public questions and convert them into approved website knowledge.
                </p>
                <p className="mt-2 w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {chatGapsLoading ? "Loading questions..." : `${chatGaps.length} question${chatGaps.length === 1 ? "" : "s"} shown`}
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
                <button type="button" onClick={loadChatGaps} className="portal-btn portal-btn-ghost">
                  Refresh
                </button>
              </div>
            </div>
            <div className="portal-card-body space-y-4">
              {chatGapsLoading ? (
                <p className="text-sm text-slate-500">Loading chatbot learning signals...</p>
              ) : chatGaps.length === 0 ? (
                <p className="text-sm text-slate-500">No chatbot knowledge gaps found for this filter.</p>
              ) : (
                chatGaps.map((gap) => {
                  const draft = chatGapDrafts[gap.id] || { title: "", summary: "", body: "", tags: "", url: "" };
                  const isExpanded = Boolean(expandedChatGapIds[gap.id]);
                  return (
                    <div key={gap.id} className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                      <div className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700">
                              Asked {gap.count}x
                            </span>
                            <span className="rounded-full bg-slate-200 px-2 py-1 text-xs font-semibold text-slate-700">
                              {gap.language === "tl" ? "Tagalog/Taglish" : "English"}
                            </span>
                            <span className={`rounded-full px-2 py-1 text-xs font-semibold ${
                              gap.status === "approved"
                                ? "bg-emerald-100 text-emerald-700"
                                : gap.status === "rejected"
                                ? "bg-rose-100 text-rose-700"
                                : "bg-blue-100 text-blue-700"
                            }`}>
                              {gap.status}
                            </span>
                            <span className="text-xs text-slate-500">
                              Last asked {new Date(gap.last_asked).toLocaleString()}
                            </span>
                          </div>
                          <p className="mt-2 truncate font-semibold text-slate-900" title={gap.question_sample}>
                            {gap.question_sample}
                          </p>
                          {gap.matched_content_title && (
                            <p className="mt-1 text-xs text-slate-500">Possibly related to: {gap.matched_content_title}</p>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => toggleChatGap(gap.id)}
                          className="portal-btn portal-btn-ghost w-fit"
                          aria-expanded={isExpanded}
                        >
                          {isExpanded ? "Hide details" : gap.status === "pending" ? "Review" : "View details"}
                        </button>
                      </div>

                      {isExpanded && gap.status === "pending" ? (
                        <div className="grid grid-cols-1 gap-3 border-t border-slate-200 bg-slate-50/70 px-4 pb-4 pt-4 xl:grid-cols-2">
                          <label className="block">
                            <span className="text-xs font-semibold text-slate-600">Approved Public Title</span>
                            <input
                              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                              value={draft.title}
                              onChange={(e) => updateChatGapDraft(gap.id, "title", e.target.value)}
                            />
                          </label>
                          <label className="block">
                            <span className="text-xs font-semibold text-slate-600">Source URL</span>
                            <input
                              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                              placeholder="/about-rdc or /contact"
                              value={draft.url}
                              onChange={(e) => updateChatGapDraft(gap.id, "url", e.target.value)}
                            />
                          </label>
                          <label className="block xl:col-span-2">
                            <span className="text-xs font-semibold text-slate-600">Short Summary</span>
                            <input
                              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                              value={draft.summary}
                              onChange={(e) => updateChatGapDraft(gap.id, "summary", e.target.value)}
                            />
                          </label>
                          <label className="block xl:col-span-2">
                            <span className="text-xs font-semibold text-slate-600">Approved Answer / Knowledge Body</span>
                            <textarea
                              className="mt-1 min-h-[96px] w-full rounded-lg border px-3 py-2 text-sm"
                              value={draft.body}
                              onChange={(e) => updateChatGapDraft(gap.id, "body", e.target.value)}
                            />
                          </label>
                          <label className="block xl:col-span-2">
                            <span className="text-xs font-semibold text-slate-600">Tags</span>
                            <input
                              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                              placeholder="dashboard, publications, contact"
                              value={draft.tags}
                              onChange={(e) => updateChatGapDraft(gap.id, "tags", e.target.value)}
                            />
                          </label>
                          <div className="flex flex-wrap gap-2 xl:col-span-2">
                            <button type="button" onClick={() => approveChatGap(gap)} className="portal-btn portal-btn-primary">
                              Approve as Knowledge
                            </button>
                            <button type="button" onClick={() => rejectChatGap(gap)} className="portal-btn portal-btn-ghost text-rose-600">
                              Reject
                            </button>
                          </div>
                        </div>
                      ) : isExpanded ? (
                        <p className="border-t border-slate-200 px-4 pb-4 pt-3 text-sm text-slate-500">
                          Reviewed {gap.reviewed_at ? new Date(gap.reviewed_at).toLocaleString() : ""}{" "}
                          {gap.reviewed_by_name ? `by ${gap.reviewed_by_name}` : ""}
                        </p>
                      ) : null}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          <div className="portal-card portal-table-wrap">
            <div className="portal-card-header flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold">System Audit Log</h2>
                <p className="text-xs text-slate-500">Review historical portal activity, security actions, and project workflow events.</p>
              </div>
              <button type="button" onClick={loadActivity} className="portal-btn portal-btn-ghost">Refresh Log</button>
            </div>
            <div className="portal-card-body border-b border-slate-200 bg-slate-50/60">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <label className="block">
                  <span className="text-xs font-semibold text-slate-600">Role</span>
                  <select
                    className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={activityFilters.role}
                    onChange={(e) => updateActivityFilter("role", e.target.value)}
                  >
                    <option value="">All roles</option>
                    <option value="admin">Admin</option>
                    <option value="validator">Validator</option>
                    <option value="staff">Contributor</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-600">Event</span>
                  <select
                    className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={activityFilters.event}
                    onChange={(e) => updateActivityFilter("event", e.target.value)}
                  >
                    <option value="">All events</option>
                    {Object.keys(eventLabels).map((event) => (
                      <option key={event} value={event}>{eventLabels[event]}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-600">Search User</span>
                  <input
                    className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm bg-white"
                    placeholder="Name, username, or email"
                    value={activityFilters.user}
                    onChange={(e) => updateActivityFilter("user", e.target.value)}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-600">From Date</span>
                  <input
                    type="date"
                    className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={activityFilters.dateFrom}
                    onChange={(e) => updateActivityFilter("dateFrom", e.target.value)}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-600">To Date</span>
                  <input
                    type="date"
                    className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={activityFilters.dateTo}
                    onChange={(e) => updateActivityFilter("dateTo", e.target.value)}
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-600">Rows Per Page</span>
                  <select
                    className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm bg-white"
                    value={activityFilters.limit}
                    onChange={(e) => updateActivityFilter("limit", e.target.value)}
                  >
                    <option value="10">10</option>
                    <option value="20">20</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                  </select>
                </label>
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-slate-500">All matching audit records remain stored in the database.</p>
                <button type="button" onClick={clearActivityFilters} className="portal-btn portal-btn-ghost">Clear Filters</button>
              </div>
            </div>
            {activityLoading ? (
              <div className="portal-card-body text-slate-500">Loading audit records...</div>
            ) : activity.length === 0 ? (
              <div className="portal-card-body text-slate-500">No audit records match the selected filters.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="portal-table portal-table-activity min-w-[940px]">
                  <thead>
                    <tr>
                      <th className="whitespace-nowrap">User</th>
                      <th className="whitespace-nowrap">Role</th>
                      <th className="whitespace-nowrap">Event</th>
                      <th className="hidden lg:table-cell">Project</th>
                      <th className="hidden xl:table-cell">IP / Location</th>
                      <th className="hidden xl:table-cell">Details</th>
                      <th className="whitespace-nowrap">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activity.map((item) => (
                      <tr key={item.id}>
                        <td className="whitespace-nowrap font-medium text-slate-800">
                          {item.full_name || item.username}
                        </td>
                        <td className="whitespace-nowrap">{labelRole(item.role)}</td>
                        <td>
                          <span className={`inline-flex whitespace-nowrap px-2 py-1 rounded-full text-xs font-semibold ${severityClass(item.event)}`}>
                            {eventLabels[item.event] || item.event.replaceAll("_", " ")}
                          </span>
                        </td>
                        <td className="hidden lg:table-cell max-w-[220px] truncate" title={item.project_title || "-"}>
                          {item.project_title || "-"}
                        </td>
                        <td className="hidden xl:table-cell whitespace-nowrap">
                          {[item.ip_address, item.location_hint].filter(Boolean).join(" | ") || "-"}
                        </td>
                        <td className="hidden xl:table-cell text-xs text-slate-500">
                          {item.details && Object.keys(item.details).length > 0 ? (
                            <div className="space-y-1">
                              {buildDetailEntries(item).map(([label, value]) => (
                                <div key={`${item.id}-${label}`}>
                                  <span className="text-slate-500">{label}:</span>{" "}
                                  <span className="text-slate-700">{value}</span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            "-"
                          )}
                        </td>
                        <td className="whitespace-nowrap">{new Date(item.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="portal-card-body flex flex-col gap-3 border-t border-slate-200 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-600">
                Showing <span className="font-semibold">{activityStart}</span>–<span className="font-semibold">{activityEnd}</span> of{" "}
                <span className="font-semibold">{activityTotal}</span> audit records
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="portal-btn portal-btn-ghost"
                  disabled={!hasPreviousActivity || activityLoading}
                  onClick={() => setActivityOffset((prev) => Math.max(0, prev - activityLimit))}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="portal-btn portal-btn-ghost"
                  disabled={!hasNextActivity || activityLoading}
                  onClick={() => setActivityOffset((prev) => prev + activityLimit)}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </PortalLayout>
  );
};

export default UserManagement;
