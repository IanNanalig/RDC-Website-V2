from copy import deepcopy

from django.db import migrations


def move_validator_facts_out_of_drafts(apps, schema_editor):
    Form = apps.get_model("cms", "CMSContributorForm")
    for form in Form.objects.all().iterator():
        schema = deepcopy(form.draft_schema_json or {})
        if not isinstance(schema, dict) or not isinstance(schema.get("sections"), list):
            continue
        if schema.get("format_version") == 3 and not any(
            isinstance(section, dict) and section.get("admin_only") for section in schema["sections"]
        ):
            continue
        internal = next((
            section.get("fields") for section in schema["sections"]
            if isinstance(section, dict) and section.get("key") == "priority_analysis"
            and section.get("admin_only") is True
        ), None)
        schema["sections"] = [
            section for section in schema["sections"]
            if not (isinstance(section, dict) and section.get("admin_only") is True)
        ]
        if "validator_fact_fields" not in schema and isinstance(internal, list):
            schema["validator_fact_fields"] = internal
        schema["format_version"] = 3
        form.draft_schema_json = schema
        form.save(update_fields=["draft_schema_json"])


def restore_validator_facts_to_legacy_drafts(apps, schema_editor):
    Form = apps.get_model("cms", "CMSContributorForm")
    for form in Form.objects.all().iterator():
        schema = deepcopy(form.draft_schema_json or {})
        if not isinstance(schema, dict) or not isinstance(schema.get("sections"), list):
            continue
        facts = schema.pop("validator_fact_fields", None)
        if isinstance(facts, list) and not any(
            isinstance(section, dict) and section.get("key") == "priority_analysis"
            for section in schema["sections"]
        ):
            schema["sections"].append({
                "key": "priority_analysis", "title": "Validator Facts",
                "description": "System-managed validator scoring inputs.",
                "visible": False, "admin_only": True, "fields": facts,
            })
        schema["format_version"] = 2
        form.draft_schema_json = schema
        form.save(update_fields=["draft_schema_json"])


class Migration(migrations.Migration):
    dependencies = [("cms", "0024_generic_form_conditions")]
    operations = [migrations.RunPython(move_validator_facts_out_of_drafts, restore_validator_facts_to_legacy_drafts)]
