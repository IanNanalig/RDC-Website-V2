import React, { useCallback, useEffect, useMemo, useState } from "react";
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
  // "medium" is accepted only while an older backend deployment or stored response is still in flight.
  final_priority: "high" | "medium" | "low";
  override_rationale?: string;
  validator_name?: string;
  created_at?: string;
};

type GuidanceField = {
  key: string;
  label: string;
  source: "contributor" | "validator";
  reasons?: string[];
  priority?: "required" | "high" | "medium" | "low";
};

type ScoreReasoning = {
  overall?: string;
  criteria?: Array<{
    key: string;
    criterion: string;
    raw: number;
    weight: number;
    score: number;
    maximum_score: number;
    explanation: string;
    evidence?: string[];
  }>;
};

type ScoreRecommendation = {
  key: string;
  criterion: string;
  priority: "required" | "high" | "medium" | "low";
  potential_gain?: number | null;
  scorecard?: "base" | "regional" | "required_input" | "risk" | "eligibility";
  recommendation: string;
  fields?: GuidanceField[];
};

type LearningResult = {
  status: "untrained" | "insufficient_evidence" | "ready";
  advisory: boolean;
  model_version?: string | null;
  dataset_version?: string | null;
  sample_count: number;
  predicted_priority?: "high" | "medium" | "low" | null;
  confidence: number;
  class_probabilities?: Record<string, number>;
  explanation?: {
    summary?: string;
    influential_features?: Array<{ feature: string; contribution: number }>;
    limitations?: string[];
    provider?: string;
    provider_model?: string;
    used_backup?: boolean;
  };
  similar_projects?: Array<{
    project_id: number;
    project_title: string;
    agency: string;
    final_priority: "high" | "medium" | "low";
    similarity: number;
    shared_features?: string[];
    confirmed_at?: string;
    validator_name?: string;
  }>;
  generated_at?: string;
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
    reasoning?: ScoreReasoning;
    recommendations?: ScoreRecommendation[];
    revision_fields?: GuidanceField[];
    ai_provider?: {
      name?: string;
      model?: string;
      primary_model?: string;
      backup_model?: string;
      used_backup?: boolean;
      status?: string;
      mode?: string;
    };
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
  learning_result?: LearningResult | null;
  created_at?: string;
};

type Props = {
  projectId: string;
  role: "validator" | "admin";
  currentSnapshot: Record<string, unknown>;
};

const priorityLabel = (value?: string) => {
  if (value === "high") return "High Priority";
  if (value === "medium" || value === "low") return "Low Priority";
  return "Incomplete";
};

const priorityBadge = (value?: string) => {
  if (value === "high") return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (value === "medium" || value === "low") return "bg-rose-100 text-rose-800 border-rose-200";
  return "bg-slate-100 text-slate-700 border-slate-200";
};

const normalizePriority = (value?: string) => {
  if (value === "high") return "high";
  if (value === "low" || value === "medium") return "low";
  return "";
};

const binaryPriorityText = (value?: string) => String(value || "")
  .replace(/Groq contextual assessment/gi, "Contextual Assessment")
  .replace(/Groq assessment/gi, "Assessment")
  .replace(/medium priority/gi, "low priority");

const featureLabel = (value: string) => (value === "rule_suggested_medium" ? "rule_suggested_low" : value)
  .replace(/^rule_suggested_/, "Rule suggestion: ")
  .replace(/^sector_/, "Sector: ")
  .replaceAll("_", " ")
  .replace(/\b\w/g, (letter) => letter.toUpperCase());

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

const plainLanguageExplanation = (value?: string) => String(value || "")
  .replace(/Groq contextual assessment/gi, "Contextual Assessment")
  .replace(/Groq assessment/gi, "Assessment")
  .replace(/Deterministic text alignment suggestion\./gi, "The suggested rating is based on relevant words found in the project details.")
  .replace(/Detected evidence:/gi, "Matching words found:")
  .replace(
    /No matching outcome evidence was detected in the analyzed project text\./gi,
    "No relevant words for this outcome were found in the project details.",
  );

const explanationPoints = (value?: string) => String(value || "")
  .split(/[.!?]\s+(?=[A-Z0-9])/)
  .map((item) => item.trim())
  .filter(Boolean);

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
            <td className="px-3 py-2 text-slate-600">
              {plainLanguageExplanation(item.remarks)}
              {item.evidence?.length ? ` Matching words: ${item.evidence.join(", ")}` : ""}
            </td>
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

  const load = useCallback(async () => {
    try {
      const response = await api.get(`${endpointBase}/${projectId}/priority-analysis/`);
      const list = Array.isArray(response?.analyses) ? response.analyses as Analysis[] : [];
      setEligible(response?.eligible !== false);
      setAnalyses(list);
      setAnalysis(list[0] || null);
    } catch (error) {
      console.error("Failed to load priority analysis:", error);
    }
  }, [endpointBase, projectId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!analysis) return;
    setSupplements(Object.fromEntries(Object.entries(analysis.supplements || {}).map(([key, value]) => [key, String(value ?? "")])));
    setAdjustedScores({});
    setFinalPriority(normalizePriority(analysis.latest_confirmation?.final_priority || analysis.suggested_priority));
    setOverrideRationale(analysis.latest_confirmation?.override_rationale || "");
    setConfirmedFlags([]);
  }, [analysis]);

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
  const scoreReasoning = analysis?.suggested_scores?.reasoning;
  const scoreRecommendations = analysis?.suggested_scores?.recommendations || [];
  const revisionFields = analysis?.suggested_scores?.revision_fields || [];
  const confirmed = analysis?.latest_confirmation;
  const visiblePriority = confirmed?.final_priority || analysis?.suggested_priority;
  const analysisComplete = Boolean(
    analysis
    && analysis.suggested_priority !== "incomplete"
    && missingFacts.length === 0,
  );
  const history = useMemo(() => analyses.slice(0, 5), [analyses]);
  const learning = analysis?.learning_result;

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
          <p className="text-xs text-slate-500">Versioned guideline score, historical similarity, and controlled learned prediction. Validator confirmation remains required.</p>
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
            {analysis.suggested_scores.ai_provider && (
              <div className={`rounded-xl border px-3 py-2 text-sm ${analysis.suggested_scores.ai_provider.model && analysisComplete ? "border-emerald-200 bg-emerald-50 text-emerald-950" : "border-amber-200 bg-amber-50 text-amber-950"}`}>
                {analysis.suggested_scores.ai_provider.model
                  ? <strong>{analysisComplete ? "Analysis successful" : "Analysis incomplete"}</strong>
                  : <>Groq was unavailable or not configured, so the safe <strong>deterministic fallback</strong> produced this analysis.</>}
              </div>
            )}
            <p className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">{binaryPriorityText(analysis.summary)}</p>
            {learning && (
              <section className="rounded-xl border border-violet-200 bg-violet-50/40 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-violet-950">Historical Context and Similar Projects</h3>
                    <p className="mt-1 text-xs text-violet-800">Advisory context only. The validator remains responsible for the final assessment.</p>
                  </div>
                  {learning.status === "ready" && learning.predicted_priority && <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${priorityBadge(learning.predicted_priority)}`}>Learned: {priorityLabel(learning.predicted_priority)}</span>}
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-700">{binaryPriorityText(learning.explanation?.summary)}</p>
                {learning.status === "ready" && (
                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                    <div className="rounded-lg border border-violet-100 bg-white p-3"><p className="text-xs uppercase text-slate-500">Model version</p><p className="mt-1 font-semibold text-slate-800">Version 1</p></div>
                    <div className="rounded-lg border border-violet-100 bg-white p-3"><p className="text-xs uppercase text-slate-500">Eligible confirmed references</p><p className="mt-1 font-semibold text-slate-800">{learning.sample_count}</p></div>
                    <div className="rounded-lg border border-violet-100 bg-white p-3"><p className="text-xs uppercase text-slate-500">Pattern confidence</p><p className="mt-1 font-semibold text-slate-800">{(Number(learning.confidence || 0) * 100).toFixed(1)}%</p></div>
                  </div>
                )}
                {(learning.explanation?.influential_features || []).length > 0 && <p className="mt-3 text-xs text-slate-600"><strong>Most influential learned inputs:</strong> {(learning.explanation?.influential_features || []).map((item) => featureLabel(item.feature)).join(", ")}</p>}
                {(learning.similar_projects || []).length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-sm font-semibold text-slate-800">Most similar validator-confirmed projects</h4>
                    <div className="mt-2 grid gap-2 lg:grid-cols-3">
                      {(learning.similar_projects || []).map((item) => <div key={item.project_id} className="rounded-lg border border-violet-100 bg-white p-3 text-sm"><div className="flex items-start justify-between gap-2"><p className="font-semibold text-slate-800">{item.project_title}</p><span className="shrink-0 text-xs font-semibold text-violet-700">{(item.similarity * 100).toFixed(1)}%</span></div><p className="mt-1 text-xs text-slate-500">{item.agency || "Agency unavailable"} · Confirmed {priorityLabel(item.final_priority)}</p>{(item.shared_features || []).length > 0 && <p className="mt-2 text-xs text-slate-600">Shared evidence: {(item.shared_features || []).join(", ")}</p>}</div>)}
                    </div>
                    <p className="mt-2 text-xs text-slate-500">Similarity provides context and does not prove that this project should receive the same priority.</p>
                  </div>
                )}
                {(learning.explanation?.limitations || []).filter(Boolean).length > 0 && <ul className="mt-3 list-disc pl-5 text-xs text-slate-500">{(learning.explanation?.limitations || []).filter(Boolean).map((item) => <li key={item}>{item}</li>)}</ul>}
              </section>
            )}
            {scoreReasoning && (
              <section className="rounded-xl border border-blue-200 bg-blue-50/40 p-4">
                <h3 className="font-semibold text-blue-950">Reasoning and Explanation</h3>
                {scoreReasoning.overall && (
                  <div className="mt-3 rounded-lg border border-blue-100 bg-white p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-blue-800">Overall score summary</p>
                    <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-700">
                      {explanationPoints(binaryPriorityText(scoreReasoning.overall)).map((point, index) => (
                        <li key={`${index}-${point}`}>{point}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="mt-3 grid gap-2 lg:grid-cols-2">
                  {(scoreReasoning.criteria || []).map((item) => (
                    <div key={item.key} className="rounded-lg border border-blue-100 bg-white p-3 text-sm">
                      <div className="flex items-start justify-between gap-3">
                        <p className="font-semibold text-slate-800">{item.criterion}</p>
                        <span className="shrink-0 rounded-full bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-800">
                          {Number(item.score || 0).toFixed(2)} / {Number(item.maximum_score || 0).toFixed(2)}
                        </span>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded-md bg-slate-50 px-2.5 py-2">
                          <p className="text-slate-500">Raw rating</p>
                          <p className="mt-0.5 font-semibold text-slate-800">{Number(item.raw || 0).toFixed(1)} / 10</p>
                        </div>
                        <div className="rounded-md bg-slate-50 px-2.5 py-2">
                          <p className="text-slate-500">Criterion weight</p>
                          <p className="mt-0.5 font-semibold text-slate-800">{Number(item.weight || 0).toFixed(1)} points</p>
                        </div>
                      </div>
                      <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Why this score was given</p>
                      <ul className="mt-1.5 list-disc space-y-1.5 pl-5 leading-5 text-slate-600">
                        {explanationPoints(plainLanguageExplanation(item.explanation)).map((point, index) => (
                          <li key={`${index}-${point}`}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {scoreRecommendations.length > 0 && (
              <section className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
                <h3 className="font-semibold text-emerald-950">Recommendations to Improve the Score</h3>
                <p className="mt-1 text-xs text-emerald-800">Only update information that is accurate and supported by project evidence.</p>
                <div className="mt-3 space-y-2">
                  {scoreRecommendations.map((item) => (
                    <div key={`${item.scorecard || "score"}-${item.key}`} className="rounded-lg border border-emerald-100 bg-white p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-slate-800">{item.criterion}</p>
                        {item.priority === "required" && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">Required input</span>}
                        {item.potential_gain !== null && item.potential_gain !== undefined && item.potential_gain > 0 && (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                            Up to {Number(item.potential_gain).toFixed(2)} {item.scorecard === "regional" ? "regional" : "base"} points
                          </span>
                        )}
                      </div>
                      <p className="mt-1 leading-5 text-slate-600">{item.recommendation}</p>
                      {(item.fields || []).length > 0 && (
                        <p className="mt-2 text-xs text-slate-500">
                          Review fields: {(item.fields || []).map((field) => field.label).join(", ")}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}
            {revisionFields.length > 0 && (
              <section className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
                <h3 className="font-semibold text-amber-950">Fields Needing Review or Revision</h3>
                <p className="mt-1 text-xs text-amber-800">These fields support incomplete, low-scoring, or flagged criteria. Validator inputs are not contributor-editable fields.</p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {revisionFields.map((field) => (
                    <div key={`${field.source}-${field.key}`} className="rounded-lg border border-amber-100 bg-white p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-slate-800">{field.label}</p>
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${field.source === "validator" ? "bg-indigo-100 text-indigo-800" : "bg-slate-100 text-slate-700"}`}>
                          {field.source === "validator" ? "Validator input" : "Contributor field"}
                        </span>
                      </div>
                      {(field.reasons || []).length > 0 && <p className="mt-1 text-xs text-slate-500">Needed for: {(field.reasons || []).join(", ")}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}
            {missingFacts.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><p className="font-semibold">Missing facts</p><ul className="mt-1 list-disc pl-5">{missingFacts.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            <CriteriaTable title="PAP Criteria" criteria={analysis.suggested_scores.pap} total={analysis.suggested_scores.pap_total} />
            <CriteriaTable title={`RDP Outcomes (${analysis.suggested_scores.rdp_track || "Sector"})`} criteria={analysis.suggested_scores.rdp_outcomes} total={analysis.suggested_scores.rdp_total} adjustable={role === "validator"} adjusted={adjustedScores} onAdjust={(key, value) => setAdjustedScores((prev) => ({ ...prev, [key]: value }))} />
            {analysis.regional_scorecard?.applicable ? <CriteriaTable title="Regional Prioritization" criteria={analysis.regional_scorecard.criteria} total={analysis.regional_scorecard.total} /> : <p className="text-sm text-slate-600">{analysis.regional_scorecard?.message}</p>}
            {negativeMatches.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm"><p className="font-semibold text-amber-900">Possible negative-list matches</p>{negativeMatches.map((item) => <label key={item.key} className="mt-2 flex gap-2"><input type="checkbox" disabled={role === "admin"} checked={confirmedFlags.includes(item.key)} onChange={(e) => setConfirmedFlags((prev) => e.target.checked ? [...prev, item.key] : prev.filter((key) => key !== item.key))} /><span>{item.label} {item.evidence?.length ? `(${item.evidence.join(", ")})` : ""}</span></label>)}</div>}
            {(analysis.flags?.risks || []).length > 0 && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900"><p className="font-semibold">Risk flags</p><ul className="mt-1 list-disc pl-5">{analysis.flags?.risks?.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            {role === "validator" && (
              <div className="rounded-xl border border-slate-200 p-3 space-y-3">
                <p className="text-sm font-semibold">Validator Confirmation</p>
                <Select label="Final Priority" value={finalPriority} onChange={setFinalPriority} options={[["high", "High Priority"], ["low", "Low Priority"]]} />
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
