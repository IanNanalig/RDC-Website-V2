export type ContributorFormFieldType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "year"
  | "select"
  | "multiselect"
  | "currency_by_year";

export type ContributorFormOption = { value: string; label: string };

export type ContributorFormField = {
  key: string;
  label: string;
  type: ContributorFormFieldType;
  required?: boolean;
  visible?: boolean;
  protected?: boolean;
  help_text?: string;
  placeholder?: string;
  options?: ContributorFormOption[];
  condition?: { field: string; equals?: string; not_equals?: string };
  condition_required?: boolean;
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
  protected: !key.startsWith("custom_"),
  help_text: "",
  placeholder: "",
  ...extra,
});

export const DEFAULT_CONTRIBUTOR_FORM_SCHEMA: ContributorFormSchema = {
  format_version: 1,
  title: "Simplified RDIP Contributor Form",
  description: "RDIP 2023-2028 list of projects format (data-type aligned)",
  sections: [
    {
      key: "project_information",
      title: "Project Information",
      fields: [
        field("agencyName", "Agency Name", "text", { required: true }),
        field("program", "Program", "text", { required: true }),
        field("projectActivity", "Project/Activity", "text", { required: true }),
        field("location", "Location", "text", { required: true }),
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
        field("uacsCode", "UACS Code (if GAA-funded)"),
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
          condition: { field: "pcbIncluded", equals: "Yes" },
          condition_required: true,
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
          "Completed", "New", "Updated", "Ongoing", "Discontinued", "Not Implemented", "N/A", "Dropped",
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
          condition: { field: "status", not_equals: "New" }, condition_required: true,
        }),
        field("financialAccomplishment", "Financial Accomplishment", "textarea", {
          condition: { field: "status", not_equals: "New" }, condition_required: true,
        }),
        field("remarks", "Remarks", "textarea"),
      ],
    },
    {
      key: "priority_analysis",
      title: "Priority Analysis Facts",
      description: "Optional factual inputs for the AI-assisted priority recommendation.",
      admin_only: true,
      fields: [
        field("priorityAnalysisFacts.readinessLevel", "Readiness Level", "select", { options: options([
          "Completed supporting documents", "Ongoing supporting documents", "Comprehensive project profile", "Concept paper / none",
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
    },
  ],
};

export const cloneContributorFormSchema = (schema: ContributorFormSchema): ContributorFormSchema =>
  JSON.parse(JSON.stringify(schema)) as ContributorFormSchema;

export const contributorFieldOptions = (field: ContributorFormField) =>
  (field.options || []).map((option) => option.value);

export const contributorFieldApplies = (
  field: ContributorFormField,
  values: Record<string, unknown>,
) => {
  if (!field.condition) return true;
  const value = values[field.condition.field];
  if (field.condition.equals !== undefined) return value === field.condition.equals;
  if (field.condition.not_equals !== undefined) return value !== field.condition.not_equals;
  return true;
};
