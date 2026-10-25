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


def _field(schema, key):
    return next(
        (
            field
            for section in schema.get("sections", [])
            if isinstance(section, dict)
            for field in section.get("fields", [])
            if isinstance(field, dict) and field.get("key") == key
        ),
        None,
    )


def _restore_text_location(schema):
    repaired = deepcopy(schema) if isinstance(schema, dict) else {}
    location = _field(repaired, "location")
    if location is None:
        return repaired
    location["type"] = "text"
    location["help_text"] = ""
    location.pop("options", None)
    return repaired


def repair_legacy_location_versions(apps, schema_editor):
    """Repair fresh databases seeded from the mutable Python form default.

    Migration 0006 historically imported the live default form schema. Once
    Location became a multi-select, a fresh database therefore mislabeled its
    legacy versions as multi-select versions. Existing projects pinned to
    version 1 still contain free-text values such as ``NCR`` and then fail
    validation. Only the recognizable contaminated seed sequence is repaired;
    databases whose version 1 already has the historical text field are left
    unchanged.
    """

    Form = apps.get_model("cms", "CMSContributorForm")
    Version = apps.get_model("cms", "CMSContributorFormVersion")
    alias = schema_editor.connection.alias
    form = Form.objects.using(alias).filter(key="simplified-rdip").first()
    if not form:
        return

    version_one = (
        Version.objects.using(alias)
        .filter(form_id=form.pk, version_number=1)
        .first()
    )
    version_one_location = _field(version_one.schema_json, "location") if version_one else None
    if not version_one_location or version_one_location.get("type") not in {
        "multiselect",
        "multiselect_dropdown",
    }:
        return

    repaired_one = _restore_text_location(version_one.schema_json)
    Version.objects.using(alias).filter(pk=version_one.pk).update(schema_json=repaired_one)

    # Migration 0010 creates the first supporting-document version. On an
    # affected fresh database it inherited the same premature Location type,
    # so restore that one historical version as well.
    supporting_version = None
    for candidate in (
        Version.objects.using(alias)
        .filter(form_id=form.pk, version_number__gt=1)
        .order_by("version_number")
    ):
        if _field(candidate.schema_json, "custom_supporting_documents") is not None:
            supporting_version = candidate
            break

    if supporting_version is not None:
        repaired_supporting = _restore_text_location(supporting_version.schema_json)
        Version.objects.using(alias).filter(pk=supporting_version.pk).update(
            schema_json=repaired_supporting
        )

    current = (
        Version.objects.using(alias)
        .filter(pk=form.current_published_version_id)
        .first()
    )
    if current is None:
        return

    # Only replace the current version when it is one of the contaminated seed
    # versions. Later Administrator-published versions remain immutable.
    contaminated_current_ids = {version_one.pk}
    if supporting_version is not None:
        contaminated_current_ids.add(supporting_version.pk)
    if current.pk not in contaminated_current_ids:
        return

    current_schema = _restore_text_location(current.schema_json)
    location = _field(current_schema, "location")
    if location is None:
        return
    location.update(
        {
            "type": "multiselect_dropdown",
            "required": True,
            "options": deepcopy(LOCATION_OPTIONS),
            "help_text": "Select one or more NCR locations covered by the project.",
        }
    )
    next_number = (
        Version.objects.using(alias)
        .filter(form_id=form.pk)
        .aggregate(value=Max("version_number"))["value"]
        or 0
    ) + 1
    replacement = Version.objects.using(alias).create(
        form_id=form.pk,
        version_number=next_number,
        schema_json=current_schema,
    )
    Form.objects.using(alias).filter(pk=form.pk).update(
        draft_schema_json=current_schema,
        current_published_version_id=replacement.pk,
        status="published",
        has_unpublished_changes=False,
        published_at=replacement.published_at,
    )


class Migration(migrations.Migration):
    dependencies = [("cms", "0012_location_multiselect_dropdown_type")]
    operations = [
        migrations.RunPython(
            repair_legacy_location_versions,
            migrations.RunPython.noop,
        )
    ]
