import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import PortalLayout from "../../components/portal/PortalLayout";
import { api } from "../../services/api";

type Profile = { id: number; username: string; full_name: string; email: string; role: string; agency: string; agency_head: string; office: string; division: string; position: string; contact_number: string; phone_number: string; date_joined: string; recent_activity: Array<{ id: number; event: string; created_at: string; target_label?: string }> };
type EditRequest = { id: number; user_id: number; user_name: string; user_email: string; status: string; expires_at?: string; created_at: string };
const editableFields = ["full_name", "agency_head", "office", "division", "position", "contact_number", "phone_number"] as const;
const labels: Record<string, string> = { full_name: "Name", agency_head: "Current Head of Agency", office: "Office", division: "Division", position: "Position", contact_number: "Office Contact No.", phone_number: "Phone Number" };

export default function ProfilePage() {
  const { userId } = useParams();
  const stored = localStorage.getItem("user");
  const current = stored ? JSON.parse(stored) as { id?: number; role?: string; full_name?: string; username?: string } : {};
  const isOwn = !userId || Number(userId) === current.id;
  const role = current.role === "admin" || current.role === "validator" || current.role === "content_editor" ? current.role : "employee";
  const [profile, setProfile] = useState<Profile | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [requests, setRequests] = useState<EditRequest[]>([]);
  const [queue, setQueue] = useState<EditRequest[]>([]);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    try {
      const data = await api.get(userId ? `admin/profiles/${userId}/` : "profile/") as Profile;
      setProfile(data);
      setDraft(Object.fromEntries(editableFields.map((field) => [field, data[field] || ""])));
      if (isOwn) setRequests(await api.get("profile/edit-requests/") as EditRequest[]);
      if (role === "admin") setQueue(await api.get("admin/profile-edit-requests/") as EditRequest[]);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Profile could not be loaded."); }
  }, [userId, isOwn, role]);
  useEffect(() => { void load(); }, [load]);
  const activeGrant = requests.find((item) => item.status === "approved" && item.expires_at && new Date(item.expires_at) > new Date());
  const pending = requests.some((item) => item.status === "pending");
  const requestEdit = async () => { setBusy(true); setError(""); try { await api.post("profile/edit-requests/", {}); setNotice("Your request was sent to an administrator."); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Request failed."); } finally { setBusy(false); } };
  const save = async () => { setBusy(true); setError(""); try { await api.patch("profile/", draft); setEditing(false); setNotice("Profile updated. This approval has been used."); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Profile update failed."); } finally { setBusy(false); } };
  const decide = async (id: number, action: "approve" | "reject") => { setBusy(true); setError(""); try { await api.post(`admin/profile-edit-requests/${id}/${action}/`, {}); setNotice(`Request ${action}d.`); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Decision failed."); } finally { setBusy(false); } };

  return <PortalLayout title="User Profile" subtitle={isOwn ? "Review your account details and request a one-time edit" : "Administrator read-only profile view"} role={role} userName={current.full_name || current.username || "User"}>
    {error && <p role="alert" className="mb-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}{notice && <p role="status" className="mb-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p>}
    {!profile ? <div className="portal-card p-5">Loading profile...</div> : <div className="space-y-4">
      <div className="portal-card"><div className="portal-card-body flex flex-wrap items-center gap-4"><div aria-hidden="true" className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-xl font-bold text-blue-700">{(profile.full_name || profile.username).slice(0, 2).toUpperCase()}</div><div><h2 className="text-xl font-semibold">{profile.full_name || profile.username}</h2><p className="text-sm text-slate-600">{profile.email} · {profile.role} · Joined {new Date(profile.date_joined).toLocaleDateString()}</p></div></div></div>
      <div className="portal-card"><div className="portal-card-header flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Profile details</h3>{isOwn && (activeGrant ? <button type="button" onClick={() => setEditing((value) => !value)} className="portal-btn portal-btn-primary">{editing ? "Cancel Edit" : "Edit Profile"}</button> : <button type="button" disabled={pending || busy} onClick={() => void requestEdit()} className="portal-btn portal-btn-ghost disabled:opacity-50">{pending ? "Request Pending" : "Request Profile Edit"}</button>)}</div><div className="portal-card-body grid gap-3 sm:grid-cols-2"><div className="text-sm"><span className="font-medium">Email</span><p>{profile.email}</p></div><div className="text-sm"><span className="font-medium">Role</span><p>{profile.role}</p></div><div className="text-sm"><span className="font-medium">Agency</span><p>{profile.agency || "—"}</p></div>{editableFields.map((field) => <label key={field} className="text-sm"><span className="font-medium">{labels[field]}</span>{editing ? <input value={draft[field] || ""} onChange={(event) => setDraft((value) => ({ ...value, [field]: event.target.value }))} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2" /> : <p>{profile[field] || "—"}</p>}</label>)}{editing && <button type="button" disabled={busy} onClick={() => void save()} className="portal-btn portal-btn-primary sm:col-span-2 sm:justify-self-start">Save Profile</button>}</div></div>
      <div className="portal-card"><div className="portal-card-header"><h3 className="font-semibold">Recent Activity</h3></div><div className="portal-card-body space-y-2">{profile.recent_activity.length ? profile.recent_activity.map((item) => <p key={item.id} className="text-sm">{item.event.replaceAll("_", " ")} · {new Date(item.created_at).toLocaleString()}</p>) : <p className="text-sm text-slate-500">No recent activity.</p>}</div></div>
      {role === "admin" && <div className="portal-card"><div className="portal-card-header"><h3 className="font-semibold">Profile Edit Requests</h3></div><div className="portal-card-body space-y-2">{queue.filter((item) => item.status === "pending").length ? queue.filter((item) => item.status === "pending").map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3"><span className="text-sm">{item.user_name} ({item.user_email}) · {new Date(item.created_at).toLocaleString()}</span><div className="flex gap-2"><button type="button" disabled={busy} onClick={() => void decide(item.id, "reject")} className="portal-btn portal-btn-ghost">Reject</button><button type="button" disabled={busy} onClick={() => void decide(item.id, "approve")} className="portal-btn portal-btn-primary">Approve</button></div></div>) : <p className="text-sm text-slate-500">No pending requests.</p>}</div></div>}
    </div>}
  </PortalLayout>;
}
