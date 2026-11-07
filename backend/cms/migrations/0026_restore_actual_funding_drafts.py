from copy import deepcopy

from django.db import migrations


ACTUAL_FUNDING_FIELD = {
    "key": "actualFundingByYear",
    "label": "Actual/Approved Funding (PHP)",
    "type": "currency_by_year",
    "required": False,
    "visible": True,
    "help_text": "",
    "placeholder": "",
}


def restore_actual_funding_to_drafts(apps, schema_editor):
    Form = apps.get_model("cms", "CMSContributorForm")
    for form in Form.objects.all().iterator():
        schema = deepcopy(form.draft_schema_json or {})
        if not isinstance(schema, dict) or not isinstance(schema.get("sections"), list):
            continue
        if any(
            field.get("key") == "actualFundingByYear"
            for section in schema["sections"] if isinstance(section, dict)
            for field in section.get("fields", []) if isinstance(field, dict)
        ):
            continue
        section = next((
            section for section in schema["sections"]
            if isinstance(section, dict) and section.get("key") == "implementation_and_funding"
            and isinstance(section.get("fields"), list)
        ), None)
        if section is None:
            continue
        fields = section["fields"]
        position = next((
            index + 1 for index, field in enumerate(fields)
            if isinstance(field, dict) and field.get("key") == "fundingRequirementByYear"
        ), len(fields))
        fields.insert(position, deepcopy(ACTUAL_FUNDING_FIELD))
        form.draft_schema_json = schema
        form.has_unpublished_changes = True
        form.status = "draft"
        form.save(update_fields=["draft_schema_json", "has_unpublished_changes", "status"])


class Migration(migrations.Migration):
    dependencies = [("cms", "0025_contributor_form_core_sections")]
    operations = [migrations.RunPython(restore_actual_funding_to_drafts, migrations.RunPython.noop)]
