from copy import deepcopy

from django.db import migrations
from django.db.models import Max


LOCATION_OPTIONS = [
    {"value": value, "label": value}
    for value in [
        "Caloocan",
        "Las Piñas",
        "Makati",
        "Malabon",
        "Mandaluyong",
        "Manila",
        "Marikina",
        "Muntinlupa",
        "Navotas",
        "Parañaque",
        "Pasay",
        "Pasig",
        "Pateros",
        "Quezon City",
        "San Juan",
        "Taguig",
        "Valenzuela",
    ]
]


def publish_multiselect_locations(apps, schema_editor):
    Form = apps.get_model("cms", "CMSContributorForm")
    Version = apps.get_model("cms", "CMSContributorFormVersion")
    alias = schema_editor.connection.alias
    form = (
        Form.objects.using(alias)
        .filter(key="simplified-rdip")
        .first()
    )
    if not form:
        return

    source = (
        form.current_published_version.schema_json
        if form.current_published_version_id
        else form.draft_schema_json
    )
    schema = deepcopy(source) if isinstance(source, dict) else {}
    location_field = next(
        (
            field
            for section in schema.get("sections", [])
            if isinstance(section, dict)
            for field in section.get("fields", [])
            if isinstance(field, dict) and field.get("key") == "location"
        ),
        None,
    )
    if location_field is None:
        return

    desired = {
        "type": "multiselect_dropdown",
        "required": True,
        "options": deepcopy(LOCATION_OPTIONS),
        "help_text": "Select one or more NCR locations covered by the project.",
    }
    if all(location_field.get(key) == value for key, value in desired.items()):
        return
    location_field.update(desired)

    next_number = (
        Version.objects.using(alias)
        .filter(form_id=form.pk)
        .aggregate(value=Max("version_number"))["value"]
        or 0
    ) + 1
    version = Version.objects.using(alias).create(
        form_id=form.pk,
        version_number=next_number,
        schema_json=schema,
    )
    Form.objects.using(alias).filter(pk=form.pk).update(
        draft_schema_json=schema,
        current_published_version_id=version.pk,
        status="published",
        has_unpublished_changes=False,
        published_at=version.published_at,
    )


class Migration(migrations.Migration):
    dependencies = [("cms", "0010_seed_supporting_documents_form")]
    operations = [migrations.RunPython(publish_multiselect_locations, migrations.RunPython.noop)]
