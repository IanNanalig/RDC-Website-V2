import React, { useEffect, useState } from "react";
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

type AccessRequestRow = {
  id: number;
  full_name: string;
  email: string;
  office_unit: string;
  requested_role: "validator" | "contributor";
  status: "pending" | "approved" | "rejected";
};

type ActivityItem = {
  id: number;
  username: string;
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

type AdminUsersTab = "create-account" | "encoding-window" | "operations";

const parseTab = (value: string | null): AdminUsersTab => {
  if (value === "create-account" || value === "encoding-window" || value === "operations") return value;
  return "operations";
};

const UserManagement = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = parseTab(searchParams.get("tab"));
  const [users, setUsers] = useState<UserRow[]>([]);
  const [requests, setRequests] = useState<AccessRequestRow[]>([]);
  const [resetRequests, setResetRequests] = useState<PasswordResetRequestRow[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState("");
  const [toast, setToast] = useState<{ message: string; type: "info" | "success" | "warn" | "error" } | null>(null);
  const [resetActionLoading, setResetActionLoading] = useState<Record<number, boolean>>({});
  const [form, setForm] = useState({
    email: "",
    role: "contributor",
  });
  const [windowForm, setWindowForm] = useState({
    enabled: true,
    start_at: "",
    end_at: "",
  });
  const [activityFilters, setActivityFilters] = useState({
    role: "",
    event: "",
    user: "",
    limit: "10",
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

  const load = async () => {
    setLoading(true);
    try {
      const [usersRes, reqRes, resetRes, winRes] = await Promise.all([
        api.get("admin/users/"),
        api.get("access-requests/"),
        api.get("password-reset-requests/"),
        api.get("encoding-window/"),
      ]);
      setUsers(Array.isArray(usersRes) ? usersRes : []);
      setRequests(Array.isArray(reqRes) ? reqRes : []);
      setResetRequests(Array.isArray(resetRes) ? resetRes : []);
      setWindowForm({
        enabled: Boolean(winRes?.enabled),
        start_at: winRes?.start_at || "",
        end_at: winRes?.end_at || "",
      });
    } catch (error) {
      console.error(error);
      setUsers([]);
      setRequests([]);
      setResetRequests([]);
      setActivity([]);
    } finally {
      setLoading(false);
    }
  };

  const loadActivity = async () => {
    try {
      const params = new URLSearchParams();
      if (activityFilters.role) params.set("role", activityFilters.role);
      if (activityFilters.event) params.set("event", activityFilters.event);
      if (activityFilters.user) params.set("user", activityFilters.user);
      if (activityFilters.limit) params.set("limit", activityFilters.limit);
      const qs = params.toString();
      const data = await api.get(`admin/activity/${qs ? `?${qs}` : ""}`);
      setActivity(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error(error);
      setActivity([]);
    }
  };

  useEffect(() => {
    load();
    loadActivity();
  }, []);

  useEffect(() => {
    loadActivity();
  }, [activityFilters.role, activityFilters.event, activityFilters.user, activityFilters.limit]);

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

  const reviewRequest = async (id: number, action: "approve" | "reject") => {
    setNotice("");
    try {
      const data = await api.post(`access-requests/${id}/${action}/`, {});
      if (action === "approve" && data?.created_user) {
        setNotice(`Approved. Setup link sent to ${data.created_user.email}.`);
      } else setNotice("Request updated.");
      await load();
    } catch {
      setNotice("Failed to update request.");
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

  const saveEncodingWindow = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    try {
      await api.post("encoding-window/", windowForm);
      setNotice("Encoding schedule updated.");
    } catch {
      setNotice("Failed to update encoding schedule.");
    }
  };

  return (
    <PortalLayout
      title="Users & Access Control"
      subtitle="Account provisioning, request approvals, and encoding schedule"
      role="admin"
      userName={displayName}
      topActions={<button onClick={load} className="portal-btn portal-btn-ghost">Refresh</button>}
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
        <div className="portal-card">
          <div className="portal-card-header"><h2 className="text-lg font-semibold">Contributor Encoding Window</h2></div>
          <form onSubmit={saveEncodingWindow} className="portal-card-body grid grid-cols-1 xl:grid-cols-2 gap-3">
            <select
              className="border rounded-xl px-3 py-2"
              value={windowForm.enabled ? "open" : "closed"}
              onChange={(e) => setWindowForm((p) => ({ ...p, enabled: e.target.value === "open" }))}
            >
              <option value="open">Open by schedule</option>
              <option value="closed">Closed (view-only)</option>
            </select>
            <div />
            <input type="datetime-local" className="border rounded-xl px-3 py-2" value={windowForm.start_at ? windowForm.start_at.slice(0, 16) : ""} onChange={(e) => setWindowForm((p) => ({ ...p, start_at: e.target.value }))} />
            <input type="datetime-local" className="border rounded-xl px-3 py-2" value={windowForm.end_at ? windowForm.end_at.slice(0, 16) : ""} onChange={(e) => setWindowForm((p) => ({ ...p, end_at: e.target.value }))} />
            <button type="submit" className="portal-btn portal-btn-primary xl:col-span-2">Save Deadline Window</button>
          </form>
        </div>
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

          <div className="portal-card portal-table-wrap">
            <div className="portal-card-header flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <h2 className="text-lg font-semibold">User Activity Feed</h2>
              <div className="flex flex-wrap gap-2">
                <select
                  className="border rounded-lg px-2 py-1 text-sm"
                  value={activityFilters.role}
                  onChange={(e) => setActivityFilters((p) => ({ ...p, role: e.target.value }))}
                >
                  <option value="">All roles</option>
                  <option value="admin">Admin</option>
                  <option value="validator">Validator</option>
                  <option value="staff">Contributor</option>
                </select>
                <select
                  className="border rounded-lg px-2 py-1 text-sm"
                  value={activityFilters.event}
                  onChange={(e) => setActivityFilters((p) => ({ ...p, event: e.target.value }))}
                >
                  <option value="">All events</option>
                  {Object.keys(eventLabels).map((event) => (
                    <option key={event} value={event}>{eventLabels[event]}</option>
                  ))}
                </select>
                <input
                  className="border rounded-lg px-2 py-1 text-sm"
                  placeholder="Search user"
                  value={activityFilters.user}
                  onChange={(e) => setActivityFilters((p) => ({ ...p, user: e.target.value }))}
                />
                <select
                  className="border rounded-lg px-2 py-1 text-sm"
                  value={activityFilters.limit}
                  onChange={(e) => setActivityFilters((p) => ({ ...p, limit: e.target.value }))}
                >
                  <option value="10">10</option>
                  <option value="15">15</option>
                  <option value="20">20</option>
                </select>
              </div>
            </div>
            {loading ? (
              <div className="portal-card-body text-slate-500">Loading activity feed...</div>
            ) : activity.length === 0 ? (
              <div className="portal-card-body text-slate-500">No recent user activity.</div>
            ) : (
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th className="hidden md:table-cell">Role</th>
                    <th>Event</th>
                    <th className="hidden lg:table-cell">Project</th>
                    <th className="hidden xl:table-cell">IP / Location</th>
                    <th className="hidden xl:table-cell">Details</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {activity.map((item) => (
                    <tr key={item.id}>
                      <td>{item.username}</td>
                      <td className="hidden md:table-cell">{labelRole(item.role)}</td>
                      <td>
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${severityClass(item.event)}`}>
                          {eventLabels[item.event] || item.event.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td className="hidden lg:table-cell">{item.project_title || "-"}</td>
                      <td className="hidden xl:table-cell">
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
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </PortalLayout>
  );
};

export default UserManagement;
