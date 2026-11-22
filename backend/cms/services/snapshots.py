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


def build_page_snapshot(page, *, draft=False):
    sections = []
    visible = page.sections.filter(is_visible=True)
    visible = visible.exclude(status="archived") if draft else visible.filter(status="published")
    for section in visible.order_by("order", "id"):
        content = dict(section.content_json or {})
        if page.slug == "publications" and section.section_key == "publication-catalog":
            content.pop("removedCategoryIds", None)
            content.pop("removedDocumentIds", None)
        sections.append(
            {
                "sectionKey": section.section_key,
                "sectionType": section.section_type,
                "order": section.order,
                "schemaVersion": section.schema_version,
                "content": _portable_media_references(sanitize_public_structure(content)),
            }
        )

    return {
        "title": sanitize_public_text(page.title),
        "slug": page.slug,
        "publishedAt": "" if draft else timezone.now().isoformat(),
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


def compose_public_page_snapshot(page, *, draft=False):
    """Apply public presentation rules to saved draft or published section membership."""
    from cms.models import (
        CMSCarouselItem,
        CMSLegacyMigrationIssue,
        CMSMediaAsset,
        CMSPublicationCategory,
        CMSPublicationDocument,
        CMSResolution,
    )
    from cms.services.collections import _referenced_keys, _stable_key, managed_content_snapshot, publication_membership

    def collection_snapshot(record):
        if not record or record.status == "archived":
            return None
        if not draft:
            return record.published_snapshot_json if record.published_at else None
        return _portable_media_references(sanitize_public_structure(managed_content_snapshot(record)))

    snapshot = build_page_snapshot(page, draft=True) if draft else deepcopy(page.published_snapshot_json or {})
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
    references = _referenced_keys(page, published=not draft)

    if page.slug == "regional-profile" and "geographic-coverage" in by_key:
        content = by_key["geographic-coverage"]["content"]
        media_id = content.get("mapAssetId")
        try:
            image = CMSMediaAsset.objects.filter(
                pk=media_id,
                is_archived=False,
                file_type=CMSMediaAsset.FILE_TYPE_IMAGE,
            ).first() if media_id else None
        except (TypeError, ValueError):
            image = None
        content.pop("mapImageUrl", None)
        if image and image.resolved_public_url:
            content["mapImageUrl"] = image.resolved_public_url

    if page.slug == "home":
        for section_key in ("development-plans", "investment-programming", "monitoring-evaluation"):
            section = by_key.get(section_key)
            if section:
                section["content"].pop("featuredCategoryCode", None)
                section["content"].pop("featuredCategory", None)
        if "hero-carousel" in by_key:
            hero = by_key["hero-carousel"]["content"]
            carousel = CMSCarouselItem.objects.filter(
                stable_key__in=references["carousel"],
            ).select_related("image").in_bulk(field_name="stable_key")
            use_normalized = draft or "hero-carousel" not in unresolved_sections
            slides = []
            for index, slide in enumerate(hero.get("slides") or [], 1):
                if not isinstance(slide, dict):
                    continue
                key = _stable_key(slide.get("id") or slide.get("key") or slide.get("title"), f"slide-{index}")
                record = carousel.get(key)
                if record and record.status == "archived":
                    continue
                slides.append((collection_snapshot(record) if use_normalized else None) or slide)
            hero["slides"] = slides

    if page.slug == "publications" and "publication-catalog" in by_key:
        catalog = by_key["publication-catalog"]["content"]
        catalog.pop("removedCategoryIds", None)
        catalog.pop("removedDocumentIds", None)
        document_records = CMSPublicationDocument.objects.filter(
            stable_key__in=references["documents"],
        ).select_related("attachment", "cover_image", "category").in_bulk(field_name="stable_key")
        category_records = CMSPublicationCategory.objects.filter(
            code__in=references["categories"],
        ).select_related("cover_image").in_bulk(field_name="code")
        use_normalized = draft or "publication-catalog" not in unresolved_sections
        categories = []
        for code, published_category, members in publication_membership(catalog):
            record = category_records.get(code)
            if record and record.status == "archived":
                continue
            category = dict(published_category)
            if use_normalized and (normalized := collection_snapshot(record)):
                category = dict(normalized)
                category.update({key: published_category[key] for key in ("visible", "isVisible") if key in published_category})
            documents = []
            for key, published_document in members.items():
                record = document_records.get(key)
                if record and record.status == "archived":
                    continue
                document = dict(published_document)
                if use_normalized and (normalized := collection_snapshot(record)):
                    document = dict(normalized)
                    document.update({field: published_document[field] for field in ("visible", "isVisible") if field in published_document})
                document["categoryCode"] = code
                documents.append(document)
            category["documents"] = sorted(documents, key=_publication_document_sort_key)
            categories.append(category)
        catalog["categories"] = sorted(categories, key=lambda category: -int(category.get("categoryNumber") or 0))

    if (
        page.slug == "about-rdc"
        and "resolutions-archive" in by_key
        and (draft or "resolutions-archive" not in unresolved_sections)
    ):
        archive_content = by_key["resolutions-archive"]["content"]
        referenced_rows = list(CMSResolution.objects.filter(
            stable_key__in=references["resolutions"],
        ).select_related("attachment"))
        archived_keys = {
            row.stable_key for row in referenced_rows if row.status == "archived"
        }
        normalized_by_key = {
            row.stable_key: value for row in referenced_rows
            if (value := collection_snapshot(row))
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
