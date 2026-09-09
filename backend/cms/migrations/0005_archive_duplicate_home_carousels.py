from django.db import migrations
from django.db.models import Max


def archive_duplicate_home_carousels(apps, schema_editor):
    CMSPage = apps.get_model("cms", "CMSPage")
    CMSPageSection = apps.get_model("cms", "CMSPageSection")

    page = CMSPage.objects.filter(slug="home").first()
    if page is None:
        return

    canonical = CMSPageSection.objects.filter(
        page=page,
        section_key="hero-carousel",
        section_type="hero_carousel",
    ).first()
    if canonical is None:
        return

    duplicates = list(
        CMSPageSection.objects.filter(page=page, section_type="hero_carousel")
        .exclude(pk=canonical.pk)
        .order_by("order", "id")
    )
    if not duplicates:
        return

    next_order = (
        CMSPageSection.objects.filter(page=page).aggregate(max_order=Max("order"))["max_order"] or 0
    ) + 1
    duplicate_keys = set()
    for offset, section in enumerate(duplicates):
        duplicate_keys.add(section.section_key)
        section.status = "archived"
        section.is_visible = False
        section.order = next_order + offset
        section.lock_owner_id = None
        section.lock_acquired_at = None
        section.save(
            update_fields=[
                "status",
                "is_visible",
                "order",
                "lock_owner",
                "lock_acquired_at",
                "updated_at",
            ]
        )

    snapshot = page.published_snapshot_json if isinstance(page.published_snapshot_json, dict) else {}
    sections = snapshot.get("sections")
    if isinstance(sections, list):
        snapshot = dict(snapshot)
        snapshot["sections"] = [
            section
            for section in sections
            if not (
                isinstance(section, dict)
                and section.get("sectionKey") in duplicate_keys
                and section.get("sectionType") == "hero_carousel"
            )
        ]
        page.published_snapshot_json = snapshot
        page.save(update_fields=["published_snapshot_json", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0004_cmsarticle_publication_date"),
    ]

    operations = [
        migrations.RunPython(archive_duplicate_home_carousels, migrations.RunPython.noop),
    ]
