from copy import deepcopy

from django.test import TestCase

from ai_engine.groq_priority import _project_payload
from cms.form_schema import default_simplified_form_schema, validate_form_schema
from cms.models import CMSContributorFormVersion
from projects.priority_scoring import default_priority_rule_config
from projects.scoring_contract import (
    contract_for_form_schema,
    contract_for_project_snapshot,
    default_scoring_input_contract,
    form_compatibility_report,
    runtime_input_report,
)


class FormAIScoringCompatibilityTests(TestCase):
    def report(self, schema):
        return form_compatibility_report(
            schema,
            default_priority_rule_config(),
            default_scoring_input_contract(),
        )

    def test_label_and_order_changes_are_compatible(self):
        schema = default_simplified_form_schema()
        fields = schema["sections"][0]["fields"]
        fields[0], fields[1] = fields[1], fields[0]
        next(field for field in fields if field["key"] == "description")["label"] = "Project Overview"

        report = self.report(schema)

        self.assertEqual(report["status"], "compatible")

    def test_hidden_scoring_information_is_a_review_warning(self):
        schema = deepcopy(default_simplified_form_schema())
        next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "description"
        )["visible"] = False

        report = self.report(schema)

        self.assertEqual(report["status"], "potential_issue")
        self.assertTrue(any(issue["field_key"] == "description" for issue in report["issues"]))

    def test_changed_scoring_information_type_is_a_review_warning(self):
        schema = deepcopy(default_simplified_form_schema())
        next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "fundingRequirementByYear"
        )["type"] = "text"

        report = self.report(schema)

        self.assertEqual(report["status"], "potential_issue")
        self.assertTrue(any(issue["field_key"] == "fundingRequirementByYear" for issue in report["issues"]))

    def test_validator_only_inputs_do_not_require_contributor_answers(self):
        schema = deepcopy(default_simplified_form_schema())
        report = self.report(schema)

        self.assertEqual(report["status"], "compatible")

    def test_scoring_select_without_options_is_a_review_warning(self):
        schema = deepcopy(default_simplified_form_schema())
        next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "developmentSector"
        )["options"] = []

        report = self.report(schema)

        self.assertEqual(report["status"], "potential_issue")
        self.assertTrue(any(issue["field_key"] == "developmentSector" for issue in report["issues"]))

    def test_legacy_ai_toggle_is_ignored_and_field_remains_available(self):
        schema = deepcopy(default_simplified_form_schema())
        field = next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "physicalAccomplishment"
        )
        field["ai_scoring_enabled"] = False

        report = self.report(schema)
        dependency = next(item for item in report["dependencies"] if item["key"] == field["key"])
        effective = contract_for_form_schema(schema, default_scoring_input_contract())

        self.assertEqual(report["status"], "compatible")
        self.assertTrue(dependency["enabled"])
        self.assertIn(field["key"], {item["key"] for item in effective["dependencies"]})

    def test_legacy_ai_toggle_cannot_disable_canonical_system_fact(self):
        schema = deepcopy(default_simplified_form_schema())
        field = next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "description"
        )
        field["ai_scoring_enabled"] = False

        report = self.report(schema)
        effective = contract_for_form_schema(schema, default_scoring_input_contract())

        self.assertEqual(report["status"], "compatible")
        self.assertIn("description", {item["key"] for item in effective["dependencies"]})

    def test_admin_can_enable_custom_field_as_general_ai_context(self):
        schema = deepcopy(default_simplified_form_schema())
        schema["sections"][0]["fields"].append({
            "key": "custom_local_context",
            "label": "Local Context",
            "type": "textarea",
            "visible": True,
            "required": False,
            "ai_scoring_enabled": True,
        })

        report = self.report(schema)
        dependency = next(item for item in report["dependencies"] if item["key"] == "custom_local_context")
        effective = contract_for_form_schema(schema, default_scoring_input_contract())

        self.assertTrue(dependency["enabled"])
        self.assertEqual(dependency["criterion_categories"], ["outcome_rules"])
        self.assertIn("custom_local_context", {item["key"] for item in effective["dependencies"]})

    def test_clean_slate_draft_keeps_project_information_and_retires_other_inputs(self):
        schema = deepcopy(default_simplified_form_schema())
        schema["reset_from_scratch"] = True
        preserved = {
            "agencyName", "projectActivity", "custom_supporting_documents",
        }
        for section in schema["sections"]:
            if section.get("admin_only"):
                continue
            keep_section = any(field["key"] in preserved for field in section["fields"])
            section["visible"] = keep_section
            for field in section["fields"]:
                if keep_section and field["key"] in preserved:
                    continue
                field.update({
                    "visible": False,
                    "required": False,
                    "condition_required": False,
                    "ai_scoring_enabled": False,
                })

        validated = validate_form_schema(schema, published_schema=default_simplified_form_schema())
        report = self.report(validated)

        self.assertTrue(validated["reset_from_scratch"])
        self.assertNotEqual(report["status"], "incompatible")

    def test_project_snapshot_uses_top_level_immutable_form_version_marker(self):
        version = CMSContributorFormVersion.objects.select_related("form").first()
        schema = deepcopy(version.schema_json)
        development_sector = next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "developmentSector"
        )
        development_sector["visible"] = False
        development_sector["required"] = False
        development_sector["ai_scoring_enabled"] = False
        version.schema_json = schema
        version.save(update_fields=["schema_json"])

        effective = contract_for_project_snapshot({
            "form_schema": {"key": version.form.key, "version": version.version_number},
            "simplified_form": {"projectActivity": "Versioned sample"},
        })

        self.assertIn("developmentSector", {item["key"] for item in effective["dependencies"]})

    def test_legacy_submission_keeps_current_contributor_requirements_compatible(self):
        report = runtime_input_report(
            {
                "projectActivity": "Legacy drainage project",
                "description": "Existing historic project description.",
                "fundingRequirementByYear": {"2026": 100},
            },
            {
                "_supporting_documents_ready": True,
                "readinessLevel": "completed_documents",
                "gadResponsiveness": "gender_responsive",
                "spatialCoverageScope": "region_wide",
            },
            regional_project=False,
            economic_environment_sector=False,
            legacy_form=True,
        )

        self.assertTrue(report["can_evaluate"])

    def test_groq_payload_automatically_labels_all_applicable_versioned_fields(self):
        version = CMSContributorFormVersion.objects.select_related("form").first()
        schema = deepcopy(version.schema_json)
        schema["sections"][0]["fields"].extend([
            {"key": "custom_public_benefit", "label": "Public Benefit", "help_text": "State the measurable benefit.", "type": "text", "visible": True, "required": False},
            {"key": "custom_completed_note", "label": "Completion Note", "type": "text", "visible": True, "required": False,
             "condition_group": {"match": "all", "conditions": [{"field": "status", "operator": "equals", "value": "Completed"}]}},
        ])
        version.schema_json = schema
        version.save(update_fields=["schema_json"])
        payload = _project_payload({
            "form_schema": {"key": version.form.key, "version": version.version_number},
            "simplified_form": {
                "status": "New",
                "custom_fields": {"custom_public_benefit": "Serves 20,000 residents", "custom_completed_note": "stale"},
            },
        })
        fields = {item["key"]: item for item in payload["form_fields"]}
        self.assertEqual(fields["custom_public_benefit"]["answer"], "Serves 20,000 residents")
        self.assertEqual(fields["custom_public_benefit"]["answer_state"], "answered")
        self.assertEqual(fields["custom_completed_note"]["applicability"], "hidden_by_condition")
        self.assertIsNone(fields["custom_completed_note"]["answer"])
