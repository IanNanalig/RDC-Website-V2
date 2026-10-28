from copy import deepcopy

from django.db import migrations
from django.db.models import Max
from django.utils import timezone


def _add_field(schema, options):
    result = deepcopy(schema) if isinstance(schema, dict) else {}
    sections = result.get("sections") if isinstance(result.get("sections"), list) else []
    if any(
        field.get("key") == "collaboratingAgencies"
        for section in sections if isinstance(section, dict)
        for field in section.get("fields", []) if isinstance(field, dict)
    ):
        return result, False
    field = {
        "key": "collaboratingAgencies",
        "label": "Collaborating Agencies",
        "type": "multiselect_dropdown",
        "required": False,
        "visible": True,
        "help_text": "Optionally select other agencies participating in this project.",
        "placeholder": "",
        "options": options,
    }
    target = next(
        (section for section in sections if isinstance(section, dict) and section.get("key") == "project_information"),
        None,
    )
    if target is None:
        return result, False
    fields = target.get("fields") if isinstance(target.get("fields"), list) else []
    insert_at = next((index + 1 for index, item in enumerate(fields) if item.get("key") == "agencyName"), 0)
    target["fields"] = fields[:insert_at] + [field] + fields[insert_at:]
    return result, True


def publish_collaborating_agencies(apps, schema_editor):
    Agency = apps.get_model("projects", "Agency")
    Form = apps.get_model("cms", "CMSContributorForm")
    Version = apps.get_model("cms", "CMSContributorFormVersion")
    form = Form.objects.filter(key="simplified-rdip").select_related("current_published_version").first()
    if form is None:
        return
    options = [
        {"value": agency.code, "label": agency.name}
        for agency in Agency.objects.filter(is_active=True).order_by("code")
    ]
    source = form.current_published_version
    source_schema = source.schema_json if source else form.draft_schema_json
    live_schema, added = _add_field(source_schema, options)
    if not added:
        return
    version_number = (Version.objects.filter(form=form).aggregate(value=Max("version_number"))["value"] or 0) + 1
    version = Version.objects.create(
        form=form,
        version_number=version_number,
        schema_json=live_schema,
        based_on_version=source,
        migration_plan_json={
            "format": 1,
            "rules": [{"field": "collaboratingAgencies", "action": "add", "required": False}],
            "attention_fields": [],
            "incompatible_changes": [],
        },
    )
    draft_schema, _ = _add_field(form.draft_schema_json, options)
    if not form.has_unpublished_changes:
        draft_schema = deepcopy(live_schema)
    form.current_published_version = version
    form.draft_schema_json = draft_schema
    form.status = "published"
    form.published_at = timezone.now()
    form.save(update_fields=[
        "current_published_version", "draft_schema_json", "status", "published_at", "updated_at",
    ])


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0044_password_reset_challenge_and_multi_agency"),
        ("cms", "0014_contributor_form_migration_metadata"),
    ]

    operations = [
        migrations.RunPython(publish_collaborating_agencies, migrations.RunPython.noop),
    ]
