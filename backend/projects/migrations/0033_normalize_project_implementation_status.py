from copy import deepcopy

from django.db import migrations
from django.db.models import Q


LEGACY_STATUS_MAP = {
    "discontinued": "Not Implemented",
    "dropped": "Not Implemented",
    "updated": "Ongoing",
}


def normalize_project_statuses(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    database = schema_editor.connection.alias
    legacy_filter = Q()
    for legacy_status in LEGACY_STATUS_MAP:
        legacy_filter |= Q(profile_data__simplified_form__status__iexact=legacy_status)
    projects = Project.objects.using(database).filter(
        legacy_filter,
    ).only("id", "profile_data")
    for project in projects.iterator(chunk_size=200):
        profile = deepcopy(project.profile_data)
        if not isinstance(profile, dict):
            continue
        simplified = profile.get("simplified_form")
        if not isinstance(simplified, dict):
            continue
        normalized = LEGACY_STATUS_MAP.get(str(simplified.get("status") or "").strip().casefold())
        if normalized is None:
            continue
        original = str(simplified.get("status") or "").strip()
        simplified["status"] = normalized
        summary = profile.get("public_summary")
        if isinstance(summary, dict):
            facts = summary.get("key_facts")
            if isinstance(facts, dict) and str(facts.get("status") or "").strip().casefold() == original.casefold():
                facts["status"] = normalized
            bullets = summary.get("bullets")
            if isinstance(bullets, list):
                summary["bullets"] = [
                    f"Status: {normalized}" if str(bullet).strip().casefold() == f"status: {original}".casefold() else bullet
                    for bullet in bullets
                ]
            text = summary.get("text")
            if isinstance(text, str):
                summary["text"] = text.replace(f"Status: {original}.", f"Status: {normalized}.")
        Project.objects.using(database).filter(pk=project.pk).update(profile_data=profile)


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0032_alter_useractivity_event"),
    ]

    operations = [
        migrations.RunPython(normalize_project_statuses, migrations.RunPython.noop),
    ]
