from urllib.parse import urlsplit
from copy import deepcopy
import re

from django.conf import settings
from django.utils import timezone

from cms.services.sanitizers import sanitize_public_html, sanitize_public_structure, sanitize_public_text


def _publication_document_sort_key(item):
    """Newest dated document first, including legacy titles with year ranges."""
    values = " ".join(str(item.get(key) or "") for key in ("publicationDate", "year", "title"))
    years = [int(value) for value in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", values)]
    newest_year = max(years, default=0)
    return (-newest_year, int(item.get("sortOrder") or 0), str(item.get("title") or ""))


def _portable_media_references(value):
    if isinstance(value, dict):
        return {key: _portable_media_references(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_portable_media_references(child) for child in value]
    if not isinstance(value, str):
        return value

    media_url = str(getattr(settings, "MEDIA_URL", "/media/") or "/media/")
    media_path = media_url if media_url.startswith("/") else "/media/"
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.path.startswith(media_path):
        portable = parsed.path
        if parsed.query:
            portable += f"?{parsed.query}"
        return portable
    return value


def build_page_snapshot(page):
    published_at = timezone.now()
    sections = []
    for section in page.sections.filter(status="published", is_visible=True).order_by("order", "id"):
        sections.append(
            {
                "sectionKey": section.section_key,
                "sectionType": section.section_type,
                "order": section.order,
                "schemaVersion": section.schema_version,
                "content": _portable_media_references(sanitize_public_structure(section.content_json or {})),
            }
        )

    return {
        "title": sanitize_public_text(page.title),
        "slug": page.slug,
        "publishedAt": published_at.isoformat(),
        "sections": sections,
    }


def build_article_snapshot(article):
    published_at = timezone.now()
    thumbnail_url = article.thumbnail.resolved_public_url if article.thumbnail and not article.thumbnail.is_archived else ""
    return {
        "title": sanitize_public_text(article.title),
        "slug": article.slug,
        "category": sanitize_public_text(article.category),
        "summary": sanitize_public_text(article.summary),
        "body": sanitize_public_html(article.body),
        "thumbnailUrl": _portable_media_references(thumbnail_url),
        "featured": article.featured,
        "author": sanitize_public_text(article.author),
        "publicationDate": article.publication_date.isoformat() if article.publication_date else "",
        "publishedAt": published_at.isoformat(),
    }


def build_page_draft_snapshot(page):
    return {
        "title": page.title,
        "slug": page.slug,
        "status": page.status,
        "hasUnpublishedChanges": page.has_unpublished_changes,
        "sections": [
            {
                "id": section.id,
                "sectionKey": section.section_key,
                "sectionType": section.section_type,
                "order": section.order,
                "schemaVersion": section.schema_version,
                "isVisible": section.is_visible,
                "status": section.status,
                "content": section.content_json or {},
            }
            for section in page.sections.order_by("order", "id")
        ],
    }


def build_article_draft_snapshot(article):
    return {
        "title": article.title,
        "slug": article.slug,
        "category": article.category,
        "summary": article.summary,
        "body": article.body,
        "thumbnail": article.thumbnail_id,
        "featured": article.featured,
        "author": article.author,
        "publication_date": article.publication_date.isoformat() if article.publication_date else None,
        "status": article.status,
        "hasUnpublishedChanges": article.has_unpublished_changes,
    }


def compose_public_page_snapshot(page):
    """Overlay normalized published collections onto a fixed page snapshot."""
    from cms.models import (
        CMSCarouselItem,
        CMSLegacyMigrationIssue,
        CMSPublicationCategory,
        CMSPublicationDocument,
        CMSResolution,
    )
    from cms.services.collections import _referenced_keys

    snapshot = deepcopy(page.published_snapshot_json or {})
    sections = snapshot.get("sections")
    if not isinstance(sections, list):
        return snapshot
    by_key = {
        row.get("sectionKey"): row
        for row in sections
        if isinstance(row, dict) and isinstance(row.get("content"), dict)
    }
    unresolved_sections = set(
        CMSLegacyMigrationIssue.objects.filter(
            page_slug=page.slug,
            resolved_at__isnull=True,
        ).values_list("section_key", flat=True)
    )
    published_references = _referenced_keys(page, published=True)

    if page.slug == "home":
        for section_key in ("development-plans", "investment-programming", "monitoring-evaluation"):
            section = by_key.get(section_key)
            if section:
                section["content"].pop("featuredCategoryCode", None)
                section["content"].pop("featuredCategory", None)
        carousel = list(
            CMSCarouselItem.objects.filter(
                published_at__isnull=False,
                stable_key__in=published_references["carousel"],
            )
            .exclude(status="archived")
            .order_by("sort_order", "id")
            .values_list("published_snapshot_json", flat=True)
        )
        if carousel and "hero-carousel" in by_key and "hero-carousel" not in unresolved_sections:
            by_key["hero-carousel"]["content"]["slides"] = [row for row in carousel if row]

    if (
        page.slug == "publications"
        and "publication-catalog" in by_key
        and "publication-catalog" not in unresolved_sections
    ):
        documents = {}
        for row in CMSPublicationDocument.objects.filter(
            published_at__isnull=False,
            stable_key__in=published_references["documents"],
        ).exclude(status="archived").select_related("category"):
            if row.published_snapshot_json:
                documents.setdefault(row.category.code, []).append(row.published_snapshot_json)
        categories = []
        for row in CMSPublicationCategory.objects.filter(
            published_at__isnull=False,
            code__in=published_references["categories"],
        ).exclude(status="archived").order_by("-display_number", "id"):
            if not row.published_snapshot_json:
                continue
            category = deepcopy(row.published_snapshot_json)
            category["documents"] = sorted(
                documents.get(row.code, []), key=_publication_document_sort_key,
            )
            categories.append(category)
        if categories:
            by_key["publication-catalog"]["content"]["categories"] = categories

    if (
        page.slug == "about-rdc"
        and "resolutions-archive" in by_key
        and "resolutions-archive" not in unresolved_sections
    ):
        archive_content = by_key["resolutions-archive"]["content"]
        referenced_rows = list(CMSResolution.objects.filter(
            stable_key__in=published_references["resolutions"],
        ))
        archived_keys = {
            row.stable_key for row in referenced_rows if row.status == "archived"
        }
        normalized_rows = [
            row for row in referenced_rows
            if row.published_at is not None and row.status != "archived"
        ]
        normalized_by_key = {
            row.stable_key: row.published_snapshot_json
            for row in normalized_rows
            if row.published_snapshot_json
        }
        # The fixed page snapshot is the authoritative list. A normalized row
        # enriches its matching entry, but a missing/stale normalized row must
        # never make an otherwise published resolution disappear publicly.
        # Draft entries are stored oldest-first, so reverse each year for the
        # requested newest-added-first public presentation.
        years = []
        for year_row in archive_content.get("years") or []:
            if not isinstance(year_row, dict):
                continue
            raw_year = str(year_row.get("year") or "").strip()
            if not raw_year.isdigit():
                continue
            resolutions = []
            for item in reversed(year_row.get("resolutions") or year_row.get("items") or []):
                if isinstance(item, dict):
                    stable_key = str(item.get("id") or "").strip()
                    if stable_key in archived_keys:
                        continue
                    resolutions.append(deepcopy(normalized_by_key.get(stable_key) or item))
                elif isinstance(item, str) and item.strip():
                    resolutions.append(item)
            years.append({"year": raw_year, "resolutions": resolutions})
        archive_content["years"] = sorted(
            years,
            key=lambda row: int(row["year"]),
            reverse=True,
        )

    return snapshot
