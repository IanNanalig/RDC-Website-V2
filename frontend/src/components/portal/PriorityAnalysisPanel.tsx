import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  document_override?: boolean;
  document_override_rationale?: string;
  adjusted_scores?: Record<string, number>;
  validator_remarks?: Record<string, string>;
  effective_score?: number | string | null;
};

type DocumentAssessment = {
  status: "not_required" | "missing" | "not_processed" | "pending" | "queued" | "processing" | "pass" | "fail" | "failed" | "unavailable" | "stalled";
  summary?: string;
  error_message?: string;
  retry_available?: boolean;
  job?: {
    status: "queued" | "processing" | "completed" | "failed" | "stalled";
    stage: string;
    stage_label: string;
    elapsed_seconds: number;
    error_message?: string;
  } | null;
  collective_sufficient?: boolean;
  document_results?: Array<{
    document_id: number;
    filename: string;
    related: boolean;
    explanation: string;
    citations?: string[];
  }>;
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
    criterion_coverage?: {
      status: "complete" | "incomplete";
      covered_criteria: number;
      total_criteria: number;
      coverage_percent: number;
      covered_subtotal: number;
      possible_total: number;
    };
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
  evaluation?: {
    adjusted_scores: Record<string, number>;
    validator_remarks: Record<string, string>;
    effective_score: number | string;
    regional_effective_score: number | string;
    calculated_priority: string;
  } | null;
  confirmations?: Confirmation[];
  learning_result?: LearningResult | null;
  document_assessment?: DocumentAssessment;
  created_at?: string;
};

type Props = {
  projectId: string;
  revisionId?: string;
  locked?: boolean;
  role: "validator" | "admin";
  developmentSector?: string;
};

type ValidationEligibility = {
  eligible: boolean;
  detail: string;
};

type ProcessingProgress = {
  completedSteps: number;
  label: string;
  detail: string;
  failed?: boolean;
};

const processingPercent = (progress: ProcessingProgress) => Math.max(0, Math.min(100, Math.round((progress.completedSteps / 3) * 100)));

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

const conciseCriterionExplanation = (value?: string) => {
  const plain = plainLanguageExplanation(value)
    .replace(/^Contextual Assessment:\s*/i, "")
    .replace(/^Criterion intent:[\s\S]*?(?=The selected RDP Main Chapter|The project narrative|The scorer found|No context-supported evidence|The RDP Main Chapter|The legacy keyword rule|No relevant wording)/i, "");
  const points = explanationPoints(plain).filter((point) => !/^(?:Criterion intent:|CMS matching guidance:|The rule assigned a raw rating|With a weight of|Evidence was found in these fields:|Evidence cited from the project:|The result is advisory|These matches show)/i.test(point));
  const useful = points.length ? points : explanationPoints(plain);
  const summary = useful.slice(0, /^The validator selected/i.test(useful[0] || "") ? 2 : 1).join(". ");
  return summary ? `${summary.replace(/[.!?]+$/, "")}.` : "See the full explanation for the evidence behind this score.";
};

const CriteriaTable: React.FC<{ title: string; group: string; criteria?: Criterion[]; total?: number; adjustable?: boolean; adjusted?: Record<string, number>; remarks?: Record<string, string>; onAdjust?: (key: string, value: number) => void; onRemark?: (key: string, value: string) => void }> = ({
  title,
  group,
  criteria = [],
  total = 0,
  adjustable,
  adjusted = {},
  remarks = {},
  onAdjust,
  onRemark,
}) => (
  <div className="overflow-x-auto rounded-xl border border-slate-200">
    <div className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800">{title}: {Number(criteria.length ? criteria.reduce((sum, item) => sum + (adjusted[`${group}:${item.key}`] ?? item.raw) * item.weight / 10, 0) : total || 0).toFixed(2)}</div>
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
                <div><input type="number" min={0} max={10} step={1} aria-label={`${item.criterion} raw score`} className="w-20 rounded border border-slate-200 px-2 py-1" value={adjusted[`${group}:${item.key}`] ?? item.raw} onChange={(e) => { const entered = Number(e.target.value); if (Number.isFinite(entered)) onAdjust?.(`${group}:${item.key}`, Math.min(10, Math.max(0, Math.trunc(entered)))); }} /><p className="mt-1 text-slate-500">AI: {item.raw}</p></div>
              ) : <span>{adjusted[`${group}:${item.key}`] ?? item.raw}{adjusted[`${group}:${item.key}`] !== undefined && adjusted[`${group}:${item.key}`] !== item.raw && <span className="block text-slate-500">AI: {item.raw}</span>}</span>}
            </td>
            <td className="px-3 py-2">{item.weight}%</td>
            <td className="px-3 py-2">{Number((adjusted[`${group}:${item.key}`] ?? item.raw) * item.weight / 10).toFixed(2)}</td>
            <td className="px-3 py-2 text-slate-600">
              {plainLanguageExplanation(item.remarks)}
              {item.evidence?.length ? ` Matching words: ${item.evidence.join(", ")}` : ""}
              {adjustable && <textarea aria-label={`${item.criterion} validator remarks`} value={remarks[`${group}:${item.key}`] || ""} onChange={(event) => onRemark?.(`${group}:${item.key}`, event.target.value)} maxLength={2000} rows={2} placeholder="Validator remarks" className="mt-2 w-full rounded border border-slate-200 p-2" />}
              {!adjustable && remarks[`${group}:${item.key}`] && <p className="mt-2 font-medium text-slate-800">Validator: {remarks[`${group}:${item.key}`]}</p>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const PriorityAnalysisPanel: React.FC<Props> = ({ projectId, revisionId, locked = false, role, developmentSector = "" }) => {
  const isSceeed = /sceeed|economic and environment/i.test(developmentSector);
  const [eligible, setEligible] = useState(true);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const initializedAnalysisId = useRef<number | null>(null);
  const [validationEligibility, setValidationEligibility] = useState<ValidationEligibility | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [retryAvailable, setRetryAvailable] = useState(false);
  const [processingProgress, setProcessingProgress] = useState<ProcessingProgress | null>(null);
  const [supplements, setSupplements] = useState<Record<string, string>>({});
  const [adjustedScores, setAdjustedScores] = useState<Record<string, number>>({});
  const [validatorRemarks, setValidatorRemarks] = useState<Record<string, string>>({});
  const [evaluationDirty, setEvaluationDirty] = useState(false);
  const [finalPriority, setFinalPriority] = useState("");
  const [overrideRationale, setOverrideRationale] = useState("");
  const [confirmedFlags, setConfirmedFlags] = useState<string[]>([]);
  const [documentOverride, setDocumentOverride] = useState(false);
  const [documentOverrideRationale, setDocumentOverrideRationale] = useState("");

  const endpointBase = role === "admin" ? "admin/projects" : "validator/projects";

  const load = useCallback(async () => {
    try {
      const response = await api.get(`${endpointBase}/${projectId}/priority-analysis/${revisionId ? `?revision=${revisionId}` : ""}`);
      const list = Array.isArray(response?.analyses) ? response.analyses as Analysis[] : [];
      setEligible(response?.eligible !== false);
      setAnalyses(list);
      setAnalysis(list[0] || null);
      setValidationEligibility(response?.validation_eligibility || null);
    } catch (error) {
      console.error("Failed to load priority analysis:", error);
    }
  }, [endpointBase, projectId, revisionId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!analysis) return;
    if (initializedAnalysisId.current === analysis.id) return;
    initializedAnalysisId.current = analysis.id;
    setSupplements(Object.fromEntries(Object.entries(analysis.supplements || {}).map(([key, value]) => [key, String(value ?? "")])));
    setAdjustedScores(analysis.evaluation?.adjusted_scores || analysis.latest_confirmation?.adjusted_scores || {});
    setValidatorRemarks(analysis.evaluation?.validator_remarks || analysis.latest_confirmation?.validator_remarks || {});
    setEvaluationDirty(false);
    setFinalPriority(normalizePriority(analysis.latest_confirmation?.final_priority || analysis.evaluation?.calculated_priority || analysis.suggested_priority));
    setOverrideRationale(analysis.latest_confirmation?.override_rationale || "");
    setConfirmedFlags([]);
    setDocumentOverride(Boolean(analysis.latest_confirmation?.document_override));
    setDocumentOverrideRationale(analysis.latest_confirmation?.document_override_rationale || "");
  }, [analysis]);

  const run = async () => {
    setBusy(true);
    setNotice("");
    setRetryAvailable(false);
    setProcessingProgress(null);
    try {
      let documentAssessment = await api.get(
        `project-supporting-documents/assessment-status/?project=${projectId}${revisionId ? `&revision=${revisionId}` : ""}`,
        true,
      ) as DocumentAssessment;

      if (documentAssessment.status === "missing") {
        throw new Error("Upload the required supporting documents before running AI Assistant analysis.");
      }

      if (documentAssessment.status !== "not_required" && !["pass", "fail"].includes(documentAssessment.status)) {
        setProcessingProgress({
          completedSteps: 0,
          label: "Step 1 of 3 — Reading supporting documents",
          detail: "The server is extracting text from the uploaded files.",
        });
        documentAssessment = await api.post("project-supporting-documents/process-inline/", {
          project: projectId,
          ...(revisionId ? { revision: revisionId } : {}),
        }) as DocumentAssessment;
        if (["failed", "stalled"].includes(documentAssessment.status)) {
          throw new Error(documentAssessment.job?.error_message || documentAssessment.error_message || documentAssessment.summary || "The uploaded document could not be read for AI analysis.");
        }

        setProcessingProgress({
          completedSteps: 1,
          label: "Step 2 of 3 — Assessing document evidence",
          detail: "The server is checking the extracted evidence with the AI service.",
        });
        documentAssessment = await api.post("project-supporting-documents/assess-inline/", {
          project: projectId,
          ...(revisionId ? { revision: revisionId } : {}),
        }) as DocumentAssessment;
        if (!["pass", "fail"].includes(documentAssessment.status)) {
          throw new Error(documentAssessment.job?.error_message || documentAssessment.error_message || documentAssessment.summary || "The document assessment did not complete. You can retry it.");
        }
      }

      setProcessingProgress({
        completedSteps: 2,
        label: "Step 3 of 3 — Creating priority recommendation",
        detail: "The server is applying the approved scoring rules to this project.",
      });
      const response = await api.post(`validator/projects/${projectId}/priority-analysis/run/`, {
        ...(revisionId ? { revision: revisionId } : {}),
        supplements: isSceeed ? supplements : { ...supplements, sceeedTrack: "" },
      });
      if (response?.processing) {
        throw new Error("The server is still configured for background document processing. Set DOCUMENT_AI_PROCESSING_MODE=inline and redeploy the API.");
      }
      const next = response?.analysis as Analysis;
      if (!next?.id) throw new Error("The AI Assistant did not return a completed analysis.");
      setAnalysis(next);
      setAnalyses((prev) => [next, ...prev.filter((item) => item.id !== next.id)]);
      setProcessingProgress({
        completedSteps: 3,
        label: "Analysis complete",
        detail: "The document assessment and priority recommendation have been saved.",
      });
      setNotice(response?.reused ? "Identical inputs detected. Reused the existing deterministic scorecard." : "Priority analysis completed.");
      await load();
    } catch (error) {
      setRetryAvailable(true);
      const message = error instanceof Error ? error.message : "Failed to run priority analysis.";
      const needsProjectInformation = message.startsWith("Required project or validator input is missing");
      setProcessingProgress((current) => current ? {
        ...current,
        failed: true,
        label: needsProjectInformation ? "Analysis needs required project information" : "AI analysis could not finish",
        detail: needsProjectInformation
          ? `${message} Ask the Contributor to update the listed fields, then run the scorer again.`
          : message,
      } : null);
      setNotice(message);
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
        ...(revisionId ? { revision: revisionId } : {}),
        adjusted_scores: adjustedScores,
        validator_remarks: validatorRemarks,
        final_priority: finalPriority,
        override_rationale: overrideRationale,
        confirmed_flags: confirmedFlags,
        document_override: documentOverride,
        document_override_rationale: documentOverrideRationale,
      }) as Analysis;
      setAnalysis(next);
      setAnalyses((prev) => [next, ...prev.filter((item) => item.id !== next.id)]);
      await load();
      setNotice("Priority analysis confirmed. Validation eligibility has been refreshed.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to confirm priority analysis.");
    } finally {
      setBusy(false);
    }
  };

  const saveEvaluation = async () => {
    if (!analysis) return;
    setBusy(true);
    setNotice("");
    try {
      const next = await api.post(`validator/projects/${projectId}/priority-analysis/${analysis.id}/evaluation/`, {
        ...(revisionId ? { revision: revisionId } : {}),
        adjusted_scores: adjustedScores,
        validator_remarks: validatorRemarks,
      }) as Analysis;
      setAnalysis(next);
      setAnalyses((previous) => [next, ...previous.filter((item) => item.id !== next.id)]);
      setAdjustedScores(next.evaluation?.adjusted_scores || {});
      setValidatorRemarks(next.evaluation?.validator_remarks || {});
      setFinalPriority(normalizePriority(next.evaluation?.calculated_priority));
      setEvaluationDirty(false);
      setNotice("Validator scores and remarks saved.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not save the evaluation.");
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
  const incompleteResult = analysis?.suggested_priority === "incomplete" || missingFacts.length > 0;
  const rationaleRequired = incompleteResult || Boolean(finalPriority && finalPriority !== (analysis?.evaluation?.calculated_priority || analysis?.suggested_priority));
  const documentOverrideRequired = Boolean(
    analysis?.document_assessment
    && !["pass", "not_required"].includes(analysis.document_assessment.status),
  );
  const analysisComplete = Boolean(
    analysis
    && analysis.suggested_priority !== "incomplete"
    && missingFacts.length === 0,
  );
  const history = useMemo(() => analyses.slice(0, 5), [analyses]);
  const learning = analysis?.learning_result;
  const liveBaseScore = [...(analysis?.suggested_scores.pap || []).map((item) => ({ ...item, group: "pap" })), ...(analysis?.suggested_scores.rdp_outcomes || []).map((item) => ({ ...item, group: "rdp" }))]
    .reduce((total, item) => total + (adjustedScores[`${item.group}:${item.key}`] ?? item.raw) * item.weight / 10, 0);

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
        {role === "validator" && validationEligibility && analysis && (
          <p className={`rounded-lg border px-3 py-2 text-sm ${validationEligibility.eligible ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
            {validationEligibility.eligible ? "Priority analysis and confirmation are ready for validation." : validationEligibility.detail}
          </p>
        )}
        {role === "validator" && !locked && (
          <div className="rounded-xl border border-slate-200 p-3">
            <p className="mb-3 text-sm font-semibold text-slate-800">Validator Facts Supplement</p>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <Select label="Readiness Level" value={supplements.readinessLevel || ""} onChange={(value) => setSupplements((prev) => ({ ...prev, readinessLevel: value }))} options={[
                ["completed_documents", "With completed documents such as pre-FS/FS/POW and detailed design, where applicable"],
                ["ongoing_documents", "Ongoing pre-FS/FS/POW and detailed design, where applicable"],
                ["project_profile", "With Comprehensive Project Profile"],
                ["concept_only", "With concept paper/none"],
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
              {isSceeed && <Select label="SCEED Track" value={supplements.sceeedTrack || ""} onChange={(value) => setSupplements((prev) => ({ ...prev, sceeedTrack: value }))} options={[["economic", "Economic"], ["environment", "Environment"]]} />}
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
              <button type="button" onClick={run} disabled={busy} className="portal-btn portal-btn-primary">{busy ? "Analyzing..." : retryAvailable ? "Retry AI Scorer" : "Run AI Scorer"}</button>
            </div>
            {processingProgress && (
              <section className={`mt-3 rounded-xl border p-3 ${processingProgress.failed ? "border-rose-200 bg-rose-50" : "border-blue-200 bg-blue-50"}`} aria-live="polite">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <p className={`font-semibold ${processingProgress.failed ? "text-rose-900" : "text-blue-950"}`}>{processingProgress.label}</p>
                  <span className={`text-xs font-medium ${processingProgress.failed ? "text-rose-800" : "text-blue-800"}`}>{processingPercent(processingProgress)}% of stages complete</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/80" role="progressbar" aria-label="AI document processing progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={processingPercent(processingProgress)}>
                  <div className={`h-full rounded-full transition-all duration-500 ${processingProgress.failed ? "bg-rose-500" : "bg-blue-600"}`} style={{ width: `${processingPercent(processingProgress)}%` }} />
                </div>
                <p className={`mt-2 text-xs ${processingProgress.failed ? "text-rose-800" : "text-blue-800"}`}>{processingProgress.detail}</p>
                <p className={`mt-1 text-xs ${processingProgress.failed ? "text-rose-700" : "text-blue-700"}`}>This shows completed processing stages, not an estimated time or file-byte percentage.</p>
              </section>
            )}
          </div>
        )}

        {notice && <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">{notice}</div>}
        {!analysis ? (
          <p className="text-sm text-slate-500">{role === "validator" ? "Run the scorer to generate the first recommendation." : "No priority analysis has been run yet."}</p>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Base Score</p><p className="mt-1 text-2xl font-bold text-slate-900">{Number(analysis.base_score).toFixed(2)}<span className="text-sm text-slate-500"> / 100</span></p>{analysis.suggested_scores.criterion_coverage && <p className="mt-1 text-xs text-slate-600">Coverage: {analysis.suggested_scores.criterion_coverage.coverage_percent}% · supported subtotal {analysis.suggested_scores.criterion_coverage.covered_subtotal.toFixed(2)}</p>}</div>
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
            {analysis.document_assessment && analysis.document_assessment.status !== "not_required" && (
              <section className={`rounded-xl border p-4 ${analysis.document_assessment.status === "pass" ? "border-emerald-200 bg-emerald-50" : analysis.document_assessment.status === "fail" ? "border-rose-200 bg-rose-50" : "border-amber-200 bg-amber-50"}`}>
                <h3 className="font-semibold text-slate-900">Supporting Document Assessment: {analysis.document_assessment.status === "pass" ? "Pass" : analysis.document_assessment.status === "fail" ? "Fail" : "Unavailable"}</h3>
                <p className="mt-1 text-sm text-slate-700">{analysis.document_assessment.summary || analysis.document_assessment.error_message || "The document assessment could not produce a passing result."}</p>
                {(analysis.document_assessment.document_results || []).map((result) => <div key={result.document_id} className="mt-3 rounded-lg border border-white/80 bg-white p-3 text-sm"><strong>{result.filename}: {result.related ? "Related" : "Unrelated"}</strong><p className="mt-1 text-slate-600">{result.explanation}</p>{result.citations?.length ? <p className="mt-1 text-xs text-slate-500">Evidence: {result.citations.join(" · ")}</p> : null}</div>)}
              </section>
            )}
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
              <details className="group rounded-xl border border-blue-200 bg-blue-50/40 p-4">
                <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-blue-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 [&::-webkit-details-marker]:hidden">Reasoning and Explanation <span className="text-blue-700 transition-transform group-open:rotate-180" aria-hidden="true">⌄</span></summary>
                <div className="mt-3 rounded-lg border border-blue-100 bg-white p-3 text-sm text-slate-700">
                  <p>The AI gave this project <strong>{Number(analysis.base_score).toFixed(2)} out of 100</strong> points and suggested <strong>{priorityLabel(analysis.suggested_priority)}</strong>.</p>
                  {missingFacts.length > 0 && <p className="mt-1">Some required information is missing, so the AI recommendation is incomplete.</p>}
                  <p className="mt-1 text-xs text-slate-500">This explains the AI score; the validator's official decision is shown separately.</p>
                  {scoreReasoning.overall && (
                    <details className="mt-2 text-xs text-slate-600">
                      <summary className="cursor-pointer font-medium text-blue-800">View full score calculation</summary>
                      <p className="mt-2 leading-5">{binaryPriorityText(scoreReasoning.overall)}</p>
                    </details>
                  )}
                </div>
                <div className="mt-3 grid gap-2 lg:grid-cols-2">
                  {(scoreReasoning.criteria || []).map((item) => (
                    <div key={item.key} className="rounded-lg border border-blue-100 bg-white p-3 text-sm">
                      <div className="flex items-start justify-between gap-3">
                        <p className="font-semibold text-slate-800">{item.criterion}</p>
                        <span className="shrink-0 rounded-full bg-blue-100 px-2 py-1 text-xs font-semibold text-blue-800">
                          {Number(item.score || 0).toFixed(2)} / {Number(item.maximum_score || 0).toFixed(2)}
                        </span>
                      </div>
                      <p className="mt-2 leading-5 text-slate-600"><strong className="text-slate-700">Why:</strong> {conciseCriterionExplanation(item.explanation)}</p>
                      <details className="mt-2 text-xs text-slate-600">
                        <summary className="cursor-pointer font-medium text-blue-800">View full explanation and scoring details</summary>
                        <p className="mt-2">Raw rating: {Number(item.raw || 0).toFixed(1)} / 10 · Criterion weight: {Number(item.weight || 0).toFixed(1)} points</p>
                        <ul className="mt-2 list-disc space-y-1 pl-5 leading-5">
                          {explanationPoints(plainLanguageExplanation(item.explanation)).map((point, index) => (
                            <li key={`${index}-${point}`}>{point}</li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  ))}
                </div>
              </details>
            )}
            {scoreRecommendations.length > 0 && (
              <details className="group rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
                <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-emerald-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-600 [&::-webkit-details-marker]:hidden">Recommendations to Improve the Score <span className="text-emerald-700 transition-transform group-open:rotate-180" aria-hidden="true">⌄</span></summary>
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
              </details>
            )}
            {revisionFields.length > 0 && (
              <details className="group rounded-xl border border-amber-200 bg-amber-50/50 p-4">
                <summary className="flex cursor-pointer list-none items-center justify-between font-semibold text-amber-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-600 [&::-webkit-details-marker]:hidden">Fields Needing Review or Revision <span className="text-amber-700 transition-transform group-open:rotate-180" aria-hidden="true">⌄</span></summary>
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
              </details>
            )}
            {missingFacts.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><p className="font-semibold">Missing facts</p><ul className="mt-1 list-disc pl-5">{missingFacts.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            <CriteriaTable title="PAP Criteria" group="pap" criteria={analysis.suggested_scores.pap} total={analysis.suggested_scores.pap_total} adjustable={role === "validator" && !locked && !confirmed} adjusted={adjustedScores} remarks={validatorRemarks} onAdjust={(key, value) => { setAdjustedScores((prev) => ({ ...prev, [key]: value })); setEvaluationDirty(true); }} onRemark={(key, value) => { setValidatorRemarks((prev) => ({ ...prev, [key]: value })); setEvaluationDirty(true); }} />
            <CriteriaTable title={`RDP Outcomes (${analysis.suggested_scores.rdp_track || "Sector"})`} group="rdp" criteria={analysis.suggested_scores.rdp_outcomes} total={analysis.suggested_scores.rdp_total} adjustable={role === "validator" && !locked && !confirmed} adjusted={adjustedScores} remarks={validatorRemarks} onAdjust={(key, value) => { setAdjustedScores((prev) => ({ ...prev, [key]: value })); setEvaluationDirty(true); }} onRemark={(key, value) => { setValidatorRemarks((prev) => ({ ...prev, [key]: value })); setEvaluationDirty(true); }} />
            {analysis.regional_scorecard?.applicable ? <CriteriaTable title="Regional Prioritization" group="regional" criteria={analysis.regional_scorecard.criteria} total={analysis.regional_scorecard.total} adjustable={role === "validator" && !locked && !confirmed} adjusted={adjustedScores} remarks={validatorRemarks} onAdjust={(key, value) => { setAdjustedScores((prev) => ({ ...prev, [key]: value })); setEvaluationDirty(true); }} onRemark={(key, value) => { setValidatorRemarks((prev) => ({ ...prev, [key]: value })); setEvaluationDirty(true); }} /> : <p className="text-sm text-slate-600">{analysis.regional_scorecard?.message}</p>}
            <p className="text-sm font-semibold text-slate-800">Validator base score: {liveBaseScore.toFixed(2)}/100 <span className="font-normal text-slate-500">(AI suggestion: {Number(analysis.base_score).toFixed(2)}/100)</span></p>
            {analysis.evaluation && <p className="text-sm text-slate-700">Saved Validator score: {Number(analysis.evaluation.effective_score).toFixed(2)}/100 · Calculated priority: {priorityLabel(analysis.evaluation.calculated_priority)}</p>}
            {role === "validator" && !locked && !confirmed && <div className="flex justify-end"><button type="button" onClick={saveEvaluation} disabled={busy} className="portal-btn portal-btn-ghost">{evaluationDirty ? "Save Validator Evaluation" : "Save Evaluation"}</button></div>}
            {negativeMatches.length > 0 && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm"><p className="font-semibold text-amber-900">Possible negative-list matches</p>{negativeMatches.map((item) => <label key={item.key} className="mt-2 flex gap-2"><input type="checkbox" disabled={role === "admin" || locked} checked={confirmedFlags.includes(item.key)} onChange={(e) => setConfirmedFlags((prev) => e.target.checked ? [...prev, item.key] : prev.filter((key) => key !== item.key))} /><span>{item.label} {item.evidence?.length ? `(${item.evidence.join(", ")})` : ""}</span></label>)}</div>}
            {(analysis.flags?.risks || []).length > 0 && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-900"><p className="font-semibold">Risk flags</p><ul className="mt-1 list-disc pl-5">{analysis.flags?.risks?.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            {role === "validator" && !locked && !confirmed && (
              <div className="rounded-xl border border-slate-200 p-3 space-y-3">
                <p className="text-sm font-semibold">Validator Confirmation</p>
                {incompleteResult && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                    The AI result is incomplete and cannot be confirmed yet. Supply the missing information and rerun the scorer to produce a reliable Low or High recommendation.
                  </div>
                )}
                <Select label="Final Priority" value={finalPriority} onChange={setFinalPriority} options={[["high", "High Priority"], ["low", "Low Priority"]]} />
                <label className="block"><span className="text-xs font-medium text-slate-600">Override rationale {rationaleRequired ? "(required)" : "(required if final priority differs)"}</span><textarea className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" rows={2} value={overrideRationale} onChange={(e) => setOverrideRationale(e.target.value)} /></label>
                {documentOverrideRequired && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3"><label className="flex items-start gap-2 text-sm font-semibold text-rose-900"><input type="checkbox" checked={documentOverride} onChange={(event) => setDocumentOverride(event.target.checked)} /><span>Override the non-passing supporting-document assessment</span></label><label className="mt-2 block"><span className="text-xs font-medium text-rose-800">Document override rationale (required)</span><textarea className="mt-1 w-full rounded-lg border border-rose-200 px-3 py-2 text-sm" rows={3} value={documentOverrideRationale} onChange={(event) => setDocumentOverrideRationale(event.target.value)} /></label></div>}
                <div className="flex justify-end"><button type="button" onClick={confirm} disabled={busy || evaluationDirty || !analysis.evaluation || incompleteResult || !finalPriority || (rationaleRequired && !overrideRationale.trim()) || (documentOverrideRequired && (!documentOverride || !documentOverrideRationale.trim()))} className="portal-btn portal-btn-primary">{busy ? "Saving..." : "Confirm Priority Analysis"}</button></div>
              </div>
            )}
            {confirmed && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">Official validator decision: <strong>{priorityLabel(confirmed.final_priority)}</strong> (AI result: {priorityLabel(analysis.suggested_priority)}){confirmed.validator_name ? ` by ${confirmed.validator_name}` : ""}{confirmed.created_at ? ` on ${new Date(confirmed.created_at).toLocaleString()}` : ""}.</div>}
            {history.length > 1 && <p className="text-xs text-slate-500">Stored scorecard versions: {history.length}. Identical inputs reuse an existing version.</p>}
          </>
        )}
      </div>
    </div>
  );
};

export default PriorityAnalysisPanel;
