import { useEffect, useMemo, useState } from "react";
import { api } from "../../services/api";

type Option = { value?: string; code?: string; label?: string; name?: string };
type PreviewRow = {
  row: number;
  email: string;
  role: string;
  agency: string;
  status: string;
  reason: string;
};

const statusStyle: Record<string, string> = {
  valid: "bg-emerald-100 text-emerald-800",
  invalid: "bg-rose-100 text-rose-800",
  duplicate: "bg-amber-100 text-amber-800",
  existing_account: "bg-slate-200 text-slate-800",
  pending_invitation: "bg-blue-100 text-blue-800",
};

export default function BatchRegistrationPanel({ onComplete }: { onComplete?: () => void }) {
  const [roles, setRoles] = useState<Option[]>([]);
  const [agencies, setAgencies] = useState<Option[]>([]);
  const [defaultRole, setDefaultRole] = useState("contributor");
  const [defaultAgency, setDefaultAgency] = useState("");
  const [manual, setManual] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [resendPending, setResendPending] = useState(false);
  const [preview, setPreview] = useState<PreviewRow[]>([]);
  const [previewToken, setPreviewToken] = useState("");
  const [busy, setBusy] = useState<"preview" | "send" | "">("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void api.get("admin/users/batch-invitations/options/").then((data) => {
      setRoles(Array.isArray(data?.roles) ? data.roles : []);
      setAgencies(Array.isArray(data?.agencies) ? data.agencies : []);
    }).catch(() => setError("Batch registration options could not be loaded."));
  }, []);

  const validCount = useMemo(() => preview.filter((row) => row.status === "valid").length, [preview]);

  const buildForm = () => {
    const body = new FormData();
    body.set("default_role", defaultRole);
    body.set("default_agency", defaultAgency);
    body.set("resend_pending", String(resendPending));
    if (file) {
      body.set("file", file);
    } else {
      const entries = manual.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
        const [email, role = "", agency = ""] = line.split(",").map((part) => part.trim());
        return { email, role, agency };
      });
      body.set("entries", JSON.stringify(entries));
    }
    return body;
  };

  const runPreview = async () => {
    if (!file && !manual.trim()) {
      setError("Enter at least one email or choose a CSV file.");
      return;
    }
    setBusy("preview");
    setError("");
    setMessage("");
    try {
      const data = await api.postForm("admin/users/batch-invitations/preview/", buildForm());
      setPreview(Array.isArray(data?.rows) ? data.rows : []);
      setPreviewToken(String(data?.preview_token || ""));
    } catch (err) {
      setPreview([]);
      setPreviewToken("");
      setError(err instanceof Error ? err.message : "The batch could not be previewed.");
    } finally {
      setBusy("");
    }
  };

  const sendInvitations = async () => {
    if (!previewToken || !validCount) return;
    setBusy("send");
    setError("");
    try {
      const data = await api.post("admin/users/batch-invitations/send/", { preview_token: previewToken });
      setMessage(`${Number(data?.sent || 0)} invitation(s) sent, ${Number(data?.skipped || 0)} skipped, and ${Number(data?.failed || 0)} failed.`);
      setPreviewToken("");
      onComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The invitations could not be sent.");
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="mt-5 border-t border-slate-200 pt-5">
      <div className="mb-4">
        <h3 className="font-semibold text-slate-900">Batch Registration</h3>
        <p className="mt-1 text-sm text-slate-600">Enter one row per user as <code>email, role, agency</code>, or upload a UTF-8 CSV with those headers. Up to 100 rows are accepted.</p>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <label className="block lg:col-span-2">
          <span className="text-sm text-slate-700">Manual entries</span>
          <textarea value={manual} onChange={(event) => { setManual(event.target.value); setFile(null); setPreview([]); }} rows={5} placeholder={"person@example.com, contributor, DENR\nvalidator@example.com, validator"} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" />
        </label>
        <label className="block lg:col-span-2">
          <span className="text-sm text-slate-700">Or CSV file</span>
          <input type="file" accept=".csv,text/csv" onChange={(event) => { setFile(event.target.files?.[0] || null); setManual(""); setPreview([]); }} className="mt-1 block w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
        </label>
        <label className="block">
          <span className="text-sm text-slate-700">Default role</span>
          <select value={defaultRole} onChange={(event) => setDefaultRole(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2">
            {roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="text-sm text-slate-700">Default contributor agency (optional)</span>
          <select value={defaultAgency} onChange={(event) => setDefaultAgency(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2">
            <option value="">Contributor selects during registration</option>
            {agencies.map((agency) => <option key={agency.code} value={agency.code}>{agency.code} — {agency.name}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm lg:col-span-2">
          <input type="checkbox" checked={resendPending} onChange={(event) => setResendPending(event.target.checked)} />
          Revoke and replace existing unexpired invitations
        </label>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" className="portal-btn portal-btn-ghost" disabled={Boolean(busy)} onClick={runPreview}>{busy === "preview" ? "Checking..." : "Preview Batch"}</button>
        <button type="button" className="portal-btn portal-btn-primary" disabled={Boolean(busy) || !previewToken || validCount === 0} onClick={sendInvitations}>{busy === "send" ? "Sending..." : `Send ${validCount} Valid Invitation${validCount === 1 ? "" : "s"}`}</button>
      </div>
      {error && <p role="alert" className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p>}
      {message && <p className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p>}
      {preview.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
          <table className="portal-table min-w-[760px]">
            <thead><tr><th>Row</th><th>Email</th><th>Role</th><th>Agency</th><th>Result</th><th>Details</th></tr></thead>
            <tbody>{preview.map((row) => <tr key={`${row.row}-${row.email}`}><td>{row.row}</td><td>{row.email || "—"}</td><td>{row.role}</td><td>{row.agency || "User selects"}</td><td><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusStyle[row.status] || "bg-slate-100 text-slate-700"}`}>{row.status.replaceAll("_", " ")}</span></td><td>{row.reason || "Ready to send"}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}
