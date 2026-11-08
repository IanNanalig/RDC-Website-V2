export const CONTRIBUTOR_DOCUMENT_MAX_BYTES = 50 * 1024 * 1024;
export const CONTRIBUTOR_DOCUMENT_MAX_TOTAL_BYTES = 200 * 1024 * 1024;

export type ContributorFormFieldType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "year"
  | "select"
  | "multiselect"
  | "multiselect_dropdown"
  | "currency_by_year"
  | "document_upload";

export type ContributorFormOption = { value: string; label: string };
export type ContributorConditionOperator =
  | "equals" | "not_equals" | "one_of" | "not_one_of"
  | "contains" | "not_contains" | "contains_any"
  | "is_empty" | "is_not_empty"
  | "greater_than" | "less_than" | "at_least" | "at_most"
  | "before" | "after";
export type ContributorConditionRule = {
  field: string;
  operator: ContributorConditionOperator;
  value?: string;
  values?: string[];
};
export type ContributorConditionGroup = {
  match: "all" | "any";
  conditions: ContributorConditionRule[];
};

export type ContributorFormRetiredOrigin = {
  section_key: string;
  section_title: string;
  section_description?: string;
  section_visible?: boolean;
  section_order: number;
  field_order: number;
  field_required?: boolean;
};

export type ContributorFormField = {
  key: string;
  label: string;
  type: ContributorFormFieldType;
  required?: boolean;
  visible?: boolean;
  help_text?: string;
  placeholder?: string;
  options?: ContributorFormOption[];
  condition?: { field: string; equals?: string; not_equals?: string; one_of?: string[]; not_one_of?: string[] };
  condition_group?: ContributorConditionGroup;
  condition_required?: boolean;
  retired_from?: ContributorFormRetiredOrigin;
  allowed_extensions?: Array<"pdf" | "docx" | "xlsx" | "csv" | "png" | "jpg" | "jpeg">;
  min_files?: number;
  max_files?: number;
  max_file_bytes?: number;
  ai_sufficiency_instructions?: string;
  ai_scoring_enabled?: boolean; // Legacy read compatibility; ignored by current scoring.
};

export type ContributorFormSection = {
  key: string;
  title: string;
  description?: string;
  visible?: boolean;
  admin_only?: boolean;
  fields: ContributorFormField[];
};

export type ContributorFormSchema = {
  format_version: number;
  title: string;
  description?: string;
  reset_from_scratch?: boolean;
  validator_fact_fields?: ContributorFormField[];
  scoring_mappings?: Record<string, string>;
  sections: ContributorFormSection[];
};

export type ContributorFormPayload = {
  key: string;
  name: string;
  version: number;
  schema: ContributorFormSchema;
  published_at?: string;
};

const options = (values: string[]): ContributorFormOption[] =>
  values.map((value) => ({ value, label: value }));

export const PROJECT_STATUS_OPTIONS = ["New", "Not Implemented", "Ongoing", "Completed", "On Hold", "Cancelled"] as const;
export const NCR_LOCATION_OPTIONS = [
  "Caloocan",
  "Las Piñas",
  "Makati",
  "Malabon",
  "Mandaluyong",
  "Manila",
  "Marikina",
  "Muntinlupa",
  "Navotas",
  "Parañaque",
  "Pasay",
  "Pasig",
  "Pateros",
  "Quezon City",
  "San Juan",
  "Taguig",
  "Valenzuela",
] as const;
export const AGENCY_OPTIONS: ContributorFormOption[] = [
  ["MMDA", "Metropolitan Manila Development Authority"],
  ["DPWH", "Department of Public Works and Highways"], ["DENR", "Department of Environment and Natural Resources"],
  ["RDC-NCR", "Regional Development Council National Capital Region"], ["DILG", "Department of the Interior and Local Government"],
  ["DEPDev", "Department of Economy, Planning, and Development"], ["DBM", "Department of Budget and Management"],
  ["DA", "Department of Agriculture"], ["DAR", "Department of Agrarian Reform"], ["DepEd", "Department of Education"],
  ["DOH", "Department of Health"], ["DHSUD", "Department of Human Settlements and Urban Development"],
  ["DICT", "Department of Information and Communications Technology"], ["DOLE", "Department of Labor and Employment"],
  ["DOST", "Department of Science and Technology"], ["DSWD", "Department of Social Welfare and Development"],
  ["DOT", "Department of Tourism"], ["DTI", "Department of Trade and Industry"], ["DOTr", "Department of Transportation"],
  ["TESDA", "Technical Education and Skills Development Authority"], ["CHED", "Commission on Higher Education"],
  ["PSA", "Philippine Statistics Authority"],
].map(([value, label]) => ({ value, label }));

const field = (
  key: string,
  label: string,
  type: ContributorFormFieldType = "text",
  extra: Partial<ContributorFormField> = {},
): ContributorFormField => ({
  key,
  label,
  type,
  visible: true,
  help_text: "",
  placeholder: "",
  ...extra,
});

export const DEFAULT_CONTRIBUTOR_FORM_SCHEMA: ContributorFormSchema = {
  format_version: 3,
  title: "Simplified RDIP Contributor Form",
  description: "RDIP 2023-2028 list of projects format (data-type aligned)",
  sections: [
    {
      key: "project_information",
      title: "Project Information",
      fields: [
        field("agencyName", "Agency Name", "text", { required: true }),
        field("collaboratingAgencies", "Collaborating Agencies", "multiselect_dropdown", {
          help_text: "Optionally select other agencies participating in this project.",
          options: AGENCY_OPTIONS,
        }),
        field("program", "Program", "text", { required: true }),
        field("projectActivity", "Project/Activity", "text", { required: true }),
        field("location", "Location", "multiselect_dropdown", {
          required: true,
          help_text: "Select one or more NCR locations covered by the project.",
          options: options([...NCR_LOCATION_OPTIONS]),
        }),
        field("description", "Description", "textarea", { required: true }),
        field("objective", "Objective", "textarea", { required: true }),
      ],
    },
    {
      key: "implementation_and_funding",
      title: "Implementation Period and Funding",
      description: "Budget fields are generated from the selected implementation years.",
      fields: [
        field("startYear", "Start Year", "year", { required: true }),
        field("endYear", "End Year", "year", { required: true }),
        field("fundingRequirementByYear", "Funding Requirement (PHP)", "currency_by_year"),
        field("actualFundingByYear", "Actual/Approved Funding (PHP)", "currency_by_year"),
      ],
    },
    {
      key: "classification",
      title: "Funding and Classification",
      fields: [
        field("fundingSource", "Funding Source", "select", { required: true, options: options([
          "NG-Local Funds (GAA)", "ODA", "PPP", "Agency", "GOCC/GFIs", "LGUs", "NGOs",
          "Special/Trust Fund", "NDRRM", "N/A", "Others",
        ]) }),
        field("uacsCode", "UACS Code (if GAA-funded)", "text", {
          required: true,
          condition_group: { match: "all", conditions: [{ field: "fundingSource", operator: "equals", value: "NG-Local Funds (GAA)" }] },
        }),
        field("pipIncluded", "PIP Included", "select", { required: true, options: options(["Yes", "No"]) }),
        field("arnipapIncluded", "ARNIPAP Included", "select", { required: true, options: options(["Yes", "No"]) }),
        field("ludipIncluded", "LUDIP (for SUCs)", "select", { required: true, options: options(["Yes", "No", "Not Applicable"]) }),
        field("ifpsIncluded", "IFPs Included", "select", { required: true, options: options(["Yes", "No"]) }),
        field("pcbIncluded", "Part of the Convergence Program (PCB)", "select", { required: true, options: options(["Yes", "No"]) }),
        field("pcbProgram", "Convergence Program (PCB)", "select", {
          options: options([
            "National Program on Population and Family Planning (NPPFP)", "Zero Hunger Program (ZHP)",
            "Agricultural Development Program (ADP)", "Export Development Program (EDP)",
            "Tourism Development Program (TDP)", "Pasig River Urban Development (PRUD)",
            "Risk Resiliency Program (RRP)", "Justice Sector Convergence Program (JSCP)",
            "Philippine Anti-Illegal Drug Strategy (PADS)", "Water Resources Program (WRP)",
            "PCB on the Sustainable Development Goals (SDGs)", "PCB on Livelihood and Employment",
          ]),
          condition_group: { match: "all", conditions: [{ field: "pcbIncluded", operator: "equals", value: "Yes" }] },
          required: true,
        }),
        field("rdcEndorsed", "RDC-NCR Endorsed", "select", { required: true, options: options(["Yes", "No"]) }),
        field("developmentSector", "RDC-NCR Development Sector", "select", { required: true, options: options([
          "Sectoral Committee on Infrastructure Development (SCID)",
          "Sectoral Committee on Social Development (SCSD)",
          "Sectoral Committee on Economic and Environment Development (SCEED)",
          "Sectoral Committee on Finance and Development Administration (SCFDA)",
        ]) }),
        field("rdpMainChapter", "RDP-NCR Main Chapter", "select", { required: true, options: options([
          "4.1 Boost Health Health & Nutrition", "4.2 Improve Education and Lifelong Learning Education",
          "4.3.1 Establish Livable Communities (Built Environment) Housing",
          "4.3.2 Establish Livable Communities (Natural Environment) Environment",
          "5 Increase Income-Earning Ability Skills & Employment", "5.1 Expand Training and Skills Development Skills",
          "5.2 Intensify Employment Facilitation Employment", "6.1 Ensure Food Security and Nutrition Food Security",
          "6.2 Strengthen Social Protection Social Protection", "7 Modernize Agriculture and Agri-business Agri",
          "8 Revitalize Industry Industry", "9 Reinvigorate Services Services",
          "10 Advance R&D, Technology, and Innovation R&D", "11 Promote Trade and Investments Trade",
          "12 Promote Financial Inclusion and Improve Public Financial Management Finance",
          "13 Expand and Upgrade Infrastructure Infrastructure", "14.1 Ensure Peace and Security Security",
          "14.2 Enhance Administration of Justice Justice",
          "15 Practice Good Governance and Improve Bureaucratic Efficiency Governance",
          "16 Accelerate Climate Action and Strengthen Disaster Resilience Climate",
        ]) }),
        field("status", "Status", "select", { required: true, options: options([
          ...PROJECT_STATUS_OPTIONS,
        ]) }),
        field("sdgSelections", "Sustainable Development Goals", "multiselect", { options: options([
          "1 - No poverty", "2 - Zero hunger", "3 - Good health and well-being", "4 - Quality education",
          "5 - Gender equality", "6- Clean water and sanitation", "7 - Affordable and clean energy",
          "8 - Decent work and economic growth", "9 - Industry, innovation and infrastructure",
          "10 - Reduced inequalities", "11 - Sustainable cities and communities",
          "12 - Responsible consumption and production", "13 - Climate action", "14 - Life below water",
          "15 - Life on land", "16 - Peace, justice and strong institutions", "17 - Partnerships for the goals",
        ]) }),
      ],
    },
    {
      key: "accomplishment",
      title: "Accomplishment and Remarks",
      fields: [
        field("physicalAccomplishment", "Physical Accomplishment", "textarea", {
          condition_group: { match: "all", conditions: [{ field: "status", operator: "one_of", values: ["Ongoing", "Completed"] }] }, required: true,
        }),
        field("financialAccomplishment", "Financial Accomplishment", "textarea", {
          condition_group: { match: "all", conditions: [{ field: "status", operator: "one_of", values: ["Ongoing", "Completed"] }] }, required: true,
        }),
        field("remarks", "Remarks", "textarea", {
          condition_group: { match: "all", conditions: [{ field: "status", operator: "one_of", values: ["On Hold", "Cancelled"] }] },
          required: true,
          help_text: "Explain the reason for the hold or cancellation.",
        }),
      ],
    },
    {
      key: "supporting_documents",
      title: "Supporting Documents",
      description: "Upload evidence that supports the project information and readiness described above.",
      fields: [
        field("custom_supporting_documents", "Supporting Documents", "document_upload", {
          required: true,
          help_text: "Required formats: PDF, DOCX, XLSX, CSV, PNG, or JPEG. Files are checked for project relevance and sufficiency.",
          allowed_extensions: ["pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"],
          min_files: 1,
          max_files: 10,
          max_file_bytes: CONTRIBUTOR_DOCUMENT_MAX_BYTES,
          ai_sufficiency_instructions: "The documents should substantiate the stated project scope, objectives, budget, readiness, intended beneficiaries, or expected outcomes.",
        }),
      ],
    },
  ],
  validator_fact_fields: [
        field("priorityAnalysisFacts.readinessLevel", "Readiness Level", "select", { options: options([
          "With completed documents such as pre-FS/FS/POW and detailed design, where applicable",
          "Ongoing pre-FS/FS/POW and detailed design, where applicable",
          "With Comprehensive Project Profile", "With concept paper/none",
        ]) }),
        field("priorityAnalysisFacts.gadResponsiveness", "GAD Responsiveness", "select", { options: options([
          "Gender-responsive", "Gender-sensitive", "Promising GAD prospects", "GAD invisible",
        ]) }),
        field("priorityAnalysisFacts.spatialCoverageScope", "Spatial Coverage Scope", "select", { options: options([
          "Specific LGUs", "Region-wide", "Interregional", "None",
        ]) }),
        field("priorityAnalysisFacts.beneficiaryCount", "Estimated Beneficiary Count", "number"),
        field("priorityAnalysisFacts.readinessNotes", "Readiness Evidence Notes", "textarea"),
  ],
};

export const cloneContributorFormSchema = (schema: ContributorFormSchema): ContributorFormSchema =>
  JSON.parse(JSON.stringify(schema)) as ContributorFormSchema;

export const contributorFieldOptions = (field: ContributorFormField) =>
  (field.options || []).map((option) => option.value);

export const normalizeReadinessLevelValue = (value: string) => ({
  "Completed supporting documents": "With completed documents such as pre-FS/FS/POW and detailed design, where applicable",
  "Ongoing supporting documents": "Ongoing pre-FS/FS/POW and detailed design, where applicable",
  "Comprehensive project profile": "With Comprehensive Project Profile",
  "Concept paper / none": "With concept paper/none",
}[value] || value);

export const contributorFieldApplies = (
  field: ContributorFormField,
  values: Record<string, unknown>,
  schema?: ContributorFormSchema,
) => {
  if (schema) {
    const fields = new Map(schema.sections.flatMap((section) => section.fields.map((item) => [item.key, {
      field: item, sectionVisible: section.visible !== false,
    }] as const)));
    const visiting = new Set<string>();
    const resolved = new Map<string, boolean>();
    const visible = (key: string): boolean => {
      if (resolved.has(key)) return resolved.get(key)!;
      const source = fields.get(key);
      if (!source || !source.sectionVisible || source.field.visible === false || visiting.has(key)) return false;
      visiting.add(key);
      const group = source.field.condition_group;
      const legacy = source.field.condition;
      const conditions = group?.conditions || (legacy ? [{ field: legacy.field }] : []);
      const matches = conditions.map((rule) => visible(rule.field) && contributorFieldApplies(source.field, values));
      const result = !conditions.length || (group?.match === "any" ? matches.some(Boolean) : matches.every(Boolean));
      visiting.delete(key);
      resolved.set(key, result);
      return result;
    };
    return visible(field.key);
  }
  const answerFor = (key: string) => {
    if (key.startsWith("priorityAnalysisFacts.")) {
      const facts = values.priorityAnalysisFacts;
      return facts && typeof facts === "object" ? (facts as Record<string, unknown>)[key.split(".", 2)[1]] : undefined;
    }
    if (key.startsWith("custom_")) {
      const custom = values.custom_fields;
      return custom && typeof custom === "object" ? (custom as Record<string, unknown>)[key] : values[key];
    }
    return values[key];
  };
  const group = field.condition_group;
  if (group?.conditions?.length) {
    const results = group.conditions.map((condition) => {
      const current = answerFor(condition.field);
      const currentText = String(current ?? "").trim();
      const expected = String(condition.value ?? "").trim();
      switch (condition.operator) {
        case "equals": return Array.isArray(current)
          ? current.some((value) => value.toLocaleLowerCase() === expected.toLocaleLowerCase())
          : currentText.toLocaleLowerCase() === expected.toLocaleLowerCase();
        case "not_equals": return currentText.toLocaleLowerCase() !== expected.toLocaleLowerCase();
        case "one_of": return Array.isArray(current)
          ? current.some((value) => (condition.values || []).includes(value))
          : (condition.values || []).includes(currentText);
        case "not_one_of": return !(condition.values || []).includes(currentText);
        case "contains": return Array.isArray(current) && current.includes(condition.value);
        case "not_contains": return !Array.isArray(current) || !current.includes(condition.value);
        case "contains_any": return Array.isArray(current) && (condition.values || []).some((value) => current.includes(value));
        case "is_empty": return current == null || current === "" || Array.isArray(current) && current.length === 0;
        case "is_not_empty": return !(current == null || current === "" || Array.isArray(current) && current.length === 0);
        case "greater_than": return currentText !== "" && Number.isFinite(Number(currentText)) && Number(currentText) > Number(condition.value);
        case "less_than": return currentText !== "" && Number.isFinite(Number(currentText)) && Number(currentText) < Number(condition.value);
        case "at_least": return currentText !== "" && Number.isFinite(Number(currentText)) && Number(currentText) >= Number(condition.value);
        case "at_most": return currentText !== "" && Number.isFinite(Number(currentText)) && Number(currentText) <= Number(condition.value);
        case "before": return Boolean(currentText && expected && currentText < expected);
        case "after": return Boolean(currentText && expected && currentText > expected);
        default: return false;
      }
    });
    return group.match === "any" ? results.some(Boolean) : results.every(Boolean);
  }
  if (!field.condition) return true;
  const value = answerFor(field.condition.field);
  if (field.condition.equals !== undefined) return value === field.condition.equals;
  if (field.condition.not_equals !== undefined) return value !== field.condition.not_equals;
  if (field.condition.one_of !== undefined) return field.condition.one_of.includes(String(value ?? ""));
  if (field.condition.not_one_of !== undefined) return !field.condition.not_one_of.includes(String(value ?? ""));
  return true;
};
