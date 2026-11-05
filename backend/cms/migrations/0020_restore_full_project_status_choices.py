"""Restore the full official implementation-status set in a new form version.

Historical form versions stay immutable.  The active version receives this
small schema correction, while an editor's unpublished draft is patched in
place without discarding any of its other changes.
"""

from copy import deepcopy

from django.db import migrations
from django.db.models import Max
from django.utils import timezone


STATUS_VALUES = [
    "New", "Not Implemented", "Ongoing", "Completed", "On Hold", "Cancelled",
]
STATUS_OPTIONS = [{"value": value, "label": value} for value in STATUS_VALUES]
ACCOMPLISHMENT_CONDITION = {"field": "status", "one_of": ["Ongoing", "Completed"]}
EXPLANATION_CONDITION = {"field": "status", "one_of": ["On Hold", "Cancelled"]}


def _fields(schema):
    for section in schema.get("sections", []) if isinstance(schema, dict) else []:
        if not isinstance(section, dict):
            continue
        for field in section.get("fields", []):
            if isinstance(field, dict) and field.get("key"):
                yield field


def _patch_schema(schema):
    result = deepcopy(schema) if isinstance(schema, dict) else {}
    by_key = {str(field["key"]): field for field in _fields(result)}
    changed = False

    status = by_key.get("status")
    if status is not None and status.get("options") != STATUS_OPTIONS:
        status["options"] = deepcopy(STATUS_OPTIONS)
        changed = True

    for key in ("physicalAccomplishment", "financialAccomplishment"):
        field = by_key.get(key)
        if field is None:
            continue
        if field.get("condition") != ACCOMPLISHMENT_CONDITION:
            field["condition"] = deepcopy(ACCOMPLISHMENT_CONDITION)
            changed = True
        if field.get("condition_required") is not True:
            field["condition_required"] = True
            changed = True

    remarks = by_key.get("remarks")
    if remarks is not None:
        if remarks.get("condition") != EXPLANATION_CONDITION:
            remarks["condition"] = deepcopy(EXPLANATION_CONDITION)
            changed = True
        if remarks.get("condition_required") is not True:
            remarks["condition_required"] = True
            changed = True
        if not str(remarks.get("help_text") or "").strip():
            remarks["help_text"] = "Explain the reason for the hold or cancellation."
            changed = True

    return result, changed


def restore_full_status_choices(apps, schema_editor):
    Form = apps.get_model("cms", "CMSContributorForm")
    Version = apps.get_model("cms", "CMSContributorFormVersion")
    form = Form.objects.filter(key="simplified-rdip").select_related("current_published_version").first()
    if form is None or form.current_published_version_id is None:
        return

    live_schema, live_changed = _patch_schema(form.current_published_version.schema_json)
    draft_schema, draft_changed = _patch_schema(form.draft_schema_json)
    if not live_changed:
        if draft_changed:
            form.draft_schema_json = draft_schema
            form.save(update_fields=["draft_schema_json", "updated_at"])
        return

    previous = form.current_published_version
    next_number = (Version.objects.filter(form=form).aggregate(value=Max("version_number"))["value"] or 0) + 1
    version = Version.objects.create(
        form=form,
        version_number=next_number,
        schema_json=live_schema,
        based_on_version=previous,
        migration_plan_json={
            "format": 1,
            "rules": [
                {"field": "status", "action": "copy", "removed_option_values": []},
                {"field": "physicalAccomplishment", "action": "copy"},
                {"field": "financialAccomplishment", "action": "copy"},
                {"field": "remarks", "action": "copy"},
            ],
            "attention_fields": [],
            "incompatible_changes": [],
        },
    )
    form.current_published_version = version
    form.published_at = timezone.now()
    if not form.has_unpublished_changes:
        form.draft_schema_json = deepcopy(live_schema)
        form.status = "published"
    elif draft_changed:
        form.draft_schema_json = draft_schema
    form.save(update_fields=[
        "current_published_version", "draft_schema_json", "status", "published_at", "updated_at",
    ])


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0019_about_resolution_display_content"),
    ]

    operations = [
        migrations.RunPython(restore_full_status_choices, migrations.RunPython.noop),
    ]
