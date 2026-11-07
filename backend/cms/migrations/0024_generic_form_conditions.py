from copy import deepcopy

from django.db import migrations


def _group(condition):
    if not isinstance(condition, dict) or not condition.get("field"):
        return None
    for operator in ("equals", "not_equals", "one_of", "not_one_of"):
        if operator not in condition:
            continue
        rule = {"field": str(condition["field"]), "operator": operator}
        if operator in {"one_of", "not_one_of"}:
            rule["values"] = list(condition.get(operator) or [])
        else:
            rule["value"] = condition.get(operator)
        return {"match": "all", "conditions": [rule]}
    return None


def upgrade_active_drafts(apps, schema_editor):
    Form = apps.get_model("cms", "CMSContributorForm")
    for form in Form.objects.all().iterator():
        schema = deepcopy(form.draft_schema_json or {})
        changed = schema.get("format_version") != 2
        schema["format_version"] = 2
        for section in schema.get("sections", []):
            if not isinstance(section, dict):
                continue
            for field in section.get("fields", []):
                if not isinstance(field, dict):
                    continue
                if "ai_scoring_enabled" in field:
                    field.pop("ai_scoring_enabled", None)
                    changed = True
                if not isinstance(field.get("condition_group"), dict):
                    group = _group(field.get("condition"))
                    if group:
                        field["condition_group"] = group
                        changed = True
                if field.pop("condition_required", False):
                    field["required"] = True
                    changed = True
                if "condition" in field:
                    field.pop("condition", None)
                    changed = True
        if changed:
            form.draft_schema_json = schema
            form.has_unpublished_changes = True
            form.save(update_fields=["draft_schema_json", "has_unpublished_changes", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("cms", "0023_publication_document_covers_and_ordering")]
    operations = [migrations.RunPython(upgrade_active_drafts, migrations.RunPython.noop)]
