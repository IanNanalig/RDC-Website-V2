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
    def test_five_core_sections_can_publish_without_removed_optional_fields(self):
        schema = minimal_form()
        self.assertEqual(len(schema["sections"]), 5)
        funding_keys = [field["key"] for field in schema["sections"][1]["fields"]]
        self.assertEqual(funding_keys, ["startYear", "endYear", "fundingRequirementByYear", "actualFundingByYear"])
        self.assertEqual(validate_form_schema(schema), schema)
        self.assertNotIn("priority_analysis", [section["key"] for section in schema["sections"]])
        self.assertTrue(schema["validator_fact_fields"])

    def test_draft_cannot_remove_required_workflow_fields(self):
        schema = minimal_form()
        schema["sections"][0]["fields"].clear()
        with self.assertRaises(FormSchemaError):
            validate_draft_schema(schema)
        with self.assertRaises(FormSchemaError):
            validate_form_schema(schema)

    def test_removed_mapped_answer_is_warning_not_publication_blocker(self):
        schema = minimal_form()
        schema["scoring_mappings"] = {"rdpMainChapter": "custom_chapter"}
        validate_form_schema(schema)
        report = form_compatibility_report(schema)
        self.assertEqual(report["status"], "potential_issue")
        self.assertIn("rdpMainChapter", [issue["field_key"] for issue in report["issues"]])

    def test_mapping_to_new_stable_field_resolves_removed_fact_warning(self):
        schema = default_simplified_form_schema()
        fields = next(section["fields"] for section in schema["sections"] if section["key"] == "classification")
        chapter = next(field for field in fields if field["key"] == "rdpMainChapter")
        fields.remove(chapter)
        fields.append({**chapter, "key": "custom_chapter", "label": "Project Chapter", "required": False})
        schema["scoring_mappings"] = {"rdpMainChapter": "custom_chapter"}
        validate_form_schema(schema)
        report = form_compatibility_report(schema)
        self.assertFalse(any(issue["field_key"] == "rdpMainChapter" for issue in report["issues"]))

    def test_legacy_mapping_supplies_canonical_fact_only_when_answer_is_applicable(self):
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
        classification = next(section for section in schema["sections"] if section["key"] == "classification")
        classification["fields"] = [field for field in classification["fields"] if field["key"] != "sdgSelections"]
        next(field for field in classification["fields"] if field["key"] == "rdcEndorsed")["visible"] = False
        validate_form_schema(schema)
        impact = form_compatibility_report(schema, baseline_schema=baseline)["impact"]
        self.assertIn("sdgSelections", impact["retired_fields"])
        self.assertIn("rdcEndorsed", impact["hidden_fields"])

    def test_description_has_the_same_protection_as_objective(self):
        schema = default_simplified_form_schema()
        fields = schema["sections"][0]["fields"]
        description = next(field for field in fields if field["key"] == "description")
        description.update(label="Project overview", help_text="Describe the work", placeholder="Project scope")
        fields.remove(description)
        fields.insert(0, description)
        validate_form_schema(schema)

        for change in (
            {"visible": False}, {"required": False}, {"type": "text"},
            {"condition_group": {"match": "all", "conditions": [{"field": "program", "operator": "is_empty"}]}},
        ):
            with self.subTest(change=change):
                invalid = deepcopy(schema)
                invalid["sections"][0]["fields"][0].update(change)
                with self.assertRaises(FormSchemaError):
                    validate_draft_schema(invalid)
                with self.assertRaises(FormSchemaError):
                    validate_form_schema(invalid)
        without_description = deepcopy(schema)
        without_description["sections"][0]["fields"].pop(0)
        with self.assertRaisesRegex(FormSchemaError, "Description"):
            validate_draft_schema(without_description)
        schema["scoring_mappings"] = {"description": "custom_other"}
        with self.assertRaisesRegex(FormSchemaError, "cannot be remapped"):
            validate_form_schema(schema)

    def test_document_ceiling_is_fifty_mib(self):
        self.assertEqual(DOCUMENT_UPLOAD_MAX_BYTES, 50 * 1024 * 1024)
        schema = minimal_form()
        document = next(section for section in schema["sections"] if section["key"] == "supporting_documents")["fields"][0]
        for size in (10, 20, 25, 50):
            document["max_file_bytes"] = size * 1024 * 1024
            validate_form_schema(schema)
        document["max_file_bytes"] = 51 * 1024 * 1024
        with self.assertRaises(FormSchemaError):
            validate_form_schema(schema)
