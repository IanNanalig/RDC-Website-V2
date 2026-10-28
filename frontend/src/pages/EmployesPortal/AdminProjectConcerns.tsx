import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import PortalLayout from "../../components/portal/PortalLayout";
import api from "../../services/api";
import { userDisplayName } from "../../utils/userDisplayName";

type Evidence = {
  id: number;
  filename: string;
  content_type: string;
  extension: string;
  size_bytes: number;
  checksum_sha256: string;
};

type ConcernReport = {
  reference: string;
  project_id: number;
  project_title: string;
  project_agency: string;
  reporting_mode: "anonymous" | "email";
  reporter_email?: string | null;
  category_code: string;
  category_label: string;
  description?: string;
  receiver_delivery_status: string;
  acknowledgement_delivery_status: string;
  receiver_delivery_attempts: number;
  acknowledgement_delivery_attempts: number;
  receiver_sent_at?: string | null;
  acknowledgement_sent_at?: string | null;
  receiver_last_error?: string;
  acknowledgement_last_error?: string;
  evidence_count: number;
  evidence?: Evidence[];
  created_at: string;
};

type PageResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ConcernReport[];
};

const formatBytes = (bytes: number) => bytes >= 1024 * 1024
  ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  : `${Math.max(1, Math.round(bytes / 1024))} KB`;

const statusClass = (value: string) => {
  if (value === "sent") return "bg-emerald-100 text-emerald-700";
  if (value === "failed") return "bg-rose-100 text-rose-700";
  if (value === "not_applicable") return "bg-slate-100 text-slate-600";
  return "bg-amber-100 text-amber-800";
};

const statusLabel = (value: string) => value === "not_applicable"
  ? "Not applicable"
  : value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());

const adminName = () => {
  try {
    return userDisplayName(JSON.parse(localStorage.getItem("user") || "{}"), "Administrator");
  } catch {
    return "Administrator";
  }
};

const AdminProjectConcerns: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [rows, setRows] = useState<ConcernReport[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState("");
  const [delivery, setDelivery] = useState("");
  const [selected, setSelected] = useState<ConcernReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "10" });
    if (search.trim()) params.set("q", search.trim());
    if (mode) params.set("reporting_mode", mode);
    if (delivery) params.set("delivery_status", delivery);
    return params.toString();
  }, [delivery, mode, page, search]);

  const loadList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get(`admin/project-concerns/?${query}`, true) as PageResponse;
      setRows(response.results || []);
      setCount(response.count || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Project concern reports could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [query]);

  const openDetail = useCallback(async (reference: string) => {
    setDetailLoading(true);
    setError("");
    try {
      const response = await api.get(`admin/project-concerns/${encodeURIComponent(reference)}/`, true) as ConcernReport;
      setSelected(response);
      setSearchParams({ reference });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Report details could not be loaded.");
    } finally {
      setDetailLoading(false);
    }
  }, [setSearchParams]);

  useEffect(() => { void loadList(); }, [loadList]);

  useEffect(() => {
    const reference = searchParams.get("reference");
    if (reference && reference !== selected?.reference) void openDetail(reference);
  }, [openDetail, searchParams, selected?.reference]);

  const closeDetail = () => {
    setSelected(null);
    setSearchParams({});
  };

  const retry = async () => {
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await api.post(`admin/project-concerns/${encodeURIComponent(selected.reference)}/retry/`, {}) as ConcernReport;
      setSelected(response);
      setNotice(response.receiver_delivery_status === "sent" ? "Delivery completed successfully." : "The report remains stored and another delivery retry was queued.");
      await loadList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delivery could not be retried.");
    } finally {
      setBusy(false);
    }
  };

  const downloadEvidence = async (evidence: Evidence) => {
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await api.download(`admin/project-concerns/${encodeURIComponent(selected.reference)}/evidence/${evidence.id}/download/`);
      const url = URL.createObjectURL(response.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = response.fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evidence could not be downloaded.");
    } finally {
      setBusy(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(count / 10));
  const retryNeeded = selected && (
    selected.receiver_delivery_status !== "sent"
    || (selected.reporting_mode === "email" && selected.acknowledgement_delivery_status !== "sent")
  );

  return (
    <PortalLayout
      title="Project Concern Reports"
      subtitle="Monitor public report email delivery and securely retrieve supporting evidence"
      role="admin"
      userName={adminName()}
    >
      <div className="space-y-4">
        {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
        {notice && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}

        <section className="portal-card">
          <div className="portal-card-header flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-slate-900">Delivery records</h2>
              <p className="text-sm text-slate-500">This is an operational delivery view, not a case-management or messaging system.</p>
            </div>
            <button type="button" onClick={() => void loadList()} disabled={loading} className="portal-btn portal-btn-ghost disabled:opacity-50">Refresh</button>
          </div>
          <div className="portal-card-body">
            <div className="mb-4 grid gap-3 md:grid-cols-3">
              <label className="block">
                <span className="text-xs font-semibold text-slate-600">Search</span>
                <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Reference, project, agency, category" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-slate-600">Reporting mode</span>
                <select value={mode} onChange={(event) => { setMode(event.target.value); setPage(1); }} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                  <option value="">All modes</option>
                  <option value="anonymous">Anonymous</option>
                  <option value="email">Email-enabled</option>
                </select>
              </label>
              <label className="block">
                <span className="text-xs font-semibold text-slate-600">Receiver delivery</span>
                <select value={delivery} onChange={(event) => { setDelivery(event.target.value); setPage(1); }} className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                  <option value="">All statuses</option>
                  <option value="pending">Pending</option>
                  <option value="sending">Sending</option>
                  <option value="sent">Sent</option>
                  <option value="failed">Failed</option>
                </select>
              </label>
            </div>

            {loading ? (
              <p className="py-10 text-center text-sm text-slate-500">Loading reports...</p>
            ) : rows.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-500">No project concern reports match these filters.</p>
            ) : (
              <>
                <div className="hidden overflow-x-auto md:block">
                  <table className="min-w-full text-left text-sm">
                    <thead className="border-b border-slate-200 text-xs uppercase text-slate-500"><tr><th className="px-3 py-3">Reference / Project</th><th className="px-3 py-3">Mode</th><th className="px-3 py-3">Receiver</th><th className="px-3 py-3">Submitted</th><th className="px-3 py-3 text-right">Action</th></tr></thead>
                    <tbody className="divide-y divide-slate-100">
                      {rows.map((row) => <tr key={row.reference}>
                        <td className="px-3 py-3"><p className="font-mono text-xs font-semibold text-blue-700">{row.reference}</p><p className="mt-1 max-w-sm font-medium text-slate-800">{row.project_title}</p><p className="text-xs text-slate-500">{row.category_label}</p></td>
                        <td className="px-3 py-3 capitalize">{row.reporting_mode === "email" ? "Email-enabled" : "Anonymous"}</td>
                        <td className="px-3 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(row.receiver_delivery_status)}`}>{statusLabel(row.receiver_delivery_status)}</span></td>
                        <td className="px-3 py-3 text-slate-600">{new Date(row.created_at).toLocaleString()}</td>
                        <td className="px-3 py-3 text-right"><button type="button" onClick={() => void openDetail(row.reference)} className="font-semibold text-blue-700">View</button></td>
                      </tr>)}
                    </tbody>
                  </table>
                </div>
                <div className="space-y-3 md:hidden">
                  {rows.map((row) => <button key={row.reference} type="button" onClick={() => void openDetail(row.reference)} className="w-full rounded-xl border border-slate-200 p-4 text-left">
                    <span className="font-mono text-xs font-semibold text-blue-700">{row.reference}</span><span className="mt-1 block font-medium text-slate-900">{row.project_title}</span><span className="mt-2 inline-flex rounded-full px-2 py-1 text-xs font-semibold capitalize bg-slate-100">{row.reporting_mode === "email" ? "Email-enabled" : "Anonymous"}</span><span className={`ml-2 inline-flex rounded-full px-2 py-1 text-xs font-semibold ${statusClass(row.receiver_delivery_status)}`}>{statusLabel(row.receiver_delivery_status)}</span>
                  </button>)}
                </div>
              </>
            )}

            <div className="mt-4 flex items-center justify-between gap-3 text-sm">
              <span className="text-slate-500">{count.toLocaleString()} report{count === 1 ? "" : "s"}</span>
              <div className="flex items-center gap-2"><button type="button" disabled={page <= 1 || loading} onClick={() => setPage((value) => Math.max(1, value - 1))} className="portal-btn portal-btn-ghost disabled:opacity-40">Previous</button><span>Page {page} of {totalPages}</span><button type="button" disabled={page >= totalPages || loading} onClick={() => setPage((value) => value + 1)} className="portal-btn portal-btn-ghost disabled:opacity-40">Next</button></div>
            </div>
          </div>
        </section>
      </div>

      {(selected || detailLoading) && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 p-3" role="dialog" aria-modal="true" aria-labelledby="concern-detail-title">
          <div className="max-h-[94vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white p-5 shadow-xl sm:p-6">
            {detailLoading && !selected ? <p className="py-12 text-center text-slate-500">Loading report details...</p> : selected && <>
              <div className="flex items-start justify-between gap-4"><div><p className="font-mono text-xs font-semibold text-blue-700">{selected.reference}</p><h2 id="concern-detail-title" className="mt-1 text-xl font-bold text-slate-900">{selected.project_title}</h2><p className="mt-1 text-sm text-slate-500">{selected.project_agency || "Agency not specified"}</p></div><button type="button" onClick={closeDetail} className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-300 text-xl" aria-label="Close report details">×</button></div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Category</p><p className="mt-1 font-medium text-slate-800">{selected.category_label}</p></div>
                <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">Reporting mode</p><p className="mt-1 font-medium text-slate-800">{selected.reporting_mode === "email" ? "Email-enabled" : "Anonymous"}</p>{selected.reporter_email && <p className="mt-1 break-all text-sm text-slate-600">{selected.reporter_email}</p>}</div>
              </div>
              <div className="mt-4 rounded-xl border border-slate-200 p-4"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Description</p><p className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-800">{selected.description}</p></div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-200 p-4"><div className="flex items-center justify-between"><span className="font-semibold text-slate-800">Receiving notification</span><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(selected.receiver_delivery_status)}`}>{statusLabel(selected.receiver_delivery_status)}</span></div><p className="mt-2 text-xs text-slate-500">Attempts: {selected.receiver_delivery_attempts}{selected.receiver_sent_at ? ` · Sent ${new Date(selected.receiver_sent_at).toLocaleString()}` : ""}</p>{selected.receiver_last_error && <p className="mt-2 text-xs text-rose-700">{selected.receiver_last_error}</p>}</div>
                <div className="rounded-xl border border-slate-200 p-4"><div className="flex items-center justify-between"><span className="font-semibold text-slate-800">Reporter acknowledgment</span><span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(selected.acknowledgement_delivery_status)}`}>{statusLabel(selected.acknowledgement_delivery_status)}</span></div><p className="mt-2 text-xs text-slate-500">Attempts: {selected.acknowledgement_delivery_attempts}{selected.acknowledgement_sent_at ? ` · Sent ${new Date(selected.acknowledgement_sent_at).toLocaleString()}` : ""}</p>{selected.acknowledgement_last_error && <p className="mt-2 text-xs text-rose-700">{selected.acknowledgement_last_error}</p>}</div>
              </div>
              <div className="mt-4"><h3 className="font-semibold text-slate-900">Supporting evidence</h3><p className="mt-1 text-xs text-amber-700">Files were format-validated but were not malware-scanned.</p>{selected.evidence?.length ? <div className="mt-2 space-y-2">{selected.evidence.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 p-3"><div className="min-w-0"><p className="truncate text-sm font-medium text-slate-800">{item.filename}</p><p className="text-xs text-slate-500">{formatBytes(item.size_bytes)} · {item.extension.toUpperCase()}</p></div><button type="button" disabled={busy} onClick={() => void downloadEvidence(item)} className="portal-btn portal-btn-ghost disabled:opacity-50">Download</button></div>)}</div> : <p className="mt-2 text-sm text-slate-500">No evidence was attached.</p>}</div>
              <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><button type="button" onClick={closeDetail} className="portal-btn portal-btn-ghost">Close</button>{retryNeeded && <button type="button" disabled={busy} onClick={() => void retry()} className="portal-btn portal-btn-primary disabled:opacity-50">{busy ? "Retrying..." : "Retry Email Delivery"}</button>}</div>
            </>}
          </div>
        </div>
      )}
    </PortalLayout>
  );
};

export default AdminProjectConcerns;
