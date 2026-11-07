"""One authoritative contract between contributor forms and priority scoring.

The priority scorer historically knew its inputs through several independent
hard-coded lists.  This module is deliberately small and data-oriented so the
form publisher, scorer, Groq adapter, and CMS can all inspect the same stable
field keys without depending on display labels or field order.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import re
from typing import Any


CONTRACT_VERSION = 1


class ScoringCompatibilityError(ValueError):
    """Structured publish/activation failure safe to return to administrators."""

    def __init__(self, report: dict[str, Any]):
        super().__init__("The configuration has unresolved scoring compatibility errors.")
        self.report = report


def _dependency(
    key: str,
    label: str,
    *,
    source: str,
    expected_types: list[str],
    criteria: list[str],
    required_for_input: bool = False,
    required_in_schema: bool = True,
    condition: str = "always",
    unavailable_behavior: str = "block",
    description: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "source": source,
        "expected_types": expected_types,
        "criteria": criteria,
        "required_for_input": required_for_input,
        "required_in_schema": required_in_schema,
        "condition": condition,
        "unavailable_behavior": unavailable_behavior,
        "description": description,
    }


# These definitions reflect the fields currently consumed by priority_scoring
# and groq_priority.  Do not use labels as identifiers: labels are explicitly
# safe to edit in the contributor form CMS.
DEFAULT_SCORING_INPUT_CONTRACT: dict[str, Any] = {
    "format": CONTRACT_VERSION,
    "dependencies": [
        _dependency("program", "Program", source="contributor", expected_types=["text", "textarea"], criteria=["outcome_rules"], required_for_input=True, description="Provides project context for outcome matching."),
        _dependency("projectActivity", "Project/Activity", source="contributor", expected_types=["text", "textarea"], criteria=["outcome_rules"], required_for_input=True, description="Provides the primary project intervention narrative."),
        _dependency("location", "Location", source="contributor", expected_types=["multiselect_dropdown", "multiselect", "text"], criteria=["outcome_rules", "spatial_coverage"], required_for_input=True, description="Supports NCR coverage and spatial checks."),
        _dependency("description", "Description", source="contributor", expected_types=["textarea", "text"], criteria=["outcome_rules"], required_for_input=True, description="Primary narrative evaluated by outcome criteria."),
        _dependency("objective", "Objective", source="contributor", expected_types=["textarea", "text"], criteria=["outcome_rules"], required_for_input=True, description="Primary intended-result narrative evaluated by outcome criteria."),
        _dependency("developmentSector", "Development Sector", source="contributor", expected_types=["select"], criteria=["outcome_rules"], required_for_input=True, description="Selects the applicable sector outcome rules."),
        _dependency("rdpMainChapter", "RDP Main Chapter", source="contributor", expected_types=["select", "text"], criteria=["outcome_rules"], required_for_input=True, description="Provides planning-alignment context."),
        _dependency("status", "Status", source="contributor", expected_types=["select", "text"], criteria=["outcome_rules", "risk_checks"], required_for_input=True, description="Controls accomplishment and risk checks."),
        _dependency("fundingRequirementByYear", "Funding Requirement", source="contributor", expected_types=["currency_by_year"], criteria=["regional_eligibility"], required_for_input=True, description="Determines the regional-project eligibility threshold."),
        _dependency("actualFundingByYear", "Actual/Approved Funding", source="contributor", expected_types=["currency_by_year"], criteria=["risk_checks"], required_for_input=False, description="Used only to identify accomplishment risks."),
        _dependency("physicalAccomplishment", "Physical Accomplishment", source="contributor", expected_types=["textarea", "text"], criteria=["risk_checks"], required_for_input=False, description="Used only when the project is not new."),
        _dependency("financialAccomplishment", "Financial Accomplishment", source="contributor", expected_types=["textarea", "text"], criteria=["risk_checks"], required_for_input=False, description="Used when actual funding is supplied."),
        _dependency("remarks", "Remarks", source="contributor", expected_types=["textarea", "text"], criteria=["outcome_rules"], required_for_input=False, description="Optional supporting narrative."),
        _dependency("sdgSelections", "Sustainable Development Goals", source="contributor", expected_types=["multiselect", "multiselect_dropdown"], criteria=["outcome_rules"], required_for_input=False, description="Optional planning-alignment context."),
        # This gate is enforced against the project's normalized document
        # records at evaluation time.  Older published form snapshots predate
        # the upload field, so they remain publishable and are not rewritten.
        _dependency("custom_supporting_documents", "Supporting Documents", source="contributor", expected_types=["document_upload"], criteria=["supporting_documents"], required_for_input=True, required_in_schema=False, description="The document-assessment gate must be available before scoring."),
        _dependency("priorityAnalysisFacts.readinessLevel", "Readiness Level", source="validator", expected_types=["select"], criteria=["readiness"], required_for_input=True, description="A validator supplies the factual readiness classification."),
        _dependency("priorityAnalysisFacts.gadResponsiveness", "GAD Responsiveness", source="validator", expected_types=["select"], criteria=["gad_responsiveness"], required_for_input=True, description="A validator supplies the factual GAD classification."),
        _dependency("priorityAnalysisFacts.spatialCoverageScope", "Spatial Coverage Scope", source="validator", expected_types=["select"], criteria=["spatial_coverage"], required_for_input=True, description="A validator supplies the official spatial category."),
        _dependency("priorityAnalysisFacts.beneficiaryCount", "Estimated Beneficiary Count", source="validator", expected_types=["number"], criteria=["regional_beneficiaries"], required_for_input=True, condition="regional_project", description="Required only when the project reaches the regional funding threshold."),
        _dependency("regionalSpatialCategory", "Regional Spatial Coverage", source="validator", expected_types=[], criteria=["regional_spatial"], required_for_input=True, required_in_schema=False, condition="regional_project", description="Validator-only regional scorecard fact."),
        _dependency("contributedOutcomeCount", "Contributed RDP Outcomes", source="validator", expected_types=[], criteria=["regional_outcomes"], required_for_input=True, required_in_schema=False, condition="regional_project", description="Validator-only regional scorecard fact."),
        _dependency("sceeedTrack", "SCEED Track Confirmation", source="validator", expected_types=[], criteria=["outcome_rules"], required_for_input=True, required_in_schema=False, condition="economic_environment_sector", description="Required for Economic and Environment sector projects."),
    ],
}


def default_scoring_input_contract() -> dict[str, Any]:
    return deepcopy(DEFAULT_SCORING_INPUT_CONTRACT)


def normalize_scoring_input_contract(value: Any) -> dict[str, Any]:
    """Return a safe, immutable-shaped contract for existing rule versions."""
    if not isinstance(value, dict) or not isinstance(value.get("dependencies"), list):
        return default_scoring_input_contract()
    candidate = deepcopy(value)
    if candidate.get("format") != CONTRACT_VERSION:
        return default_scoring_input_contract()
    if not all(isinstance(item, dict) and str(item.get("key") or "") for item in candidate["dependencies"]):
        return default_scoring_input_contract()
    return candidate


def contract_for_rule_set(rule_set=None) -> dict[str, Any]:
    return normalize_scoring_input_contract(getattr(rule_set, "input_contract", None))


def narrative_field_keys(contract: dict[str, Any] | None = None) -> tuple[str, ...]:
    current = normalize_scoring_input_contract(contract)
    return tuple(
        item["key"]
        for item in current["dependencies"]
        if item.get("source") == "contributor" and "outcome_rules" in item.get("criteria", [])
    )


# Older detailed-form snapshots may contain these values.  They remain usable
# for historical analysis, but are never required from the current simplified
# contributor form and therefore cannot make a current form incompatible.
LEGACY_OPTIONAL_NARRATIVE_FIELD_KEYS = (
    "mainInfrastructureSector",
    "mainInfrastructureSubsector",
    "spatialCoverageByCost",
    "spatialCoverageByImpact",
)


def scoring_text_field_keys(contract: dict[str, Any] | None = None) -> tuple[str, ...]:
    return (*narrative_field_keys(contract), *LEGACY_OPTIONAL_NARRATIVE_FIELD_KEYS)


def criterion_dependencies(config: dict[str, Any] | None = None, contract: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Expand the contract into criterion-facing records for APIs and UI."""
    current = normalize_scoring_input_contract(contract)
    outcomes: list[dict[str, str]] = []
    if isinstance(config, dict):
        dictionaries = config.get("keyword_dictionaries") if isinstance(config.get("keyword_dictionaries"), dict) else {}
        candidates = list(dictionaries.get("common_outcomes") or [])
        sectors = config.get("sector_criteria") if isinstance(config.get("sector_criteria"), dict) else {}
        for rows in sectors.values():
            candidates.extend(rows if isinstance(rows, list) else [])
        outcomes = [
            {"key": str(row.get("key") or ""), "label": str(row.get("label") or row.get("key") or "Outcome criterion")}
            for row in candidates if isinstance(row, dict) and row.get("key")
        ]
    result = []
    for item in current["dependencies"]:
        targets = []
        for criterion in item.get("criteria", []):
            if criterion == "outcome_rules":
                targets.extend(outcomes)
            else:
                targets.append({"key": criterion, "label": criterion.replace("_", " ").title()})
        result.append({
            **deepcopy(item),
            # Keep the concise category code alongside the expanded internal
            # criterion references. This avoids rendering every outcome label
            # in administrator dependency explanations.
            "criterion_categories": list(item.get("criteria", [])),
            "criteria": targets,
        })
    return result


def _schema_fields(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    if not isinstance(schema, dict):
        return fields
    for section in schema.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_visible = section.get("visible") is not False
        for field in section.get("fields", []):
            if not isinstance(field, dict) or not field.get("key"):
                continue
            fields[str(field["key"])] = {
                **field,
                "_section_visible": section_visible,
                "_section_key": section.get("key"),
            }
    return fields


def contract_for_form_schema(
    schema: dict[str, Any] | None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add every contributor field as labelled AI context for this form version."""
    current = normalize_scoring_input_contract(contract)
    fields = _schema_fields(schema)
    dependencies = [deepcopy(dependency) for dependency in current["dependencies"]]
    known_keys = {dependency["key"] for dependency in dependencies}
    for field in fields.values():
        key = str(field.get("key") or "")
        if not key or key in known_keys or field.get("type") == "document_upload":
            continue
        dependencies.append(_dependency(
            key,
            str(field.get("label") or key),
            source="contributor",
            expected_types=[str(field.get("type") or "text")],
            criteria=["outcome_rules"],
            required_for_input=False,
            required_in_schema=False,
            description="Applicable contributor-form context from the project's immutable form version.",
        ))
    return {**deepcopy(current), "dependencies": dependencies}


def apply_scoring_mappings(
    form: dict[str, Any], schema: dict[str, Any], applicable_keys: set[str],
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve canonical facts from stable keys in the published form version."""
    result = deepcopy(form)
    mappings = schema.get("scoring_mappings") if isinstance(schema.get("scoring_mappings"), dict) else {}
    allowed = {
        item["key"] for item in normalize_scoring_input_contract(contract)["dependencies"]
        if item.get("source") == "contributor"
    }
    for canonical_key, source_key in mappings.items():
        if canonical_key not in allowed or not isinstance(source_key, str):
            continue
        if source_key not in applicable_keys:
            result.pop(canonical_key, None)
            continue
        answer = (result.get("custom_fields") or {}).get(source_key) if source_key.startswith("custom_") else result.get(source_key)
        if answer in (None, "", [], {}):
            result.pop(canonical_key, None)
        else:
            result[canonical_key] = deepcopy(answer)
    return result


def contract_for_project_snapshot(
    snapshot: dict[str, Any] | None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the immutable form version attached to a project snapshot."""
    if not isinstance(snapshot, dict):
        return normalize_scoring_input_contract(contract)
    form = snapshot.get("simplified_form") if isinstance(snapshot.get("simplified_form"), dict) else snapshot
    # Project profiles store the immutable form marker beside simplified_form.
    # Some older snapshots embedded it inside simplified_form, so retain that
    # fallback while preferring the current canonical location.
    marker = snapshot.get("form_schema") if isinstance(snapshot.get("form_schema"), dict) else {}
    if not marker and isinstance(form.get("form_schema"), dict):
        marker = form.get("form_schema")
    key = str(marker.get("key") or "")
    version_number = marker.get("version")
    if not key or not version_number:
        return normalize_scoring_input_contract(contract)
    try:
        from cms.models import CMSContributorFormVersion

        version = CMSContributorFormVersion.objects.filter(
            form__key=key,
            version_number=version_number,
        ).only("schema_json").first()
    except (TypeError, ValueError):
        version = None
    return contract_for_form_schema(version.schema_json, contract) if version else normalize_scoring_input_contract(contract)


def form_version_for_project_snapshot(snapshot: dict[str, Any] | None):
    """Resolve the exact immutable CMS form version recorded by a project."""
    if not isinstance(snapshot, dict):
        return None
    form = snapshot.get("simplified_form") if isinstance(snapshot.get("simplified_form"), dict) else snapshot
    marker = snapshot.get("form_schema") if isinstance(snapshot.get("form_schema"), dict) else {}
    if not marker and isinstance(form.get("form_schema"), dict):
        marker = form.get("form_schema")
    key, version_number = str(marker.get("key") or ""), marker.get("version")
    if not key or not version_number:
        return None
    try:
        from cms.models import CMSContributorFormVersion
        return CMSContributorFormVersion.objects.filter(
            form__key=key, version_number=version_number,
        ).first()
    except (TypeError, ValueError):
        return None


def _issue(status: str, dependency: dict[str, Any], message: str, recommendation: str) -> dict[str, Any]:
    return {
        "status": status,
        "field_key": dependency["key"],
        "field_label": dependency["label"],
        "source": dependency["source"],
        "criteria": dependency.get("criteria", []),
        "message": message,
        "recommendation": recommendation,
    }


def form_compatibility_report(
    schema: dict[str, Any],
    config: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
    baseline_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check a candidate contributor schema without saving it."""
    fields = _schema_fields(schema)
    mappings = schema.get("scoring_mappings") if isinstance(schema, dict) else None
    mappings = mappings if isinstance(mappings, dict) else {}
    issues: list[dict[str, Any]] = []
    dependencies = criterion_dependencies(config, contract)
    dependency_keys = {dependency["key"] for dependency in dependencies}
    effective_dependencies = criterion_dependencies(config, contract_for_form_schema(schema, contract))
    dependencies.extend(
        dependency for dependency in effective_dependencies
        if dependency["key"] not in dependency_keys
    )
    for dependency in dependencies:
        mapped_key = str(mappings.get(dependency["key"]) or dependency["key"])
        field = fields.get(mapped_key)
        dependency["mapped_field_key"] = mapped_key
        dependency["enabled"] = True
        if dependency.get("source") != "contributor":
            continue
        if not dependency.get("required_in_schema"):
            continue
        blocking = bool(dependency.get("required_for_input"))
        severity = "potential_issue"
        if field is None:
            issues.append(_issue(
                severity, dependency,
                f"{dependency['label']} has no available form answer ({mapped_key}).",
                "Choose another form field for this scoring fact, or accept an incomplete criterion until it is supplied.",
            ))
            continue
        if field.get("visible") is False or not field.get("_section_visible"):
            issues.append(_issue(
                severity, dependency,
                f"{dependency['label']} is hidden but is used by scoring.",
                "Keep the field and its section active, or remove the dependent scoring use after review.",
            ))
            continue
        if blocking and (isinstance(field.get("condition"), dict) or isinstance(field.get("condition_group"), dict)):
            issues.append(_issue(
                "potential_issue", dependency,
                f"{dependency['label']} is conditionally hidden, so scoring cannot rely on it for every eligible project.",
                "Review the affected criteria; analyses without this answer will identify the evidence gap.",
            ))
            continue
        expected = set(dependency.get("expected_types") or [])
        if expected and str(field.get("type") or "") not in expected:
            issues.append(_issue(
                severity, dependency,
                f"{dependency['label']} has type '{field.get('type')}', but scoring expects {', '.join(sorted(expected))}.",
                "Restore a compatible field type before publishing.",
            ))
            continue
        if blocking and str(field.get("type") or "") in {"select", "multiselect", "multiselect_dropdown"}:
            option_values = {
                str(option.get("value") or "").strip()
                for option in field.get("options", [])
                if isinstance(option, dict) and str(option.get("value") or "").strip()
            }
            if not option_values:
                issues.append(_issue(
                    "potential_issue", dependency,
                    f"{dependency['label']} has no valid selectable values.",
                    "Restore at least one valid option before publishing the form.",
                ))
    status = "potential_issue" if issues else "compatible"
    baseline_fields = _schema_fields(baseline_schema) if isinstance(baseline_schema, dict) else {}
    added = sorted(set(fields) - set(baseline_fields))
    retired = sorted(
        key for key in set(baseline_fields) - set(fields)
        if baseline_fields[key].get("visible") is not False
    )
    modified = []
    review_keys = ("type", "options", "required", "visible", "condition", "condition_group")
    for key in sorted(set(fields) & set(baseline_fields)):
        changes = [name for name in review_keys if fields[key].get(name) != baseline_fields[key].get(name)]
        if changes:
            modified.append({"field_key": key, "field_label": fields[key].get("label") or key, "changes": changes})
    baseline_sections = {str(section.get("key")): section for section in (baseline_schema or {}).get("sections", []) if isinstance(section, dict)}
    current_sections = {str(section.get("key")): section for section in (schema or {}).get("sections", []) if isinstance(section, dict)}
    hidden = sorted(key for key, field in fields.items() if field.get("visible") is False and baseline_fields.get(key, {}).get("visible") is not False)
    return {
        "status": status,
        "status_label": {
            "compatible": "Compatible",
            "potential_issue": "Potential issue",
            "incompatible": "Incompatible",
        }[status],
        "issues": issues,
        "dependencies": dependencies,
        "impact": {
            "structurally_valid": status != "incompatible",
            "added_fields": added,
            "retired_fields": retired,
            "hidden_fields": hidden,
            "added_sections": sorted(set(current_sections) - set(baseline_sections)),
            "removed_sections": sorted(set(baseline_sections) - set(current_sections)),
            "modified_fields": modified,
            "dependency_conflicts": [issue for issue in issues if issue["status"] == "incompatible"],
            "ai_review_warnings": [issue for issue in issues if issue["status"] == "potential_issue"],
        },
    }


def _value_present(value: Any, expected_types: list[str]) -> bool:
    if value is None:
        return False
    if "currency_by_year" in expected_types:
        if not isinstance(value, dict) or not value:
            return False
        for amount in value.values():
            try:
                # The contributor form formats entered PHP amounts for display
                # (for example, ``240,000,000.00``). Treat that valid stored
                # representation exactly as the priority scorer's total does,
                # instead of rejecting a completed funding requirement during
                # the input preflight.
                normalized = re.sub(r"[^0-9.-]", "", str(amount or ""))
                if not normalized:
                    continue
                Decimal(normalized)
                return True
            except (InvalidOperation, TypeError, ValueError):
                continue
        return False
    if "number" in expected_types:
        try:
            Decimal(str(value))
            return True
        except (InvalidOperation, TypeError, ValueError):
            return False
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return bool(str(value).strip())


def runtime_input_report(
    form: dict[str, Any],
    facts: dict[str, Any],
    *,
    regional_project: bool,
    economic_environment_sector: bool,
    legacy_form: bool = False,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate actual values before an AI request is made.

    This intentionally reports missing values rather than assigning a score of
    zero.  The caller decides whether to return the report or render it in a
    non-persistent preview.
    """
    missing = []
    for dependency in normalize_scoring_input_contract(contract)["dependencies"]:
        if not dependency.get("required_for_input"):
            continue
        condition = dependency.get("condition")
        if condition == "regional_project" and not regional_project:
            continue
        if condition == "economic_environment_sector" and not economic_environment_sector:
            continue
        source = dependency.get("source")
        # Historical submissions were created under older form versions. They
        # must remain analyzable with their original input shape; current-form
        # contributor requirements are enforced only for new/current forms.
        # Validator facts remain required because the scorer cannot infer them
        # safely from historical narrative text.
        if legacy_form and source == "contributor":
            continue
        key = dependency["key"]
        if source == "contributor":
            # File metadata is not stored in profile_data.  The scorer adds a
            # verified boolean from the project's active document records.
            if key == "custom_supporting_documents":
                value = facts.get("_supporting_documents_ready")
            else:
                value = form.get(key)
        elif source == "validator":
            value = facts.get(key.rsplit(".", 1)[-1])
        else:
            value = facts.get(key)
        if not _value_present(value, dependency.get("expected_types") or []):
            missing.append({
                "field_key": key,
                "field_label": dependency["label"],
                "source": source,
                "criteria": dependency.get("criteria", []),
                "message": f"{dependency['label']} is required before this scoring configuration can evaluate the project.",
            })
    return {
        "status": "incomplete" if missing else "compatible",
        "missing": missing,
        "can_evaluate": not missing,
    }
