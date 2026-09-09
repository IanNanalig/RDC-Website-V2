from django.db import migrations
from django.utils import timezone


def _merge_missing(existing, defaults):
    """Add new schema keys without replacing content already edited by staff."""
    if not isinstance(existing, dict):
        existing = {}
    merged = dict(existing)
    for key, value in defaults.items():
        if key not in merged:
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_missing(merged[key], value)
    return merged


def seed_complete_public_page_registry(apps, schema_editor):
    # These modules contain data-only section definitions also used by the
    # idempotent management commands. Importing them here keeps the migration
    # and manual repair command aligned.
    from cms.management.commands.seed_about_cms import ABOUT_SECTIONS
    from cms.management.commands.seed_contact_cms import CONTACT_SECTIONS
    from cms.management.commands.seed_home_cms import HOME_SECTIONS
    from cms.management.commands.seed_news_cms import NEWS_SECTIONS
    from cms.management.commands.seed_projects_dashboard_cms import PROJECTS_DASHBOARD_SECTIONS
    from cms.management.commands.seed_publications_cms import PUBLICATIONS_SECTIONS
    from cms.management.commands.seed_region_profile_cms import REGION_PROFILE_SECTIONS

    CMSPage = apps.get_model("cms", "CMSPage")
    CMSPageSection = apps.get_model("cms", "CMSPageSection")
    now = timezone.now()
    page_definitions = [
        ("home", "Home", HOME_SECTIONS),
        ("about-rdc", "About RDC", ABOUT_SECTIONS),
        ("regional-profile", "Region Profile", REGION_PROFILE_SECTIONS),
        ("publications", "Publications", PUBLICATIONS_SECTIONS),
        ("news", "News", NEWS_SECTIONS),
        ("projects-dashboard", "Projects Dashboard", PROJECTS_DASHBOARD_SECTIONS),
        ("contact", "Contact", CONTACT_SECTIONS),
    ]

    for slug, title, section_definitions in page_definitions:
        page, page_created = CMSPage.objects.get_or_create(
            slug=slug,
            defaults={
                "title": title,
                "status": "draft",
                "has_unpublished_changes": True,
            },
        )
        publish_defaults = page_created or page.published_at is None
        page_changed = page_created

        existing_sections = list(CMSPageSection.objects.filter(page=page).order_by("order", "id"))
        for index, section in enumerate(existing_sections, start=1):
            temporary_order = 1000 + index
            if section.order != temporary_order:
                section.order = temporary_order
                section.save(update_fields=["order", "updated_at"])

        canonical_keys = []
        canonical_sections = []
        for definition in section_definitions:
            key = definition["section_key"]
            canonical_keys.append(key)
            section, section_created = CMSPageSection.objects.get_or_create(
                page=page,
                section_key=key,
                defaults={
                    "section_type": definition["section_type"],
                    "order": definition["order"],
                    "content_json": definition["content_json"],
                    "schema_version": 1,
                    "is_visible": True,
                    "status": "published" if publish_defaults else "draft",
                },
            )
            canonical_sections.append(section)

            merged_content = _merge_missing(section.content_json, definition["content_json"])
            changed_fields = []
            for field, value in (
                ("section_type", definition["section_type"]),
                ("order", definition["order"]),
                ("content_json", merged_content),
            ):
                if getattr(section, field) != value:
                    setattr(section, field, value)
                    changed_fields.append(field)
            if publish_defaults and section.status != "published":
                section.status = "published"
                changed_fields.append("status")
            if changed_fields:
                section.save(update_fields=[*changed_fields, "updated_at"])
                page_changed = True
            page_changed = page_changed or section_created

        extra_sections = CMSPageSection.objects.filter(page=page).exclude(section_key__in=canonical_keys).order_by(
            "order", "id"
        )
        next_order = len(section_definitions) + 1
        for offset, section in enumerate(extra_sections):
            desired_order = next_order + offset
            if section.order != desired_order:
                section.order = desired_order
                section.save(update_fields=["order", "updated_at"])
                page_changed = True

        if publish_defaults:
            refreshed_sections = CMSPageSection.objects.filter(
                page=page,
                section_key__in=canonical_keys,
                status="published",
                is_visible=True,
            ).order_by("order", "id")
            page.status = "published"
            page.published_at = now
            page.published_snapshot_json = {
                "title": page.title,
                "slug": page.slug,
                "publishedAt": now.isoformat(),
                "sections": [
                    {
                        "sectionKey": section.section_key,
                        "sectionType": section.section_type,
                        "order": section.order,
                        "schemaVersion": section.schema_version,
                        "content": section.content_json or {},
                    }
                    for section in refreshed_sections
                ],
            }
            page.has_unpublished_changes = False
            page.save(
                update_fields=[
                    "status",
                    "published_at",
                    "published_snapshot_json",
                    "has_unpublished_changes",
                    "updated_at",
                ]
            )
        elif page_changed:
            page.has_unpublished_changes = True
            page.save(update_fields=["has_unpublished_changes", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0002_cms_v2_foundation"),
    ]

    operations = [
        migrations.RunPython(seed_complete_public_page_registry, migrations.RunPython.noop),
    ]
