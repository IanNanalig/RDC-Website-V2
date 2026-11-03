from copy import deepcopy

from django.test import TestCase

from cms.form_schema import default_simplified_form_schema
from projects.priority_scoring import default_priority_rule_config
from projects.scoring_contract import (
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
