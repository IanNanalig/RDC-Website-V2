from copy import deepcopy

from django.db import migrations


LEGEND_ITEMS = [
    {"label": "RDC Resolution", "color": "blue"},
    {"label": "Advisory/Referendum", "color": "amber"},
    {"label": "MMDA Resolution", "color": "purple"},
    {"label": "Sectoral Committee", "color": "emerald"},
]

CATEGORY_ITEMS = [
    {"title": "Budget", "description": "Budget Endorsements", "color": "blue"},
    {"title": "Infrastructure", "description": "Project Endorsements", "color": "green"},
    {"title": "Policy", "description": "Policy Approvals", "color": "purple"},
    {"title": "Administrative", "description": "Committee Creations", "color": "amber"},
]


def add_resolution_display_content(apps, schema_editor):
    Page = apps.get_model("cms", "CMSPage")
    page = Page.objects.filter(slug="about-rdc").first()
    if not page:
        return

    section = page.sections.filter(section_key="resolutions-archive").first()
    if section and isinstance(section.content_json, dict):
        content = deepcopy(section.content_json)
        changed = False
        if "legendItems" not in content:
            content["legendItems"] = deepcopy(LEGEND_ITEMS)
            changed = True
        if "categoryItems" not in content:
            content["categoryItems"] = deepcopy(CATEGORY_ITEMS)
            changed = True
        if changed:
            section.content_json = content
            section.save(update_fields=["content_json", "updated_at"])

    snapshot = deepcopy(page.published_snapshot_json or {})
    changed = False
    for row in snapshot.get("sections") or []:
        if not isinstance(row, dict) or row.get("sectionKey") != "resolutions-archive":
            continue
        content = row.get("content")
        if not isinstance(content, dict):
            continue
        if "legendItems" not in content:
            content["legendItems"] = deepcopy(LEGEND_ITEMS)
            changed = True
        if "categoryItems" not in content:
            content["categoryItems"] = deepcopy(CATEGORY_ITEMS)
            changed = True
    if changed:
        page.published_snapshot_json = snapshot
        page.save(update_fields=["published_snapshot_json"])


class Migration(migrations.Migration):
    dependencies = [("cms", "0018_repair_collection_stable_identities")]
    operations = [migrations.RunPython(add_resolution_display_content, migrations.RunPython.noop)]
