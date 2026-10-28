from datetime import date
from urllib.parse import urlsplit

from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from cms.models import (
    CMSCarouselItem,
    CMSPublicationCategory,
    CMSPublicationDocument,
    CMSResolution,
)


def _stable_key(value, fallback):
    return slugify(str(value or "").strip())[:120] or fallback


def _safe_url(value):
    value = str(value or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} or value.startswith("/"):
        return value
    return ""


def _year_date(value):
    raw = str(value or "").strip()
    return date(int(raw), 1, 1) if raw.isdigit() and 1900 <= int(raw) <= 2200 else None


def _upsert(model, lookup, defaults, user=None):
    obj, created = model.objects.update_or_create(defaults=defaults, **lookup)
    if created and user:
        obj.created_by = user
        obj.save(update_fields=["created_by"])
    return obj


def managed_content_snapshot(obj):
    if isinstance(obj, CMSCarouselItem):
        image_url = obj.image.resolved_public_url if obj.image and not obj.image.is_archived else obj.legacy_image_url
        snapshot = {
            "id": obj.stable_key,
            "title": obj.title,
            "subtitle": obj.description,
            "button1": {"text": obj.primary_label, "link": obj.primary_url},
            "button2": {"text": obj.secondary_label, "link": obj.secondary_url},
            "sortOrder": obj.sort_order,
        }
        if image_url.startswith(("/", "http://", "https://")):
            snapshot["imageUrl"] = image_url
        elif image_url:
            snapshot["imageKey"] = image_url
        return snapshot
    if isinstance(obj, CMSPublicationCategory):
        return {
            "id": obj.code,
            "title": obj.name,
            "description": obj.description,
            "icon": obj.icon,
            "color": obj.color,
            "sortOrder": obj.sort_order,
        }
    if isinstance(obj, CMSPublicationDocument):
        url = obj.attachment.resolved_public_url if obj.attachment and not obj.attachment.is_archived else obj.external_url
        return {
            "id": obj.stable_key,
            "title": obj.title,
            "description": obj.description,
            "year": str(obj.publication_date.year) if obj.publication_date else "",
            "publicationDate": obj.publication_date.isoformat() if obj.publication_date else "",
            "fileType": obj.document_type,
            "fileSize": obj.legacy_file_size,
            "url": url,
            "categoryCode": obj.category.code,
            "sortOrder": obj.sort_order,
        }
    if isinstance(obj, CMSResolution):
        url = obj.attachment.resolved_public_url if obj.attachment and not obj.attachment.is_archived else obj.external_url
        return {
            "id": obj.stable_key,
            "number": obj.resolution_number,
            "title": obj.title,
            "description": obj.description,
            "year": obj.year,
            "date": obj.resolution_date.isoformat() if obj.resolution_date else "",
            "url": url,
            "sortOrder": obj.sort_order,
        }
    return {}


def sync_normalized_section_draft(section, user=None):
    """Mirror fixed-section collection editors into normalized draft records."""
    content = section.content_json if isinstance(section.content_json, dict) else {}
    common = {"updated_by": user, "has_unpublished_changes": True, "status": "draft"}

    if section.page.slug == "home" and section.section_key == "hero-carousel":
        for index, row in enumerate(content.get("slides") or [], 1):
            if not isinstance(row, dict):
                continue
            key = _stable_key(row.get("id") or row.get("key") or row.get("title"), f"slide-{index}")
            first = row.get("button1") if isinstance(row.get("button1"), dict) else {}
            second = row.get("button2") if isinstance(row.get("button2"), dict) else {}
            _upsert(
                CMSCarouselItem, {"stable_key": key}, {
                    **common,
                    "title": str(row.get("title") or "Untitled slide"),
                    "description": str(row.get("subtitle") or row.get("description") or ""),
                    "legacy_image_url": str(row.get("imageUrl") or row.get("image") or row.get("imageKey") or "").strip(),
                    "primary_label": str(first.get("text") or ""),
                    "primary_url": _safe_url(first.get("link")),
                    "secondary_label": str(second.get("text") or ""),
                    "secondary_url": _safe_url(second.get("link")),
                    "sort_order": index,
                }, user,
            )

    if section.page.slug == "publications" and section.section_key == "publication-catalog":
        for category_index, row in enumerate(content.get("categories") or [], 1):
            if not isinstance(row, dict):
                continue
            code = _stable_key(row.get("id") or row.get("code") or row.get("title"), f"category-{category_index}")
            category = _upsert(
                CMSPublicationCategory, {"code": code}, {
                    **common,
                    "name": str(row.get("title") or row.get("name") or "Publication category"),
                    "description": str(row.get("description") or ""),
                    "icon": str(row.get("icon") or "document"),
                    "color": str(row.get("color") or ""),
                    "sort_order": category_index,
                }, user,
            )
            for document_index, item in enumerate(row.get("documents") or [], 1):
                if not isinstance(item, dict):
                    continue
                item_key = _stable_key(item.get("id") or item.get("title"), f"document-{document_index}")
                key = _stable_key(f"{code}-{item_key}", f"{code}-document-{document_index}")
                raw_date = str(item.get("publicationDate") or "").strip()
                try:
                    publication_date = date.fromisoformat(raw_date) if raw_date else _year_date(item.get("year"))
                except ValueError:
                    publication_date = _year_date(item.get("year"))
                _upsert(
                    CMSPublicationDocument, {"stable_key": key}, {
                        **common,
                        "category": category,
                        "title": str(item.get("title") or "Untitled publication"),
                        "description": str(item.get("description") or ""),
                        "publication_date": publication_date,
                        "document_type": str(item.get("fileType") or "PDF"),
                        "external_url": _safe_url(item.get("url")),
                        "legacy_file_size": str(item.get("fileSize") or ""),
                        "sort_order": document_index,
                    }, user,
                )

    if section.page.slug == "about-rdc" and section.section_key == "resolutions-archive":
        for year_row in content.get("years") or []:
            if not isinstance(year_row, dict):
                continue
            digits = "".join(character for character in str(year_row.get("year") or year_row.get("title") or "") if character.isdigit())
            if len(digits) < 4:
                continue
            year = int(digits[:4])
            rows = year_row.get("resolutions") or year_row.get("items") or year_row.get("documents") or []
            for item_index, item in enumerate(rows, 1):
                if not isinstance(item, dict):
                    continue
                number = str(item.get("number") or item.get("resolutionNumber") or item.get("title") or f"Resolution {item_index}")
                key = _stable_key(item.get("id") or f"{year}-{number}", f"resolution-{year}-{item_index}")
                try:
                    resolution_date = date.fromisoformat(str(item.get("date") or "")) if item.get("date") else None
                except ValueError:
                    resolution_date = None
                _upsert(
                    CMSResolution, {"stable_key": key}, {
                        **common,
                        "resolution_number": number,
                        "title": str(item.get("title") or number),
                        "description": str(item.get("description") or ""),
                        "year": year,
                        "resolution_date": resolution_date,
                        "external_url": _safe_url(item.get("url") or item.get("link")),
                        "sort_order": item_index,
                    }, user,
                )


def _referenced_keys(page):
    result = {"carousel": set(), "categories": set(), "documents": set(), "resolutions": set()}
    for section in page.sections.exclude(status="archived"):
        content = section.content_json if isinstance(section.content_json, dict) else {}
        if page.slug == "home" and section.section_key == "hero-carousel":
            for index, row in enumerate(content.get("slides") or [], 1):
                if isinstance(row, dict):
                    result["carousel"].add(_stable_key(row.get("id") or row.get("key") or row.get("title"), f"slide-{index}"))
        elif page.slug == "publications" and section.section_key == "publication-catalog":
            for category_index, row in enumerate(content.get("categories") or [], 1):
                if not isinstance(row, dict):
                    continue
                code = _stable_key(row.get("id") or row.get("code") or row.get("title"), f"category-{category_index}")
                result["categories"].add(code)
                for document_index, item in enumerate(row.get("documents") or [], 1):
                    if isinstance(item, dict):
                        item_key = _stable_key(item.get("id") or item.get("title"), f"document-{document_index}")
                        result["documents"].add(_stable_key(f"{code}-{item_key}", f"{code}-document-{document_index}"))
        elif page.slug == "about-rdc" and section.section_key == "resolutions-archive":
            for year_row in content.get("years") or []:
                if not isinstance(year_row, dict):
                    continue
                digits = "".join(character for character in str(year_row.get("year") or year_row.get("title") or "") if character.isdigit())
                if len(digits) < 4:
                    continue
                year = int(digits[:4])
                rows = year_row.get("resolutions") or year_row.get("items") or year_row.get("documents") or []
                for item_index, item in enumerate(rows, 1):
                    if isinstance(item, dict):
                        number = str(item.get("number") or item.get("resolutionNumber") or item.get("title") or f"Resolution {item_index}")
                        result["resolutions"].add(_stable_key(item.get("id") or f"{year}-{number}", f"resolution-{year}-{item_index}"))
    return result


def submit_normalized_page_content(page, user=None):
    models = []
    if page.slug == "home":
        models = [CMSCarouselItem]
    elif page.slug == "publications":
        models = [CMSPublicationCategory, CMSPublicationDocument]
    elif page.slug == "about-rdc":
        models = [CMSResolution]
    for model in models:
        model.objects.filter(has_unpublished_changes=True).exclude(status="archived").update(
            status="submitted", submitted_by=user, review_notes=""
        )


def publish_normalized_page_content(page, user=None):
    referenced = _referenced_keys(page)
    now = timezone.now()
    groups = []
    if page.slug == "home":
        groups = [(CMSCarouselItem, "stable_key", referenced["carousel"])]
    elif page.slug == "publications":
        groups = [
            (CMSPublicationCategory, "code", referenced["categories"]),
            (CMSPublicationDocument, "stable_key", referenced["documents"]),
        ]
    elif page.slug == "about-rdc":
        groups = [(CMSResolution, "stable_key", referenced["resolutions"])]
    for model, key_field, keys in groups:
        queryset = model.objects.select_for_update()
        omitted = queryset.exclude(**{f"{key_field}__in": keys}).exclude(status="archived").filter(
            published_at__isnull=False,
        )
        if omitted.exists():
            labels = ", ".join(str(item) for item in omitted[:5])
            raise serializers.ValidationError({
                "detail": f"Archive removed content through its archive action before publishing: {labels}."
            })
        for obj in queryset.filter(**{f"{key_field}__in": keys}):
            obj.published_snapshot_json = managed_content_snapshot(obj)
            obj.status = "published"
            obj.has_unpublished_changes = False
            obj.published_at = now
            obj.archived_at = None
            obj.reviewed_by = user
            obj.updated_by = user
            obj.review_notes = ""
            obj.save(update_fields=[
                "published_snapshot_json", "status", "has_unpublished_changes", "published_at",
                "archived_at", "reviewed_by", "updated_by", "review_notes", "updated_at",
            ])
