from django.db import migrations
from django.utils.text import slugify


def _key(value, fallback="", limit=120):
    return (slugify(str(value or "").strip()) or fallback)[:limit]


def _section(page, section_key, published=False):
    if published:
        snapshot = dict(page.published_snapshot_json or {})
        sections = list(snapshot.get("sections") or [])
        for row in sections:
            if isinstance(row, dict) and row.get("sectionKey") == section_key and isinstance(row.get("content"), dict):
                return row["content"], snapshot
        return None, snapshot
    row = page.sections.filter(section_key=section_key).first()
    return (row.content_json if row and isinstance(row.content_json, dict) else None), row


def _record_issue(Issue, page_slug, section_key, item_path, reason, payload):
    Issue.objects.get_or_create(
        page_slug=page_slug,
        section_key=section_key,
        item_path=item_path,
        resolved_at__isnull=True,
        defaults={"reason": f"Stable identity repair: {reason}", "legacy_payload": payload if isinstance(payload, dict) else {"value": payload}},
    )


def _resolve(model, field, candidates, position, title_field, title):
    for candidate in candidates:
        if candidate and model.objects.filter(**{field: candidate}).exists():
            return candidate
    if str(title or "").strip():
        rows = list(model.objects.filter(
            sort_order=position,
            **{f"{title_field}__iexact": str(title).strip()},
        ).values_list(field, flat=True)[:2])
        if len(rows) == 1:
            return rows[0]
    return ""


def repair_stable_identities(apps, schema_editor):
    Page = apps.get_model("cms", "CMSPage")
    Carousel = apps.get_model("cms", "CMSCarouselItem")
    Category = apps.get_model("cms", "CMSPublicationCategory")
    Document = apps.get_model("cms", "CMSPublicationDocument")
    Resolution = apps.get_model("cms", "CMSResolution")
    Issue = apps.get_model("cms", "CMSLegacyMigrationIssue")

    for slug, section_key, published in (
        ("home", "hero-carousel", False),
        ("home", "hero-carousel", True),
        ("publications", "publication-catalog", False),
        ("publications", "publication-catalog", True),
        ("about-rdc", "resolutions-archive", False),
        ("about-rdc", "resolutions-archive", True),
    ):
        page = Page.objects.filter(slug=slug).first()
        if not page:
            continue
        content, owner = _section(page, section_key, published=published)
        if not isinstance(content, dict) or owner is None:
            continue
        changed = False
        source_label = "published" if published else "draft"

        if slug == "home":
            for index, row in enumerate(content.get("slides") or [], 1):
                if not isinstance(row, dict) or row.get("id"):
                    continue
                legacy = _key(row.get("key") or row.get("title"), f"slide-{index}")
                stable = _resolve(Carousel, "stable_key", [legacy], index, "title", row.get("title"))
                if stable:
                    row["id"] = stable
                    changed = True
                else:
                    _record_issue(Issue, slug, section_key, f"{source_label}.slides[{index - 1}]", "Carousel identity could not be matched unambiguously.", row)

        elif slug == "publications":
            for category_index, row in enumerate(content.get("categories") or [], 1):
                if not isinstance(row, dict):
                    continue
                code = _key(row.get("code") or row.get("id"), "", 80)
                if not code:
                    legacy = _key(row.get("title") or row.get("name"), f"category-{category_index}", 80)
                    code = _resolve(Category, "code", [legacy], category_index, "name", row.get("title") or row.get("name"))
                if not code:
                    _record_issue(Issue, slug, section_key, f"{source_label}.categories[{category_index - 1}]", "Publication category identity could not be matched unambiguously.", row)
                    continue
                if row.get("id") != code or row.get("code") != code:
                    row["id"] = code
                    row["code"] = code
                    changed = True
                for document_index, item in enumerate(row.get("documents") or [], 1):
                    if not isinstance(item, dict):
                        continue
                    raw = _key(item.get("id"), "")
                    legacy_item = raw or _key(item.get("title"), f"document-{document_index}")
                    composite = _key(f"{code}-{legacy_item}", f"{code}-document-{document_index}")
                    stable = _resolve(Document, "stable_key", [raw, composite], document_index, "title", item.get("title"))
                    if stable:
                        if item.get("id") != stable:
                            item["id"] = stable
                            changed = True
                    else:
                        _record_issue(Issue, slug, section_key, f"{source_label}.categories[{category_index - 1}].documents[{document_index - 1}]", "Publication document identity could not be matched unambiguously.", item)

        elif slug == "about-rdc":
            for year_index, year_row in enumerate(content.get("years") or [], 1):
                if not isinstance(year_row, dict):
                    continue
                digits = "".join(character for character in str(year_row.get("year") or year_row.get("title") or "") if character.isdigit())
                if len(digits) < 4:
                    continue
                year = int(digits[:4])
                rows = year_row.get("resolutions") or year_row.get("items") or year_row.get("documents") or []
                for item_index, item in enumerate(rows, 1):
                    if not isinstance(item, dict) or item.get("id"):
                        continue
                    number = str(item.get("number") or item.get("resolutionNumber") or item.get("title") or f"Resolution {item_index}")
                    legacy = _key(f"{year}-{number}", f"resolution-{year}-{item_index}")
                    stable = _resolve(Resolution, "stable_key", [legacy], item_index, "resolution_number", number)
                    if stable:
                        item["id"] = stable
                        changed = True
                    else:
                        _record_issue(Issue, slug, section_key, f"{source_label}.years[{year_index - 1}].resolutions[{item_index - 1}]", "Resolution identity could not be matched unambiguously.", item)

        if changed:
            if published:
                page.published_snapshot_json = owner
                page.save(update_fields=["published_snapshot_json"])
            else:
                owner.content_json = content
                owner.save(update_fields=["content_json", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("cms", "0017_content_only_models")]
    operations = [migrations.RunPython(repair_stable_identities, migrations.RunPython.noop)]
