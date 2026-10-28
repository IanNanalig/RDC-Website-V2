import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import PortalLayout from "../../components/portal/PortalLayout";
import RefreshButton from "../../components/portal/RefreshButton";
import { api } from "../../services/api";
import { userDisplayName } from "../../utils/userDisplayName";

type PeriodState = {
  enabled: boolean;
  manual_open?: boolean;
  is_open: boolean;
  status_code: string;
  message: string;
  start_at: string;
  end_at: string;
  eligible_project_count: number;
};

const localDateValue = (value?: string) => value ? value.slice(0, 16) : "";
const displayDate = (value?: string) => value ? new Date(value).toLocaleString("en-PH", { timeZone: "Asia/Manila" }) : "Not scheduled";

export default function AdminProjectUpdatePeriod() {
  const user = useMemo(() => JSON.parse(localStorage.getItem("user") || "{}"), []);
  const [state, setState] = useState<PeriodState | null>(null);
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"open" | "schedule" | "close" | "">("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get("progress-update-window/", true);
      setState(data);
      setStartAt(localDateValue(data?.start_at));
      setEndAt(localDateValue(data?.end_at));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The update-period status could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const update = async (action: "open" | "schedule" | "close", event?: FormEvent) => {
    event?.preventDefault();
    if (busy) return;
    if (action === "schedule" && (!startAt || !endAt || new Date(startAt) >= new Date(endAt))) {
      setError("Choose an opening time earlier than the closing time.");
      return;
    }
    const prompt = action === "open"
      ? "Open the Project Update Period now? Eligible contributors will be able to save project updates."
      : action === "close"
        ? "Close the Project Update Period now? Forms already open in a browser will no longer be able to save."
        : "Save this Project Update Period schedule?";
    if (!window.confirm(prompt)) return;
    setBusy(action);
    setError("");
    setNotice("");
    try {
      const data = await api.post("progress-update-window/", {
        action,
        enabled: action !== "close",
        start_at: startAt,
        end_at: endAt,
      });
      setState(data);
      setStartAt(localDateValue(data?.start_at));
      setEndAt(localDateValue(data?.end_at));
      setNotice(action === "open" ? "The update period is open." : action === "close" ? "The update period is closed. The saved schedule was preserved." : "The update schedule was saved.");
      localStorage.setItem("portal_window_changed", String(Date.now()));
      window.dispatchEvent(new CustomEvent("portal:data-changed"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The update period could not be changed.");
    } finally {
      setBusy("");
    }
  };

  return (
    <PortalLayout title="Project Update Period" subtitle="Control when contributors may update eligible validated projects" role="admin" userName={userDisplayName(user, "Administrator")} topActions={<RefreshButton loading={loading} onClick={load} />}>
      {notice && <p className="mb-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
      {error && <p role="alert" className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section className="portal-card">
          <div className="portal-card-header"><h2 className="text-lg font-semibold">Current Update Access</h2></div>
          <div className="portal-card-body space-y-4">
            <div className={`rounded-xl border p-4 ${state?.is_open ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Status</p><p className="mt-1 text-xl font-semibold text-slate-900">{loading ? "Loading..." : state?.is_open ? "Open" : "Closed"}</p><p className="mt-1 text-sm text-slate-700">{state?.message}</p></div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${state?.is_open ? "bg-emerald-200 text-emerald-900" : "bg-amber-200 text-amber-900"}`}>{state?.is_open ? "Contributors may update" : "Updates are read-only"}</span>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">Eligible projects</p><p className="mt-1 text-2xl font-semibold">{state?.eligible_project_count ?? 0}</p></div>
              <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">Scheduled opening</p><p className="mt-1 text-sm font-medium">{displayDate(state?.start_at)}</p></div>
              <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs text-slate-500">Scheduled closing</p><p className="mt-1 text-sm font-medium">{displayDate(state?.end_at)}</p></div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void update("open")} disabled={Boolean(busy) || Boolean(state?.is_open)} className="portal-btn portal-btn-primary disabled:opacity-50">{busy === "open" ? "Opening..." : "Open Update Period"}</button>
              <button type="button" onClick={() => void update("close")} disabled={Boolean(busy) || !state?.is_open} className="portal-btn portal-btn-ghost disabled:opacity-50">{busy === "close" ? "Closing..." : "Close Update Period"}</button>
            </div>
          </div>
        </section>
        <form onSubmit={(event) => void update("schedule", event)} className="portal-card">
          <div className="portal-card-header"><h2 className="text-lg font-semibold">Schedule a Period</h2></div>
          <div className="portal-card-body space-y-3">
            <p className="text-sm text-slate-600">Dates use Philippine Standard Time (UTC+8).</p>
            <label className="block"><span className="text-sm text-slate-700">Opening date and time</span><input type="datetime-local" required value={startAt} onChange={(event) => setStartAt(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /></label>
            <label className="block"><span className="text-sm text-slate-700">Closing date and time</span><input type="datetime-local" required value={endAt} onChange={(event) => setEndAt(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2" /></label>
            <button type="submit" disabled={Boolean(busy)} className="portal-btn portal-btn-primary w-full disabled:opacity-50">{busy === "schedule" ? "Saving..." : "Save Scheduled Period"}</button>
            <p className="text-xs text-slate-500">Closing the period keeps these dates for review or reuse.</p>
          </div>
        </form>
      </div>
    </PortalLayout>
  );
}
