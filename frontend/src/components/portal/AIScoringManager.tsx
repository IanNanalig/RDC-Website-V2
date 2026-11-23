import React, { useCallback, useEffect, useState } from "react";
import cmsApi, {
  type CMSAIOutcomeRule,
  type CMSAIRuleConfig,
  type CMSAIRuleSet,
  type CMSAIScoringWorkspace,
} from "../../services/cmsApi";
import { AIScoringRuleHistory } from "./AIScoringRuleHistory";
import { ScoringHistoryPagination } from "./ScoringHistoryPagination";

type Props = { mode: "admin" | "editor" };

const sectorLabels: Record<string, string> = {
  infrastructure: "Infrastructure",
  social: "Social",
  economic: "Economic",
  environment: "Environment",
  financial_admin: "Financial and Administrative",
};

const defaultContextPhrases = [
  "improve", "increase", "expand", "provide", "strengthen", "reduce", "protect",
  "develop", "upgrade", "enhance", "support", "deliver", "implement", "restore",
  "modernize", "promote", "ensure", "construct", "build", "rehabilitate", "establish",
];

const cloneConfig = (value: CMSAIRuleConfig) => JSON.parse(JSON.stringify(value)) as CMSAIRuleConfig;

const prepareContextualConfig = (value: CMSAIRuleConfig) => {
  const next = cloneConfig(value);
  const outcomeRules = [
    ...next.keyword_dictionaries.common_outcomes,
    ...Object.values(next.sector_criteria).flat(),
  ];
  outcomeRules.forEach((rule) => {
    rule.match_mode = "contextual";
  });
  return next;
};

const errorDetail = (error: unknown, fallback: string) => {
  if (!(error instanceof Error) || !error.message) return fallback;
  try {
    const parsed = JSON.parse(error.message) as { detail?: string };
    return parsed.detail || fallback;
  } catch {
    return error.message.length < 300 ? error.message : fallback;
  }
};

const formatDate = (value?: string) => {
  if (!value) return "Unknown";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "Unknown" : parsed.toLocaleString();
};

const priorityLabel = (value: string) => {
  if (value === "high") return "High";
  if (value === "medium" || value === "low") return "Low";
  return value || "Unknown";
};

const withinRange = (value: number, min: number, max = Infinity) =>
  Number.isFinite(value) && value >= min && value <= max;

const regionalBandDefinitions = {
  cost: { title: "Total Regional Project Cost", keys: ["at_least_5b", "over_3b", "over_1b", "over_500m"] },
  outcome_contribution: { title: "RDP Sectoral Outcome Contribution", keys: ["at_least_7", "at_least_5", "at_least_3", "at_least_2", "at_least_1"] },
  beneficiaries: { title: "Magnitude of Beneficiaries", keys: ["over_3m", "over_1m", "at_least_1"] },
} as const;
const spatialLabels = {
  interregional: "Interregional", region_wide: "Region-wide",
  eight_to_twelve_lgus: "8–12 LGUs", single_city: "Single city",
} as const;
const outcomeRatingLabels = {
  chapter_and_two_keywords: "Chapter + 2 valid matches",
  chapter_or_three_keywords: "Chapter + context or 3 matches",
  one_keyword: "At least 1 valid match",
  no_keywords: "No valid evidence",
} as const;
const papScaleOrder = {
  readiness: ["completed_documents", "ongoing_documents", "project_profile", "concept_only"],
  gad: ["gender_responsive", "gender_sensitive", "promising_prospects", "invisible"],
} as const;
type RegionalBandGroup = keyof typeof regionalBandDefinitions;
const regionalNumber = new Intl.NumberFormat("en-PH", { maximumFractionDigits: 20 });

const regionalBandLabel = (group: RegionalBandGroup, key: string, value: number) => {
  const operator = key.startsWith("at_least_") ? "At least" : "More than";
  if (!Number.isFinite(value)) return `${operator}: enter a threshold`;
  const quantity = regionalNumber.format(value);
  if (group === "cost") return `${operator} PHP ${quantity}`;
  const unit = group === "outcome_contribution"
    ? (value === 1 ? "outcome" : "outcomes")
    : (value === 1 ? "beneficiary" : "beneficiaries");
  return `${operator} ${quantity} ${unit}`;
};

const bandLevels = (keys: readonly string[]): Record<string, string> =>
  Object.fromEntries(keys.map((key, index) => [key, `Level ${keys.length - index}`]));

const papSpatialLabels = {
  wide_coverage: "Region-wide or interregional",
  six_to_twelve_lgus: "6–12 cities/municipalities",
  one_to_five_lgus: "1–5 cities/municipalities",
  none: "None",
} as const;
const papSpatialDefaults = { wide_coverage: 10, six_to_twelve_lgus: 6, one_to_five_lgus: 3, none: 0 };

const collectRankingErrors = (config: CMSAIRuleConfig) => {
  const errors: Record<RegionalBandGroup | "spatial_coverage" | "pap_spatial" | "outcome_rating" | keyof typeof papScaleOrder, string[]> = {
    cost: [], spatial_coverage: [], outcome_contribution: [], beneficiaries: [],
    readiness: [], gad: [], outcome_rating: [], pap_spatial: [],
  };
  const regional = config.thresholds.regional_criteria;
  const rules = config.keyword_dictionaries;
  const check = (group: keyof typeof errors, title: string, labels: Record<string, string>, values: Record<string, number>) => {
    const keys = Object.keys(labels);
    for (let index = 1; index < keys.length; index++) {
      const [higher, lower] = [keys[index - 1], keys[index]];
      if (Number.isFinite(values[higher]) && Number.isFinite(values[lower]) && values[higher] <= values[lower]) {
        errors[group].push(`${title}: ${labels[higher]} (${values[higher]}) must be greater than ${labels[lower]} (${values[lower]}).`);
      }
    }
  };
  for (const group of Object.keys(regionalBandDefinitions) as RegionalBandGroup[]) {
    const { title, keys } = regionalBandDefinitions[group];
    const labels = bandLevels(keys);
    if (!Object.values(regional[group].thresholds).every((value) => withinRange(value, 0))) {
      errors[group].push(`${title} thresholds must be valid numbers of at least 0.`);
    }
    check(group, `${title} thresholds`, labels, regional[group].thresholds);
    check(group, `${title} scores`, { ...labels, otherwise: "Otherwise" }, regional[group].scores);
  }
  const eligibilityCutoff = config.thresholds.regional_project_cost;
  if (withinRange(eligibilityCutoff, 0) && Object.values(regional.cost.thresholds).some(
    (threshold) => withinRange(threshold, 0) && threshold < eligibilityCutoff,
  )) {
    errors.cost.push(`Cost bands must be at least the regional eligibility cutoff of PHP ${regionalNumber.format(eligibilityCutoff)}.`);
  }
  check("spatial_coverage", "Regional spatial coverage scores", spatialLabels, regional.spatial_coverage.scores);
  check("pap_spatial", "PAP Spatial Coverage scores", papSpatialLabels, config.thresholds.pap_spatial_scores || papSpatialDefaults);
  check("outcome_rating", "Text-matching scores", outcomeRatingLabels, rules.outcome_rating);
  for (const group of ["readiness", "gad"] as const) {
    const labels = Object.fromEntries(papScaleOrder[group].map((key) => [key, key.replaceAll("_", " ")]));
    const values = Object.fromEntries(rules[group].map((row) => [row.key, row.raw]));
    const title = group === "readiness" ? "Readiness scores" : "GAD responsiveness scores";
    if (Object.keys(values).length !== Object.keys(labels).length || Object.keys(labels).some((key) => !(key in values))) {
      errors[group].push(`${title} must contain each supported level exactly once.`);
    } else {
      check(group, title, labels, values);
    }
  }
  return errors;
};

const validWeight = (weight: number) => Number.isInteger(weight) && withinRange(weight, 1, 100);

const scoringLimits = (config: CMSAIRuleConfig) => {
  const { thresholds, keyword_dictionaries: rules, sector_criteria: sectors } = config;
  const sharedWeights = [
    ...Object.values(thresholds.pap_weights),
    ...rules.common_outcomes.map((rule) => rule.weight),
  ];
  const rawScores = [
    ...Object.values(rules.outcome_rating),
    ...Object.values(thresholds.pap_spatial_scores || papSpatialDefaults),
    ...[...rules.readiness, ...rules.gad].map((rule) => rule.raw),
    ...Object.values(thresholds.regional_criteria).flatMap((criterion) => Object.values(criterion.scores)),
  ];
  const sectorWeightTotals: Record<string, number> = {};
  let invalid = !sharedWeights.every(validWeight)
    || !withinRange(thresholds.high, 1, 100)
    || !withinRange(thresholds.regional_project_cost, 0)
    || !rawScores.every((score) => withinRange(score, 0, 10));
  for (const [sector, outcomes] of Object.entries(sectors)) {
    const outcomeWeights = outcomes.map((rule) => rule.weight);
    if (!outcomeWeights.every(validWeight)) invalid = true;
    const weights = [...sharedWeights, ...outcomeWeights];
    const total = weights.reduce((sum, weight) => sum + weight, 0);
    if (weights.every(validWeight) && total !== 100) {
      sectorWeightTotals[sector] = total;
      invalid = true;
    }
  }
  return { invalid, sectorWeightTotals };
};

const hasScoringErrors = (config: CMSAIRuleConfig) =>
  scoringLimits(config).invalid || Object.values(collectRankingErrors(config)).some((errors) => errors.length > 0);

const CriterionWarnings = ({ errors }: { errors: string[] }) => errors.length ? (
  <ul className="mt-2 space-y-1 text-xs text-rose-700" aria-live="polite">
    {errors.map((error) => <li key={error}>{error}</li>)}
  </ul>
) : null;

const NumberInput = ({
  label,
  value,
  disabled,
  onChange,
  min = 0,
  max,
  wholeWeight = false,
  alignLabel = false,
}: {
  label: string;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  wholeWeight?: boolean;
  alignLabel?: boolean;
}) => {
  const valid = wholeWeight ? validWeight(value) : withinRange(value, min, max);
  return (
    <label className="block">
      <span className={`text-xs font-medium text-slate-600 ${alignLabel ? "block break-words leading-4 sm:min-h-8" : ""}`}>{label}</span>
      <input
        type="number"
        min={wholeWeight ? 1 : min}
        max={wholeWeight ? 100 : max}
        step={wholeWeight ? 1 : "any"}
        disabled={disabled}
        aria-invalid={!valid}
        value={Number.isFinite(value) ? value : ""}
        onChange={(event) => onChange(event.target.valueAsNumber)}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
      />
      {!valid && <span className="mt-1 block text-xs text-rose-700">
        {wholeWeight
          ? "Enter a whole-number weight from 1 to 100."
          : max === undefined ? `Enter a number of at least ${min}.` : `Enter a number from ${min} to ${max}.`}
      </span>}
    </label>
  );
};

const OutcomeRuleEditor = ({
  title,
  rules,
  disabled,
  onChange,
}: {
  title: string;
  rules: CMSAIOutcomeRule[];
  disabled: boolean;
  onChange: (rules: CMSAIOutcomeRule[]) => void;
}) => {
  const update = (index: number, patch: Partial<CMSAIOutcomeRule>) => {
    onChange(rules.map((rule, ruleIndex) => ruleIndex === index ? { ...rule, ...patch } : rule));
  };
  const add = () => {
    const key = `custom_${title.toLowerCase().replace(/[^a-z0-9]+/g, "_")}_${Date.now()}`;
    onChange([...rules, {
      key,
      label: "New outcome criterion",
      weight: 0,
      keywords: ["new keyword"],
      description: "Explain what project outcome this criterion is intended to measure.",
      matching_guidance: "Explain what the project sentence must demonstrate before a matching term counts as evidence.",
      match_mode: "contextual",
      context_phrases: defaultContextPhrases,
    }]);
  };
  return (
    <details className="rounded-xl border border-slate-200 bg-white" open={title === "Common outcomes"}>
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-800">
        {title} <span className="font-normal text-slate-500">({rules.reduce((sum, rule) => sum + Number(rule.weight || 0), 0)} points)</span>
        {rules.some((rule) => !validWeight(rule.weight)) && (
          <span className="mt-1 block text-xs font-normal text-rose-700">Check the highlighted criterion weights.</span>
        )}
      </summary>
      <div className="space-y-3 border-t border-slate-100 p-4">
        {rules.map((rule, index) => (
          <div key={rule.key} className="rounded-lg border border-slate-200 p-3">
            <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_120px]">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Criterion label</span>
                <input disabled={disabled} value={rule.label} onChange={(event) => update(index, { label: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />
              </label>
              <NumberInput label="Weight" value={rule.weight} wholeWeight disabled={disabled} onChange={(weight) => update(index, { weight })} />
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">What this criterion measures</span>
                <textarea rows={3} disabled={disabled} value={rule.description || ""} onChange={(event) => update(index, { description: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" placeholder="Briefly explain the intended outcome and what the project should contribute." />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-slate-600">What counts as valid evidence</span>
                <textarea rows={3} disabled={disabled} value={rule.matching_guidance || ""} onChange={(event) => update(index, { matching_guidance: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" placeholder="Explain how a sentence must connect the terms to an activity, output, beneficiary, or result." />
              </label>
            </div>
            <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
              <span className="text-xs font-medium text-slate-600">Matching method</span>
              <p className="mt-0.5 text-sm font-semibold text-blue-900">
                {rule.match_mode === "contextual" || !disabled
                  ? "Contextual sentence match"
                  : "Keyword presence only (historical active version)"}
              </p>
              <p className="mt-1 text-xs text-slate-600">
                {rule.match_mode === "contextual" || !disabled
                  ? "A topic word counts only when the same sentence also explains a relevant action, output, beneficiary effect, or result."
                  : "This older version is preserved for audit history. An administrator can replace it by activating a contextual-only rule version."}
              </p>
            </div>
            <label className="mt-3 block">
              <span className="text-xs font-medium text-slate-600">Primary matching words or phrases, separated by commas</span>
              <input disabled={disabled} value={rule.keywords.join(", ")} onChange={(event) => update(index, { keywords: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />
            </label>
            {(rule.match_mode || "keyword") === "contextual" && (
              <div className="mt-3 block">
                <span className="text-xs font-medium text-slate-600">Required supporting words or phrases in the same sentence</span>
                <input disabled={disabled} value={(rule.context_phrases || []).join(", ")} onChange={(event) => update(index, { context_phrases: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />
                <span className="mt-1 block text-xs text-slate-500">These phrases are specific to this criterion. A primary term scores only when the same sentence also contains at least one of these relevant supporting phrases.</span>
              </div>
            )}
            <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500">
              <span>Rule key: {rule.key}</span>
              {!disabled && rules.length > 1 && <button type="button" className="font-semibold text-rose-700" onClick={() => onChange(rules.filter((_, ruleIndex) => ruleIndex !== index))}>Remove criterion</button>}
            </div>
          </div>
        ))}
        {!disabled && <button type="button" className="portal-btn portal-btn-ghost" onClick={add}>Add outcome criterion</button>}
      </div>
    </details>
  );
};

const AIScoringManager: React.FC<Props> = ({ mode }) => {
  const canEdit = mode === "admin";
  const [workspace, setWorkspace] = useState<CMSAIScoringWorkspace | null>(null);
  const [config, setConfig] = useState<CMSAIRuleConfig | null>(null);
  const [draft, setDraft] = useState<CMSAIRuleSet | null>(null);
  const [rawDraftConfig, setRawDraftConfig] = useState("");
  const [changeNote, setChangeNote] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [historyPage, setHistoryPage] = useState(1);
  const [historical, setHistorical] = useState<Awaited<ReturnType<typeof cmsApi.getAIHistoricalReferences>> | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [saving, setSaving] = useState(false);
  const [training, setTraining] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await cmsApi.getAIScoringWorkspace(0);
      setWorkspace(next);
      const nextDraft = next.draft_rule_set || null;
      setDraft(nextDraft);
      setRawDraftConfig(nextDraft?.editor_error ? JSON.stringify(nextDraft.raw_config, null, 2) : "");
      setConfig(canEdit
        ? prepareContextualConfig(nextDraft?.config || next.active_rule_set.draft_config || next.active_rule_set.config)
        : cloneConfig(next.active_rule_set.config));
      setChangeNote(nextDraft?.change_note || "");
    } catch (error) {
      setNotice(errorDetail(error, "Failed to load AI scoring rules and reference projects."));
    } finally {
      setLoading(false);
    }
  }, [canEdit]);

  useEffect(() => { void load(); }, [load]);

  const updateConfig = (updater: (next: CMSAIRuleConfig) => void) => {
    setConfig((current) => {
      if (!current) return current;
      const next = cloneConfig(current);
      updater(next);
      return next;
    });
  };

  const activeRuleId = workspace?.active_rule_set.id;
  const referenceVersion = workspace?.rag_pipeline?.reference_model_version;
  useEffect(() => {
    if (activeRuleId === undefined) return;
    let current = true;
    setHistoryError("");
    setHistoryLoading(true);
    const timer = window.setTimeout(() => {
      void cmsApi.getAIHistoricalReferences(historyPage, search.trim())
        .then((data) => { if (current) setHistorical(data); })
        .catch((error) => {
          if (current) {
            setHistorical(null);
            setHistoryError(errorDetail(error, "Historical projects could not be loaded."));
          }
        })
        .finally(() => { if (current) setHistoryLoading(false); });
    }, 250);
    return () => { current = false; window.clearTimeout(timer); };
  }, [activeRuleId, historyPage, referenceVersion, search]);

  const filteredHistory = historical?.results || [];
  const historicalCount = !historyLoading && historical ? historical.count : search.trim() ? null : workspace?.historical_count;

  const save = async () => {
    if (!config || !canEdit || !workspace) return;
    if (!draft?.editor_error && hasScoringErrors(config)) {
      setNotice("Correct the highlighted scoring settings before saving.");
      return;
    }
    if (!changeNote.trim()) {
      setNotice("Add a short change note explaining why the scoring rules are being updated.");
      return;
    }
    setSaving(true);
    setNotice("");
    try {
      const submittedConfig = draft?.editor_error ? JSON.parse(rawDraftConfig) as CMSAIRuleConfig : config;
      const response = draft
        ? await cmsApi.updateAIScoringDraft(draft.id, submittedConfig, changeNote.trim(), workspace.active_rule_set.id)
        : await cmsApi.createAIScoringDraft(submittedConfig, changeNote.trim(), workspace.active_rule_set.id);
      setDraft(response.draft_rule_set);
      setWorkspace((previous) => previous && ({
        ...previous, draft_rule_sets: [
          { id: response.draft_rule_set.id, version: response.draft_rule_set.version },
          ...(previous.draft_rule_sets || []).filter((item) => item.id !== response.draft_rule_set.id),
        ],
      }));
      setRawDraftConfig("");
      setConfig(prepareContextualConfig(response.draft_rule_set.config));
      setNotice("AI scoring draft saved. Activate it when ready.");
    } catch (error) {
      setNotice(errorDetail(error, "The AI scoring rules could not be activated."));
    } finally {
      setSaving(false);
    }
  };

  const activateDraft = async () => {
    if (!draft || !canEdit || !config || hasScoringErrors(config) || draftHasUnsavedChanges || draft.editor_error) return;
    if (!window.confirm("Activate this saved AI scoring draft? Existing analyses will remain unchanged.")) return;
    setSaving(true);
    setNotice("");
    try {
      const next = await cmsApi.publishAIScoringDraft(draft.id);
      setWorkspace(next);
      setDraft(null);
      setRawDraftConfig("");
      setConfig(prepareContextualConfig(next.active_rule_set.draft_config || next.active_rule_set.config));
      setChangeNote("");
      setNotice(next.detail || "AI scoring draft activated as a new rule version.");
    } catch (error) {
      setNotice(errorDetail(error, "The AI scoring draft could not be activated."));
    } finally {
      setSaving(false);
    }
  };

  const openDraft = async (id: number) => {
    if (id === draft?.id) return;
    if (draftHasUnsavedChanges && !window.confirm("Open another draft and discard the unsaved edits on this screen?")) return;
    setSaving(true);
    try {
      const next = await cmsApi.getAIScoringDraft(id);
      setDraft(next);
      setConfig(prepareContextualConfig(next.config));
      setRawDraftConfig(next.editor_error ? JSON.stringify(next.raw_config, null, 2) : "");
      setChangeNote(next.change_note || "");
    } catch (error) {
      setNotice(errorDetail(error, "The scoring draft could not be opened."));
    } finally {
      setSaving(false);
    }
  };

  const trainModel = async () => {
    if (!canEdit || !workspace?.training_dataset?.ready_to_train) return;
    if (!window.confirm("Rebuild and activate the historical reference context from the currently eligible validator-confirmed projects? This creates a new versioned RAG dataset and local calibration model. It does not fine-tune Groq, change the approved scoring rules, or alter previous analyses.")) return;
    setTraining(true);
    setNotice("");
    try {
      const response = await cmsApi.trainAIModel() as { detail?: string };
      setNotice(response?.detail || "The rebuilt historical reference context is active.");
      await load();
    } catch (error) {
      setNotice(errorDetail(error, "The historical reference context could not be rebuilt."));
    } finally {
      setTraining(false);
    }
  };



  if (loading && !workspace) return <div className="portal-card p-5 text-sm text-slate-600">Loading AI scoring rules and historical references...</div>;
  if (!workspace || !config) return <div className="portal-card p-5 text-sm text-rose-700">{notice || "AI scoring settings are unavailable."}</div>;

  const limits = scoringLimits(config);
  const invalidSectorTotals = Object.entries(limits.sectorWeightTotals);
  const sharedInvalidTotal = invalidSectorTotals.length > 1
    && invalidSectorTotals.length === Object.keys(config.sector_criteria).length
    && invalidSectorTotals.every(([, total]) => total === invalidSectorTotals[0][1]);
  const rankingErrors = collectRankingErrors(config);
  const regionalCostFloor = withinRange(config.thresholds.regional_project_cost, 0) ? config.thresholds.regional_project_cost : 0;
  const hasInvalidScoring = limits.invalid || Object.values(rankingErrors).some((errors) => errors.length > 0);
  const draftHasUnsavedChanges = Boolean(draft && (
    JSON.stringify(config) !== JSON.stringify(draft.config) || changeNote.trim() !== (draft.change_note || "")
  ));
  const papWeights = config.thresholds.pap_weights;
  const papTotal = Object.values(papWeights).reduce((sum, value) => sum + Number(value || 0), 0);
  const commonTotal = config.keyword_dictionaries.common_outcomes.reduce((sum, rule) => sum + Number(rule.weight || 0), 0);
  const trainingDataset = workspace.training_dataset || {
    candidate_count: workspace.historical_count,
    eligible_project_count: 0,
    excluded_count: 0,
    label_counts: { low: 0, high: 0 },
    minimum_projects: 2,
    required_labels: ["low", "high"],
    ready_to_train: false,
  };
  const modelVersions = workspace.model_versions || [];
  const groqEnabled = workspace.ai_provider?.name === "groq" && workspace.ai_provider.enabled;
  const referenceContextCurrent = trainingDataset.is_current ?? false;
  const requiresReferenceRebuild = trainingDataset.requires_retraining ?? !referenceContextCurrent;
  const ragSteps = workspace.rag_pipeline?.steps || [
    { key: "confirm", title: "Human-confirmed projects", description: "Validator-confirmed outcomes become candidates." },
    { key: "curate", title: "Administrator curation", description: "Include reliable records and exclude unsuitable ones." },
    { key: "rebuild", title: "Versioned rebuild", description: "Snapshot the references and train local calibration." },
    { key: "retrieve", title: "Similarity retrieval", description: "Find the most comparable approved projects." },
    { key: "analyze", title: "Rules-first analysis", description: "Use history as secondary context, never as the rule." },
    { key: "decide", title: "Validator decision", description: "A human remains responsible for the final result." },
  ];

  return (
    <div className="space-y-4">
      {notice && <div role="status" aria-live="polite" className="portal-card border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">{notice}</div>}

      <section className="portal-card overflow-hidden border-indigo-200">
        <div className="portal-card-header">
          <h3 className="font-bold text-slate-900">How the AI-Assisted Scorer Works</h3>
          <p className="mt-1 text-sm text-slate-600">Transparent information for administrators and content employees.</p>
        </div>
        <div className="portal-card-body grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            <p className="font-bold">{groqEnabled ? "This is a controlled Groq-assisted analysis engine." : "This is a controlled hybrid analysis engine."}</p>
            <p className="mt-2 leading-6">{workspace.learning_explanation}</p>
            <p className="mt-2 leading-6">It does not learn from its own predictions. Only validator-confirmed outcomes can be used as historical reference data.</p>
          </div>
          <div className="rounded-xl border border-slate-200 p-4 text-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Active rule version</p>
            <p className="mt-1 font-bold text-slate-900">{workspace.active_rule_set.version}</p>
            <p className="mt-1 text-slate-600">Algorithm: {workspace.active_rule_set.algorithm_version}</p>
            <p className="text-slate-600">Activated: {formatDate(workspace.active_rule_set.created_at)}</p>
            <div className="mt-3 border-t border-slate-200 pt-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Active AI provider</p>
              <p className="mt-1 font-bold text-slate-900">{groqEnabled ? `Groq · ${workspace.ai_provider?.primary_model}` : workspace.active_model?.version || "Local fallback only"}</p>
              {groqEnabled
                ? <p className="text-slate-600">Backup: {workspace.ai_provider?.backup_model}</p>
                : workspace.active_model && <p className="text-slate-600">{workspace.active_model.sample_count} confirmed projects · {workspace.active_model.algorithm}</p>}
            </div>
          </div>
        </div>
      </section>

      <section className="portal-card overflow-hidden">
        <div className="portal-card-header flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-900">Rules and Employee Guidelines</h3>
            <p className="text-xs text-slate-500">{canEdit ? "Edits become active only after creating a new version." : "Only administrators can view or change these scoring rules."}</p>
          </div>
          {!canEdit && <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">Read only</span>}
        </div>
        <div className="portal-card-body space-y-5">
          {!draft?.editor_error && <>
          <div>
            <h4 className="font-semibold text-slate-800">Priority thresholds</h4>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"><span className="block text-xs font-medium text-slate-600">Priority grade</span><span className="mt-1 block">{withinRange(config.thresholds.high, 1, 100)
                ? `Low: below ${config.thresholds.high} · High: ${config.thresholds.high}–100`
                : "Enter a valid cutoff to see the priority ranges."}</span></div>
              <NumberInput label="High-priority score starts at" value={config.thresholds.high} min={1} max={100} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.high = value; })} />
              <NumberInput label="Regional eligibility and automatic-Low cutoff (PHP)" value={config.thresholds.regional_project_cost} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_project_cost = value; })} />
            </div>
            <p className="mt-1 text-xs text-slate-500">A project below the regional cutoff skips the regional scorecard and receives an automatic Low recommendation, even when its score reaches the configured High threshold. Validators may still override it with a rationale. Exactly the cutoff amount qualifies for regional scoring.</p>
          </div>

          <div className="space-y-3">
            <div>
              <h4 className="font-semibold text-slate-800">Regional Prioritization Criteria</h4>
              <p className="mt-1 text-xs text-slate-500">Four criteria contribute up to {workspace.scoring_formula?.regional_criterion_weight ?? 25} points each. For eligible projects, this scorecard supplies half of the overall score.</p>
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="rounded-xl border border-slate-200 p-4">
                <h5 className="font-semibold text-slate-800">Total Regional Project Cost</h5>
                <CriterionWarnings errors={rankingErrors.cost} />
                <p className="mt-1 text-xs text-slate-500">The Otherwise score applies to eligible projects at or below the lowest band's cutoff.</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <NumberInput label={regionalBandLabel("cost", "at_least_5b", config.thresholds.regional_criteria.cost.thresholds.at_least_5b)} value={config.thresholds.regional_criteria.cost.thresholds.at_least_5b} min={regionalCostFloor} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.thresholds.at_least_5b = value; })} />
                  <NumberInput label="Highest-band score" value={config.thresholds.regional_criteria.cost.scores.at_least_5b} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.scores.at_least_5b = value; })} />
                  <NumberInput label={regionalBandLabel("cost", "over_3b", config.thresholds.regional_criteria.cost.thresholds.over_3b)} value={config.thresholds.regional_criteria.cost.thresholds.over_3b} min={regionalCostFloor} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.thresholds.over_3b = value; })} />
                  <NumberInput label="Next-band score" value={config.thresholds.regional_criteria.cost.scores.over_3b} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.scores.over_3b = value; })} />
                  <NumberInput label={regionalBandLabel("cost", "over_1b", config.thresholds.regional_criteria.cost.thresholds.over_1b)} value={config.thresholds.regional_criteria.cost.thresholds.over_1b} min={regionalCostFloor} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.thresholds.over_1b = value; })} />
                  <NumberInput label="Middle-band score" value={config.thresholds.regional_criteria.cost.scores.over_1b} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.scores.over_1b = value; })} />
                  <NumberInput label={regionalBandLabel("cost", "over_500m", config.thresholds.regional_criteria.cost.thresholds.over_500m)} value={config.thresholds.regional_criteria.cost.thresholds.over_500m} min={regionalCostFloor} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.thresholds.over_500m = value; })} />
                  <NumberInput label="Lower-band score" value={config.thresholds.regional_criteria.cost.scores.over_500m} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.scores.over_500m = value; })} />
                  <NumberInput label="Otherwise score" value={config.thresholds.regional_criteria.cost.scores.otherwise} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.cost.scores.otherwise = value; })} />
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 p-4">
                <h5 className="font-semibold text-slate-800">Regional Spatial Coverage</h5>
                <CriterionWarnings errors={rankingErrors.spatial_coverage} />
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <NumberInput label="Interregional score" value={config.thresholds.regional_criteria.spatial_coverage.scores.interregional} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.spatial_coverage.scores.interregional = value; })} />
                  <NumberInput label="Region-wide score" value={config.thresholds.regional_criteria.spatial_coverage.scores.region_wide} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.spatial_coverage.scores.region_wide = value; })} />
                  <NumberInput label="8–12 LGUs score" value={config.thresholds.regional_criteria.spatial_coverage.scores.eight_to_twelve_lgus} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.spatial_coverage.scores.eight_to_twelve_lgus = value; })} />
                  <NumberInput label="Single-city score" value={config.thresholds.regional_criteria.spatial_coverage.scores.single_city} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.spatial_coverage.scores.single_city = value; })} />
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 p-4">
                <h5 className="font-semibold text-slate-800">RDP Sectoral Outcome Contribution</h5>
                <CriterionWarnings errors={rankingErrors.outcome_contribution} />
                <p className="mt-1 text-xs text-slate-500">Minimum outcome counts and their raw scores.</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <NumberInput label={regionalBandLabel("outcome_contribution", "at_least_7", config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_7)} value={config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_7} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_7 = value; })} />
                  <NumberInput label="Score" value={config.thresholds.regional_criteria.outcome_contribution.scores.at_least_7} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.scores.at_least_7 = value; })} />
                  <NumberInput label={regionalBandLabel("outcome_contribution", "at_least_5", config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_5)} value={config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_5} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_5 = value; })} />
                  <NumberInput label="Score" value={config.thresholds.regional_criteria.outcome_contribution.scores.at_least_5} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.scores.at_least_5 = value; })} />
                  <NumberInput label={regionalBandLabel("outcome_contribution", "at_least_3", config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_3)} value={config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_3} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_3 = value; })} />
                  <NumberInput label="Score" value={config.thresholds.regional_criteria.outcome_contribution.scores.at_least_3} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.scores.at_least_3 = value; })} />
                  <NumberInput label={regionalBandLabel("outcome_contribution", "at_least_2", config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_2)} value={config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_2} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_2 = value; })} />
                  <NumberInput label="Score" value={config.thresholds.regional_criteria.outcome_contribution.scores.at_least_2} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.scores.at_least_2 = value; })} />
                  <NumberInput label={regionalBandLabel("outcome_contribution", "at_least_1", config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_1)} value={config.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_1} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.thresholds.at_least_1 = value; })} />
                  <NumberInput label="Score" value={config.thresholds.regional_criteria.outcome_contribution.scores.at_least_1} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.scores.at_least_1 = value; })} />
                  <NumberInput label="Otherwise score" value={config.thresholds.regional_criteria.outcome_contribution.scores.otherwise} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.outcome_contribution.scores.otherwise = value; })} />
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 p-4">
                <h5 className="font-semibold text-slate-800">Magnitude of Beneficiaries</h5>
                <CriterionWarnings errors={rankingErrors.beneficiaries} />
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <NumberInput label={regionalBandLabel("beneficiaries", "over_3m", config.thresholds.regional_criteria.beneficiaries.thresholds.over_3m)} value={config.thresholds.regional_criteria.beneficiaries.thresholds.over_3m} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.beneficiaries.thresholds.over_3m = value; })} />
                  <NumberInput label="Highest-band score" value={config.thresholds.regional_criteria.beneficiaries.scores.over_3m} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.beneficiaries.scores.over_3m = value; })} />
                  <NumberInput label={regionalBandLabel("beneficiaries", "over_1m", config.thresholds.regional_criteria.beneficiaries.thresholds.over_1m)} value={config.thresholds.regional_criteria.beneficiaries.thresholds.over_1m} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.beneficiaries.thresholds.over_1m = value; })} />
                  <NumberInput label="Next-band score" value={config.thresholds.regional_criteria.beneficiaries.scores.over_1m} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.beneficiaries.scores.over_1m = value; })} />
                  <NumberInput label={regionalBandLabel("beneficiaries", "at_least_1", config.thresholds.regional_criteria.beneficiaries.thresholds.at_least_1)} value={config.thresholds.regional_criteria.beneficiaries.thresholds.at_least_1} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.beneficiaries.thresholds.at_least_1 = value; })} />
                  <NumberInput label="Lowest-band score" value={config.thresholds.regional_criteria.beneficiaries.scores.at_least_1} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.beneficiaries.scores.at_least_1 = value; })} />
                  <NumberInput label="Otherwise score" value={config.thresholds.regional_criteria.beneficiaries.scores.otherwise} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_criteria.beneficiaries.scores.otherwise = value; })} />
                </div>
              </div>
            </div>
          </div>

          <section className="space-y-3">
          <h4 className="font-semibold text-slate-800">PAPs Criteria</h4>
          <div className="space-y-1 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
            <p>Each raw score is rated from 0 to {workspace.scoring_formula?.max_raw_score ?? 10}. The criterion weight is its maximum point contribution.</p>
            <p>Weighted points = raw score × criterion weight ÷ {workspace.scoring_formula?.max_raw_score ?? 10}.</p>
            <p>The base score adds PAP and RDP outcome points. The base and regional scores each range from 0 to 100.</p>
            <p>At or above the regional cutoff, the final score = (base score + regional score) ÷ 2. Below the cutoff, the final score = base score and the system recommends Low. Final scores range from 0 to 100 and are rounded to two decimals.</p>
            {workspace.scoring_formula && <p>For a base score of {workspace.scoring_formula.example.base} and a regional score of {workspace.scoring_formula.example.regional}, an eligible project scores {workspace.scoring_formula.example.eligible}. A project below the cutoff scores {workspace.scoring_formula.example.below_cutoff}.</p>}
          </div>
          <p className="text-xs text-slate-500">PAP weight total: {papTotal}. PAP + common outcomes ({commonTotal}) + the selected sector outcomes must total 100.</p>
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {(["readiness", "gad"] as const).map((group) => (
              <div key={group} className="rounded-xl border border-slate-200 p-4">
                <h4 className="font-semibold text-slate-800">{group === "readiness" ? "Readiness scoring" : "GAD responsiveness scoring"}</h4>
                <CriterionWarnings errors={rankingErrors[group]} />
                <div className="mt-3 space-y-3">
                  <NumberInput label={group === "readiness" ? "Readiness weight" : "GAD responsiveness weight"} value={papWeights[group === "readiness" ? "readiness" : "gad_responsiveness"]} wholeWeight disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.pap_weights[group === "readiness" ? "readiness" : "gad_responsiveness"] = value; })} />
                  {config.keyword_dictionaries[group].map((rule, index) => (
                    <div key={rule.key} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] sm:items-start">
                      <NumberInput label={`${rule.key.replaceAll("_", " ")} raw score`} alignLabel value={rule.raw} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries[group][index].raw = value; })} />
                      <label className="block"><span className="block text-xs font-medium leading-4 text-slate-600 sm:min-h-8">Guidance</span><textarea rows={2} disabled={!canEdit} value={rule.guideline} onChange={(event) => updateConfig((next) => { next.keyword_dictionaries[group][index].guideline = event.target.value; })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" /></label>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <div className="rounded-xl border border-slate-200 p-4">
              <h5 className="font-semibold text-slate-800">Spatial Coverage</h5>
              <p className="mt-1 text-xs text-slate-500">Uses the PAP coverage scope and the project’s listed NCR locations.</p>
              <CriterionWarnings errors={rankingErrors.pap_spatial} />
              <div className="mt-3 space-y-3">
                <NumberInput label="Spatial coverage weight" value={papWeights.spatial_coverage} wholeWeight disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.pap_weights.spatial_coverage = value; })} />
                {(Object.keys(papSpatialLabels) as Array<keyof typeof papSpatialLabels>).map((key) => (
                  <NumberInput key={key} label={papSpatialLabels[key]} value={(config.thresholds.pap_spatial_scores || papSpatialDefaults)[key]} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => {
                    next.thresholds.pap_spatial_scores = { ...(next.thresholds.pap_spatial_scores || papSpatialDefaults), [key]: value };
                  })} />
                ))}
              </div>
            </div>
          </div>
          </section>

          <div className="rounded-xl border border-slate-200 p-4">
            <h4 className="font-semibold text-slate-800">Project-text matching scores</h4>
            <CriterionWarnings errors={rankingErrors.outcome_rating} />
            <p className="mt-1 text-xs text-slate-500">These values determine the raw rating after the active criterion rule decides whether the project contains valid evidence. Contextual rules require a matching term and supporting wording in the same sentence.</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <NumberInput label="Chapter + 2 valid matches" value={config.keyword_dictionaries.outcome_rating.chapter_and_two_keywords} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.chapter_and_two_keywords = value; })} />
              <NumberInput label="Chapter + context or 3 matches" value={config.keyword_dictionaries.outcome_rating.chapter_or_three_keywords} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.chapter_or_three_keywords = value; })} />
              <NumberInput label="At least 1 valid match" value={config.keyword_dictionaries.outcome_rating.one_keyword} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.one_keyword = value; })} />
              <NumberInput label="No valid evidence" value={config.keyword_dictionaries.outcome_rating.no_keywords} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.no_keywords = value; })} />
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <h4 className="font-semibold text-slate-800">RDP outcome criteria and matching words</h4>
              {!!invalidSectorTotals.length && (
                <p className="mt-1 text-xs text-rose-700" aria-live="polite">
                  Combined weights must total 100. {sharedInvalidTotal
                    ? `Each sector currently totals ${invalidSectorTotals[0][1]}.`
                    : invalidSectorTotals.map(([sector, total]) => `${sectorLabels[sector] || sector} totals ${total}`).join(", ") + "."}
                </p>
              )}
            </div>
            <OutcomeRuleEditor title="Common outcomes" rules={config.keyword_dictionaries.common_outcomes} disabled={!canEdit} onChange={(rules) => updateConfig((next) => { next.keyword_dictionaries.common_outcomes = rules; })} />
            <h5 className="text-sm font-semibold text-slate-800">Committee-specific outcome criteria</h5>
            {Object.entries(config.sector_criteria).map(([sector, rules]) => (
              <OutcomeRuleEditor key={sector} title={`${sectorLabels[sector] || sector} outcomes`} rules={rules} disabled={!canEdit} onChange={(nextRules) => updateConfig((next) => { next.sector_criteria[sector] = nextRules; })} />
            ))}
            {!!workspace.committee_outcome_links?.length && (
              <details className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                <summary className="cursor-pointer font-medium text-slate-800">Committee assignments</summary>
                <ul className="mt-2 space-y-2 text-slate-600">
                  {workspace.committee_outcome_links.map((committee) => (
                    <li key={committee.code}>
                      <span className="font-medium text-slate-800">{committee.name}</span>
                      {!committee.is_active && <span className="ml-2 text-xs">Inactive</span>}
                      <p>{committee.groups.map((group) => sectorLabels[group] || group).join(", ") || "No outcome groups assigned"}</p>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 p-4">
            <h4 className="font-semibold text-slate-800">Possible negative-list matches</h4>
            <p className="mt-1 text-xs text-slate-500">These words create review flags; they do not automatically reject a project.</p>
            <div className="mt-3 space-y-3">
              {config.keyword_dictionaries.negative_rules.map((rule, index) => (
                <div key={rule.key} className="rounded-lg border border-slate-100 p-3">
                  <input disabled={!canEdit} value={rule.label} onChange={(event) => updateConfig((next) => { next.keyword_dictionaries.negative_rules[index].label = event.target.value; })} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium disabled:bg-slate-100" />
                  <input disabled={!canEdit} value={rule.keywords.join(", ")} onChange={(event) => updateConfig((next) => { next.keyword_dictionaries.negative_rules[index].keywords = event.target.value.split(",").map((value) => value.trim()).filter(Boolean); })} className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" aria-label={`${rule.label} matching words`} />
                  {!canEdit ? null : <button type="button" className="mt-2 text-xs font-semibold text-rose-700" onClick={() => updateConfig((next) => { next.keyword_dictionaries.negative_rules = next.keyword_dictionaries.negative_rules.filter((_, ruleIndex) => ruleIndex !== index); })}>Remove rule</button>}
                </div>
              ))}
              {canEdit && <button type="button" className="portal-btn portal-btn-ghost" onClick={() => updateConfig((next) => { next.keyword_dictionaries.negative_rules.push({ key: `custom_negative_${Date.now()}`, label: "New review flag", keywords: ["new keyword"] }); })}>Add negative-list rule</button>}
            </div>
          </div>

          <label className="block">
            <span className="text-sm font-semibold text-slate-800">Employee guidelines</span>
            <span className="mt-1 block text-xs text-slate-500">Enter one guideline per line. These are reference instructions and do not add points by themselves.</span>
            <textarea disabled={!canEdit} rows={6} value={config.keyword_dictionaries.guidelines.join("\n")} onChange={(event) => updateConfig((next) => { next.keyword_dictionaries.guidelines = event.target.value.split("\n"); })} className="mt-2 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />
          </label>

          </>}
          {draft?.editor_error && (
            <label className="block text-sm font-semibold">Repair draft configuration
              <span className="block text-rose-700">{draft.editor_error}</span>
              <textarea rows={18} value={rawDraftConfig} onChange={(event) => setRawDraftConfig(event.target.value)} className="mt-2 w-full rounded border border-slate-300 p-3 font-mono text-xs" />
            </label>
          )}
          {canEdit && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              {(workspace.draft_rule_sets || []).length > (draft ? 1 : 0) && (
                <label className="mb-3 block text-sm font-semibold">Saved drafts
                  <select value={draft?.id ?? ""} disabled={saving} onChange={(event) => void openDraft(Number(event.target.value))} className="ml-2 rounded border border-slate-300 p-1">
                    <option value="" disabled>Select a draft</option>
                    {workspace.draft_rule_sets?.map((item) => <option key={item.id} value={item.id}>{item.version}</option>)}
                  </select>
                </label>
              )}
              {draft?.restored_from_version && <p className="mb-2 text-sm">Repair draft from {draft.restored_from_version}</p>}
              {draft?.based_on && draft.based_on !== workspace.active_rule_set.id && <p className="mb-2 text-sm">The active version changed. Review these settings and save the draft before activating it.</p>}
              <label className="block"><span className="text-sm font-semibold text-amber-950">Required change note</span><textarea rows={2} maxLength={500} value={changeNote} onChange={(event) => setChangeNote(event.target.value)} className="mt-2 w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm" placeholder="Example: Updated thresholds based on the approved RDC scoring memorandum." /></label>
              <div className="mt-3 flex flex-wrap justify-end gap-2">
                <button type="button" disabled={saving || !changeNote.trim() || (!draft?.editor_error && hasInvalidScoring)} onClick={() => void save()} className="portal-btn portal-btn-primary">
                  {saving ? "Saving..." : draft ? "Save Draft" : "Create Draft"}
                </button>
                {draft && (
                  <button type="button" disabled={saving || hasInvalidScoring || draftHasUnsavedChanges || !!draft.editor_error || draft.based_on !== workspace.active_rule_set.id} onClick={() => void activateDraft()} className="portal-btn portal-btn-primary">
                    Activate Draft
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="portal-card overflow-hidden border-violet-200">
        <div className="portal-card-header flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-900">Historical Project Context and RAG Training</h3>
            <p className="text-xs text-slate-500">Administrators control the reference dataset. Approved rules stay primary; previous scores provide secondary calibration for nuanced proposals.</p>
          </div>
          {canEdit && (
            <button type="button" className="portal-btn portal-btn-primary" disabled={training || !trainingDataset.ready_to_train || !requiresReferenceRebuild} onClick={() => void trainModel()}>
              {training ? "Rebuilding..." : !trainingDataset.ready_to_train ? "More Confirmed Projects Needed" : referenceContextCurrent ? "Historical Context Is Current" : "Retrain Historical Context"}
            </button>
          )}
        </div>
        <div className="portal-card-body space-y-4">
          <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-bold text-indigo-950">How this RAG mini-system works</p>
                <p className="mt-1 max-w-4xl text-xs text-indigo-900">This operation rebuilds a controlled reference collection and a local advisory calibration model. It does not modify or fine-tune the hosted Groq model. During analysis, Groq receives only the most similar approved references, including their rule score, final validator priority, and rationale.</p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-indigo-800 ring-1 ring-indigo-200">Rules remain primary</span>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {ragSteps.map((step, index) => (
                <div key={step.key} className="rounded-lg border border-indigo-100 bg-white p-3">
                  <p className="text-xs font-bold uppercase tracking-wide text-indigo-600">Step {index + 1}</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">{step.title}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-600">{step.description}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Eligible projects</p><p className="mt-1 text-xl font-bold">{trainingDataset.eligible_project_count}</p></div>
            <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-3"><p className="text-xs uppercase text-rose-700">Low priority</p><p className="mt-1 text-xl font-bold">{trainingDataset.label_counts.low || 0}</p></div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-3"><p className="text-xs uppercase text-emerald-700">High priority</p><p className="mt-1 text-xl font-bold">{trainingDataset.label_counts.high || 0}</p></div>
            <div className={`rounded-xl border p-3 ${referenceContextCurrent ? "border-emerald-200 bg-emerald-50/40" : "border-amber-200 bg-amber-50/50"}`}><p className="text-xs uppercase text-slate-500">Reference status</p><p className="mt-1 text-base font-bold">{referenceContextCurrent ? "Current" : trainingDataset.ready_to_train ? "Rebuild needed" : "Not ready"}</p><p className="mt-1 text-xs text-slate-500">{trainingDataset.active_model_version || "No active version"}</p></div>
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Excluded records</p><p className="mt-1 text-xl font-bold">{trainingDataset.excluded_count}</p></div>
          </div>
          {!trainingDataset.ready_to_train && <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">A rebuild requires at least one eligible validator-confirmed project in each category: low and high priority.</p>}
          {trainingDataset.ready_to_train && requiresReferenceRebuild && <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">The eligible records have changed since the active reference version. Rebuild the historical context before expecting those changes to affect new analyses.</p>}
          {groqEnabled && referenceContextCurrent && <p className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-900">New analyses retrieve up to {workspace.rag_pipeline?.retrieval_limit || 6} similar projects from this active version. Historical results can refine comparisons, but cannot override the active rules or make the validator's decision.</p>}
          {modelVersions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-800">Historical Reference Version History</h4>
              {modelVersions.map((model) => (
                <div key={model.id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  <div><p className="font-semibold text-slate-800">{model.version} {model.status === "active" && <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs text-violet-800">active</span>}</p><p className="text-xs text-slate-500">{model.algorithm} · {model.sample_count} projects · {formatDate(model.created_at)}</p>{model.metrics.warning && <p className="mt-1 text-xs text-amber-700">{model.metrics.warning}</p>}</div>
                  <span className="text-xs font-medium text-slate-600">{model.metrics.accuracy === null || model.metrics.accuracy === undefined ? "Not evaluated" : `${(model.metrics.accuracy * 100).toFixed(1)}% measured accuracy`}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <AIScoringRuleHistory versions={workspace.rule_versions} initialTotalPages={workspace.rule_versions_total_pages} activeId={workspace.active_rule_set.id} onRestored={async (result) => {
        await load();
        setNotice([result.detail, ...result.issues].join(" "));
      }} />

      <section className="portal-card overflow-hidden">
        <div className="portal-card-header flex flex-wrap items-start justify-between gap-3">
          <div><h3 className="font-bold text-slate-900">Historical Project Reference Dataset</h3><p className="text-xs text-slate-500">Shows human-confirmed outcomes and their historical reference status.</p></div>
          {historicalCount != null && <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{historicalCount} confirmed record{historicalCount === 1 ? "" : "s"}</span>}
        </div>
        <div className="portal-card-body">
          <input value={search} onChange={(event) => { setSearch(event.target.value); setHistoryPage(1); }} className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Search project, agency, sector, priority, rule version, or validator" />
          {historyLoading ? <p role="status">Loading historical projects...</p> : historyError ? <p role="alert" className="text-sm text-rose-700">{historyError}</p> : filteredHistory.length === 0 ? <p className="text-sm text-slate-500">No confirmed historical priority analyses match this search.</p> : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[1120px] text-left text-xs">
                <thead className="bg-slate-50 text-slate-700"><tr><th className="px-3 py-2">Project</th><th className="px-3 py-2">Agency / Sector</th><th className="px-3 py-2">Score</th><th className="px-3 py-2">Suggested</th><th className="px-3 py-2">Final</th><th className="px-3 py-2">Rule version</th><th className="px-3 py-2">Confirmed by</th><th className="px-3 py-2">Date</th><th className="px-3 py-2">AI reference use</th></tr></thead>
                <tbody>{filteredHistory.map((row) => <tr key={row.confirmation_id} className="border-t border-slate-100 align-top"><td className="px-3 py-2"><p className="font-semibold text-slate-800">{row.project_title}</p><p className="text-slate-500">{row.submission_type} · {row.project_status}</p>{row.override_rationale && <p className="mt-1 text-amber-700">Override: {row.override_rationale}</p>}</td><td className="px-3 py-2">{row.agency || "-"}<br /><span className="text-slate-500">{row.sector || "Unspecified"}</span></td><td className="px-3 py-2">{Number(row.base_score).toFixed(2)}</td><td className="px-3 py-2">{priorityLabel(row.suggested_priority)}</td><td className="px-3 py-2 font-semibold">{priorityLabel(row.final_priority)}</td><td className="px-3 py-2">{row.rule_version}</td><td className="px-3 py-2">{row.validator_name || "-"}</td><td className="px-3 py-2">{formatDate(row.confirmed_at)}</td><td className="px-3 py-2"><span className={`rounded-full px-2 py-1 font-semibold ${row.training_eligible ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{row.training_eligible ? "Eligible" : "Excluded"}</span><p className={`mt-1 text-[11px] font-medium ${row.in_active_reference && !row.training_eligible ? "text-amber-700" : "text-slate-500"}`}>{row.in_active_reference ? row.training_eligible ? "In active reference version" : "Remains active until rebuild" : row.training_eligible ? "Pending next rebuild" : "Not in active version"}</p>{row.exclusion_reason && <p className="mt-1 max-w-[220px] text-slate-500">{row.exclusion_reason}</p>}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          <ScoringHistoryPagination label="Historical reference pages" page={historyPage} totalPages={historical?.total_pages ?? 1} loading={historyLoading} onPage={setHistoryPage} />
        </div>
      </section>
    </div>
  );
};

export default AIScoringManager;
