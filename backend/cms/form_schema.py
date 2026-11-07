from copy import deepcopy
from datetime import date
import re


SIMPLIFIED_FORM_KEY = "simplified-rdip"
FORM_SCHEMA_FORMAT_VERSION = 3
ALLOWED_FIELD_TYPES = {
    "text",
    "textarea",
    "number",
    "date",
    "year",
    "select",
    "multiselect",
    "multiselect_dropdown",
    "currency_by_year",
    "document_upload",
}

DOCUMENT_UPLOAD_EXTENSIONS = {"pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"}
DOCUMENT_UPLOAD_MAX_FILES = 10
DOCUMENT_UPLOAD_MAX_BYTES = 50 * 1024 * 1024


def _options(values):
    return [{"value": value, "label": value} for value in values]


YES_NO_OPTIONS = _options(["Yes", "No"])
YES_NO_NA_OPTIONS = _options(["Yes", "No", "Not Applicable"])
FUNDING_SOURCE_OPTIONS = _options([
    "NG-Local Funds (GAA)", "ODA", "PPP", "Agency", "GOCC/GFIs", "LGUs", "NGOs",
    "Special/Trust Fund", "NDRRM", "N/A", "Others",
])
DEVELOPMENT_SECTOR_OPTIONS = _options([
    "Sectoral Committee on Infrastructure Development (SCID)",
    "Sectoral Committee on Social Development (SCSD)",
    "Sectoral Committee on Economic and Environment Development (SCEED)",
    "Sectoral Committee on Finance and Development Administration (SCFDA)",
])
PCB_PROGRAM_OPTIONS = _options([
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
])
RDP_CHAPTER_OPTIONS = _options([
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
])
STATUS_OPTIONS = _options([
    "New", "Not Implemented", "Ongoing", "Completed", "On Hold", "Cancelled",
])
CURRENT_PROJECT_STATUS_VALUES = frozenset(option["value"] for option in STATUS_OPTIONS)
NCR_LOCATION_OPTIONS = _options([
    "Caloocan", "Las Piñas", "Makati", "Malabon", "Mandaluyong", "Manila", "Marikina",
    "Muntinlupa", "Navotas", "Parañaque", "Pasay", "Pasig", "Pateros", "Quezon City",
    "San Juan", "Taguig", "Valenzuela",
])
SDG_OPTIONS = _options([
    "1 - No poverty", "2 - Zero hunger", "3 - Good health and well-being", "4 - Quality education",
    "5 - Gender equality", "6- Clean water and sanitation", "7 - Affordable and clean energy",
    "8 - Decent work and economic growth", "9 - Industry, innovation and infrastructure",
    "10 - Reduced inequalities", "11 - Sustainable cities and communities",
    "12 - Responsible consumption and production", "13 - Climate action", "14 - Life below water",
    "15 - Life on land", "16 - Peace, justice and strong institutions", "17 - Partnerships for the goals",
])
AGENCY_OPTIONS = sorted([
    {"value": code, "label": name}
    for code, name in [
        ("MMDA", "Metropolitan Manila Development Authority"),
        ("DPWH", "Department of Public Works and Highways"),
        ("DENR", "Department of Environment and Natural Resources"),
        ("RDC-NCR", "Regional Development Council National Capital Region"),
        ("DILG", "Department of the Interior and Local Government"),
        ("DEPDev", "Department of Economy, Planning, and Development"),
        ("DBM", "Department of Budget and Management"),
        ("DA", "Department of Agriculture"),
        ("DAR", "Department of Agrarian Reform"),
        ("DepEd", "Department of Education"),
        ("DOH", "Department of Health"),
        ("DHSUD", "Department of Human Settlements and Urban Development"),
        ("DICT", "Department of Information and Communications Technology"),
        ("DOLE", "Department of Labor and Employment"),
        ("DOST", "Department of Science and Technology"),
        ("DSWD", "Department of Social Welfare and Development"),
        ("DOT", "Department of Tourism"),
        ("DTI", "Department of Trade and Industry"),
        ("DOTr", "Department of Transportation"),
        ("TESDA", "Technical Education and Skills Development Authority"),
        ("CHED", "Commission on Higher Education"),
        ("PSA", "Philippine Statistics Authority"),
    ]
], key=lambda option: option["value"].casefold())


def _field(key, label, field_type="text", required=False, options=None, **extra):
    value = {
        "key": key,
        "label": label,
        "type": field_type,
        "required": required,
        "visible": True,
        "help_text": "",
        "placeholder": "",
    }
    if options is not None:
        value["options"] = deepcopy(options)
    value.update(extra)
    return value


DEFAULT_SIMPLIFIED_FORM_SCHEMA = {
    "format_version": FORM_SCHEMA_FORMAT_VERSION,
    "title": "Simplified RDIP Contributor Form",
    "description": "RDIP 2023-2028 list of projects format (data-type aligned)",
    "sections": [
        {
            "key": "project_information",
            "title": "Project Information",
            "description": "",
            "visible": True,
            "fields": [
                _field("agencyName", "Agency Name", required=True),
                _field(
                    "collaboratingAgencies",
                    "Collaborating Agencies",
                    "multiselect_dropdown",
                    options=AGENCY_OPTIONS,
                    help_text="Optionally select other agencies participating in this project.",
                ),
                _field("program", "Program", required=True),
                _field("projectActivity", "Project/Activity", required=True),
                _field(
                    "location", "Location", "multiselect_dropdown", required=True,
                    options=NCR_LOCATION_OPTIONS,
                    help_text="Select one or more NCR locations covered by the project.",
                ),
                _field("description", "Description", "textarea", required=True),
                _field("objective", "Objective", "textarea", required=True),
            ],
        },
        {
            "key": "implementation_and_funding",
            "title": "Implementation Period and Funding",
            "description": "Budget fields are generated from the selected implementation years.",
            "visible": True,
            "fields": [
                _field("startYear", "Start Year", "year", required=True),
                _field("endYear", "End Year", "year", required=True),
                _field("fundingRequirementByYear", "Funding Requirement (PHP)", "currency_by_year"),
                _field("actualFundingByYear", "Actual/Approved Funding (PHP)", "currency_by_year"),
            ],
        },
        {
            "key": "classification",
            "title": "Funding and Classification",
            "description": "",
            "visible": True,
            "fields": [
                _field("fundingSource", "Funding Source", "select", required=True, options=FUNDING_SOURCE_OPTIONS),
                _field(
                    "uacsCode", "UACS Code (if GAA-funded)", required=True,
                    condition_group={"match": "all", "conditions": [{
                        "field": "fundingSource", "operator": "equals", "value": "NG-Local Funds (GAA)",
                    }]},
                ),
                _field("pipIncluded", "PIP Included", "select", required=True, options=YES_NO_OPTIONS),
                _field("arnipapIncluded", "ARNIPAP Included", "select", required=True, options=YES_NO_OPTIONS),
                _field("ludipIncluded", "LUDIP (for SUCs)", "select", required=True, options=YES_NO_NA_OPTIONS),
                _field("ifpsIncluded", "IFPs Included", "select", required=True, options=YES_NO_OPTIONS),
                _field("pcbIncluded", "Part of the Convergence Program (PCB)", "select", required=True, options=YES_NO_OPTIONS),
                _field(
                    "pcbProgram", "Convergence Program (PCB)", "select", options=PCB_PROGRAM_OPTIONS,
                    condition_group={"match": "all", "conditions": [{"field": "pcbIncluded", "operator": "equals", "value": "Yes"}]}, required=True,
                ),
                _field("rdcEndorsed", "RDC-NCR Endorsed", "select", required=True, options=YES_NO_OPTIONS),
                _field("developmentSector", "RDC-NCR Development Sector", "select", required=True, options=DEVELOPMENT_SECTOR_OPTIONS),
                _field("rdpMainChapter", "RDP-NCR Main Chapter", "select", required=True, options=RDP_CHAPTER_OPTIONS),
                _field("status", "Status", "select", required=True, options=STATUS_OPTIONS),
                _field("sdgSelections", "Sustainable Development Goals", "multiselect", options=SDG_OPTIONS),
            ],
        },
        {
            "key": "accomplishment",
            "title": "Accomplishment and Remarks",
            "description": "",
            "visible": True,
            "fields": [
                _field(
                    "physicalAccomplishment", "Physical Accomplishment", "textarea",
                    condition_group={"match": "all", "conditions": [{"field": "status", "operator": "one_of", "values": ["Ongoing", "Completed"]}]}, required=True,
                ),
                _field(
                    "financialAccomplishment", "Financial Accomplishment", "textarea",
                    condition_group={"match": "all", "conditions": [{"field": "status", "operator": "one_of", "values": ["Ongoing", "Completed"]}]}, required=True,
                ),
                _field(
                    "remarks", "Remarks", "textarea",
                    condition_group={"match": "all", "conditions": [{"field": "status", "operator": "one_of", "values": ["On Hold", "Cancelled"]}]},
                    required=True,
                    help_text="Explain the reason for the hold or cancellation.",
                ),
            ],
        },
        {
            "key": "supporting_documents",
            "title": "Supporting Documents",
            "description": "Upload evidence that supports the project information and readiness described above.",
            "visible": True,
            "fields": [
                _field(
                    "custom_supporting_documents",
                    "Supporting Documents",
                    "document_upload",
                    required=True,
                    help_text=(
                        "Required formats: PDF, DOCX, XLSX, CSV, PNG, or JPEG. "
                        "Files are checked for project relevance and sufficiency."
                    ),
                    allowed_extensions=["pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"],
                    min_files=1,
                    max_files=10,
                    max_file_bytes=DOCUMENT_UPLOAD_MAX_BYTES,
                    ai_sufficiency_instructions=(
                        "The documents should substantiate the stated project scope, objectives, budget, "
                        "readiness, intended beneficiaries, or expected outcomes."
                    ),
                ),
            ],
        },
    ],
    "validator_fact_fields": [
                _field("priorityAnalysisFacts.readinessLevel", "Readiness Level", "select", options=_options([
                    "With completed documents such as pre-FS/FS/POW and detailed design, where applicable",
                    "Ongoing pre-FS/FS/POW and detailed design, where applicable",
                    "With Comprehensive Project Profile", "With concept paper/none",
                ])),
                _field("priorityAnalysisFacts.gadResponsiveness", "GAD Responsiveness", "select", options=_options([
                    "Gender-responsive", "Gender-sensitive", "Promising GAD prospects", "GAD invisible",
                ])),
                _field("priorityAnalysisFacts.spatialCoverageScope", "Spatial Coverage Scope", "select", options=_options([
                    "Specific LGUs", "Region-wide", "Interregional", "None",
                ])),
                _field("priorityAnalysisFacts.beneficiaryCount", "Estimated Beneficiary Count", "number"),
                _field("priorityAnalysisFacts.readinessNotes", "Readiness Evidence Notes", "textarea"),
    ],
}


CORE_FIELDS = {
    field["key"]: deepcopy(field)
    for section in DEFAULT_SIMPLIFIED_FORM_SCHEMA["sections"]
    for field in section["fields"]
    if not str(field.get("key") or "").startswith("custom_")
}
REQUIRED_CORE_FIELDS = {key for key, field in CORE_FIELDS.items() if field.get("required")}
CONDITION_REQUIRED_CORE_FIELDS = set()
FIXED_FIELD_TYPES = {
    "agencyName": "text",
    "projectActivity": "text",
    "startYear": "year",
    "endYear": "year",
    "fundingRequirementByYear": "currency_by_year",
    "actualFundingByYear": "currency_by_year",
    "custom_supporting_documents": "document_upload",
}
PROTECTED_OPTION_FIELDS = {"collaboratingAgencies"}
PROTECTED_SECTION_KEYS = {
    "project_information", "implementation_and_funding", "supporting_documents",
}
PROTECTED_WORKFLOW_FIELD_KEYS = {
    "agencyName", "projectActivity", "startYear", "endYear",
    "fundingRequirementByYear", "actualFundingByYear", "custom_supporting_documents",
}
PROTECTED_FIELD_SECTIONS = {
    "agencyName": "project_information", "projectActivity": "project_information",
    "startYear": "implementation_and_funding", "endYear": "implementation_and_funding",
    "fundingRequirementByYear": "implementation_and_funding",
    "actualFundingByYear": "implementation_and_funding",
    "custom_supporting_documents": "supporting_documents",
}


class FormSchemaError(ValueError):
    pass


def describe_form_error(error, schema):
    """Show configured labels to editors while retaining stable keys in logs."""
    message = str(error)
    if not isinstance(schema, dict):
        return message
    labels = {
        str(field.get("key")): str(field.get("label") or field.get("key"))
        for section in schema.get("sections", []) if isinstance(section, dict)
        for field in section.get("fields", []) if isinstance(field, dict) and field.get("key")
    }
    labels.update({
        str(section.get("key")): str(section.get("title") or section.get("key"))
        for section in schema.get("sections", []) if isinstance(section, dict) and section.get("key")
    })
    for key in sorted(labels, key=len, reverse=True):
        if labels[key] != key:
            message = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])", labels[key], message)
    return message


def default_simplified_form_schema():
    return deepcopy(DEFAULT_SIMPLIFIED_FORM_SCHEMA)


def normalize_system_managed_sections(schema, reference_schema=None):
    """Convert a legacy editor draft without changing its published source."""
    result = deepcopy(schema) if isinstance(schema, dict) else {}
    sections = result.get("sections", []) if isinstance(result.get("sections"), list) else []
    result["sections"] = [
        section for section in sections
        if not (isinstance(section, dict) and section.get("admin_only") is True)
    ]
    legacy_facts = next((
        section.get("fields") for section in sections
        if isinstance(section, dict) and section.get("admin_only") is True
        and section.get("key") == "priority_analysis"
    ), None)
    result["validator_fact_fields"] = deepcopy(
        result.get("validator_fact_fields") or legacy_facts
        or DEFAULT_SIMPLIFIED_FORM_SCHEMA["validator_fact_fields"]
    )
    result["format_version"] = FORM_SCHEMA_FORMAT_VERSION
    return result


def validate_system_managed_sections(schema, reference_schema):
    reference = reference_schema if isinstance(reference_schema, dict) else {}
    expected = reference.get("validator_fact_fields") or next((
        section.get("fields") for section in reference.get("sections", [])
        if isinstance(section, dict) and section.get("admin_only") is True
        and section.get("key") == "priority_analysis"
    ), None) or DEFAULT_SIMPLIFIED_FORM_SCHEMA["validator_fact_fields"]
    if schema.get("validator_fact_fields", expected) != expected:
        raise FormSchemaError("Validator Facts configuration cannot be changed in the Contributor Form builder.")
    if any(section.get("admin_only") for section in schema.get("sections", []) if isinstance(section, dict)):
        raise FormSchemaError("Internal Validator Facts must stay outside Contributor Form sections.")


def _field_map(schema):
    return {
        str(field.get("key")): field
        for section in schema.get("sections", [])
        if isinstance(section, dict)
        for field in section.get("fields", [])
        if isinstance(field, dict) and field.get("key")
    }


def legacy_condition_group(condition):
    if not isinstance(condition, dict) or not condition.get("field"):
        return None
    for operator in ("equals", "not_equals", "one_of", "not_one_of"):
        if operator in condition:
            rule = {"field": str(condition["field"]), "operator": operator}
            if operator in {"one_of", "not_one_of"}:
                rule["values"] = list(condition.get(operator) or [])
            else:
                rule["value"] = condition.get(operator)
            return {"match": "all", "conditions": [rule]}
    return None


def field_condition_group(field):
    if not isinstance(field, dict):
        return None
    group = field.get("condition_group")
    if isinstance(group, dict):
        return group
    return legacy_condition_group(field.get("condition"))


def _condition_value(values, key):
    if key.startswith("priorityAnalysisFacts."):
        facts = values.get("priorityAnalysisFacts") if isinstance(values.get("priorityAnalysisFacts"), dict) else {}
        return facts.get(key.split(".", 1)[1])
    if key.startswith("custom_"):
        custom = values.get("custom_fields") if isinstance(values.get("custom_fields"), dict) else {}
        return custom.get(key)
    return values.get(key)


def _compare_condition(current, rule):
    operator = str(rule.get("operator") or "")
    expected = rule.get("value")
    expected_values = rule.get("values") if isinstance(rule.get("values"), list) else []
    if operator == "equals":
        return str(current or "").strip().casefold() == str(expected or "").strip().casefold()
    if operator == "not_equals":
        return str(current or "").strip().casefold() != str(expected or "").strip().casefold()
    if operator == "one_of":
        return str(current or "") in {str(value) for value in expected_values}
    if operator == "not_one_of":
        return str(current or "") not in {str(value) for value in expected_values}
    if operator in {"contains", "not_contains", "contains_any"}:
        members = current if isinstance(current, list) else []
        if operator == "contains_any":
            return any(value in members for value in expected_values)
        result = expected in members
        return result if operator == "contains" else not result
    if operator == "is_empty":
        return current in (None, "", [], {})
    if operator == "is_not_empty":
        return current not in (None, "", [], {})
    if operator in {"greater_than", "less_than", "at_least", "at_most"}:
        try:
            left, right = float(str(current).replace(",", "")), float(str(expected).replace(",", ""))
        except (TypeError, ValueError):
            return False
        return {
            "greater_than": left > right, "less_than": left < right,
            "at_least": left >= right, "at_most": left <= right,
        }[operator]
    if operator in {"before", "after"}:
        left, right = str(current or ""), str(expected or "")
        return bool(left and right and (left < right if operator == "before" else left > right))
    return False


def condition_group_applies(group, values):
    if not isinstance(group, dict) or not group.get("conditions"):
        return True
    results = [
        _compare_condition(_condition_value(values, str(rule.get("field") or "")), rule)
        for rule in group.get("conditions", []) if isinstance(rule, dict)
    ]
    return (any(results) if group.get("match") == "any" else all(results)) if results else True


def field_applies(field, values):
    return condition_group_applies(field_condition_group(field), values)


def applicable_field_keys(schema, values):
    """Resolve conditional chains against the immutable schema, independent of field order."""
    fields = _field_map(schema)
    section_active = {
        str(field.get("key")): section.get("visible") is not False and section.get("admin_only") is not True
        for section in schema.get("sections", [])
        if isinstance(section, dict)
        for field in section.get("fields", [])
        if isinstance(field, dict) and field.get("key")
    }
    resolved = {}
    visiting = set()

    def visible(key):
        if key in resolved:
            return resolved[key]
        if key in visiting:
            return False
        field = fields.get(key)
        if not field or field.get("visible") is False or not section_active.get(key, False):
            resolved[key] = False
            return False
        visiting.add(key)
        group = field_condition_group(field)
        if group:
            results = [
                visible(str(rule.get("field") or ""))
                and _compare_condition(_condition_value(values, str(rule.get("field") or "")), rule)
                for rule in group.get("conditions", []) if isinstance(rule, dict)
            ]
            result = (any(results) if group.get("match") == "any" else all(results)) if results else False
        else:
            result = True
        visiting.remove(key)
        resolved[key] = result
        return result

    return {key for key in fields if visible(key)}


def build_form_migration_plan(previous_schema, next_schema):
    """Describe deterministic, non-destructive migration rules between versions."""
    old_fields = _field_map(previous_schema or {})
    new_fields = _field_map(next_schema or {})
    rules = []
    incompatible = []
    attention = []

    for key, target in new_fields.items():
        source = old_fields.get(key)
        if source is None:
            rule = {"field": key, "action": "add", "required": bool(target.get("required"))}
            rules.append(rule)
            if rule["required"] and target.get("visible") is not False:
                attention.append(key)
            continue
        source_type = str(source.get("type") or "")
        target_type = str(target.get("type") or "")
        if source_type != target_type:
            if key == "location" and target_type == "multiselect_dropdown":
                rules.append({"field": key, "action": "transform_location", "from": source_type, "to": target_type})
            else:
                item = {"field": key, "reason": f"Field type changed from {source_type} to {target_type}."}
                incompatible.append(item)
                rules.append({"field": key, "action": "unsupported", **item})
            continue
        removed_values = []
        if target_type in {"select", "multiselect", "multiselect_dropdown"}:
            old_values = {str(item.get("value")) for item in source.get("options", []) if isinstance(item, dict)}
            new_values = {str(item.get("value")) for item in target.get("options", []) if isinstance(item, dict)}
            removed_values = sorted(old_values - new_values)
        rules.append({"field": key, "action": "copy", "removed_option_values": removed_values})

    for key, source in old_fields.items():
        if key not in new_fields:
            rules.append({"field": key, "action": "retain_hidden", "source_type": source.get("type")})

    return {
        "format": 1,
        "rules": rules,
        "attention_fields": attention,
        "incompatible_changes": incompatible,
    }


def validate_form_schema(schema, published_schema=None):
    if not isinstance(schema, dict):
        raise FormSchemaError("Form schema must be a JSON object.")
    if not str(schema.get("title") or "").strip():
        raise FormSchemaError("The form title is required.")
    sections = schema.get("sections")
    if not isinstance(sections, list) or not sections:
        raise FormSchemaError("The form must contain at least one section.")
    if len(sections) > 20:
        raise FormSchemaError("A form can contain at most 20 sections.")

    section_keys = set()
    field_keys = set()
    field_count = 0
    active_document_fields = []
    for section in sections:
        if not isinstance(section, dict):
            raise FormSchemaError("Every section must be an object.")
        section_key = str(section.get("key") or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", section_key):
            raise FormSchemaError("Section keys must use lowercase letters, numbers, and underscores.")
        if section_key in section_keys:
            raise FormSchemaError(f"Duplicate section key: {section_key}.")
        section_keys.add(section_key)
        if not str(section.get("title") or "").strip():
            raise FormSchemaError(f"Section {section_key} needs a title.")
        fields = section.get("fields")
        if not isinstance(fields, list):
            raise FormSchemaError(f"Section {section_key} must contain a fields list.")
        for field in fields:
            if not isinstance(field, dict):
                raise FormSchemaError("Every field must be an object.")
            key = str(field.get("key") or "").strip()
            if not re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9_]*|priorityAnalysisFacts\.[A-Za-z][A-Za-z0-9_]*)", key):
                raise FormSchemaError(f"Invalid field key: {key or '(empty)'}.")
            if key in field_keys:
                raise FormSchemaError(f"Duplicate field key: {key}.")
            field_keys.add(key)
            field_count += 1
            field_type = str(field.get("type") or "")
            if field_type not in ALLOWED_FIELD_TYPES:
                raise FormSchemaError(f"Unsupported field type for {key}.")
            if key not in CORE_FIELDS and not key.startswith("custom_"):
                raise FormSchemaError("New fields must use a stable key beginning with custom_ .")
            if not str(field.get("label") or "").strip():
                raise FormSchemaError(f"Field {key} needs a label.")
            if field_type == "currency_by_year" and key not in {"fundingRequirementByYear", "actualFundingByYear"}:
                raise FormSchemaError("Year-based currency is only supported by the project funding fields.")
            if field_type == "document_upload":
                if not key.startswith("custom_"):
                    raise FormSchemaError("Supporting-document fields must use a custom field key.")
                if section.get("admin_only") is True:
                    raise FormSchemaError("Supporting-document fields must be contributor-facing.")
                extensions = field.get("allowed_extensions")
                if not isinstance(extensions, list) or not extensions:
                    raise FormSchemaError(f"Field {key} needs at least one allowed document format.")
                normalized_extensions = [str(value or "").strip().lower().lstrip(".") for value in extensions]
                if (
                    len(set(normalized_extensions)) != len(normalized_extensions)
                    or any(value not in DOCUMENT_UPLOAD_EXTENSIONS for value in normalized_extensions)
                ):
                    raise FormSchemaError(f"Field {key} contains an unsupported or duplicate document format.")
                try:
                    min_files = int(field.get("min_files", 1 if field.get("required") else 0))
                    max_files = int(field.get("max_files", DOCUMENT_UPLOAD_MAX_FILES))
                    max_file_bytes = int(field.get("max_file_bytes", DOCUMENT_UPLOAD_MAX_BYTES))
                except (TypeError, ValueError) as exc:
                    raise FormSchemaError(f"Field {key} has invalid document limits.") from exc
                if min_files < 0 or max_files < 1 or max_files > DOCUMENT_UPLOAD_MAX_FILES or min_files > max_files:
                    raise FormSchemaError(f"Field {key} must allow between 1 and {DOCUMENT_UPLOAD_MAX_FILES} files.")
                if field.get("required") and min_files < 1:
                    raise FormSchemaError(f"Required document field {key} must require at least one file.")
                if max_file_bytes < 1 or max_file_bytes > DOCUMENT_UPLOAD_MAX_BYTES:
                    raise FormSchemaError(f"Field {key} has an invalid per-file size limit.")
                instructions = str(field.get("ai_sufficiency_instructions") or "").strip()
                if len(instructions) > 4000:
                    raise FormSchemaError(f"Field {key} AI sufficiency instructions are too long.")
                if section.get("visible") is not False and field.get("visible") is not False:
                    active_document_fields.append(key)
            options = field.get("options", [])
            if field_type in {"select", "multiselect", "multiselect_dropdown"}:
                if not isinstance(options, list) or not options:
                    raise FormSchemaError(f"Field {key} needs at least one option.")
                values = [str(option.get("value") or "") for option in options if isinstance(option, dict)]
                if len(values) != len(options) or any(not value for value in values) or len(set(values)) != len(values):
                    raise FormSchemaError(f"Field {key} has invalid or duplicate option values.")

    if field_count > 100:
        raise FormSchemaError("A form can contain at most 100 fields.")
    missing_sections = PROTECTED_SECTION_KEYS - section_keys
    if missing_sections:
        titles = {
            section["key"]: section["title"]
            for section in DEFAULT_SIMPLIFIED_FORM_SCHEMA["sections"]
        }
        raise FormSchemaError("Essential sections cannot be removed: " + ", ".join(titles[key] for key in sorted(missing_sections)) + ".")
    if len(active_document_fields) > 1:
        raise FormSchemaError("A contributor form can contain only one active supporting-document field.")
    missing = PROTECTED_WORKFLOW_FIELD_KEYS - field_keys
    if missing:
        labels = {key: DEFAULT_SIMPLIFIED_FORM_SCHEMA["sections"][0]["title"] if key == "agencyName" else CORE_FIELDS.get(key, {}).get("label", key) for key in missing}
        raise FormSchemaError("Essential project fields cannot be removed: " + ", ".join(sorted(labels.values())) + ".")

    current = _field_map(schema)
    mappings = schema.get("scoring_mappings", {})
    if not isinstance(mappings, dict):
        raise FormSchemaError("AI scoring mappings must be an object.")
    if mappings:
        from projects.scoring_contract import default_scoring_input_contract

        allowed_facts = {
            item["key"] for item in default_scoring_input_contract()["dependencies"]
            if item.get("source") == "contributor" and item["key"] != "custom_supporting_documents"
        }
        if any(key not in allowed_facts or not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value) for key, value in mappings.items()):
            raise FormSchemaError("AI scoring mappings contain an unsupported fact or field identity.")
    published_fields = _field_map(published_schema) if isinstance(published_schema, dict) else {}
    reset_from_scratch = schema.get("reset_from_scratch") is True
    section_visible_for_field = {
        str(field.get("key")): section.get("visible") is not False and section.get("admin_only") is not True
        for section in sections
        for field in section.get("fields", [])
        if isinstance(field, dict) and field.get("key")
    }
    section_for_field = {
        str(field.get("key")): str(section.get("key"))
        for section in sections for field in section.get("fields", []) if isinstance(field, dict)
    }
    for key in PROTECTED_WORKFLOW_FIELD_KEYS:
        candidate = current.get(key)
        if candidate is None:
            continue
        if (
            (key in {"agencyName", "projectActivity", "startYear", "endYear"} and not candidate.get("required"))
            or candidate.get("visible") is False
            or not section_visible_for_field.get(key, False)
            or section_for_field.get(key) != PROTECTED_FIELD_SECTIONS[key]
        ):
            raise FormSchemaError(f"The essential field '{candidate.get('label') or CORE_FIELDS.get(key, {}).get('label', key)}' must stay in its core section and remain available.")
    for key, original in CORE_FIELDS.items():
        candidate = current.get(key)
        if candidate is None:
            continue
        if key in CONDITION_REQUIRED_CORE_FIELDS and (
            not candidate.get("condition_required")
            or candidate.get("visible") is False
            or not section_visible_for_field.get(key, False)
        ):
            raise FormSchemaError(f"Conditional validation for {key} must remain visible and cannot be removed.")
        original_values = [option["value"] for option in original.get("options", [])]
        if original_values:
            candidate_values = [option.get("value") for option in candidate.get("options", []) if isinstance(option, dict)]
            # A deployed form can contain an earlier official value set after system wording is revised.
            # Keep those already-published values valid so ordinary CMS edits are not blocked, while
            # continuing to require generated keys for genuinely new choices.
            published_values = {
                option.get("value")
                for option in published_fields.get(key, {}).get("options", [])
                if isinstance(option, dict)
            }
            generated_values = set(candidate_values) - set(original_values) - published_values
            if any(not re.fullmatch(r"option_[1-9][0-9]*", str(value)) for value in generated_values):
                raise FormSchemaError(f"New choices for workflow field {key} must use generated option values.")

    for key, field_type in FIXED_FIELD_TYPES.items():
        candidate = current.get(key)
        if candidate is not None and candidate.get("type") != field_type:
            raise FormSchemaError(f"The field type for {key} is managed by the system and cannot be changed.")

    for key in PROTECTED_OPTION_FIELDS:
        candidate = current.get(key)
        original = CORE_FIELDS.get(key)
        if candidate is not None and original is not None and candidate.get("options") != original.get("options"):
            raise FormSchemaError("Collaborating Agency choices are managed by the Agency catalog and cannot be edited in the form builder.")

    operator_types = {
        "select": {"equals", "not_equals", "one_of", "not_one_of", "is_empty", "is_not_empty"},
        "multiselect": {"contains", "not_contains", "contains_any", "is_empty", "is_not_empty"},
        "multiselect_dropdown": {"contains", "not_contains", "contains_any", "is_empty", "is_not_empty"},
        "text": {"equals", "not_equals", "is_empty", "is_not_empty"},
        "textarea": {"equals", "not_equals", "is_empty", "is_not_empty"},
        "number": {"equals", "not_equals", "greater_than", "less_than", "at_least", "at_most", "is_empty", "is_not_empty"},
        "year": {"equals", "not_equals", "greater_than", "less_than", "at_least", "at_most", "is_empty", "is_not_empty"},
        "date": {"equals", "not_equals", "before", "after", "is_empty", "is_not_empty"},
    }
    active_fields = {
        key for key, field in current.items()
        if field.get("visible") is not False and section_visible_for_field.get(key, False)
    }
    dependency_graph = {key: set() for key in active_fields}
    for field in current.values():
        if field.get("key") not in active_fields:
            continue
        group = field_condition_group(field)
        if not group:
            continue
        if group.get("match") not in {"all", "any"} or not isinstance(group.get("conditions"), list) or not group["conditions"]:
            raise FormSchemaError(f"Conditional field {field.get('key')} needs a valid ALL or ANY rule group.")
        for rule in group["conditions"]:
            if not isinstance(rule, dict):
                raise FormSchemaError(f"Conditional field {field.get('key')} contains an invalid rule.")
            source_key = str(rule.get("field") or "")
            source = current.get(source_key)
            if source is None:
                raise FormSchemaError(f"Conditional field {field.get('key')} references a missing field.")
            if source_key == field.get("key"):
                raise FormSchemaError(f"Field {source_key} cannot depend on itself.")
            if source_key not in active_fields:
                raise FormSchemaError(f"Conditional field {field.get('key')} references an inaccessible field {source_key}.")
            operator = str(rule.get("operator") or "")
            if operator not in operator_types.get(str(source.get("type") or ""), set()):
                raise FormSchemaError(f"Operator {operator or '(missing)'} is not valid for {source.get('label') or source_key}.")
            dependency_graph[str(field.get("key"))].add(source_key)
            expected = rule.get("values") if operator in {"one_of", "not_one_of", "contains_any"} else [rule.get("value")]
            if operator not in {"is_empty", "is_not_empty"} and (not isinstance(expected, list) or not expected):
                raise FormSchemaError(f"Conditional field {field.get('key')} needs an expected answer.")
            if operator not in {"is_empty", "is_not_empty"} and any(value is None or str(value).strip() == "" for value in expected):
                raise FormSchemaError(f"Conditional field {field.get('key')} needs a non-empty expected answer.")
            if source.get("type") in {"number", "year"} and operator not in {"is_empty", "is_not_empty"}:
                try:
                    for value in expected:
                        float(str(value).replace(",", ""))
                except (ValueError, TypeError) as exc:
                    raise FormSchemaError(f"Conditional field {field.get('key')} needs a valid number for {source_key}.") from exc
            if source.get("type") == "date" and operator not in {"is_empty", "is_not_empty"}:
                try:
                    for value in expected:
                        date.fromisoformat(str(value))
                except (ValueError, TypeError) as exc:
                    raise FormSchemaError(f"Conditional field {field.get('key')} needs a valid date for {source_key}.") from exc
            if source.get("type") in {"select", "multiselect", "multiselect_dropdown"} and operator not in {"is_empty", "is_not_empty"}:
                allowed_values = {str(option.get("value")) for option in source.get("options", []) if isinstance(option, dict)}
                if any(str(value) not in allowed_values for value in expected):
                    raise FormSchemaError(f"A condition for {field.get('key')} references an unavailable choice in {source_key}.")

    visiting, visited = set(), set()
    def visit(key):
        if key in visiting:
            raise FormSchemaError("Conditional fields cannot contain circular dependencies.")
        if key in visited:
            return
        visiting.add(key)
        for source_key in dependency_graph.get(key, set()):
            visit(source_key)
        visiting.remove(key)
        visited.add(key)
    for field_key in dependency_graph:
        visit(field_key)

    validate_system_managed_sections(schema, published_schema)
    return deepcopy(schema)


def validate_draft_schema(schema):
    """Allow unfinished definitions while rejecting unsafe or ambiguous JSON shapes."""
    if not isinstance(schema, dict):
        raise FormSchemaError("The form draft must be an object.")
    sections = schema.get("sections")
    if not isinstance(sections, list) or len(sections) > 20:
        raise FormSchemaError("The form draft must contain a sections list of at most 20 items.")
    section_keys, field_keys = set(), set()
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("fields"), list):
            raise FormSchemaError("Each section needs a valid fields list.")
        key = str(section.get("key") or "")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or key in section_keys:
            raise FormSchemaError("Section identities must be unique and valid.")
        if section.get("admin_only"):
            raise FormSchemaError("Validator Facts are managed outside Contributor Form sections.")
        section_keys.add(key)
        for field in section["fields"]:
            if not isinstance(field, dict):
                raise FormSchemaError("Each field must be an object.")
            field_key = str(field.get("key") or "")
            if not re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9_]*|priorityAnalysisFacts\.[A-Za-z][A-Za-z0-9_]*)", field_key) or field_key in field_keys:
                raise FormSchemaError("Field identities must be unique and valid.")
            field_keys.add(field_key)
    if len(field_keys) > 100:
        raise FormSchemaError("A form draft can contain at most 100 fields.")
    return deepcopy(schema)


def validate_update_mode(previous_schema, next_schema):
    old_sections = [section for section in previous_schema.get("sections", []) if isinstance(section, dict)]
    new_sections = [section for section in next_schema.get("sections", []) if isinstance(section, dict)]
    old_keys = [section.get("key") for section in old_sections]
    new_keys = [section.get("key") for section in new_sections]
    if old_keys != new_keys[: len(old_keys)]:
        raise FormSchemaError("Update Form cannot reorder or remove sections. Use Change Form instead.")
    new_by_key = {section.get("key"): section for section in new_sections}
    for old_section in old_sections:
        new_section = new_by_key.get(old_section.get("key"), {})
        if old_section.get("visible", True) != new_section.get("visible", True):
            raise FormSchemaError("Update Form cannot hide sections. Use Change Form instead.")
        old_fields = [field for field in old_section.get("fields", []) if isinstance(field, dict)]
        new_fields = [field for field in new_section.get("fields", []) if isinstance(field, dict)]
        new_field_map = {field.get("key"): field for field in new_fields}
        existing_order = [field.get("key") for field in new_fields if field.get("key") in {item.get("key") for item in old_fields}]
        if existing_order != [field.get("key") for field in old_fields]:
            raise FormSchemaError("Update Form cannot reorder existing fields. Use Change Form instead.")
        for old_field in old_fields:
            new_field = new_field_map.get(old_field.get("key"))
            if not new_field:
                raise FormSchemaError("Update Form cannot remove fields. Use Change Form instead.")
            for key in ("type", "required", "visible", "condition", "condition_group", "condition_required"):
                if old_field.get(key) != new_field.get(key):
                    raise FormSchemaError("Update Form only changes wording and adds fields. Use Change Form for structural changes.")
            old_values = [option.get("value") for option in old_field.get("options", []) if isinstance(option, dict)]
            new_values = [option.get("value") for option in new_field.get("options", []) if isinstance(option, dict)]
            if old_values != new_values:
                raise FormSchemaError("Update Form cannot change option values. Use Change Form instead.")


def schema_fields(schema):
    for section in schema.get("sections", []) if isinstance(schema, dict) else []:
        if not isinstance(section, dict) or section.get("visible") is False:
            continue
        for field in section.get("fields", []):
            if isinstance(field, dict) and field.get("visible") is not False:
                yield field


def resolve_simplified_form_schema(profile_data, schema_version=None):
    """Return the immutable schema selected by a project profile marker."""
    from cms.models import CMSContributorForm, CMSContributorFormVersion

    marker = profile_data.get("form_schema") if isinstance(profile_data, dict) and isinstance(profile_data.get("form_schema"), dict) else {}
    key = str(marker.get("key") or SIMPLIFIED_FORM_KEY)
    try:
        version_number = int(marker.get("version") or 0)
    except (TypeError, ValueError):
        version_number = 0
    version = schema_version
    if version is None and version_number:
        version = CMSContributorFormVersion.objects.filter(
            form__key=key, version_number=version_number,
        ).select_related("form").first()
    if version is None:
        form = CMSContributorForm.objects.filter(key=key).select_related("current_published_version").first()
        version = form.current_published_version if form else None
    return (version.schema_json if version else default_simplified_form_schema()), version


def validate_simplified_answers(profile_data, require_complete=False, legacy_status=None, schema_version=None):
    if not isinstance(profile_data, dict) or not isinstance(profile_data.get("simplified_form"), dict):
        return profile_data
    from projects.project_status import canonical_implementation_status

    marker = profile_data.get("form_schema") if isinstance(profile_data.get("form_schema"), dict) else {}
    legacy_marker = marker.get("legacy") is True
    schema, version = resolve_simplified_form_schema(profile_data, schema_version)
    if version:
        profile_data["form_schema"] = {"key": version.form.key, "version": version.version_number}
    else:
        profile_data["form_schema"] = {"key": SIMPLIFIED_FORM_KEY, "version": 1}
    if legacy_marker:
        profile_data["form_schema"]["legacy"] = True
    simplified = profile_data["simplified_form"]
    saved_status = simplified.get("status")
    normalized_status = canonical_implementation_status(saved_status)
    # Retired implementation statuses are only normalized while preserving an
    # unchanged historical project.  A new or edited submission must select a
    # value from its published CMS form instead.  This keeps the official
    # legacy migration path without letting values such as "Updated" bypass a
    # current schema merely because they have a canonical replacement.
    if (
        normalized_status
        and normalized_status != str(saved_status or "").strip()
        and str(saved_status or "").strip() == str(legacy_status or "").strip()
    ):
        simplified["status"] = normalized_status
    custom = simplified.get("custom_fields") if isinstance(simplified.get("custom_fields"), dict) else {}
    current_fields = _field_map(schema)
    # Existing projects can carry answers from an earlier immutable form
    # version. Keep those answers when a saved version marker is present.
    if not marker.get("version"):
        for key in list(custom):
            if key not in current_fields:
                custom.pop(key, None)
    # A newly published form may retire a former built-in field entirely.
    # Ignore values posted under those old keys for submissions using it.
    if not marker.get("version"):
        for key in CORE_FIELDS:
            if key not in current_fields:
                simplified.pop(key, None)
    applicable = applicable_field_keys(schema, simplified)
    for key, field in current_fields.items():
        if key in applicable or field.get("type") == "document_upload" or key.startswith("priorityAnalysisFacts."):
            continue
        if key.startswith("custom_"):
            custom.pop(key, None)
        elif key.startswith("priorityAnalysisFacts."):
            facts = simplified.get("priorityAnalysisFacts") if isinstance(simplified.get("priorityAnalysisFacts"), dict) else {}
            facts.pop(key.split(".", 1)[1], None)
        else:
            simplified.pop(key, None)
    missing = []
    invalid = []
    for field in schema_fields(schema):
        if field.get("key") not in applicable:
            key = str(field.get("key"))
            if key.startswith("custom_"):
                custom.pop(key, None)
            elif key.startswith("priorityAnalysisFacts."):
                facts = simplified.get("priorityAnalysisFacts") if isinstance(simplified.get("priorityAnalysisFacts"), dict) else {}
                facts.pop(key.split(".", 1)[1], None)
            else:
                simplified.pop(key, None)
            continue
        key = str(field.get("key"))
        field_type = field.get("type")
        if field_type == "document_upload":
            # Supporting files are normalized in their own project-owned table,
            # not inside the JSON answer snapshot.
            continue
        if key.startswith("custom_"):
            value = custom.get(key)
        elif key.startswith("priorityAnalysisFacts."):
            facts = simplified.get("priorityAnalysisFacts") if isinstance(simplified.get("priorityAnalysisFacts"), dict) else {}
            value = facts.get(key.split(".", 1)[1])
        else:
            value = simplified.get(key)
        empty = value is None or value == "" or (isinstance(value, (list, dict)) and not value)
        required = bool(field.get("required") or field.get("condition_required"))
        if require_complete and required and empty:
            missing.append(str(field.get("label") or key))
            continue
        if empty:
            continue
        if field_type in {"multiselect", "multiselect_dropdown"} and not isinstance(value, list):
            invalid.append(str(field.get("label") or key))
        elif field_type == "currency_by_year" and not isinstance(value, dict):
            invalid.append(str(field.get("label") or key))
        elif field_type in {"number", "year"}:
            try:
                float(str(value).replace(",", ""))
            except (TypeError, ValueError):
                invalid.append(str(field.get("label") or key))
        elif field_type in {"select", "multiselect", "multiselect_dropdown"}:
            allowed = {str(option.get("value")) for option in field.get("options", []) if isinstance(option, dict)}
            if key == "status":
                allowed.update(CURRENT_PROJECT_STATUS_VALUES)
            selected = value if isinstance(value, list) else [value]
            if any(
                str(item) not in allowed and not (key == "status" and str(item) == legacy_status)
                for item in selected
            ):
                invalid.append(str(field.get("label") or key))
    if simplified.get("status") in {"New", "Not Implemented"}:
        for key, label in (
            ("physicalAccomplishment", "Physical Accomplishment"),
            ("financialAccomplishment", "Financial Accomplishment"),
        ):
            if str(simplified.get(key) or "").strip():
                invalid.append(f"{label} (not applicable to {simplified.get('status')})")
    if missing:
        raise FormSchemaError("Complete the required form fields: " + ", ".join(missing) + ".")
    if invalid:
        raise FormSchemaError("Correct invalid form values: " + ", ".join(invalid) + ".")
    return profile_data
