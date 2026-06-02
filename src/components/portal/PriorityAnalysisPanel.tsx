import React, { useEffect, useMemo, useState } from "react";
import { api } from "../../services/api";

type Criterion = {
  key: string;
  criterion: string;
  raw: number;
  weight: number;
  score: number;
  remarks: string;
  evidence?: string[];
};

type Confirmation = {
  id: number;
  final_priority: "high" | "medium" | "low";
  override_rationale?: string;
  validator_name?: string;
  created_at?: string;
};

type Analysis = {
  id: number;
  base_score: string | number;
  suggested_priority: "high" | "medium" | "low" | "incomplete";
  summary: string;
  rule_version?: string;
  algorithm_version?: string;
  supplements?: Record<string, unknown>;
  suggested_scores: {
    pap?: Criterion[];
    pap_total?: number;
    rdp_track?: string;
    rdp_outcomes?: Criterion[];
    rdp_total?: number;
    base_total?: number;
    missing_facts?: string[];
  };
  regional_scorecard?: {
    applicable?: boolean;
    total?: number;
    criteria?: Criterion[];
    message?: string;
  };
  flags?: {
    negative_matches?: Array<{ key: string; label: string; evidence?: string[] }>;
    risks?: string[];
  };
  latest_confirmation?: Confirmation | null;
  confirmations?: Confirmation[];
  created_at?: string;
};

type Props = {
  projectId: string;
  role: "validator" | "admin";
  currentSnapshot: Record<string, unknown>;
};

const priorityLabel = (value?: string) => {
  if (value === "high") return "High Priority";
  if (value === "medium") return "Medium Priority";
  if (value === "low") return "Low Priority";
  return "Incomplete";
};

const priorityBadge = (value?: string) => {
  if (value === "high") return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (value === "medium") return "bg-amber-100 text-amber-800 border-amber-200";
  if (value === "low") return "bg-rose-100 text-rose-800 border-rose-200";
  return "bg-slate-100 text-slate-700 border-slate-200";
};

const Select: React.FC<{
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}> = ({ label, value, onChange, options }) => (
  <label className="block">
    <span className="text-xs font-medium text-slate-600">{label}</span>
    <select className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">Choose</option>
      {options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
    </select>
  </label>
);

const CriteriaTable: React.FC<{ title: string; criteria?: Criterion[]; total?: number; adjustable?: boolean; adjusted?: Record<string, number>; onAdjust?: (key: string, value: number) => void }> = ({
  title,
  criteria = [],
  total = 0,
  adjustable,
  adjusted = {},
  onAdjust,
}) => (
  <div className="overflow-x-auto rounded-xl border border-slate-200">
    <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800">{title}: {Number(total || 0).toFixed(2)}</div>
    <table className="w-full min-w-[720px] text-xs">
      <thead className="bg-emerald-50 text-left text-emerald-900">
        <tr><th className="px-3 py-2">Criterion</th><th className="px-3 py-2">Raw</th><th className="px-3 py-2">Weight</th><th className="px-3 py-2">Score</th><th className="px-3 py-2">Remarks</th></tr>
      </thead>
      <tbody>
        {criteria.map((item) => (
          <tr key={item.key} className="border-t border-slate-100 align-top">
            <td className="px-3 py-2 font-medium text-slate-800">{item.criterion}</td>
            <td className="px-3 py-2">
              {adjustable ? (
                <select className="rounded border border-slate-200 px-2 py-1" value={adjusted[item.key] ?? item.raw} onChange={(e) => onAdjust?.(item.key, Number(e.target.value))}>
                  {[0, 3, 5, 8, 10].map((score) => <option key={score} value={score}>{score}</option>)}
                </select>
              ) : item.raw}
            </td>
            <td className="px-3 py-2">{item.weight}%</td>
            <td className="px-3 py-2">{Number(item.score || 0).toFixed(2)}</td>
            <td className="px-3 py-2 text-slate-600">{item.remarks}{item.evidence?.length ? ` Evidence: ${item.evidence.join(", ")}` : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const PriorityAnalysisPanel: React.FC<Props> = ({ projectId, role, currentSnapshot }) => {
  const [eligible, setEligible] = useState(true);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [supplements, setSupplements] = useState<Record<string, string>>({});
  const [adjustedScores, setAdjustedScores] = useState<Record<string, number>>({});
  const [finalPriority, setFinalPriority] = useState("");
  const [overrideRationale, setOverrideRationale] = useState("");
  const [confirmedFlags, setConfirmedFlags] = useState<string[]>([]);

  const endpointBase = role === "admin" ? "admin/projects" : "validator/projects";

  const load = async () => {
    try {
      const response = await api.get(`${endpointBase}/${projectId}/priority-analysis/`);
      const list = Array.isArray(response?.analyses) ? response.analyses as Analysis[] : [];
      setEligible(response?.eligible !== false);
      setAnalyses(list);
      setAnalysis(list[0] || null);
    } catch (error) {
      console.error("Failed to load priority analysis:", error);
    }
  };

  useEffect(() => {
    load();
  }, [projectId, role]);

  useEffect(() => {
    if (!analysis) return;
    setSupplements(Object.fromEntries(Object.entries(analysis.supplements || {}).map(([key, value]) => [key, String(value ?? "")])));
    setAdjustedScores({});
    setFinalPriority(analysis.latest_confirmation?.final_priority || (analysis.suggested_priority === "incomplete" ? "" : analysis.suggested_priority));
    setOverrideRationale(analysis.latest_confirmation?.override_rationale || "");
    setConfirmedFlags([]);
  }, [analysis?.id]);

  const run = async () => {
    setBusy(true);
    setNotice("");
    try {
      const response = await api.post(`validator/projects/${projectId}/priority-analysis/run/`, {
        supplements,
        edited_profile_data: currentSnapshot,
      });
      const next = response?.analysis as Analysis;
      setAnalysis(next);
      setAnalyses((prev) => [next, ...prev.filter((item) => item.id !== next.id)]);
      setNotice(response?.reused ? "Identical inputs detected. Reused the existing deterministic scorecard." : "Priority analysis completed.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to run priority analysis.");
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!analysis) return;
    setBusy(true);
    setNotice("");
    try {
      const next = await api.post(`validator/projects/${projectId}/priority-analysis/${analysis.id}/confirm/`, {
        adjusted_scores: adjustedScores,
        final_priority: finalPriority,
        override_rationale: overrideRationale,
        confirmed_flags: confirmedFlags,
      }) as Analysis;
      setAnalysis(next);
      setAnalyses((prev) => [next, ...prev.filter((item) => item.id !== next.id)]);
      setNotice("Priority analysis confirmed. The current validator copy is eligible for endorsement.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to confirm priority analysis.");
    } finally {
      setBusy(false);
    }
  };

  const negativeMatches = analysis?.flags?.negative_matches || [];
  const missingFacts = analysis?.suggested_scores?.missing_facts || [];
  const confirmed = analysis?.latest_confirmation;
  const visiblePriority = confirmed?.final_priority || analysis?.suggested_priority;
  const history = useMemo(() => analyses.slice(0, 5), [analyses]);

  if (!eligible) {
    return (
      <div className="portal-card p-4 border-slate-200 bg-slate-50">
        <h2 className="font-semibold text-slate-800">AI-Assisted Priority Scorer</h2>
        <p className="mt-1 text-sm text-slate-600">Legacy project: scorer enforcement is not required.</p>
      </div>
    );
  }

  return (
    <div className="portal-card border-emerald-200">
      <div className="portal-card-header flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">AI-Assisted Priority Scorer</h2>
          <p className="text-xs text-slate-500">Local deterministic recommendation. Validator confirmation remains required.</p>
        </div>
        {analysis && <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${priorityBadge(visiblePriority)}`}>{priorityLabel(visiblePriority)}</span>}
      </div>
      <div className="portal-card-body space-y-4">
        {role === "validator" && (
          <div className="rounded-xl border border-slate-200 p-3">
            <p className="mb-3 text-sm font-semibold text-slate-800">Validator Facts Supplement</p>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <Select label="Readiness Level" value={supplements.readinessLevel || ""} onChange={(value) => setSupplements((prev) => ({ ...prev, readinessLevel: value }))} options={[
                ["completed_documents", "Completed supporting documents"],
                ["ongoing_documents", "Ongoing supporting documents"],
                ["project_profile", "Comprehensive project profile"],
                ["concept_only", "Concept paper / none"],
              ]} />
              <Select label="GAD Responsiveness" value={supplements.gadResponsiveness || ""} onChange={(value) => setSupplements((prev) => ({ ...prev, gadResponsiveness: value }))} options={[
                ["gender_responsive", "Gender-responsive"],
                ["gender_sensitive", "Gender-sensitive"],
                ["promising_prospects", "Promising GAD prospects"],
                ["invisible", "GAD invisible"],
              ]} />
              <Select label="Spatial Coverage" value={supplements.spatialCoverageScope || ""} onChange={(value) => setSupplements((prev) => ({ ...prev, spatialCoverageScope: value }))} options={[
                ["specific_lgus", "Specific LGUs"],
                ["region_wide", "Region-wide"],
                ["interregional", "Interregional"],
                ["none", "None"],
              ]} />
              <Select label="SCEED Track (if applicable)" value={supplements.sceeedTrack || ""} onChange={(value) => setSupplements((prev) => ({ ...prev, sceeedTrack: value }))} options={[["economic", "Economic"], ["environment", "Environment"]]} />
              <label className="block"><span className="text-xs font-medium text-slate-600">Estimated Beneficiaries</span><input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" inputMode="numeric" value={supplements.beneficiaryCount || ""} onChange={(e) => setSupplements((prev) => ({ ...prev, beneficiaryCount: e.target.value }))} /></label>
              <label className="block"><span className="text-xs font-medium text-slate-600">Contributed RDP Outcomes</span><input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" type="number" min="0" value={supplements.contributedOutcomeCount || ""} onChange={(e) => setSupplements((prev) => ({ ...prev, contributedOutcomeCount: e.target.value }))} /></label>
              <Select label="Regional Spatial Category" value={supplements.regionalSpatialCategory || ""} onChange={(value) => setSupplements((prev) => ({ ...prev, regionalSpatialCategory: value }))} options={[
                ["interregional", "Interregional"],
                ["region_wide", "Region-wide"],
                ["eight_to_twelve_lgus", "8 to 12 LGUs"],
                ["single_city", "Single city"],
              ]} />
              <label className="block md:col-span-2"><span className="text-xs font-medium text-slate-600">Readiness Evidence Notes</span><input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value={supplements.readinessNotes || ""} onChange={(e) => setSupplements((prev) => ({ ...prev, readinessNotes: e.target.value }))} /></label>
            </div>
            <div className="mt-3 flex justify-end">
              <button type="button" onClick={run} disabled={busy} className="portal-btn portal-btn-primary">{busy ? "Analyzing..." : "Run AI Scorer"}</button>
            </div>
          </div>
        )}

        {notice && <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">{notice}</div>}
        {!analysis ? (
          <p className="text-sm text-slate-500">{role === "validator" ? "Run the scorer to generate the first recommendation." : "No priority analysis has been run yet."}</p>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Base Score</p><p className="mt-1 text-2xl font-bold text-slate-900">{Number(analysis.base_score).toFixed(2)}<span className="text-sm text-slate-500"> / 100</span></p></div>
              <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Suggested</p><p className="mt-1 font-semibold">{priorityLabel(analysis.suggested_priority)}</p></div>
              <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Rule Version</p><p className="mt-1 font-semibold">{analysis.rule_version || "-"}</p></div>
            </div>
            <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{analysis.summary}</p>
            {missingFacts.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><p className="font-semibold">Missing facts</p><ul className="mt-1 list-disc pl-5">{missingFacts.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            <CriteriaTable title="PAP Criteria" criteria={analysis.suggested_scores.pap} total={analysis.suggested_scores.pap_total} />
            <CriteriaTable title={`RDP Outcomes (${analysis.suggested_scores.rdp_track || "Sector"})`} criteria={analysis.suggested_scores.rdp_outcomes} total={analysis.suggested_scores.rdp_total} adjustable={role === "validator"} adjusted={adjustedScores} onAdjust={(key, value) => setAdjustedScores((prev) => ({ ...prev, [key]: value }))} />
            {analysis.regional_scorecard?.applicable ? <CriteriaTable title="Regional Prioritization" criteria={analysis.regional_scorecard.criteria} total={analysis.regional_scorecard.total} /> : <p className="text-sm text-slate-600">{analysis.regional_scorecard?.message}</p>}
            {negativeMatches.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm"><p className="font-semibold text-amber-900">Possible negative-list matches</p>{negativeMatches.map((item) => <label key={item.key} className="mt-2 flex gap-2"><input type="checkbox" disabled={role === "admin"} checked={confirmedFlags.includes(item.key)} onChange={(e) => setConfirmedFlags((prev) => e.target.checked ? [...prev, item.key] : prev.filter((key) => key !== item.key))} /><span>{item.label} {item.evidence?.length ? `(${item.evidence.join(", ")})` : ""}</span></label>)}</div>}
            {(analysis.flags?.risks || []).length > 0 && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900"><p className="font-semibold">Risk flags</p><ul className="mt-1 list-disc pl-5">{analysis.flags?.risks?.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            {role === "validator" && (
              <div className="rounded-xl border border-slate-200 p-3 space-y-3">
                <p className="text-sm font-semibold">Validator Confirmation</p>
                <Select label="Final Priority" value={finalPriority} onChange={setFinalPriority} options={[["high", "High Priority"], ["medium", "Medium Priority"], ["low", "Low Priority"]]} />
                <label className="block"><span className="text-xs font-medium text-slate-600">Override rationale (required if final priority differs)</span><textarea className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" rows={2} value={overrideRationale} onChange={(e) => setOverrideRationale(e.target.value)} /></label>
                <div className="flex justify-end"><button type="button" onClick={confirm} disabled={busy || missingFacts.length > 0 || !finalPriority} className="portal-btn portal-btn-primary">{busy ? "Saving..." : "Confirm Priority Analysis"}</button></div>
              </div>
            )}
            {confirmed && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">Confirmed as <strong>{priorityLabel(confirmed.final_priority)}</strong>{confirmed.validator_name ? ` by ${confirmed.validator_name}` : ""}{confirmed.created_at ? ` on ${new Date(confirmed.created_at).toLocaleString()}` : ""}.</div>}
            {history.length > 1 && <p className="text-xs text-slate-500">Stored scorecard versions: {history.length}. Identical inputs reuse an existing version.</p>}
          </>
        )}
      </div>
    </div>
  );
};

export default PriorityAnalysisPanel;
