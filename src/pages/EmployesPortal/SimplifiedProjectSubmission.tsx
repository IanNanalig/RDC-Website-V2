import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../services/api";
import PortalLayout from "../../components/portal/PortalLayout";

type FormAction = "save" | "submit" | "draft" | "reviewed" | "endorsed";
type YesNo = "Yes" | "No";

type SimplifiedForm = {
  agencyName: string;
  program: string;
  projectActivity: string;
  location: string;
  description: string;
  objective: string;
  startYear: string;
  endYear: string;
  fundingRequirementByYear: Record<string, string>;
  actualFundingByYear: Record<string, string>;
  fundingSource: string;
  uacsCode: string;
  rdcEndorsed: YesNo | "";
  pipIncluded: YesNo | "";
  arnipapIncluded: YesNo | "";
  ludipIncluded: YesNo | "";
  ifpsIncluded: YesNo | "";
  pcbIncluded: YesNo | "";
  pcbProgram: string;
  developmentSector: string;
  rdpMainChapter: string;
  sdgSelections: string[];
  status: string;
  physicalAccomplishment: string;
  financialAccomplishment: string;
  remarks: string;
};

type ProjectComment = {
  id: number;
  comment: string;
  created_at: string;
  username?: string;
  full_name?: string;
  role?: string;
  agency?: string;
};

type EditMeta = {
  by?: string;
  name?: string;
  at?: string;
  before?: string;
};

type DiffField = {
  before: string;
  after: string;
};

const initialForm: SimplifiedForm = {
  agencyName: "",
  program: "",
  projectActivity: "",
  location: "",
  description: "",
  objective: "",
  startYear: "",
  endYear: "",
  fundingRequirementByYear: {},
  actualFundingByYear: {},
  fundingSource: "",
  uacsCode: "",
  rdcEndorsed: "",
  pipIncluded: "",
  arnipapIncluded: "",
  ludipIncluded: "",
  ifpsIncluded: "",
  pcbIncluded: "",
  pcbProgram: "",
  developmentSector: "",
  rdpMainChapter: "",
  sdgSelections: [],
  status: "",
  physicalAccomplishment: "",
  financialAccomplishment: "",
  remarks: "",
};

const yesNoOptions = ["Yes", "No"];
const yesNoNaOptions = ["Yes", "No", "Not Applicable"];
const fundingSourceOptions = [
  "NG-Local Funds (GAA)",
  "ODA",
  "PPP",
  "Agency",
  "GOCC/GFIs",
  "LGUs",
  "NGOs",
  "Special/Trust Fund",
  "NDRRM",
  "N/A",
  "Others",
];
const developmentSectorOptions = [
  "Sectoral Committee on Infrastructure Development (SCID)",
  "Sectoral Committee on Social Development (SCSD)",
  "Sectoral Committee on Economic and Environment Development (SCEED)",
  "Sectoral Committee on Finance and Development Administration (SCFDA)",
];
const pcbProgramOptions = [
  "National Program on Population and Family Planning (NPPFP)",
  "Zero Hunger Program (ZHP)",
  "Agricultural Development Program (ADP)",
  "Export Development Program (EDP)",
  "Tourism Development Program (TDP)",
  "Pasig River Urban Development (PRUD)",
  "Risk Resiliency Program (RRP)",
  "Justice Sector Convergence Program (JSCP)",
  "Philippine Anti-Illegal Drug Strategy (PADS)",
  "Water Resources Program (WRP)",
  "PCB on the Sustainable Development Goals (SDGs)",
  "PCB on Livelihood and Employment",
];
const rdpChapterOptions = [
  "4.1 Boost Health Health & Nutrition",
  "4.2 Improve Education and Lifelong Learning Education",
  "4.3.1 Establish Livable Communities (Built Environment) Housing",
  "4.3.2 Establish Livable Communities (Natural Environment) Environment",
  "5 Increase Income-Earning Ability Skills & Employment",
  "5.1 Expand Training and Skills Development Skills",
  "5.2 Intensify Employment Facilitation Employment",
  "6.1 Ensure Food Security and Nutrition Food Security",
  "6.2 Strengthen Social Protection Social Protection",
  "7 Modernize Agriculture and Agri-business Agri",
  "8 Revitalize Industry Industry",
  "9 Reinvigorate Services Services",
  "10 Advance R&D, Technology, and Innovation R&D",
  "11 Promote Trade and Investments Trade",
  "12 Promote Financial Inclusion and Improve Public Financial Management Finance",
  "13 Expand and Upgrade Infrastructure Infrastructure",
  "14.1 Ensure Peace and Security Security",
  "14.2 Enhance Administration of Justice Justice",
  "15 Practice Good Governance and Improve Bureaucratic Efficiency Governance",
  "16 Accelerate Climate Action and Strengthen Disaster Resilience Climate",
];
const statusOptions = ["Completed", "New", "Updated", "Ongoing", "Discontinued", "Not Implemented", "N/A", "Dropped"];
const sdgOptions = [
  "1 - No poverty",
  "2 - Zero hunger",
  "3 - Good health and well-being",
  "4 - Quality education",
  "5 - Gender equality",
  "6- Clean water and sanitation",
  "7 - Affordable and clean energy",
  "8 - Decent work and economic growth",
  "9 - Industry, innovation and infrastructure",
  "10 - Reduced inequalities",
  "11 - Sustainable cities and communities",
  "12 - Responsible consumption and production",
  "13 - Climate action",
  "14 - Life below water",
  "15 - Life on land",
  "16 - Peace, justice and strong institutions",
  "17 - Partnerships for the goals",
];

const toNumber = (raw: string) => {
  const n = Number((raw || "").replace(/[^0-9.-]/g, ""));
  return Number.isFinite(n) ? Math.max(0, n) : 0;
};

const parseYear = (value: string): number | null => {
  const n = Number(String(value || "").trim());
  if (!Number.isInteger(n) || n < 1900 || n > 2200) return null;
  return n;
};

const fmtNumber = (n: number) => (n > 0 ? n.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "0");

const formatMoneyInput = (raw: string) => {
  const cleaned = String(raw || "")
    .replace(/,/g, "")
    .replace(/[^0-9.]/g, "");
  if (!cleaned) return "";

  const hasDecimal = cleaned.includes(".");
  const [integerRaw, ...decimalParts] = cleaned.split(".");
  const integer = (integerRaw || "0").replace(/^0+(?=\d)/, "");
  const formattedInteger = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return hasDecimal ? `${formattedInteger}.${decimalParts.join("")}` : formattedInteger;
};

const stringifyDiffValue = (value: unknown) => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

const normalizeSimplifiedDiffPath = (path: string) => {
  let next = String(path || "").trim();
  if (!next) return "";
  if (next.startsWith("profile_data.")) next = next.slice("profile_data.".length);
  if (next.startsWith("simplified_form.")) next = next.slice("simplified_form.".length);
  if (!next.startsWith("fundingRequirementByYear.") && !next.startsWith("actualFundingByYear.")) {
    next = next.replace(/\.\d+(?=\.|$)/g, "");
  }
  return next;
};

const normalizeFundingMap = (
  raw: unknown,
  legacy: Record<string, unknown>,
  prefix: "fr" | "aa",
): Record<string, string> => {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const next: Record<string, string> = {};
    Object.entries(raw as Record<string, unknown>).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      next[String(key)] = String(value);
    });
    return next;
  }
  const next: Record<string, string> = {};
  const priorKey = `${prefix}2022Prior`;
  if (Object.prototype.hasOwnProperty.call(legacy, priorKey)) {
    const value = legacy[priorKey];
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      next["2022_prior"] = String(value);
    }
  }
  for (let year = 2023; year <= 2028; year += 1) {
    const key = `${prefix}${year}`;
    if (!Object.prototype.hasOwnProperty.call(legacy, key)) continue;
    const value = legacy[key];
    if (value === undefined || value === null || String(value).trim() === "") continue;
    next[String(year)] = String(value);
  }
  return next;
};

const TextField: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  diffBefore?: string;
  editMeta?: EditMeta;
}> = ({ label, value, onChange, required, diffBefore, editMeta }) => {
  const hasEditMeta = Boolean(editMeta && (editMeta.name || editMeta.by || editMeta.at));
  const metaLabel = hasEditMeta
    ? `Last edited by ${editMeta?.name || editMeta?.by || "User"}${editMeta?.at ? ` at ${new Date(editMeta.at).toLocaleString()}` : ""}`
    : "";
  const showPrevious = hasEditMeta && editMeta?.before !== undefined;
  return (
  <label className="block">
    <span className="text-sm text-slate-700">{label}{required ? " *" : ""}</span>
    <input
      className={`mt-1 w-full border rounded p-2 ${diffBefore !== undefined ? "border-amber-500 bg-amber-50" : hasEditMeta ? "border-cyan-500 bg-cyan-50" : ""}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required={required}
    />
    {diffBefore !== undefined && (
      <p className="text-xs text-amber-700 mt-1">Original: {diffBefore || "(empty)"}</p>
    )}
    {showPrevious && (
      <p className="text-xs text-cyan-700 mt-1">Original: {editMeta?.before || "(empty)"}</p>
    )}
    {hasEditMeta && (
      <p className="text-xs text-cyan-700 mt-1">{metaLabel}</p>
    )}
  </label>
  );
};

const TextAreaField: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  rows?: number;
  diffBefore?: string;
  editMeta?: EditMeta;
}> = ({ label, value, onChange, required, rows = 3, diffBefore, editMeta }) => {
  const hasEditMeta = Boolean(editMeta && (editMeta.name || editMeta.by || editMeta.at));
  const metaLabel = hasEditMeta
    ? `Last edited by ${editMeta?.name || editMeta?.by || "User"}${editMeta?.at ? ` at ${new Date(editMeta.at).toLocaleString()}` : ""}`
    : "";
  const showPrevious = hasEditMeta && editMeta?.before !== undefined;
  return (
  <label className="block">
    <span className="text-sm text-slate-700">{label}{required ? " *" : ""}</span>
    <textarea
      className={`mt-1 w-full border rounded p-2 ${diffBefore !== undefined ? "border-amber-500 bg-amber-50" : hasEditMeta ? "border-cyan-500 bg-cyan-50" : ""}`}
      rows={rows}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required={required}
    />
    {diffBefore !== undefined && (
      <p className="text-xs text-amber-700 mt-1">Original: {diffBefore || "(empty)"}</p>
    )}
      {showPrevious && (
        <p className="text-xs text-cyan-700 mt-1">Original: {editMeta?.before || "(empty)"}</p>
      )}
    {hasEditMeta && (
      <p className="text-xs text-cyan-700 mt-1">{metaLabel}</p>
    )}
  </label>
  );
};

const NumberField: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  disabled?: boolean;
  formatMoney?: boolean;
  diffBefore?: string;
  editMeta?: EditMeta;
}> = ({ label, value, onChange, required, disabled, formatMoney, diffBefore, editMeta }) => {
  const hasEditMeta = Boolean(editMeta && (editMeta.name || editMeta.by || editMeta.at));
  const metaLabel = hasEditMeta
    ? `Last edited by ${editMeta?.name || editMeta?.by || "User"}${editMeta?.at ? ` at ${new Date(editMeta.at).toLocaleString()}` : ""}`
    : "";
  const showPrevious = hasEditMeta && editMeta?.before !== undefined;
  const displayValue = formatMoney ? formatMoneyInput(value) : value;
  return (
  <label className="block">
    <span className="text-sm text-slate-700">{label}{required ? " *" : ""}</span>
    <input
      type={formatMoney ? "text" : "number"}
      inputMode="decimal"
      {...(!formatMoney ? { step: "any", min: "0" } : {})}
      className={`mt-1 w-full border rounded p-2 ${disabled ? "bg-slate-100 text-slate-400" : ""} ${diffBefore !== undefined ? "border-amber-500 bg-amber-50" : hasEditMeta ? "border-cyan-500 bg-cyan-50" : ""}`}
      value={displayValue}
      onChange={(e) => onChange(formatMoney ? formatMoneyInput(e.target.value) : e.target.value)}
      required={required}
      disabled={disabled}
    />
    {diffBefore !== undefined && (
      <p className="text-xs text-amber-700 mt-1">Original: {diffBefore || "(empty)"}</p>
    )}
    {showPrevious && (
      <p className="text-xs text-cyan-700 mt-1">Original: {editMeta?.before || "(empty)"}</p>
    )}
    {hasEditMeta && (
      <p className="text-xs text-cyan-700 mt-1">{metaLabel}</p>
    )}
  </label>
  );
};

const CheckboxGroup: React.FC<{
  label: string;
  options: string[];
  values: string[];
  onChange: (values: string[]) => void;
  diffBefore?: string;
  editMeta?: EditMeta;
}> = ({ label, options, values, onChange, diffBefore, editMeta }) => {
  const hasEditMeta = Boolean(editMeta && (editMeta.name || editMeta.by || editMeta.at));
  const metaLabel = hasEditMeta
    ? `Last edited by ${editMeta?.name || editMeta?.by || "User"}${editMeta?.at ? ` at ${new Date(editMeta.at).toLocaleString()}` : ""}`
    : "";
  const showPrevious = hasEditMeta && editMeta?.before !== undefined;
  return (
  <div>
    <p className="text-sm text-slate-700 mb-1">{label}</p>
    <div className={`columns-1 sm:columns-2 lg:columns-3 gap-x-6 border rounded p-2 ${diffBefore !== undefined ? "border-amber-500 bg-amber-50" : hasEditMeta ? "border-cyan-500 bg-cyan-50" : ""}`}>
      {options.map((option) => {
        const checked = values.includes(option);
        return (
          <label key={option} className="mb-2 flex min-w-0 break-inside-avoid items-start gap-2 text-xs">
            <input
              className="mt-0.5"
              type="checkbox"
              checked={checked}
              onChange={(e) => {
                if (e.target.checked) onChange([...values, option]);
                else onChange(values.filter((v) => v !== option));
              }}
            />
            <span className="min-w-0 whitespace-normal break-words">{option}</span>
          </label>
        );
      })}
    </div>
    {diffBefore !== undefined && (
      <p className="text-xs text-amber-700 mt-1">Original: {diffBefore || "(empty)"}</p>
    )}
    {showPrevious && (
      <p className="text-xs text-cyan-700 mt-1">Original: {editMeta?.before || "(empty)"}</p>
    )}
    {hasEditMeta && (
      <p className="text-xs text-cyan-700 mt-1">{metaLabel}</p>
    )}
  </div>
  );
};

const SelectField: React.FC<{
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  required?: boolean;
  diffBefore?: string;
  editMeta?: EditMeta;
}> = ({ label, value, onChange, options, required, diffBefore, editMeta }) => {
  const hasEditMeta = Boolean(editMeta && (editMeta.name || editMeta.by || editMeta.at));
  const metaLabel = hasEditMeta
    ? `Last edited by ${editMeta?.name || editMeta?.by || "User"}${editMeta?.at ? ` at ${new Date(editMeta.at).toLocaleString()}` : ""}`
    : "";
  const showPrevious = hasEditMeta && editMeta?.before !== undefined;
  return (
  <label className="block">
    <span className="text-sm text-slate-700">{label}{required ? " *" : ""}</span>
    <select
      className={`mt-1 w-full border rounded p-2 ${diffBefore !== undefined ? "border-amber-500 bg-amber-50" : hasEditMeta ? "border-cyan-500 bg-cyan-50" : ""}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required={required}
    >
      <option value="">Choose</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
    {diffBefore !== undefined && (
      <p className="text-xs text-amber-700 mt-1">Original: {diffBefore || "(empty)"}</p>
    )}
    {showPrevious && (
      <p className="text-xs text-cyan-700 mt-1">Original: {editMeta?.before || "(empty)"}</p>
    )}
    {hasEditMeta && (
      <p className="text-xs text-cyan-700 mt-1">{metaLabel}</p>
    )}
  </label>
  );
};

const SimplifiedProjectSubmission: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const isEditMode = Boolean(id);

  const userRaw = localStorage.getItem("user");
  const user = userRaw ? JSON.parse(userRaw) : null;
  const [form, setForm] = useState<SimplifiedForm>(initialForm);
  const [loading, setLoading] = useState(false);
  const [canEncode, setCanEncode] = useState(true);
  const [encodeMessage, setEncodeMessage] = useState("");
  const [projectStatus, setProjectStatus] = useState<string>("planning");
  const [formReady, setFormReady] = useState(false);
  const [localDraftHydrated, setLocalDraftHydrated] = useState(false);
  const [restoreNotice, setRestoreNotice] = useState("");
  const [lastLocalSaveAt, setLastLocalSaveAt] = useState("");
  const [serverUpdatedAt, setServerUpdatedAt] = useState<string | null>(null);
  const [validatorNotes, setValidatorNotes] = useState("");
  const [validatorReviewStatus, setValidatorReviewStatus] = useState("");
  const [diffMap, setDiffMap] = useState<Record<string, DiffField>>({});
  const [diffEntries, setDiffEntries] = useState<Array<{ field: string; before: string; after: string }>>([]);
  const [fieldEditMeta, setFieldEditMeta] = useState<Record<string, EditMeta>>({});
  const [comments, setComments] = useState<ProjectComment[]>([]);
  const [commentInput, setCommentInput] = useState("");
  const [commentLoading, setCommentLoading] = useState(false);
  const isValidator = user?.role === "validator";
  const isAdmin = user?.role === "admin";
  const isEmployee = user?.role === "employee";
  const isDiffMode = isAdmin && searchParams.get("mode") === "diff";
  const normalizedReviewStatus = validatorReviewStatus === "validated" ? "endorsed" : validatorReviewStatus;
  const formRef = useRef(form);

  const draftStorageKey = useMemo(() => {
    const identity =
      user?.username ||
      user?.email ||
      (user?.id ? String(user.id) : "") ||
      user?.role ||
      "";
    if (!identity) return "";
    return `simplified_submission_draft_v3_${identity}_${id || "new"}`;
  }, [user?.username, user?.email, user?.id, user?.role, id]);

  const updateFormWithLocalDraft = (updater: (prev: SimplifiedForm) => SimplifiedForm) => {
    setForm((prev) => {
      const next = updater(prev);
      formRef.current = next;
      if (isEmployee && draftStorageKey) {
        try {
          localStorage.setItem(
            draftStorageKey,
            JSON.stringify({
              form: next,
              savedAt: new Date().toISOString(),
            }),
          );
        } catch (error) {
          console.error("Failed to persist simplified local draft:", error);
        }
      }
      return next;
    });
  };

  useEffect(() => {
    if (!user) {
      navigate("/login");
      return;
    }
    const loadEncoding = async () => {
      try {
        const state = await api.get("encoding-window/");
        setCanEncode(Boolean(state?.can_encode));
        setEncodeMessage(state?.message || "");
      } catch {
        setCanEncode(true);
      }
    };
    loadEncoding();
  }, [navigate, user]);

  useEffect(() => {
    const loadExisting = async () => {
      if (!isEditMode || !id) {
        setFormReady(true);
        return;
      }
      try {
        const base = isValidator ? "validator" : isAdmin ? "admin" : "employee";
        const data = await api.get(`${base}/projects/${id}/`);
        setProjectStatus(data?.status || "planning");
        if (data?.updated_at) {
          setServerUpdatedAt(String(data.updated_at));
        }
        const pd = (data?.profile_data || {}) as Record<string, unknown>;
        const metaRaw = pd?.simplified_form_meta;
        const editsRaw =
          metaRaw && typeof metaRaw === "object" && (metaRaw as Record<string, unknown>).field_edits;
        if (editsRaw && typeof editsRaw === "object") {
          setFieldEditMeta(editsRaw as Record<string, EditMeta>);
        } else {
          setFieldEditMeta({});
        }
        const validatorReview = pd?.validator_review as Record<string, unknown> | undefined;
        const contributorSnapshot =
          pd?.contributor_snapshot && typeof pd.contributor_snapshot === "object"
            ? (pd.contributor_snapshot as Record<string, unknown>)
            : pd;
        const workingCopy =
          validatorReview && typeof validatorReview.working_copy === "object"
            ? (validatorReview.working_copy as Record<string, unknown>)
            : contributorSnapshot;
        const sourceData = isValidator
          ? workingCopy
          : isAdmin
          ? (isDiffMode ? workingCopy : contributorSnapshot)
          : pd;
        const simplified = (sourceData.simplified_form || sourceData) as Partial<SimplifiedForm> & Record<string, unknown>;
        const fundingRequirementByYear = normalizeFundingMap(
          simplified.fundingRequirementByYear,
          simplified,
          "fr",
        );
        const actualFundingByYear = normalizeFundingMap(
          simplified.actualFundingByYear,
          simplified,
          "aa",
        );
        setForm({
          ...initialForm,
          ...simplified,
          fundingRequirementByYear,
          actualFundingByYear,
          agencyName: String(simplified.agencyName || data?.agency || ""),
          projectActivity: String(simplified.projectActivity || data?.title || data?.name || ""),
        });
        if (isValidator && validatorReview) {
          setValidatorNotes(String(validatorReview.review_notes || ""));
          const status = String(validatorReview.review_status || "").toLowerCase();
          setValidatorReviewStatus(status === "validated" ? "endorsed" : status);
        } else if (isValidator) {
          setValidatorReviewStatus("");
        }
        if (isAdmin && isDiffMode && Array.isArray(validatorReview?.edited_fields)) {
          const nextDiffs: Record<string, DiffField> = {};
          const nextEntries: Array<{ field: string; before: string; after: string }> = [];
          for (const raw of validatorReview.edited_fields as Array<Record<string, unknown>>) {
            const key = normalizeSimplifiedDiffPath(String(raw?.field || ""));
            if (!key) continue;
            const before = stringifyDiffValue(raw?.before);
            const after = stringifyDiffValue(raw?.after);
            nextDiffs[key] = {
              before,
              after,
            };
            nextEntries.push({ field: key, before, after });
          }
          setDiffMap(nextDiffs);
          setDiffEntries(nextEntries);
        } else {
          setDiffMap({});
          setDiffEntries([]);
        }
      } catch (error) {
        console.error("Failed to load simplified project:", error);
      } finally {
        setFormReady(true);
      }
    };
    loadExisting();
  }, [id, isEditMode, navigate, isValidator, isAdmin, isDiffMode]);

  useEffect(() => {
    formRef.current = form;
  }, [form]);

  useEffect(() => {
    if (!isEmployee || !formReady || !draftStorageKey) return;
    setLocalDraftHydrated(false);
    try {
      const raw = localStorage.getItem(draftStorageKey);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { form?: Partial<SimplifiedForm>; savedAt?: string };
      if (!parsed?.form || typeof parsed.form !== "object") return;
      if (parsed.savedAt && serverUpdatedAt) {
        const localTime = new Date(parsed.savedAt).getTime();
        const serverTime = new Date(serverUpdatedAt).getTime();
        if (!Number.isNaN(localTime) && !Number.isNaN(serverTime) && localTime <= serverTime) {
          return;
        }
      }
      setForm((prev) => ({ ...prev, ...parsed.form }));
      if (parsed.savedAt) setLastLocalSaveAt(parsed.savedAt);
      setRestoreNotice("Recovered your unsaved local inputs from this browser.");
    } catch (error) {
      console.error("Failed to restore simplified local draft:", error);
    } finally {
      setLocalDraftHydrated(true);
    }
  }, [isEmployee, formReady, draftStorageKey, serverUpdatedAt]);

  const commentEndpointBase = isAdmin
    ? "admin/projects"
    : isValidator
    ? "validator/projects"
    : "employee/projects";

  const loadComments = async () => {
    if (!id) return;
    try {
      const data = await api.get(`${commentEndpointBase}/${id}/comments/`);
      setComments(Array.isArray(data) ? data : []);
    } catch {
      setComments([]);
    }
  };

  const submitComment = async () => {
    if (!id || !commentInput.trim()) return;
    setCommentLoading(true);
    try {
      const data = await api.post(`${commentEndpointBase}/${id}/comments/`, { comment: commentInput.trim() });
      setComments((prev) => [data, ...prev]);
      setCommentInput("");
    } catch (error) {
      console.error("Failed to add comment:", error);
    } finally {
      setCommentLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    loadComments();
  }, [id]);

  useEffect(() => {
    if (!isEmployee || isEditMode || !formReady) return;
    if (user?.agency && !form.agencyName.trim()) {
      updateFormWithLocalDraft((prev) => ({ ...prev, agencyName: String(user.agency || "") }));
    }
  }, [isEmployee, isEditMode, formReady, user?.agency, form.agencyName]);

  useEffect(() => {
    if (!isEmployee || !formReady || !localDraftHydrated || !draftStorageKey) return;
    const timer = window.setTimeout(() => {
      try {
        const savedAt = new Date().toISOString();
        localStorage.setItem(
          draftStorageKey,
          JSON.stringify({
            form,
            savedAt,
          }),
        );
        setLastLocalSaveAt(savedAt);
      } catch (error) {
        console.error("Failed to autosave simplified local draft:", error);
      }
    }, 600);
    return () => window.clearTimeout(timer);
  }, [isEmployee, form, draftStorageKey, formReady, localDraftHydrated]);

  useEffect(() => {
    if (!isEmployee || !formReady || !localDraftHydrated || !draftStorageKey) return;
    const persistNow = () => {
      try {
        localStorage.setItem(
          draftStorageKey,
          JSON.stringify({
            form: formRef.current,
            savedAt: new Date().toISOString(),
          }),
        );
      } catch (error) {
        console.error("Failed to persist simplified local draft before unload:", error);
      }
    };
    const handleVisibility = () => {
      if (document.hidden) persistNow();
    };
    const handlePageHide = () => persistNow();
    window.addEventListener("beforeunload", persistNow);
    window.addEventListener("pagehide", handlePageHide);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("beforeunload", persistNow);
      window.removeEventListener("pagehide", handlePageHide);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [isEmployee, draftStorageKey, formReady, localDraftHydrated]);

  const startYearNum = useMemo(() => parseYear(form.startYear), [form.startYear]);
  const endYearNum = useMemo(() => parseYear(form.endYear), [form.endYear]);
  const fundingRange = useMemo(() => {
    if (startYearNum === null || endYearNum === null) return null;
    return {
      start: Math.min(startYearNum, endYearNum),
      end: Math.max(startYearNum, endYearNum),
    };
  }, [startYearNum, endYearNum]);

  const rangeTooLarge = useMemo(() => {
    if (!fundingRange) return false;
    return fundingRange.end - fundingRange.start > 15;
  }, [fundingRange]);

  const showPriorBucket = useMemo(() => {
    if (!fundingRange) return false;
    return fundingRange.start <= 2022;
  }, [fundingRange]);

  const yearKeys = useMemo(() => {
    if (!fundingRange) return [] as string[];
    const keys: string[] = [];
    if (showPriorBucket) keys.push("2022_prior");
    const firstYear = showPriorBucket ? Math.max(2023, fundingRange.start) : fundingRange.start;
    for (let year = firstYear; year <= fundingRange.end; year += 1) {
      keys.push(String(year));
    }
    return keys;
  }, [fundingRange, showPriorBucket]);

  const pruneMap = (map: Record<string, string>, keys: string[]) => {
    const next: Record<string, string> = {};
    keys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(map, key)) {
        next[key] = String(map[key] ?? "");
      }
    });
    return next;
  };

  const mapsEqual = (a: Record<string, string>, b: Record<string, string>) => {
    const aKeys = Object.keys(a);
    const bKeys = Object.keys(b);
    if (aKeys.length !== bKeys.length) return false;
    return aKeys.every((key) => a[key] === b[key]);
  };

  useEffect(() => {
    if (!yearKeys.length) return;
    updateFormWithLocalDraft((prev) => {
      const nextFr = pruneMap(prev.fundingRequirementByYear, yearKeys);
      const nextAa = pruneMap(prev.actualFundingByYear, yearKeys);
      if (mapsEqual(prev.fundingRequirementByYear, nextFr) && mapsEqual(prev.actualFundingByYear, nextAa)) {
        return prev;
      }
      return {
        ...prev,
        fundingRequirementByYear: nextFr,
        actualFundingByYear: nextAa,
      };
    });
  }, [yearKeys.join("|")]);

  const frTotal = useMemo(
    () => yearKeys.reduce((sum, key) => sum + toNumber(form.fundingRequirementByYear[key] || ""), 0),
    [yearKeys, form.fundingRequirementByYear],
  );
  const aaTotal = useMemo(
    () => yearKeys.reduce((sum, key) => sum + toNumber(form.actualFundingByYear[key] || ""), 0),
    [yearKeys, form.actualFundingByYear],
  );

  const isReadOnly =
    isAdmin ||
    (isEmployee && !canEncode) ||
    (isEmployee && isEditMode && projectStatus !== "planning") ||
    (isValidator && normalizedReviewStatus === "endorsed");
  const formatDiffFieldLabel = (field: string) => {
    if (field.startsWith("fundingRequirementByYear.")) {
      const key = field.split(".")[1] || "";
      return `Funding Requirement ${key === "2022_prior" ? "2022 & Prior" : key}`;
    }
    if (field.startsWith("actualFundingByYear.")) {
      const key = field.split(".")[1] || "";
      return `Actual Funding ${key === "2022_prior" ? "2022 & Prior" : key}`;
    }
    return field;
  };
  const diffOf = (field: string) => diffMap[field];
  const editMetaOf = (field: string) => fieldEditMeta[field];

  const setField = <K extends keyof SimplifiedForm>(key: K, value: SimplifiedForm[K]) => {
    updateFormWithLocalDraft((prev) => ({ ...prev, [key]: value }));
  };

  const save = async (e: React.FormEvent, action: FormAction) => {
    e.preventDefault();
    if (isReadOnly) {
      alert(isAdmin ? "Admin form view is read-only." : encodeMessage || "Encoding is closed. This form is view-only.");
      return;
    }
    if (isValidator && !id) {
      alert("Validator review requires an existing project.");
      return;
    }
    if (rangeTooLarge) {
      alert("Year range is too large. Please keep the span within 15 years.");
      return;
    }
    const required: Array<keyof SimplifiedForm> = [
      "agencyName",
      "program",
      "projectActivity",
      "location",
      "description",
      "objective",
      "startYear",
      "endYear",
      "fundingSource",
      "rdcEndorsed",
      "pipIncluded",
      "arnipapIncluded",
      "ludipIncluded",
      "ifpsIncluded",
      "pcbIncluded",
      "developmentSector",
      "rdpMainChapter",
      "status",
    ];
    if (form.status !== "New") {
      required.push("physicalAccomplishment", "financialAccomplishment");
    }
    if (!isValidator && action === "submit") {
      const missing = required.filter((k) => !String(form[k] || "").trim());
      if (missing.length > 0) {
        alert("Please complete all required fields before submit.");
        return;
      }
      if (parseYear(form.startYear) === null || parseYear(form.endYear) === null) {
        alert("Start Year and End Year must be valid years.");
        return;
      }
      if (form.pcbIncluded === "Yes" && !form.pcbProgram.trim()) {
        alert("Please select the convergence program (PCB).");
        return;
      }
    }

    setLoading(true);
    try {
      const normalizedProfileData = {
        submission_type: "simplified",
        templateName: "RDIP 2023-2028 Simplified",
        simplified_form: {
          ...form,
          fundingRequirementTotal: frTotal,
          actualApprovedTotal: aaTotal,
        },
      };

      if (isValidator && id) {
        const validatorAction =
          action === "draft"
            ? "save_draft"
            : action === "reviewed"
            ? "save_reviewed"
            : action === "endorsed"
            ? "endorse"
            : "save_reviewed";
        if (
          validatorAction === "endorse" &&
          normalizedReviewStatus !== "reviewed" &&
          normalizedReviewStatus !== "endorsed"
        ) {
          const ok = window.confirm(
            "This will endorse the project without a prior Reviewed state. Continue?",
          );
          if (!ok) {
            setLoading(false);
            return;
          }
        }
        const response = await api.post(`validator/projects/${id}/validate/`, {
          action: validatorAction,
          notes: validatorNotes,
          edited_profile_data: normalizedProfileData,
        });
        localStorage.setItem("projects_last_update", Date.now().toString());
        if (response?.warning) {
          alert(response.warning);
        }
        const nextStatus = String(response?.review_status || "");
        if (nextStatus) setValidatorReviewStatus(nextStatus);
        alert(
          action === "draft"
            ? "Saved as draft."
            : action === "reviewed"
            ? "Saved as reviewed."
            : "Project endorsed.",
        );
        navigate("/validator/projects");
        return;
      }

      const payload: Record<string, unknown> = {
        title: form.projectActivity || form.program || "Untitled Project",
        description: form.description || form.objective || form.remarks || form.projectActivity || "",
        agency: form.agencyName,
        budget: Math.round(frTotal),
        completion: 0,
        municipality: "NCR",
        profile_data: normalizedProfileData,
      };
      if (action === "save") {
        payload.status = "draft";
      }
      let targetId = id;
      if (isEditMode && id) {
        await api.put(`employee/projects/${id}/`, payload);
      } else {
        const created = await api.post("employee/projects/", payload);
        targetId = String(created?.id || "");
      }
      if (action === "submit" && targetId) {
        await api.post(`employee/projects/${targetId}/submit/`, {});
      }
      if (draftStorageKey) {
        localStorage.removeItem(draftStorageKey);
      }
      localStorage.setItem("projects_last_update", Date.now().toString());
      alert(action === "save" ? "Simplified draft saved." : "Simplified submission sent for validation.");
      navigate(isAdmin ? "/admin/projects" : "/employee/projects");
    } catch (error) {
      console.error(error);
      const detail = error instanceof Error ? error.message : "";
      alert(detail ? `Failed to save simplified form. ${detail}` : "Failed to save simplified form.");
    } finally {
      setLoading(false);
    }
  };

  if (!user) return <div className="min-h-screen flex items-center justify-center">Loading...</div>;
  const localSavedLabel = lastLocalSaveAt ? new Date(lastLocalSaveAt).toLocaleString() : "";
  const displayName = user?.full_name || user?.username || "User";

  return (
    <PortalLayout
      title={
        isValidator
          ? "Validator Simplified Review Form"
          : isAdmin
          ? "Admin Simplified Form View"
          : isEditMode
          ? "Simplified RDIP Submission Editor"
          : "New Simplified RDIP Submission"
      }
      subtitle={
        isValidator
          ? "Edit reviewer working copy without changing contributor original"
          : isAdmin
          ? isDiffMode
            ? "Read-only validator diff view with original contributor values"
            : "Read-only contributor submission view"
          : "RDIP 2023-2028 list of projects format (data-type aligned)"
      }
      role={(user.role || "employee") as "admin" | "validator" | "employee"}
      userName={displayName}
      topActions={
        <>
          <button type="button" onClick={() => navigate(isValidator ? "/validator/projects" : isAdmin ? "/admin/projects" : "/employee/projects")} className="portal-btn portal-btn-ghost">Back to Projects</button>
        </>
      }
    >
      {!canEncode && (
        <div className="portal-card p-3 mb-3 border-amber-200 bg-amber-50 text-amber-800">
          {encodeMessage || "Encoding is currently closed by admin."}
        </div>
      )}
      {isEditMode && isEmployee && projectStatus !== "planning" && (
        <div className="portal-card p-3 mb-3 border-blue-200 bg-blue-50 text-blue-800">
          This submission is already sent and is now view-only for contributors.
        </div>
      )}
      {(restoreNotice || localSavedLabel) && (
        <div className="portal-card p-3 mb-3 border-emerald-200 bg-emerald-50 text-emerald-800 text-sm">
          {restoreNotice || "Local draft autosave is active."}
          {localSavedLabel ? ` Last local save: ${localSavedLabel}` : ""}
        </div>
      )}
      {isValidator && (
        <div className="portal-card p-3 mb-3 border-indigo-200 bg-indigo-50 text-indigo-800 text-sm">
          You are editing a validator review copy. Contributor original form remains unchanged.
        </div>
      )}
      {isValidator && normalizedReviewStatus === "endorsed" && (
        <div className="portal-card p-3 mb-3 border-emerald-200 bg-emerald-50 text-emerald-800 text-sm">
          This project is already endorsed and is now view-only.
        </div>
      )}
      {isAdmin && (
        <div className={`portal-card p-3 mb-3 text-sm ${isDiffMode ? "border-amber-200 bg-amber-50 text-amber-800" : "border-slate-200 bg-slate-50 text-slate-700"}`}>
          {isDiffMode
            ? `Diff mode is active. Highlighted fields were edited by validator. Changed fields: ${Object.keys(diffMap).length}.`
            : "Admin read-only mode. This shows the contributor's original submitted form values."}
        </div>
      )}
      {isAdmin && isDiffMode && diffEntries.length > 0 && (
        <div className="portal-card mb-3 border-amber-200">
          <div className="px-3 py-2 border-b border-amber-200 bg-amber-50 text-amber-900 text-sm font-semibold">
            Validator Edited Fields
          </div>
          <div className="max-h-64 overflow-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 sticky top-0">
                <tr>
                  <th className="px-2 py-1 text-left">Field</th>
                  <th className="px-2 py-1 text-left">Original</th>
                  <th className="px-2 py-1 text-left">Validator Copy</th>
                </tr>
              </thead>
              <tbody>
                {diffEntries.slice(0, 200).map((entry, idx) => (
                  <tr key={`${entry.field}-${idx}`} className="border-t border-slate-100 align-top">
                    <td className="px-2 py-1 font-mono">{formatDiffFieldLabel(entry.field)}</td>
                    <td className="px-2 py-1 whitespace-pre-wrap break-words">{entry.before || "(empty)"}</td>
                    <td className="px-2 py-1 whitespace-pre-wrap break-words">{entry.after || "(empty)"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <form onSubmit={(e) => save(e, "submit")} className="portal-card p-3 sm:p-4 lg:p-6 space-y-6">
        <fieldset disabled={isReadOnly} className="space-y-6">
          <div className="rounded-lg border border-slate-200 p-4 space-y-4">
            <TextField label="Agency Name" value={form.agencyName} onChange={(v) => setField("agencyName", v)} required diffBefore={diffOf("agencyName")?.before} editMeta={editMetaOf("agencyName")} />
            <TextField label="Program" value={form.program} onChange={(v) => setField("program", v)} required diffBefore={diffOf("program")?.before} editMeta={editMetaOf("program")} />
            <TextField label="Project/Activity" value={form.projectActivity} onChange={(v) => setField("projectActivity", v)} required diffBefore={diffOf("projectActivity")?.before} editMeta={editMetaOf("projectActivity")} />
            <TextField label="Location" value={form.location} onChange={(v) => setField("location", v)} required diffBefore={diffOf("location")?.before} editMeta={editMetaOf("location")} />
            <TextAreaField label="Description" value={form.description} onChange={(v) => setField("description", v)} required rows={4} diffBefore={diffOf("description")?.before} editMeta={editMetaOf("description")} />
            <TextAreaField label="Objective" value={form.objective} onChange={(v) => setField("objective", v)} required rows={4} diffBefore={diffOf("objective")?.before} editMeta={editMetaOf("objective")} />
          </div>

          <div className="rounded-lg border border-slate-200 p-4 space-y-4">
            <div className="space-y-2">
              <h3 className="font-semibold">Implementation Period</h3>
              <div className="grid sm:grid-cols-2 gap-4">
                <NumberField label="Start Year" value={form.startYear} onChange={(v) => setField("startYear", v)} required diffBefore={diffOf("startYear")?.before} editMeta={editMetaOf("startYear")} />
                <NumberField label="End Year" value={form.endYear} onChange={(v) => setField("endYear", v)} required diffBefore={diffOf("endYear")?.before} editMeta={editMetaOf("endYear")} />
              </div>
            </div>

            <div className="border-t border-slate-200" />

            <div className="grid xl:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h3 className="font-semibold">Funding Requirement (PHP)</h3>
                {yearKeys.length === 0 ? (
                  <p className="text-sm text-slate-500">Enter Start Year and End Year to generate fields.</p>
                ) : (
                  <div className="grid sm:grid-cols-3 gap-2">
                    {yearKeys.map((key) => (
                      <NumberField
                        key={`fr-${key}`}
                        label={key === "2022_prior" ? "2022 & Prior" : key}
                        value={form.fundingRequirementByYear[key] || ""}
                        onChange={(v) =>
                          updateFormWithLocalDraft((prev) => ({
                            ...prev,
                            fundingRequirementByYear: { ...prev.fundingRequirementByYear, [key]: v },
                          }))
                        }
                        diffBefore={diffOf(`fundingRequirementByYear.${key}`)?.before}
                        editMeta={editMetaOf(`fundingRequirementByYear.${key}`)}
                        formatMoney
                      />
                    ))}
                  </div>
                )}
                <p className="text-sm text-slate-600">Total: <strong>{fmtNumber(frTotal)}</strong></p>
              </div>
              <div className="space-y-2">
                <h3 className="font-semibold">Actual/Approved Funding (PHP)</h3>
                {yearKeys.length === 0 ? (
                  <p className="text-sm text-slate-500">Enter Start Year and End Year to generate fields.</p>
                ) : (
                  <div className="grid sm:grid-cols-3 gap-2">
                    {yearKeys.map((key) => (
                      <NumberField
                        key={`aa-${key}`}
                        label={key === "2022_prior" ? "2022 & Prior" : key}
                        value={form.actualFundingByYear[key] || ""}
                        onChange={(v) =>
                          updateFormWithLocalDraft((prev) => ({
                            ...prev,
                            actualFundingByYear: { ...prev.actualFundingByYear, [key]: v },
                          }))
                        }
                        diffBefore={diffOf(`actualFundingByYear.${key}`)?.before}
                        editMeta={editMetaOf(`actualFundingByYear.${key}`)}
                        formatMoney
                      />
                    ))}
                  </div>
                )}
                <p className="text-sm text-slate-600">Total: <strong>{fmtNumber(aaTotal)}</strong></p>
              </div>
            </div>
            {rangeTooLarge && (
              <p className="text-xs text-rose-600">Year range is too large. Please keep the span within 15 years.</p>
            )}
            <p className="text-xs text-slate-600">
              Editable budget fields are controlled by Start Year and End Year.
              Current range: {fundingRange ? (showPriorBucket
                ? fundingRange.end < 2023
                  ? "2022 & Prior"
                  : `2022 & Prior, ${Math.max(2023, fundingRange.start)} to ${fundingRange.end}`
                : fundingRange.start === fundingRange.end
                ? String(fundingRange.start)
                : `${fundingRange.start} to ${fundingRange.end}`) : "not set"}.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 p-4 space-y-4">
            <div className="grid xl:grid-cols-2 gap-4">
              <SelectField label="Funding Source" value={form.fundingSource} onChange={(v) => setField("fundingSource", v)} options={fundingSourceOptions} required diffBefore={diffOf("fundingSource")?.before} editMeta={editMetaOf("fundingSource")} />
              <TextField label="UACS Code (if GAA-funded)" value={form.uacsCode} onChange={(v) => setField("uacsCode", v)} diffBefore={diffOf("uacsCode")?.before} editMeta={editMetaOf("uacsCode")} />
              <SelectField label="PIP Included" value={form.pipIncluded} onChange={(v) => setField("pipIncluded", v as YesNo)} options={yesNoOptions} required diffBefore={diffOf("pipIncluded")?.before} editMeta={editMetaOf("pipIncluded")} />
              <SelectField label="ARNIPAP Included" value={form.arnipapIncluded} onChange={(v) => setField("arnipapIncluded", v as YesNo)} options={yesNoOptions} required diffBefore={diffOf("arnipapIncluded")?.before} editMeta={editMetaOf("arnipapIncluded")} />
              <SelectField label="LUDIP (for SUCs)" value={form.ludipIncluded} onChange={(v) => setField("ludipIncluded", v as YesNo)} options={yesNoNaOptions} required diffBefore={diffOf("ludipIncluded")?.before} editMeta={editMetaOf("ludipIncluded")} />
              <SelectField label="IFPs Included" value={form.ifpsIncluded} onChange={(v) => setField("ifpsIncluded", v as YesNo)} options={yesNoOptions} required diffBefore={diffOf("ifpsIncluded")?.before} editMeta={editMetaOf("ifpsIncluded")} />
              <SelectField
                label="Part of the Convergence Program (PCB)"
                value={form.pcbIncluded}
                onChange={(v) =>
                  updateFormWithLocalDraft((prev) => ({
                    ...prev,
                    pcbIncluded: v as YesNo,
                    ...(v === "No" ? { pcbProgram: "" } : {}),
                  }))
                }
                options={yesNoOptions}
                required
                diffBefore={diffOf("pcbIncluded")?.before}
                editMeta={editMetaOf("pcbIncluded")}
              />
              {form.pcbIncluded === "Yes" && (
                <SelectField
                  label="Convergence Program (PCB)"
                  value={form.pcbProgram}
                  onChange={(v) => setField("pcbProgram", v)}
                  options={pcbProgramOptions}
                  required
                  diffBefore={diffOf("pcbProgram")?.before}
                  editMeta={editMetaOf("pcbProgram")}
                />
              )}
              <SelectField label="RDC-NCR Endorsed" value={form.rdcEndorsed} onChange={(v) => setField("rdcEndorsed", v as YesNo)} options={yesNoOptions} required diffBefore={diffOf("rdcEndorsed")?.before} editMeta={editMetaOf("rdcEndorsed")} />
              <SelectField label="RDC-NCR Development Sector" value={form.developmentSector} onChange={(v) => setField("developmentSector", v)} options={developmentSectorOptions} required diffBefore={diffOf("developmentSector")?.before} editMeta={editMetaOf("developmentSector")} />
              <SelectField label="RDP-NCR Main Chapter" value={form.rdpMainChapter} onChange={(v) => setField("rdpMainChapter", v)} options={rdpChapterOptions} required diffBefore={diffOf("rdpMainChapter")?.before} editMeta={editMetaOf("rdpMainChapter")} />
              <SelectField label="Status" value={form.status} onChange={(v) => setField("status", v)} options={statusOptions} required diffBefore={diffOf("status")?.before} editMeta={editMetaOf("status")} />
            </div>

            <CheckboxGroup
              label="Sustainable Development Goals"
              options={sdgOptions}
              values={form.sdgSelections}
              onChange={(values) => setField("sdgSelections", values)}
              diffBefore={diffOf("sdgSelections")?.before}
              editMeta={editMetaOf("sdgSelections")}
            />

            {form.status !== "New" && (
              <div className="grid xl:grid-cols-2 gap-4">
                <TextAreaField label="Physical Accomplishment" value={form.physicalAccomplishment} onChange={(v) => setField("physicalAccomplishment", v)} required rows={3} diffBefore={diffOf("physicalAccomplishment")?.before} editMeta={editMetaOf("physicalAccomplishment")} />
                <TextAreaField label="Financial Accomplishment" value={form.financialAccomplishment} onChange={(v) => setField("financialAccomplishment", v)} required rows={3} diffBefore={diffOf("financialAccomplishment")?.before} editMeta={editMetaOf("financialAccomplishment")} />
              </div>
            )}
            <TextAreaField label="Remarks" value={form.remarks} onChange={(v) => setField("remarks", v)} rows={4} diffBefore={diffOf("remarks")?.before} editMeta={editMetaOf("remarks")} />
          </div>

          {isValidator && (
            <div className="rounded-lg border border-slate-200 p-4 space-y-2">
              <label className="block">
                <span className="text-sm text-slate-700">Validator Notes</span>
                <textarea
                  className="mt-1 w-full border rounded p-2"
                  rows={3}
                  value={validatorNotes}
                  onChange={(e) => setValidatorNotes(e.target.value)}
                  placeholder="Optional notes for admin and audit trail"
                />
              </label>
            </div>
          )}

          {!isAdmin && (
            <div className="pt-4 border-t flex flex-wrap gap-3 justify-end">
              {isValidator ? (
                <>
                  <button
                    type="button"
                    onClick={(e) => save(e as unknown as React.FormEvent, "draft")}
                    className="portal-btn portal-btn-ghost"
                    disabled={loading || isReadOnly || rangeTooLarge}
                  >
                    {loading ? "Saving..." : "Save as Draft"}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => save(e as unknown as React.FormEvent, "reviewed")}
                    className="portal-btn portal-btn-ghost"
                    disabled={loading || isReadOnly || rangeTooLarge}
                  >
                    {loading ? "Saving..." : "Save as Reviewed"}
                  </button>
                  <button
                    type="button"
                    onClick={(e) => save(e as unknown as React.FormEvent, "endorsed")}
                    className="portal-btn portal-btn-primary"
                    disabled={loading || isReadOnly || rangeTooLarge}
                  >
                    {loading ? "Submitting..." : "Save as Endorsed"}
                  </button>
                </>
              ) : (
                <>
                  <button type="button" onClick={(e) => save(e as unknown as React.FormEvent, "save")} className="portal-btn portal-btn-ghost" disabled={loading || isReadOnly || rangeTooLarge}>
                    {loading ? "Saving..." : "Save Draft"}
                  </button>
                  <button type="submit" className="portal-btn portal-btn-primary" disabled={loading || isReadOnly || rangeTooLarge}>
                    {loading ? "Submitting..." : "Submit for Validation"}
                  </button>
                </>
              )}
            </div>
          )}
        </fieldset>
      </form>
      {id && (
        <div className="portal-card mt-4">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Project Comments</h2>
          </div>
          <div className="portal-card-body space-y-4">
            <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
              {comments.length === 0 ? (
                <p className="text-sm text-slate-500">No comments yet.</p>
              ) : (
                comments.map((c) => (
                  <div key={c.id} className="border rounded-lg p-3">
                    <p className="text-sm text-slate-800">{c.comment}</p>
                    <p className="text-xs text-slate-500 mt-2">
                      {c.full_name || c.username || "User"}{" "}
                      <span className="uppercase">{c.role || ""}</span>{" "}
                      {c.created_at ? `- ${new Date(c.created_at).toLocaleString()}` : ""}
                    </p>
                  </div>
                ))
              )}
            </div>
            <div className="border-t pt-3">
              <label className="block text-sm text-slate-700 mb-2">Add a comment</label>
              <textarea
                value={commentInput}
                onChange={(e) => setCommentInput(e.target.value)}
                rows={3}
                className="w-full border rounded-lg px-3 py-2"
                placeholder="Write a note for your agency team..."
              />
              <div className="mt-2 flex justify-end">
                <button
                  type="button"
                  onClick={submitComment}
                  disabled={commentLoading || !commentInput.trim()}
                  className="portal-btn portal-btn-primary"
                >
                  {commentLoading ? "Posting..." : "Post Comment"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PortalLayout>
  );
};

export default SimplifiedProjectSubmission;
