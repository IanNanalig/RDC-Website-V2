from copy import deepcopy

from django.test import TestCase

from cms.form_schema import default_simplified_form_schema, validate_form_schema
from projects.priority_scoring import default_priority_rule_config
from projects.scoring_contract import (
    contract_for_form_schema,
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

    def test_required_scoring_field_cannot_be_hidden(self):
        schema = deepcopy(default_simplified_form_schema())
        next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "description"
        )["visible"] = False

        report = self.report(schema)

        self.assertEqual(report["status"], "incompatible")
        self.assertTrue(any(issue["field_key"] == "description" for issue in report["issues"]))

    def test_required_scoring_field_type_must_remain_compatible(self):
        schema = deepcopy(default_simplified_form_schema())
        next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "fundingRequirementByYear"
        )["type"] = "text"

        report = self.report(schema)

        self.assertEqual(report["status"], "incompatible")
        self.assertTrue(any(issue["field_key"] == "fundingRequirementByYear" for issue in report["issues"]))

    def test_validator_only_inputs_do_not_require_contributor_answers(self):
        schema = deepcopy(default_simplified_form_schema())
        report = self.report(schema)

        self.assertEqual(report["status"], "compatible")

    def test_required_scoring_select_needs_valid_options(self):
        schema = deepcopy(default_simplified_form_schema())
        next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "developmentSector"
        )["options"] = []

        report = self.report(schema)

        self.assertEqual(report["status"], "incompatible")
        self.assertTrue(any(issue["field_key"] == "developmentSector" for issue in report["issues"]))

    def test_optional_ai_input_can_be_disabled_and_is_removed_from_contract(self):
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
        self.assertFalse(dependency["enabled"])
        self.assertNotIn(field["key"], {item["key"] for item in effective["dependencies"]})

    def test_admin_can_disable_default_required_ai_input_with_warning(self):
        schema = deepcopy(default_simplified_form_schema())
        field = next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "description"
        )
        field["ai_scoring_enabled"] = False

        report = self.report(schema)
        effective = contract_for_form_schema(schema, default_scoring_input_contract())

        self.assertEqual(report["status"], "potential_issue")
        self.assertTrue(any(
            issue["field_key"] == "description" and "excluded" in issue["message"]
            for issue in report["issues"]
        ))
        self.assertNotIn("description", {item["key"] for item in effective["dependencies"]})

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
            "agencyName", "collaboratingAgencies", "program", "projectActivity",
            "location", "description", "objective",
        }
        for section in schema["sections"]:
            if section.get("admin_only"):
                continue
            keep_section = section["key"] == "project_information"
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
