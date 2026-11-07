from copy import deepcopy

from django.test import SimpleTestCase

from cms.form_schema import (
    DOCUMENT_UPLOAD_MAX_BYTES,
    FormSchemaError,
    PROTECTED_SECTION_KEYS,
    PROTECTED_WORKFLOW_FIELD_KEYS,
    default_simplified_form_schema,
    validate_draft_schema,
    validate_form_schema,
)
from projects.scoring_contract import apply_scoring_mappings, form_compatibility_report


def minimal_form():
    schema = default_simplified_form_schema()
    schema["sections"] = [
        {**section, "fields": [field for field in section["fields"] if field["key"] in PROTECTED_WORKFLOW_FIELD_KEYS]}
        for section in schema["sections"] if section["key"] in PROTECTED_SECTION_KEYS
    ]
    return schema


class ContributorFormRefactorTests(SimpleTestCase):
    def test_three_core_sections_can_publish_without_removed_optional_fields(self):
        schema = minimal_form()
        self.assertEqual(len(schema["sections"]), 3)
        funding_keys = [field["key"] for field in schema["sections"][1]["fields"]]
        self.assertEqual(funding_keys, ["startYear", "endYear", "fundingRequirementByYear", "actualFundingByYear"])
        self.assertEqual(validate_form_schema(schema), schema)
        self.assertNotIn("priority_analysis", [section["key"] for section in schema["sections"]])
        self.assertTrue(schema["validator_fact_fields"])

    def test_incomplete_draft_can_save_but_cannot_publish(self):
        schema = minimal_form()
        schema["sections"][0]["fields"].clear()
        self.assertEqual(validate_draft_schema(schema), schema)
        with self.assertRaises(FormSchemaError):
            validate_form_schema(schema)

    def test_removed_mapped_answer_is_warning_not_publication_blocker(self):
        schema = minimal_form()
        schema["scoring_mappings"] = {"description": "custom_summary"}
        validate_form_schema(schema)
        report = form_compatibility_report(schema)
        self.assertEqual(report["status"], "potential_issue")
        self.assertIn("description", [issue["field_key"] for issue in report["issues"]])

    def test_mapping_to_new_stable_field_resolves_removed_fact_warning(self):
        schema = default_simplified_form_schema()
        schema["sections"][0]["fields"] = [
            field for field in schema["sections"][0]["fields"] if field["key"] != "description"
        ]
        schema["sections"][0]["fields"].append({
            "key": "custom_summary", "label": "Project Summary", "type": "textarea",
            "visible": True, "required": False,
        })
        schema["scoring_mappings"] = {"description": "custom_summary"}
        validate_form_schema(schema)
        report = form_compatibility_report(schema)
        self.assertFalse(any(issue["field_key"] == "description" for issue in report["issues"]))

    def test_mapping_supplies_canonical_fact_only_when_answer_is_applicable(self):
        schema = minimal_form()
        schema["scoring_mappings"] = {"description": "custom_summary"}
        original = {"custom_fields": {"custom_summary": "A health facility"}}
        mapped = apply_scoring_mappings(original, schema, {"custom_summary"})
        self.assertEqual(mapped["description"], "A health facility")
        self.assertNotIn("description", original)
        hidden = apply_scoring_mappings(original, schema, set())
        self.assertNotIn("description", hidden)

    def test_visible_and_hidden_are_distinct_from_removed(self):
        baseline = default_simplified_form_schema()
        schema = deepcopy(baseline)
        schema["sections"][0]["fields"] = [field for field in schema["sections"][0]["fields"] if field["key"] != "program"]
        next(field for field in schema["sections"][0]["fields"] if field["key"] == "description")["visible"] = False
        validate_form_schema(schema)
        impact = form_compatibility_report(schema, baseline_schema=baseline)["impact"]
        self.assertIn("program", impact["retired_fields"])
        self.assertIn("description", impact["hidden_fields"])

    def test_document_ceiling_is_fifty_mib(self):
        self.assertEqual(DOCUMENT_UPLOAD_MAX_BYTES, 50 * 1024 * 1024)
        schema = minimal_form()
        document = schema["sections"][2]["fields"][0]
        for size in (10, 20, 25, 50):
            document["max_file_bytes"] = size * 1024 * 1024
            validate_form_schema(schema)
        document["max_file_bytes"] = 51 * 1024 * 1024
        with self.assertRaises(FormSchemaError):
            validate_form_schema(schema)
