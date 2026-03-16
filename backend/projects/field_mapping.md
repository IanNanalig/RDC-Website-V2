# Field Mapping — Project Profile Form

This document maps the PDF form fields to structured field names, types, and requirements for the web form / API / DB model.

Notation
- name: machine_name
- label: human-friendly label
- type: text | textarea | select | radio | checkbox | boolean | number | decimal | date | year | file | array | json
- required: yes/no
- notes: UI/DB considerations

---

SECTION: Basic Project Info
- name: title
  label: Project Title
  type: text
  required: yes

- name: office_unit
  label: MMDA Office / Unit-in-Charge
  type: text
  required: yes

- name: project_type
  label: Is it a Program or a Project?
  type: select
  options: [program, project]
  required: yes

-- when `program` selected:
- name: is_regular
  label: Is it a regular program?
  type: boolean
  required: no

-- when `project` selected:
- name: is_subproject
  label: Is this a part/subcomponent/subproject of a Program?
  type: boolean
  required: no

- name: parent_program_title
  label: Parent Program Title
  type: text
  required: conditional (when is_subproject)

- name: parent_program_pip_code
  label: Parent Program PIP Code
  type: text
  required: conditional

- name: sub_program
  label: Sub Program
  type: text
  required: conditional

- name: is_convergence_program
  label: Is this a part of a convergence program (PCB)?
  type: boolean
  required: no

SECTION: Basis for Implementation (multiple checkboxes)
- name: basis_for_implementation
  label: Basis for Implementation
  type: json (array of strings)
  required: no
  notes: store selected items; include free-text 'others' field

SECTION: Objective & Description
- name: objective
  label: Project Objective
  type: textarea
  required: yes

- name: description
  label: Project Description
  type: textarea
  required: no
  notes: if infrastructure, include component list/specs

SECTION: Implementing Agency
- name: implementing_agency
  label: Implementing Agency (parent/attached/co-implementing)
  type: json (object)
  required: no
  notes: { parent: '', attached: '', co_implementing: [] }

SECTION: Implementation Period
- name: start_year
  label: Start of Project Implementation
  type: year
  required: no

- name: completion_year
  label: Year of Project Completion
  type: year
  required: no

SECTION: Spatial Coverage (By Cost / By Impact)
- name: spatial_coverage
  label: Spatial Coverage
  type: json (object)
  required: no
  notes: structure: { coverage_type: 'inter-regional|region|province|locality', regions: [], provinces: [], localities: [], river_basins: {is_river_basin: bool, type: 'major|principal', name: ''} }

SECTION: Inclusion in Programming Documents
- name: inclusion_program_docs
  label: Inclusion in Programming Document(s)
  type: json (object/array)
  required: no
  notes: store selected PIP/CIP/Trip flags and values

SECTION: Physical and Financial Status
- name: phys_fin_category
  label: Category
  type: select
  options: [CIP, Non-CIP]
  required: no

- name: implementation_readiness
  label: Status of Implementation Readiness
  type: select
  options: [1,2,3]  # map to CIP/Non-CIP descriptors
  required: no

- name: implementation_risk
  label: Implementation Risk
  type: textarea
  required: no

- name: mitigation_strategies
  label: Mitigation Strategies
  type: textarea
  required: no

- name: pap_code
  label: PAP Code
  type: text
  required: no

- name: updates
  label: Updates (timeline or short notes)
  type: textarea
  required: no

SECTION: Funding Sources & Mode of Implementation
- name: funding_sources
  label: Funding Sources (checkbox list)
  type: json (array)
  required: no
  notes: selected types: NG, ODA Loan, ODA Grant, GOCC/GFIs, LGU, Private, Others

- name: main_funding_sources
  label: Main Funding Source details
  type: array of objects
  required: no
  object fields: { source_type, selected_flag, details }

- name: procurement_modes
  label: Mode of Implementation / Procurement
  type: json (array)
  required: no
  notes: list of checkboxes with free-text for 'others'

SECTION: Project Cost (table)
- name: project_costs
  label: Project Cost by funding source and year
  type: array of objects
  required: no
  object fields: { funding_source, amounts: {"2022_and_prior":0, "2023":0, "2024":0, ...}, overall_total }
  notes: store year amounts as JSON for flexibility; normalize later if needed

SECTION: PIP-Budget Tracker
- name: pip_budget_tracker
  label: PIP-Budget Tracker
  type: json (object)
  required: no
  notes: store rows for Year / Amount submitted / Amount included in NEP / Amount allocated in GAA

SECTION: Provincial / District Breakdown
- name: provincial_breakdown
  label: Provincial/District Breakdown
  type: array of objects
  required: no
  object fields: { province, district_name, year_amounts, overall_total }

SECTION: Level of Approval
- name: level_of_approval
  label: Level of Approval
  type: select
  options: [will_require_icc_ed_council_approval, not_applicable, other]
  required: no

SECTION: PDP Chapters & Outcome Indicators
- name: pdp_main_chapter
  label: Main PDP Chapter
  type: text or select
  required: no

- name: pdp_other_chapters
  label: Other PDP Chapter(s)
  type: json (array)
  required: no

- name: outcome_indicator_statements
  label: Outcome / Indicator Statements
  type: json (object)
  required: no
  notes: structure: { outcome: '', subchapter_outcome: '', indicators: [] }

SECTION: Main Infrastructure Sector / Subsector
- name: main_infra_sector
  label: Main Infrastructure Sector / Subsector
  type: text
  required: no

SECTION: Project Readiness (flags)
- name: project_readiness_flags
  label: Project Readiness
  type: json (array/obj)
  required: no
  notes: include booleans for: pre-feasibility, feasibility_study, right_of_way, resettlement_plan, rdcd_endorsement, detailed_design, env_compliance, other_preinvestment

SECTION: Expected Outputs / Deliverables
- name: expected_outputs
  label: Expected Outputs/Deliverables
  type: array of objects
  required: no
  object fields: { title, indicator, value, unit }

SECTION: Socioeconomic Agenda & SDGs
- name: socioeconomic_agenda
  label: 8-Point Socioeconomic Agenda (checkboxes)
  type: json (array)

- name: sdg_goals
  label: Sustainable Development Goals (checkboxes)
  type: json (array)

SECTION: GAD Responsiveness
- name: gad_responsiveness_level
  label: Level of Gender and Development (GAD) Responsiveness
  type: select
  options: [Level 0, Level 1, Level 2, Level 3]  # map as needed

SECTION: Employment Generation
- name: employment_generation
  label: Employment Generation
  type: json { total: int, male: int, female: int }

SECTION: Remarks
- name: remarks
  label: Remarks / Other pertinent information
  type: textarea

SECTION: Contact Information
- name: focal_person
  label: Focal Person (signature over full name)
  type: json { name, designation, department_office_unit }

- name: alternative_representative
  label: Alternative Representative
  type: json { name, designation, department }

- name: contact_details
  label: Contact Details
  type: json { agency_office_address, telephone_no, email }

SECTION: Attachments
- name: attachments
  label: Attachments (supporting docs)
  type: files (one-to-many)
  required: no
  notes: allow multiple files; store metadata in Attachment model

---

Storage guidance
- Use structured relational tables for records you will query often: `Project`, `FundingRow`, `RegionalBreakdown`, `OutputDeliverable`, `ValidationLog`, `Attachment`.
- Use JSON fields for highly variable or nested groups: `basis_for_implementation`, `spatial_coverage`, `inclusion_program_docs`, `expected_outputs` (if simple array), `pip_budget_tracker`.

API mapping notes
- On create/update requests, accept full JSON payload matching the field names above. Recommended endpoints:
  - POST /api/projects/ (create draft or submit flag)
  - PATCH /api/projects/{id}/ (update)
  - POST /api/projects/{id}/submit (changes status)
  - POST /api/projects/{id}/assign (assign validator)
  - POST /api/projects/{id}/validate (validator action)

Validation rules (MVP)
- Required: `title`, `office_unit`, `project_type`, `objective`, `contact_info.name` or `contact_details.email`.
- If `is_subproject` true → `parent_program_title` recommended.

Next: use this mapping to create DRF serializers and viewsets that accept/return the same shape. Frontend should implement a multi-step form using these keys.

---
End of mapping.
