import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../services/api";
import RefreshButton from "./RefreshButton";

type AgencyRow = {
  id: number;
  code: string;
  name: string;
  head_name: string;
  is_active: boolean;
  is_legacy: boolean;
  is_protected: boolean;
  can_archive: boolean;
  dependency_counts: {
    users: number;
    pending_invitations: number;
    primary_projects: number;
    collaborating_projects: number;
  };
  contributor_capacity: {
    limit: number;
    active: number;
    reserved: number;
    used: number;
    available: number;
  };
};

const emptyForm = { code: "", name: "", head_name: "" };

type CodeSuggestion = {
  suggested_code: string;
  source: "official" | "generated";
};

const errorDetail = (error: unknown, fallback: string) => {
  if (!(error instanceof Error) || !error.message) return fallback;
  try {
    const payload = JSON.parse(error.message);
    if (payload?.detail) return String(payload.detail);
    const first = Object.values(payload || {})[0];
    return Array.isArray(first) ? String(first[0]) : String(first || fallback);
  } catch {
    return error.message;
  }
};

const AgencyManagementPanel: React.FC = () => {
  const [agencies, setAgencies] = useState<AgencyRow[]>([]);
  const [archived, setArchived] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busyCode, setBusyCode] = useState("");
  const [editingCode, setEditingCode] = useState("");
  const [originalName, setOriginalName] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [suggestion, setSuggestion] = useState<CodeSuggestion | null>(null);
  const [codeManuallyEdited, setCodeManuallyEdited] = useState(false);
  const [codeReviewed, setCodeReviewed] = useState(false);
  const [codeError, setCodeError] = useState("");
  const lastAutomaticCode = useRef("");
  const [notice, setNotice] = useState<{ tone: "success" | "error" | "warning"; text: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get(`admin/agencies/?archived=${archived ? "1" : "0"}`);
      setAgencies(Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : []);
    } catch (error) {
      setNotice({ tone: "error", text: errorDetail(error, "Failed to load agencies.") });
    } finally {
      setLoading(false);
    }
  }, [archived]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const name = form.name.trim();
    if (!name || archived) {
      setSuggestion(null);
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void api.get(`admin/agencies/suggest-code/?name=${encodeURIComponent(name)}`)
        .then((data) => {
          if (cancelled) return;
          const next: CodeSuggestion = {
            suggested_code: String(data?.suggested_code || ""),
            source: data?.source === "official" ? "official" : "generated",
          };
          setSuggestion(next);
          if (!editingCode && !codeManuallyEdited && next.suggested_code) {
            setForm((current) => {
              const currentCode = current.code.trim();
              if (currentCode && currentCode !== lastAutomaticCode.current) return current;
              lastAutomaticCode.current = next.suggested_code;
              return { ...current, code: next.suggested_code };
            });
          }
        })
        .catch(() => {
          if (!cancelled) setSuggestion(null);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [archived, codeManuallyEdited, editingCode, form.name]);

  const edit = (agency: AgencyRow) => {
    setEditingCode(agency.code);
    setOriginalName(agency.name);
    setForm({ code: agency.code, name: agency.name, head_name: agency.head_name || "" });
    setSuggestion(null);
    setCodeManuallyEdited(false);
    setCodeReviewed(false);
    setCodeError("");
    lastAutomaticCode.current = "";
    setNotice(null);
  };

  const cancel = () => {
    setEditingCode("");
    setOriginalName("");
    setForm(emptyForm);
    setSuggestion(null);
    setCodeManuallyEdited(false);
    setCodeReviewed(false);
    setCodeError("");
    lastAutomaticCode.current = "";
  };

  const normalizedNameChanged = Boolean(
    editingCode && form.name.trim().toLocaleLowerCase() !== originalName.trim().toLocaleLowerCase(),
  );
  const suggestionDiffers = Boolean(
    suggestion?.suggested_code
      && suggestion.suggested_code.toLocaleLowerCase() !== form.code.trim().toLocaleLowerCase(),
  );
  const codeReviewRequired = normalizedNameChanged && suggestionDiffers && !codeReviewed;

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusyCode(editingCode || "new");
    setNotice(null);
    setCodeError("");
    if (codeReviewRequired) {
      setNotice({ tone: "warning", text: "Review the suggested agency code before saving the renamed agency." });
      setBusyCode("");
      return;
    }
    try {
      if (editingCode) {
        await api.patch(`admin/agencies/${encodeURIComponent(editingCode)}/`, {
          code: form.code.trim(),
          name: form.name.trim(),
          head_name: form.head_name.trim(),
        });
        setNotice({ tone: "success", text: "Agency details updated. Existing relationships were preserved." });
      } else {
        await api.post("admin/agencies/", {
          code: form.code.trim(),
          name: form.name.trim(),
          head_name: form.head_name.trim(),
        });
        setNotice({ tone: "success", text: "Agency created." });
      }
      cancel();
      await load();
    } catch (error) {
      if (error instanceof Error && error.message) {
        try {
          const payload = JSON.parse(error.message);
          if (Array.isArray(payload?.code)) setCodeError(String(payload.code[0] || ""));
        } catch {
          // The general error notice below handles non-JSON failures.
        }
      }
      setNotice({ tone: "error", text: errorDetail(error, "Failed to save the agency.") });
    } finally {
      setBusyCode("");
    }
  };

  const archiveAgency = async (agency: AgencyRow) => {
    setBusyCode(agency.code);
    setNotice(null);
    try {
      const preview = await api.get(`admin/agencies/${encodeURIComponent(agency.code)}/dependencies/`);
      const counts = preview?.counts || agency.dependency_counts;
      const message = [
        `Archive ${agency.code} — ${agency.name}?`,
        "",
        `Users: ${counts.users || 0}`,
        `Pending invitations: ${counts.pending_invitations || 0}`,
        `Primary projects: ${counts.primary_projects || 0}`,
        `Collaborating projects: ${counts.collaborating_projects || 0}`,
        "",
        "Existing accounts and project relationships will remain unchanged. The agency will no longer be available for new selections.",
      ].join("\n");
      if (!window.confirm(message)) return;
      await api.post(`admin/agencies/${encodeURIComponent(agency.code)}/archive/`, { confirm: true });
      setNotice({ tone: "success", text: "Agency archived without changing existing users or projects." });
      await load();
    } catch (error) {
      setNotice({ tone: "error", text: errorDetail(error, "Failed to archive the agency.") });
    } finally {
      setBusyCode("");
    }
  };

  const restoreAgency = async (agency: AgencyRow) => {
    setBusyCode(agency.code);
    setNotice(null);
    try {
      await api.post(`admin/agencies/${encodeURIComponent(agency.code)}/restore/`, {});
      setNotice({ tone: "success", text: "Agency restored and available for new selections." });
      await load();
    } catch (error) {
      setNotice({ tone: "error", text: errorDetail(error, "Failed to restore the agency.") });
    } finally {
      setBusyCode("");
    }
  };

  const noticeClass = notice?.tone === "error"
    ? "border-rose-200 bg-rose-50 text-rose-800"
    : notice?.tone === "warning"
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-emerald-200 bg-emerald-50 text-emerald-800";

  return (
    <div className="space-y-4">
      {notice && <div role={notice.tone === "error" ? "alert" : "status"} className={`rounded-xl border px-4 py-3 text-sm ${noticeClass}`}>{notice.text}</div>}
      <div className="portal-card">
        <div className="portal-card-header flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Agency Catalog</h2>
            <p className="text-xs text-slate-500">Names, agency codes, and the current Head of Agency may be updated without changing agency identity.</p>
          </div>
          <div className="flex gap-2">
            <button type="button" className="portal-btn portal-btn-ghost" onClick={() => { setArchived((value) => !value); cancel(); }}>
              {archived ? "View Active" : "View Archived"}
            </button>
            <RefreshButton loading={loading} onClick={load} label="Refresh Agencies" />
          </div>
        </div>
        {!archived && (
          <form onSubmit={save} className="portal-card-body grid grid-cols-1 gap-3 border-b border-slate-200 lg:grid-cols-3">
            <label className="block">
              <span className="text-sm text-slate-700">Agency Code *</span>
              <input
                className={`mt-1 w-full rounded-lg border px-3 py-2 ${codeError ? "border-rose-500" : ""}`}
                value={form.code}
                onChange={(event) => {
                  setForm((row) => ({ ...row, code: event.target.value }));
                  setCodeManuallyEdited(true);
                  setCodeReviewed(true);
                  setCodeError("");
                }}
                required
              />
              {codeError && <span role="alert" className="mt-1 block text-xs text-rose-700">{codeError}</span>}
              {suggestion?.suggested_code && (
                <span className="mt-1 block text-xs text-slate-500">
                  Suggested ({suggestion.source}): <strong>{suggestion.suggested_code}</strong>
                </span>
              )}
            </label>
            <label className="block">
              <span className="text-sm text-slate-700">Agency Name *</span>
              <input
                className="mt-1 w-full rounded-lg border px-3 py-2"
                value={form.name}
                onChange={(event) => {
                  setForm((row) => ({ ...row, name: event.target.value }));
                  if (editingCode) setCodeReviewed(false);
                }}
                required
              />
            </label>
            <label className="block">
              <span className="text-sm text-slate-700">Head of Agency <span className="text-slate-400">(optional)</span></span>
              <input className="mt-1 w-full rounded-lg border px-3 py-2" value={form.head_name} onChange={(event) => setForm((row) => ({ ...row, head_name: event.target.value }))} placeholder="Leave blank if not designated" />
            </label>
            {codeReviewRequired && suggestion && (
              <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 lg:col-span-3">
                <p className="font-semibold">Review the code for the updated agency name.</p>
                <p className="mt-1">Keep <strong>{form.code}</strong> or apply the suggested code <strong>{suggestion.suggested_code}</strong>.</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className="portal-btn portal-btn-primary" onClick={() => {
                    setForm((row) => ({ ...row, code: suggestion.suggested_code }));
                    setCodeReviewed(true);
                    setCodeError("");
                  }}>Use Suggestion</button>
                  <button type="button" className="portal-btn portal-btn-ghost" onClick={() => setCodeReviewed(true)}>Keep Current Code</button>
                </div>
              </div>
            )}
            <div className="flex flex-wrap gap-2 lg:col-span-3">
              <button type="submit" disabled={Boolean(busyCode) || codeReviewRequired} className="portal-btn portal-btn-primary">{editingCode ? "Save Agency" : "Create Agency"}</button>
              {editingCode && <button type="button" className="portal-btn portal-btn-ghost" onClick={cancel}>Cancel</button>}
            </div>
          </form>
        )}
        <div className="portal-card-body overflow-x-auto">
          {loading ? <p className="text-sm text-slate-500">Loading agencies…</p> : agencies.length === 0 ? <p className="text-sm text-slate-500">No {archived ? "archived" : "active"} agencies.</p> : (
            <table className="portal-table min-w-[960px]">
              <thead><tr><th>Code</th><th>Agency</th><th>Current Head</th><th>Contributor Capacity</th><th>Dependencies</th><th>Actions</th></tr></thead>
              <tbody>{agencies.map((agency) => (
                <tr key={agency.id}>
                  <td className="font-semibold">{agency.code}</td>
                  <td>{agency.name}{agency.is_legacy && <span className="ml-2 rounded bg-slate-100 px-2 py-1 text-xs">Legacy</span>}{agency.is_protected && <span className="ml-2 rounded bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-800">Protected</span>}</td>
                  <td>{agency.head_name || <span className="text-slate-400">Not configured</span>}</td>
                  <td className="text-xs text-slate-700">
                    {agency.is_protected ? (
                      <>
                        <span className="font-semibold text-blue-800">Internal agency</span>
                        <span className="block text-slate-500">Not eligible for Contributor assignments</span>
                      </>
                    ) : (
                      <>
                        <span className="font-semibold">{agency.contributor_capacity.available} available</span>
                        <span className="block text-slate-500">
                          {agency.contributor_capacity.active} active + {agency.contributor_capacity.reserved} reserved / {agency.contributor_capacity.limit}
                        </span>
                      </>
                    )}
                  </td>
                  <td className="text-xs text-slate-600">{agency.dependency_counts.users} users · {agency.dependency_counts.primary_projects} primary · {agency.dependency_counts.collaborating_projects} collaborating</td>
                  <td><div className="flex gap-3">
                    {!archived && <button type="button" className="text-sm font-semibold text-blue-600" onClick={() => edit(agency)}>Edit</button>}
                    {!archived && agency.can_archive && <button type="button" disabled={busyCode === agency.code} className="text-sm font-semibold text-amber-700" onClick={() => archiveAgency(agency)}>Archive</button>}
                    {archived && <button type="button" disabled={busyCode === agency.code} className="text-sm font-semibold text-emerald-700" onClick={() => restoreAgency(agency)}>Restore</button>}
                  </div></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgencyManagementPanel;
