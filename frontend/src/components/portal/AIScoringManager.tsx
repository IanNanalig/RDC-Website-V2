import React, { useCallback, useEffect, useMemo, useState } from "react";
import cmsApi, {
  type CMSAIOutcomeRule,
  type CMSAIRuleConfig,
  type CMSAIScoringWorkspace,
} from "../../services/cmsApi";

type Props = { mode: "admin" | "editor" };

const sectorLabels: Record<string, string> = {
  infrastructure: "Infrastructure",
  social: "Social",
  economic: "Economic",
  environment: "Environment",
  financial_admin: "Financial and Administrative",
};

const cloneConfig = (value: CMSAIRuleConfig) => JSON.parse(JSON.stringify(value)) as CMSAIRuleConfig;

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

const NumberInput = ({
  label,
  value,
  disabled,
  onChange,
  min = 0,
  max,
}: {
  label: string;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
}) => (
  <label className="block">
    <span className="text-xs font-medium text-slate-600">{label}</span>
    <input
      type="number"
      min={min}
      max={max}
      disabled={disabled}
      value={value}
      onChange={(event) => onChange(Number(event.target.value))}
      className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
    />
  </label>
);

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
    onChange([...rules, { key, label: "New outcome criterion", weight: 0, keywords: ["new keyword"] }]);
  };
  return (
    <details className="rounded-xl border border-slate-200 bg-white" open={title === "Common outcomes"}>
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-800">
        {title} <span className="font-normal text-slate-500">({rules.reduce((sum, rule) => sum + Number(rule.weight || 0), 0)} points)</span>
      </summary>
      <div className="space-y-3 border-t border-slate-100 p-4">
        {rules.map((rule, index) => (
          <div key={rule.key} className="rounded-lg border border-slate-200 p-3">
            <div className="grid gap-3 lg:grid-cols-[minmax(220px,1fr)_120px]">
              <label className="block">
                <span className="text-xs font-medium text-slate-600">Criterion label</span>
                <input disabled={disabled} value={rule.label} onChange={(event) => update(index, { label: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />
              </label>
              <NumberInput label="Weight" value={rule.weight} min={0} max={100} disabled={disabled} onChange={(weight) => update(index, { weight })} />
            </div>
            <label className="mt-3 block">
              <span className="text-xs font-medium text-slate-600">Matching words or phrases, separated by commas</span>
              <input disabled={disabled} value={rule.keywords.join(", ")} onChange={(event) => update(index, { keywords: event.target.value.split(",").map((value) => value.trim()).filter(Boolean) })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" />
            </label>
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
  const [changeNote, setChangeNote] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [training, setTraining] = useState(false);
  const [updatingRecordId, setUpdatingRecordId] = useState<number | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await cmsApi.getAIScoringWorkspace();
      setWorkspace(next);
      setConfig(cloneConfig(next.active_rule_set.config));
    } catch (error) {
      setNotice(errorDetail(error, "Failed to load AI scoring rules and reference projects."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const updateConfig = (updater: (next: CMSAIRuleConfig) => void) => {
    setConfig((current) => {
      if (!current) return current;
      const next = cloneConfig(current);
      updater(next);
      return next;
    });
  };

  const filteredHistory = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return workspace?.historical_projects || [];
    return (workspace?.historical_projects || []).filter((row) => [
      row.project_title,
      row.agency,
      row.sector,
      row.final_priority,
      row.rule_version,
      row.validator_name,
    ].some((value) => String(value || "").toLowerCase().includes(query)));
  }, [search, workspace?.historical_projects]);

  const save = async () => {
    if (!config || !canEdit) return;
    if (!changeNote.trim()) {
      setNotice("Add a short change note explaining why the scoring rules are being updated.");
      return;
    }
    if (!window.confirm("Activate these rules as a new version? Existing analyses will remain unchanged, but pending projects must be analyzed again under the new version.")) return;
    setSaving(true);
    setNotice("");
    try {
      const next = await cmsApi.activateAIScoringRules(config, changeNote.trim());
      setWorkspace(next);
      setConfig(cloneConfig(next.active_rule_set.config));
      setChangeNote("");
      setNotice(next.detail || "New AI scoring rules activated.");
    } catch (error) {
      setNotice(errorDetail(error, "The AI scoring rules could not be activated."));
    } finally {
      setSaving(false);
    }
  };

  const trainModel = async () => {
    if (!canEdit || !workspace?.training_dataset?.ready_to_train) return;
    if (!window.confirm("Train and activate a new model version from the currently eligible validator-confirmed projects? Existing model versions and analyses will remain preserved.")) return;
    setTraining(true);
    setNotice("");
    try {
      const response = await cmsApi.trainAIModel() as { detail?: string };
      setNotice(response?.detail || "A new historical learning model is active.");
      await load();
    } catch (error) {
      setNotice(errorDetail(error, "The historical learning model could not be trained."));
    } finally {
      setTraining(false);
    }
  };

  const toggleTrainingRecord = async (row: CMSAIScoringWorkspace["historical_projects"][number]) => {
    if (!canEdit) return;
    if (!row.training_record_id) {
      setNotice("This historical record is not available for training yet. Refresh after the backend update is deployed.");
      return;
    }
    const nextEligible = !row.training_eligible;
    let reason = "";
    if (!nextEligible) {
      reason = window.prompt("Why should this confirmed project be excluded from model training?", "")?.trim() || "";
      if (!reason) {
        setNotice("An exclusion reason is required.");
        return;
      }
    }
    setUpdatingRecordId(row.training_record_id);
    setNotice("");
    try {
      await cmsApi.updateAITrainingRecord(row.training_record_id, nextEligible, reason);
      setNotice(nextEligible ? "The project is eligible for the next model training run." : "The project was excluded from future model training runs.");
      await load();
    } catch (error) {
      setNotice(errorDetail(error, "The training record could not be updated."));
    } finally {
      setUpdatingRecordId(null);
    }
  };

  if (loading && !workspace) return <div className="portal-card p-5 text-sm text-slate-600">Loading AI scoring rules and historical references...</div>;
  if (!workspace || !config) return <div className="portal-card p-5 text-sm text-rose-700">{notice || "AI scoring settings are unavailable."}</div>;

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
            <p className="font-bold">This is a controlled hybrid analysis engine.</p>
            <p className="mt-2 leading-6">{workspace.learning_explanation}</p>
            <p className="mt-2 leading-6">It does not learn from its own predictions. Only validator-confirmed outcomes can enter a controlled administrator-started training run.</p>
          </div>
          <div className="rounded-xl border border-slate-200 p-4 text-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">Active rule version</p>
            <p className="mt-1 font-bold text-slate-900">{workspace.active_rule_set.version}</p>
            <p className="mt-1 text-slate-600">Algorithm: {workspace.active_rule_set.algorithm_version}</p>
            <p className="text-slate-600">Activated: {formatDate(workspace.active_rule_set.created_at)}</p>
            <div className="mt-3 border-t border-slate-200 pt-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Active learned model</p>
              <p className="mt-1 font-bold text-slate-900">{workspace.active_model?.version || "Not trained yet"}</p>
              {workspace.active_model && <p className="text-slate-600">{workspace.active_model.sample_count} confirmed projects · {workspace.active_model.algorithm}</p>}
            </div>
          </div>
        </div>
      </section>

      <section className="portal-card overflow-hidden">
        <div className="portal-card-header flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-900">Rules and Employee Guidelines</h3>
            <p className="text-xs text-slate-500">{canEdit ? "Edits become active only after creating a new version." : "Content editors can view these rules; only administrators can activate changes."}</p>
          </div>
          {!canEdit && <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">Read only</span>}
        </div>
        <div className="portal-card-body space-y-5">
          <div>
            <h4 className="font-semibold text-slate-800">Priority thresholds and PAP weights</h4>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"><span className="block text-xs font-medium text-slate-600">Priority ranges</span><span className="mt-1 block">Low: 0–80 · High: 81–100</span></div>
              <NumberInput label="Regional scorecard starts at (PHP)" value={config.thresholds.regional_project_cost} min={0} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.regional_project_cost = value; })} />
              <NumberInput label="Readiness weight" value={papWeights.readiness} min={0} max={100} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.pap_weights.readiness = value; })} />
              <NumberInput label="GAD responsiveness weight" value={papWeights.gad_responsiveness} min={0} max={100} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.pap_weights.gad_responsiveness = value; })} />
              <NumberInput label="Spatial coverage weight" value={papWeights.spatial_coverage} min={0} max={100} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.thresholds.pap_weights.spatial_coverage = value; })} />
            </div>
            <p className="mt-2 text-xs text-slate-500">PAP weight total: {papTotal}. PAP + common outcomes ({commonTotal}) + the selected sector outcomes must total 100.</p>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            {(["readiness", "gad"] as const).map((group) => (
              <div key={group} className="rounded-xl border border-slate-200 p-4">
                <h4 className="font-semibold text-slate-800">{group === "readiness" ? "Readiness scoring" : "GAD responsiveness scoring"}</h4>
                <div className="mt-3 space-y-3">
                  {config.keyword_dictionaries[group].map((rule, index) => (
                    <div key={rule.key} className="grid gap-2 sm:grid-cols-[100px_1fr]">
                      <NumberInput label={`${rule.key.replaceAll("_", " ")} score`} value={rule.raw} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries[group][index].raw = value; })} />
                      <label className="block"><span className="text-xs font-medium text-slate-600">Guidance</span><input disabled={!canEdit} value={rule.guideline} onChange={(event) => updateConfig((next) => { next.keyword_dictionaries[group][index].guideline = event.target.value; })} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100" /></label>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-slate-200 p-4">
            <h4 className="font-semibold text-slate-800">Project-text matching scores</h4>
            <p className="mt-1 text-xs text-slate-500">These values determine the raw rating when relevant words are found in the project details.</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <NumberInput label="Chapter + 2 words" value={config.keyword_dictionaries.outcome_rating.chapter_and_two_keywords} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.chapter_and_two_keywords = value; })} />
              <NumberInput label="Chapter or 3 words" value={config.keyword_dictionaries.outcome_rating.chapter_or_three_keywords} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.chapter_or_three_keywords = value; })} />
              <NumberInput label="At least 1 word" value={config.keyword_dictionaries.outcome_rating.one_keyword} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.one_keyword = value; })} />
              <NumberInput label="No matching words" value={config.keyword_dictionaries.outcome_rating.no_keywords} min={0} max={10} disabled={!canEdit} onChange={(value) => updateConfig((next) => { next.keyword_dictionaries.outcome_rating.no_keywords = value; })} />
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-slate-800">RDP outcome criteria and matching words</h4>
            <OutcomeRuleEditor title="Common outcomes" rules={config.keyword_dictionaries.common_outcomes} disabled={!canEdit} onChange={(rules) => updateConfig((next) => { next.keyword_dictionaries.common_outcomes = rules; })} />
            {Object.entries(config.sector_criteria).map(([sector, rules]) => (
              <OutcomeRuleEditor key={sector} title={`${sectorLabels[sector] || sector} outcomes`} rules={rules} disabled={!canEdit} onChange={(nextRules) => updateConfig((next) => { next.sector_criteria[sector] = nextRules; })} />
            ))}
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

          {canEdit && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <label className="block"><span className="text-sm font-semibold text-amber-950">Required change note</span><textarea rows={2} value={changeNote} onChange={(event) => setChangeNote(event.target.value)} className="mt-2 w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm" placeholder="Example: Updated thresholds based on the approved RDC scoring memorandum." /></label>
              <div className="mt-3 flex justify-end"><button type="button" disabled={saving} onClick={() => void save()} className="portal-btn portal-btn-primary">{saving ? "Activating..." : "Activate as New Rule Version"}</button></div>
            </div>
          )}
        </div>
      </section>

      <section className="portal-card overflow-hidden border-violet-200">
        <div className="portal-card-header flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-bold text-slate-900">Controlled Historical Learning</h3>
            <p className="text-xs text-slate-500">Training runs only when an administrator starts one. AI predictions never become training labels.</p>
          </div>
          {canEdit && (
            <button type="button" className="portal-btn portal-btn-primary" disabled={training || !trainingDataset.ready_to_train} onClick={() => void trainModel()}>
              {training ? "Training..." : "Train New Model Version"}
            </button>
          )}
        </div>
        <div className="portal-card-body space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Eligible projects</p><p className="mt-1 text-xl font-bold">{trainingDataset.eligible_project_count}</p></div>
            <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-3"><p className="text-xs uppercase text-rose-700">Low priority</p><p className="mt-1 text-xl font-bold">{trainingDataset.label_counts.low || 0}</p></div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-3"><p className="text-xs uppercase text-emerald-700">High priority</p><p className="mt-1 text-xl font-bold">{trainingDataset.label_counts.high || 0}</p></div>
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-xs uppercase text-slate-500">Excluded records</p><p className="mt-1 text-xl font-bold">{trainingDataset.excluded_count}</p></div>
          </div>
          {!trainingDataset.ready_to_train && <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">Training requires at least one eligible validator-confirmed project in each category: low and high priority.</p>}
          {modelVersions.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-slate-800">Model Version History</h4>
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

      <section className="portal-card overflow-hidden">
        <div className="portal-card-header"><h3 className="font-bold text-slate-900">Rule Version History</h3><p className="text-xs text-slate-500">Old versions remain attached to the analyses they produced.</p></div>
        <div className="portal-card-body space-y-2">
          {workspace.rule_versions.map((rule) => (
            <div key={rule.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <div><p className="font-semibold text-slate-800">{rule.version} {rule.is_active && <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">active</span>}</p><p className="text-xs text-slate-500">{rule.algorithm_version} · {formatDate(rule.created_at)}</p></div>
              <span className="text-xs font-medium text-slate-600">{rule.analysis_count} analysis{rule.analysis_count === 1 ? "" : "es"}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="portal-card overflow-hidden">
        <div className="portal-card-header flex flex-wrap items-start justify-between gap-3">
          <div><h3 className="font-bold text-slate-900">Historical Project Training Dataset</h3><p className="text-xs text-slate-500">Only human-confirmed outcomes are eligible. Administrators can exclude unsuitable records before the next controlled training run.</p></div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">{workspace.historical_count} confirmed record{workspace.historical_count === 1 ? "" : "s"}</span>
        </div>
        <div className="portal-card-body">
          <input value={search} onChange={(event) => setSearch(event.target.value)} className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Search project, agency, sector, priority, rule version, or validator" />
          {filteredHistory.length === 0 ? <p className="text-sm text-slate-500">No confirmed historical priority analyses match this search.</p> : (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full min-w-[1120px] text-left text-xs">
                <thead className="bg-slate-50 text-slate-700"><tr><th className="px-3 py-2">Project</th><th className="px-3 py-2">Agency / Sector</th><th className="px-3 py-2">Score</th><th className="px-3 py-2">Suggested</th><th className="px-3 py-2">Final</th><th className="px-3 py-2">Rule version</th><th className="px-3 py-2">Confirmed by</th><th className="px-3 py-2">Date</th><th className="px-3 py-2">Model training</th></tr></thead>
                <tbody>{filteredHistory.map((row) => <tr key={row.confirmation_id} className="border-t border-slate-100 align-top"><td className="px-3 py-2"><p className="font-semibold text-slate-800">{row.project_title}</p><p className="text-slate-500">{row.submission_type} · {row.project_status}</p>{row.override_rationale && <p className="mt-1 text-amber-700">Override: {row.override_rationale}</p>}</td><td className="px-3 py-2">{row.agency || "-"}<br /><span className="text-slate-500">{row.sector || "Unspecified"}</span></td><td className="px-3 py-2">{Number(row.base_score).toFixed(2)}</td><td className="px-3 py-2">{priorityLabel(row.suggested_priority)}</td><td className="px-3 py-2 font-semibold">{priorityLabel(row.final_priority)}</td><td className="px-3 py-2">{row.rule_version}</td><td className="px-3 py-2">{row.validator_name || "-"}</td><td className="px-3 py-2">{formatDate(row.confirmed_at)}</td><td className="px-3 py-2"><span className={`rounded-full px-2 py-1 font-semibold ${row.training_eligible ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{row.training_eligible ? "Eligible" : "Excluded"}</span>{row.exclusion_reason && <p className="mt-1 max-w-[220px] text-slate-500">{row.exclusion_reason}</p>}{canEdit && <button type="button" disabled={updatingRecordId === row.training_record_id} onClick={() => void toggleTrainingRecord(row)} className="mt-2 block font-semibold text-blue-700 disabled:text-slate-400">{updatingRecordId === row.training_record_id ? "Updating..." : row.training_eligible ? "Exclude" : "Include"}</button>}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          {workspace.historical_count > workspace.historical_projects.length && <p className="mt-2 text-xs text-slate-500">Showing the latest {workspace.historical_projects.length} confirmed records.</p>}
        </div>
      </section>
    </div>
  );
};

export default AIScoringManager;
