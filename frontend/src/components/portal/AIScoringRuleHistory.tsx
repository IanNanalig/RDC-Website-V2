import { useEffect, useState, type ReactNode } from "react";
import { cmsApi, type CMSAIRuleHistoryDetail, type CMSAIRuleHistoryEntry } from "../../services/cmsApi";
import { ScoringHistoryPagination } from "./ScoringHistoryPagination";

type RestoreResult = Awaited<ReturnType<typeof cmsApi.restoreAIScoringVersion>>;

const dateLabel = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
};

const settingLabels: Record<string, string> = {
  keyword_dictionaries: "Scoring rules",
  sector_criteria: "Sector outcomes",
  pap_weights: "PAP weights",
  pap_spatial_scores: "PAP spatial scores",
  input_contract: "Scoring inputs",
  label: "Name",
  match_mode: "Matching method",
  context_phrases: "Supporting phrases",
  matching_guidance: "What counts as valid evidence",
  high: "High-priority cutoff",
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const labelFor = (key: string) => {
  if (/^custom_.+_\d+$/.test(key)) return "Custom criterion";
  const words = key.replaceAll("_", " ");
  return settingLabels[key] || words.charAt(0).toUpperCase() + words.slice(1);
};

const recordName = (value: unknown) =>
  isRecord(value) && typeof value.label === "string" ? value.label.trim() : "";

function changeLabel(version: CMSAIRuleHistoryDetail, change: CMSAIRuleHistoryDetail["changes"][number]) {
  let current: unknown = {
    ...(isRecord(version.config) ? version.config : {}),
    input_contract: version.input_contract,
  };
  return change.path.map((part, index) => {
    const changedItemName = index === change.path.length - 1
      ? recordName(change.after) || recordName(change.before)
      : "";
    if (Array.isArray(current)) {
      current = current.find((item) => isRecord(item) && item.key === part);
      return recordName(current) || changedItemName || labelFor(part);
    }
    current = isRecord(current) ? current[part] : undefined;
    return changedItemName || labelFor(part);
  }).join(" / ");
}

function displayValue(value: unknown, setting?: string): ReactNode {
  if (value == null || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (setting === "match_mode") {
    if (value === "contextual") return "Contextual sentence matching";
    if (value === "keyword") return "Keyword matching";
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "None";
    if (value.every((item) => typeof item === "string")) return value.join(", ");
    return <ul className="space-y-2">{value.map((item, index) => (
      <li key={index}>{displayValue(item)}</li>
    ))}</ul>;
  }
  if (isRecord(value)) {
    const fields = Object.entries(value).filter(([key]) => key !== "key");
    if (!fields.length) return "—";
    return (
      <dl className="space-y-2">
        {fields.map(([key, item]) => (
          <div key={key}>
            <dt className="font-medium text-slate-800">{labelFor(key)}</dt>
            <dd className="mt-0.5">{displayValue(item, key)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return String(value);
}

export function AIScoringRuleHistory({ versions, initialTotalPages, activeId, onRestored }: {
  versions: CMSAIRuleHistoryEntry[];
  initialTotalPages: number;
  activeId: number;
  onRestored: (result: RestoreResult) => Promise<void>;
}) {
  const [page, setPage] = useState(1);
  const [entries, setEntries] = useState(versions);
  const [totalPages, setTotalPages] = useState(initialTotalPages);
  const [details, setDetails] = useState<Record<number, CMSAIRuleHistoryDetail>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setPage(1);
    setEntries(versions);
    setDetails({});
    setTotalPages(initialTotalPages);
  }, [versions, initialTotalPages]);

  const run = async (operation: () => Promise<void>) => {
    setLoading(true);
    setError("");
    try {
      await operation();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The scoring history request failed.");
    } finally {
      setLoading(false);
    }
  };

  const inspect = (id: number) => run(async () => {
    const detail = await cmsApi.getAIScoringVersion(id);
    setDetails((current) => ({ ...current, [id]: detail }));
  });

  const restore = (selected: CMSAIRuleHistoryDetail, note: string) => {
    if (!note.trim()) return;
    if (!window.confirm(`Restore ${selected.version}? A compatible configuration becomes a new active version. An incompatible configuration opens as a repair draft.`)) return;
    void run(async () => {
      const result = await cmsApi.restoreAIScoringVersion(selected.id, activeId, note.trim());
      setDetails({});
      setNotes({});
      await onRestored(result);
    });
  };

  const loadPage = (target: number) => void run(async () => {
    const result = await cmsApi.getAIScoringVersions(target);
    setEntries(result.results);
    setPage(result.page);
    setTotalPages(result.total_pages);
    setDetails({});
  });

  return (
    <section className="portal-card overflow-hidden">
      <div className="portal-card-header"><h3 className="font-bold text-slate-900">Rule Version History</h3><p className="text-xs text-slate-500">Old versions remain attached to the analyses they produced.</p></div>
      <div className="portal-card-body space-y-3">
        {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
        {entries.map((rule) => {
          const selected = details[rule.id];
          const note = notes[rule.id] || "";
          return (
            <div key={rule.id} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-slate-800">{rule.version} {rule.is_active && <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">Active</span>}</p>
                  <p className="text-xs text-slate-500">{dateLabel(rule.published_at || rule.created_at)} · {rule.activated_by || "Publisher unavailable"} · {rule.analysis_count} analyses</p>
                  {rule.restored_from_version && <p className="text-xs text-slate-500">Restored from {rule.restored_from_version}</p>}
                </div>
                {selected?.id !== rule.id && <button type="button" disabled={loading} onClick={() => void inspect(rule.id)} className="portal-btn portal-btn-ghost" aria-label={`View version ${rule.version}`}>View changes</button>}
              </div>
              <p className="mt-1 whitespace-pre-wrap text-slate-700">{rule.change_note?.trim() || "Change note unavailable"}</p>
              {selected?.id === rule.id && (
                <div className="space-y-3 rounded-xl border border-blue-200 bg-blue-50 p-4" aria-label="Selected scoring version">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="font-semibold text-slate-900">{selected.version}</h4>
                      <p className="text-sm text-slate-600">{selected.previous_version ? `Changes since ${selected.previous_version}` : "First published version"}</p>
                    </div>
                    <button type="button" onClick={() => setDetails((current) => Object.fromEntries(Object.entries(current).filter(([id]) => Number(id) !== rule.id)))} className="portal-btn portal-btn-ghost">Close details</button>
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-slate-700">{selected.change_note?.trim() || "Change note unavailable"}</p>
                  {selected.previous_version && selected.changes.length === 0 && <p className="text-sm text-slate-600">The configuration matches the preceding version.</p>}
                  {selected.changes.length > 0 && (
                    <table className="w-full table-fixed text-left text-sm">
                      <thead><tr><th>Setting</th><th>Before</th><th>After</th></tr></thead>
                      <tbody>
                        {selected.changes.map((change) => (
                          <tr key={JSON.stringify(change.path)} className="border-t border-blue-100 align-top">
                            <td className="break-words py-2 pr-2">{changeLabel(selected, change)}<span className="block text-xs text-slate-600">{labelFor(change.kind)}</span></td>
                            <td className="whitespace-pre-wrap break-words py-2 pr-2">{displayValue(change.before, change.path.at(-1))}</td>
                            <td className="whitespace-pre-wrap break-words py-2">{displayValue(change.after, change.path.at(-1))}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <details>
                    <summary className="cursor-pointer text-sm font-semibold">Configuration snapshot</summary>
                    <div className="mt-2 max-h-96 overflow-auto break-words rounded bg-white p-3 text-xs">
                      {displayValue({ configuration: selected.config, input_contract: selected.input_contract })}
                    </div>
                  </details>
                  {!selected.is_active && (
                    <div className="space-y-2">
                      <label className="block text-sm font-semibold">Restore change note
                        <textarea className="mt-1 w-full rounded border border-slate-300 p-2 font-normal" maxLength={500} value={note} onChange={(event) => setNotes((current) => ({ ...current, [rule.id]: event.target.value }))} />
                      </label>
                      <button type="button" disabled={loading || !note.trim()} onClick={() => restore(selected, note)} className="portal-btn portal-btn-primary">Restore version</button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        <ScoringHistoryPagination label="Rule version history pages" page={page} totalPages={totalPages} loading={loading} onPage={loadPage} />
      </div>
    </section>
  );
}
