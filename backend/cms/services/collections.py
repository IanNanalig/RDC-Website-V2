from copy import deepcopy
from datetime import date
from urllib.parse import urlsplit
from uuid import uuid4

from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from cms.models import (
    CMSCarouselItem,
    CMSLegacyMigrationIssue,
    CMSMediaAsset,
    CMSPublicationCategory,
    CMSPublicationDocument,
    CMSResolution,
)


def _stable_key(value, fallback):
    return slugify(str(value or "").strip())[:120] or fallback


def _generated_key(model, field, prefix, max_length=120):
    while True:
        value = f"{prefix}-{uuid4().hex[:16]}"[:max_length]
        if not model.objects.filter(**{field: value}).exists():
            return value


def _existing_key(model, field, candidates, *, position=None, title_field=None, title=None):
    for candidate in candidates:
        if candidate and model.objects.exclude(status="archived").filter(**{field: candidate}).exists():
            return candidate
    if position is not None and title_field and str(title or "").strip():
        matches = model.objects.exclude(status="archived").filter(
            sort_order=position,
            **{f"{title_field}__iexact": str(title).strip()},
        ).values_list(field, flat=True)[:2]
        matches = list(matches)
        if len(matches) == 1:
            return matches[0]
    return ""


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


def _publication_file_metadata(attachment):
    size = attachment.size or 0
    if size >= 1024 * 1024:
        display_size = f"{size / (1024 * 1024):.1f} MB"
    elif size:
        display_size = f"{max(1, round(size / 1024))} KB"
    else:
        display_size = ""
    display_type = "PDF" if attachment.mime_type == "application/pdf" else "Document" if attachment.mime_type else ""
    return display_type, display_size


def _upsert(model, lookup, defaults, user=None, *, restoring=False):
    obj = model.objects.filter(**lookup).first()
    if obj and obj.status == "archived":
        if restoring:
            return obj
        raise serializers.ValidationError({
            "detail": f'"{obj}" belongs to historical records. Add a new item in the page editor.',
            "code": "historical_content_not_editable",
        })
    obj, created = model.objects.update_or_create(defaults=defaults, **lookup)
    if created and user:
        obj.created_by = user
        obj.save(update_fields=["created_by"])
    return obj


def _resolution_rows(year_row):
    from cms.services.resolution_legend import resolution_year_rows

    return resolution_year_rows(year_row)[1] if isinstance(year_row, dict) else []


def resolution_attachment_id(value):
    try:
        pk = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return pk if 0 < pk <= 2**63 - 1 else None


def active_resolution_attachment_ids(content):
    years = content.get("years")
    if not isinstance(years, list):
        return set()
    ids = {
        pk for year in years for item in _resolution_rows(year)
        if isinstance(item, dict) and (pk := resolution_attachment_id(
            item.get("mediaAssetId") or item.get("documentAssetId") or item.get("attachment")
        )) is not None
    }
    return set(CMSMediaAsset.objects.filter(
        pk__in=ids, is_archived=False, file_type=CMSMediaAsset.FILE_TYPE_DOCUMENT,
    ).values_list("pk", flat=True))


def managed_content_snapshot(obj):
    if isinstance(obj, CMSCarouselItem):
        image_url = obj.image.resolved_public_url if obj.image and not obj.image.is_archived else obj.legacy_image_url
        snapshot = {
            "id": obj.stable_key,
            "title": obj.title,
            "subtitle": obj.description,
            "imageAlt": obj.image_alt_text or (obj.image.alt_text if obj.image else ""),
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
        snapshot = {
            "id": obj.code,
            "title": obj.name,
            "description": obj.description,
            "color": obj.color,
            "categoryNumber": obj.display_number,
            "sortOrder": obj.sort_order,
        }
        if obj.cover_image and not obj.cover_image.is_archived:
            snapshot["coverAssetId"] = str(obj.cover_image_id)
            snapshot["coverImage"] = obj.cover_image.resolved_public_url
            snapshot["coverAlt"] = obj.cover_alt_text or obj.cover_image.alt_text or obj.name
        return snapshot
    if isinstance(obj, CMSPublicationDocument):
        url = obj.attachment.resolved_public_url if obj.attachment and not obj.attachment.is_archived else obj.external_url
        snapshot = {
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
        if obj.cover_image and not obj.cover_image.is_archived:
            snapshot["coverAssetId"] = str(obj.cover_image_id)
            snapshot["coverImage"] = obj.cover_image.resolved_public_url
            snapshot["coverAlt"] = obj.cover_alt_text or obj.cover_image.alt_text or obj.title
        return snapshot
    if isinstance(obj, CMSResolution):
        url = obj.attachment.resolved_public_url if obj.attachment and not obj.attachment.is_archived else obj.external_url
        snapshot = {
            "id": obj.stable_key,
            "number": obj.resolution_number,
            "title": obj.title,
            "description": obj.description,
            "year": obj.year,
            "date": obj.resolution_date.isoformat() if obj.resolution_date else "",
            "url": url,
            "sortOrder": obj.sort_order,
        }
        if obj.attachment and not obj.attachment.is_archived:
            snapshot["mediaAssetId"] = str(obj.attachment_id)
            snapshot["documentAssetId"] = str(obj.attachment_id)
        return snapshot
    return {}


def affected_page_slugs(obj):
    if isinstance(obj, CMSCarouselItem):
        return {"home"}
    if isinstance(obj, (CMSPublicationCategory, CMSPublicationDocument)):
        return {"publications"}
    if isinstance(obj, CMSResolution):
        return {"about-rdc"}
    return set()


def _page_sections(slug):
    from cms.models import CMSPageSection
    return CMSPageSection.objects.filter(page__slug=slug).select_related("page")


def mark_managed_content_pages_changed(obj, user=None):
    from cms.models import CMSPage
    for page in CMSPage.objects.filter(slug__in=affected_page_slugs(obj)):
        page.status = "draft"
        page.has_unpublished_changes = True
        if user and getattr(user, "is_authenticated", False):
            page.updated_by = user
        page.save(update_fields=["status", "has_unpublished_changes", "updated_by", "updated_at"])


def sync_resolution_to_draft(obj, user=None, *, resolution_type_key=None):
    """Mirror one normalized resolution into the fixed About RDC draft."""
    if not isinstance(obj, CMSResolution):
        return
    section = _page_sections("about-rdc").filter(section_key="resolutions-archive").first()
    if not section:
        raise serializers.ValidationError({"resolution_type_key": "The resolution legend is unavailable."})
    from cms.services.resolution_legend import RESOLUTION_ROW_KEYS, resolution_year_rows, validate_resolution_types

    content = deepcopy(section.content_json or {})
    years = list(content.get("years") or [])
    target = None
    previous = None
    position = None
    for year_row in years:
        if not isinstance(year_row, dict):
            continue
        rows = list(resolution_year_rows(year_row)[1])
        if str(year_row.get("year") or "").strip() == str(obj.year):
            target = year_row
        for index, row in enumerate(rows):
            if isinstance(row, dict) and str(row.get("id") or "") == obj.stable_key:
                previous = row
                if year_row is target:
                    position = index
                rows.pop(index)
                break
        for alias in RESOLUTION_ROW_KEYS[1:]:
            year_row.pop(alias, None)
        year_row["resolutions"] = rows
    if target is None:
        target = {"year": str(obj.year), "resolutions": []}
        years.append(target)
    target_rows = list(target.get("resolutions") or target.get("items") or [])
    candidate = {**(previous or {}), **managed_content_snapshot(obj)}
    if not obj.attachment_id:
        candidate.pop("mediaAssetId", None)
        candidate.pop("documentAssetId", None)
    if resolution_type_key is not None:
        candidate["resolutionTypeKey"] = resolution_type_key
        candidate.pop("legendItems", None)
    legend = {"legendItems": content.get("legendItems", [])}
    updated = validate_resolution_types(
        {**legend, "years": [{"year": obj.year, "resolutions": [candidate]}]},
        {**legend, "years": [{"year": obj.year, "resolutions": [previous] if previous else []}]},
    )["years"][0]["resolutions"][0]
    target_rows.insert(len(target_rows) if position is None else position, updated)
    target["resolutions"] = target_rows
    target.pop("items", None)
    content["years"] = years
    section.content_json = content
    section.status = "draft"
    section.save(update_fields=["content_json", "status", "updated_at"])
    mark_managed_content_pages_changed(obj, user)
    return updated["resolutionTypeKey"]


def sync_normalized_section_draft(section, user=None, *, restoring=False, resolution_attachment_ids=None):
    """Mirror fixed-section collection editors into normalized draft records."""
    content = section.content_json if isinstance(section.content_json, dict) else {}
    common = {
        "updated_by": user,
        "has_unpublished_changes": not restoring,
        "status": "published" if restoring else "draft",
    }
    identity_changed = False

    if section.page.slug == "home" and section.section_key == "hero-carousel":
        for index, row in enumerate(content.get("slides") or [], 1):
            if not isinstance(row, dict):
                continue
            explicit = _stable_key(row.get("id") or row.get("key"), "")
            legacy = _stable_key(row.get("title"), f"slide-{index}")
            key = explicit or _existing_key(
                CMSCarouselItem,
                "stable_key",
                [legacy],
                position=index,
                title_field="title",
                title=row.get("title"),
            ) or _generated_key(CMSCarouselItem, "stable_key", "slide")
            if row.get("id") != key:
                row["id"] = key
                identity_changed = True
            first = row.get("button1") if isinstance(row.get("button1"), dict) else {}
            second = row.get("button2") if isinstance(row.get("button2"), dict) else {}
            media_id = row.get("mediaAssetId") or row.get("imageAssetId")
            try:
                image = CMSMediaAsset.objects.filter(
                    pk=media_id,
                    is_archived=False,
                    file_type=CMSMediaAsset.FILE_TYPE_IMAGE,
                ).first() if media_id else None
            except (TypeError, ValueError):
                image = None
            _upsert(
                CMSCarouselItem, {"stable_key": key}, {
                    **common,
                    "title": str(row.get("title") or "Untitled slide"),
                    "description": str(row.get("subtitle") or row.get("description") or ""),
                    "legacy_image_url": str(row.get("imageUrl") or row.get("image") or row.get("imageKey") or "").strip(),
                    "image": image,
                    "image_alt_text": str(row.get("imageAlt") or "").strip(),
                    "primary_label": str(first.get("text") or ""),
                    "primary_url": _safe_url(first.get("link")),
                    "secondary_label": str(second.get("text") or ""),
                    "secondary_url": _safe_url(second.get("link")),
                    "sort_order": index,
                }, user, restoring=restoring,
            )

    if section.page.slug == "publications" and section.section_key == "publication-catalog":
        if not isinstance(content.get("categories"), list):
            raise serializers.ValidationError({"detail": "The publication catalog must contain a category list."})
        category_codes = set()
        document_keys = set()
        document_ids = set()
        for category_index, row in enumerate(content.get("categories") or [], 1):
            if not isinstance(row, dict):
                raise serializers.ValidationError({"detail": "Each publication category must be an object."})
            if not isinstance(row.get("documents", []), list):
                raise serializers.ValidationError({"detail": "Each publication category must contain a document list."})
            explicit = _stable_key(row.get("code") or row.get("id"), "")[:80]
            legacy = _stable_key(row.get("title"), f"category-{category_index}")[:80]
            code = explicit or _existing_key(
                CMSPublicationCategory,
                "code",
                [legacy],
                position=category_index,
                title_field="name",
                title=row.get("title") or row.get("name"),
            ) or _generated_key(CMSPublicationCategory, "code", "category", 80)
            if code in category_codes:
                raise serializers.ValidationError({"detail": f"Duplicate publication category identifier: {code}."})
            category_codes.add(code)
            if row.get("id") != code or row.get("code") != code:
                row["id"] = code
                row["code"] = code
                identity_changed = True
            cover_media_id = row.get("coverAssetId") or row.get("coverImageAssetId")
            try:
                cover_image = CMSMediaAsset.objects.filter(
                    pk=cover_media_id,
                    is_archived=False,
                    file_type=CMSMediaAsset.FILE_TYPE_IMAGE,
                ).first() if cover_media_id else None
            except (TypeError, ValueError):
                cover_image = None
            existing_category = CMSPublicationCategory.objects.filter(code=code).first()
            try:
                display_number = max(1, int(row.get("categoryNumber")))
            except (TypeError, ValueError):
                if existing_category:
                    display_number = existing_category.display_number
                else:
                    highest_number = CMSPublicationCategory.objects.order_by("-display_number").values_list(
                        "display_number", flat=True,
                    ).first() or 0
                    display_number = highest_number + 1
                row["categoryNumber"] = display_number
                identity_changed = True
            category = _upsert(
                CMSPublicationCategory, {"code": code}, {
                    **common,
                    "name": str(row.get("title") or row.get("name") or "Publication category"),
                    "description": str(row.get("description") or ""),
                    "icon": "",
                    "color": str(row.get("color") or ""),
                    "cover_image": cover_image,
                    "cover_alt_text": str(row.get("coverAlt") or "").strip(),
                    "display_number": display_number,
                    "sort_order": category_index,
                }, user, restoring=restoring,
            )
            for document_index, item in enumerate(row.get("documents") or [], 1):
                if not isinstance(item, dict):
                    raise serializers.ValidationError({"detail": "Each publication document must be an object."})
                raw_id = _stable_key(item.get("id"), "")
                if raw_id in document_ids:
                    raise serializers.ValidationError({"detail": f"Duplicate publication document identifier: {raw_id}."})
                if raw_id:
                    document_ids.add(raw_id)
                    if CMSPublicationDocument.objects.filter(stable_key=raw_id, status="archived").exists():
                        raise serializers.ValidationError({"detail": "Add a new publication template and select its attachment from the Media Library.", "code": "historical_content_not_editable"})
                legacy_item_key = _stable_key(item.get("title"), f"document-{document_index}")
                composite = (
                    raw_id
                    if raw_id.startswith(f"{code}-")
                    else _stable_key(f"{code}-{raw_id or legacy_item_key}", f"{code}-document-{document_index}")
                )
                key = _existing_key(
                    CMSPublicationDocument,
                    "stable_key",
                    [raw_id, composite],
                    position=None if raw_id else document_index,
                    title_field="title",
                    title=item.get("title"),
                ) or (composite if raw_id else _generated_key(CMSPublicationDocument, "stable_key", f"{code}-document"))
                if key in document_keys:
                    raise serializers.ValidationError({"detail": f"Duplicate publication document identifier: {key}."})
                document_keys.add(key)
                if item.get("id") != key:
                    item["id"] = key
                    identity_changed = True
                raw_date = str(item.get("publicationDate") or "").strip()
                try:
                    publication_date = date.fromisoformat(raw_date) if raw_date else _year_date(item.get("year"))
                except ValueError:
                    publication_date = _year_date(item.get("year"))
                cover_media_id = item.get("coverAssetId") or item.get("coverImageAssetId")
                try:
                    document_cover = CMSMediaAsset.objects.filter(
                        pk=cover_media_id,
                        is_archived=False,
                        file_type=CMSMediaAsset.FILE_TYPE_IMAGE,
                    ).first() if cover_media_id else None
                except (TypeError, ValueError):
                    document_cover = None
                attachment_fields = {}
                file_type = str(item.get("fileType") or "PDF")
                file_size = str(item.get("fileSize") or "")
                if "mediaAssetId" in item:
                    media_id = item["mediaAssetId"]
                    attachment = None
                    if media_id:
                        try:
                            attachments = CMSMediaAsset.objects.filter(pk=media_id, file_type=CMSMediaAsset.FILE_TYPE_DOCUMENT)
                            attachment = (attachments if restoring else attachments.filter(is_archived=False)).first()
                        except (TypeError, ValueError):
                            pass
                        if not attachment and not restoring:
                            raise serializers.ValidationError({"detail": "Choose an active publication document from the Media Library."})
                    if attachment or not media_id or not restoring:
                        attachment_fields["attachment"] = attachment
                    if attachment:
                        media_type, media_size = _publication_file_metadata(attachment)
                        file_type = media_type or file_type
                        file_size = media_size or file_size
                _upsert(
                    CMSPublicationDocument, {"stable_key": key}, {
                        **common,
                        "category": category,
                        **attachment_fields,
                        "title": str(item.get("title") or "Untitled publication"),
                        "description": str(item.get("description") or ""),
                        "publication_date": publication_date,
                        "document_type": file_type,
                        "cover_image": document_cover,
                        "cover_alt_text": str(item.get("coverAlt") or "").strip(),
                        "external_url": _safe_url(item.get("url")),
                        "legacy_file_size": file_size,
                        "sort_order": document_index,
                    }, user, restoring=restoring,
                )

    if section.page.slug == "about-rdc" and section.section_key == "resolutions-archive":
        if resolution_attachment_ids is None:
            resolution_attachment_ids = active_resolution_attachment_ids(content)
        keys = {
            key for year_row in content.get("years") or [] for item in _resolution_rows(year_row)
            if isinstance(item, dict) and (key := _stable_key(item.get("id"), ""))
        }
        existing = CMSResolution.objects.select_for_update().in_bulk(keys, field_name="stable_key")
        for year_row in content.get("years") or []:
            if not isinstance(year_row, dict):
                continue
            digits = "".join(character for character in str(year_row.get("year") or year_row.get("title") or "") if character.isdigit())
            if len(digits) < 4:
                continue
            year = int(digits[:4])
            rows = _resolution_rows(year_row)
            for item_index, item in enumerate(rows, 1):
                if not isinstance(item, dict):
                    continue
                number = str(item.get("number") or item.get("resolutionNumber") or item.get("title") or f"Resolution {item_index}")
                explicit = _stable_key(item.get("id"), "")
                legacy = _stable_key(f"{year}-{number}", f"resolution-{year}-{item_index}")
                key = explicit or _existing_key(
                    CMSResolution,
                    "stable_key",
                    [legacy],
                    position=item_index,
                    title_field="resolution_number",
                    title=number,
                ) or _generated_key(CMSResolution, "stable_key", f"resolution-{year}")
                if item.get("id") != key:
                    item["id"] = key
                    identity_changed = True
                try:
                    resolution_date = date.fromisoformat(str(item.get("date") or "")) if item.get("date") else None
                except ValueError:
                    resolution_date = None
                media_id = resolution_attachment_id(
                    item.get("mediaAssetId") or item.get("documentAssetId") or item.get("attachment")
                )
                fields = {
                    "resolution_number": number,
                    "title": str(item.get("title") or number),
                    "description": str(item.get("description") or ""),
                    "year": year,
                    "resolution_date": resolution_date,
                    "attachment_id": media_id if media_id in resolution_attachment_ids else None,
                    "external_url": _safe_url(item.get("url") or item.get("link")),
                    "sort_order": item_index,
                }
                if not explicit and key not in existing:
                    # Legacy entries without IDs can match a pre-existing record.
                    existing[key] = CMSResolution.objects.select_for_update().filter(stable_key=key).first()
                obj = existing.get(key)
                if obj is None:
                    obj, created = CMSResolution.objects.select_for_update().get_or_create(
                        stable_key=key, defaults={"created_by": user, **fields, **common},
                    )
                    existing[key] = obj
                    if created:
                        continue
                if obj.status == "archived":
                    if restoring:
                        continue
                    raise serializers.ValidationError({
                        "detail": f'"{obj}" belongs to historical records. Add a new item in the page editor.',
                        "code": "historical_content_not_editable",
                    })
                changed = {name: value for name, value in fields.items() if getattr(obj, name) != value}
                if changed or (restoring and (obj.status != "published" or obj.has_unpublished_changes)):
                    changes = {**changed, **common}
                    for name, value in changes.items():
                        setattr(obj, name, value)
                    obj.save(update_fields=[*changes, "updated_at"])

    if section.page.slug == "publications" and section.section_key == "publication-catalog":
        for field in ("removedCategoryIds", "removedDocumentIds"):
            if field in content:
                del content[field]
                identity_changed = True

    if identity_changed:
        # Stable identities are content metadata, not structure. Persisting them
        # prevents a later title edit from looking like removal plus insertion.
        section.content_json = content
        section.save(update_fields=["content_json", "updated_at"])
        complete = True
        if section.page.slug == "home" and section.section_key == "hero-carousel":
            complete = all(
                not isinstance(row, dict) or bool(row.get("id") or row.get("key"))
                for row in content.get("slides") or []
            )
        elif section.page.slug == "publications" and section.section_key == "publication-catalog":
            complete = all(
                not isinstance(row, dict) or (
                    bool(row.get("id") or row.get("code"))
                    and all(not isinstance(item, dict) or bool(item.get("id")) for item in row.get("documents") or [])
                )
                for row in content.get("categories") or []
            )
        elif section.page.slug == "about-rdc" and section.section_key == "resolutions-archive":
            complete = all(
                not isinstance(item, dict) or bool(item.get("id"))
                for year_row in content.get("years") or [] if isinstance(year_row, dict)
                for item in (year_row.get("resolutions") or year_row.get("items") or year_row.get("documents") or [])
            )
        if complete:
            CMSLegacyMigrationIssue.objects.filter(
                page_slug=section.page.slug,
                section_key=section.section_key,
                reason__startswith="Stable identity repair:",
                resolved_at__isnull=True,
            ).update(resolved_at=timezone.now())


def reconcile_normalized_page_content(page, user=None):
    """Make the normalized collection rows match the page draft before review/publish.

    Older databases and maintenance commands can update the fixed section JSON
    without going through the section editor. Publishing must therefore not rely
    on a previous editor save having synchronized the normalized rows.
    """
    section_key = {
        "home": "hero-carousel",
        "publications": "publication-catalog",
        "about-rdc": "resolutions-archive",
    }.get(page.slug)
    if not section_key:
        return
    section = page.sections.exclude(status="archived").filter(section_key=section_key).first()
    if section:
        sync_normalized_section_draft(section, user)


def _section_content_rows(page, published=False):
    if published:
        for row in (page.published_snapshot_json or {}).get("sections", []):
            if isinstance(row, dict) and isinstance(row.get("content"), dict):
                yield row.get("sectionKey"), row["content"]
        return
    for section in page.sections.exclude(status="archived"):
        yield section.section_key, section.content_json if isinstance(section.content_json, dict) else {}


def _document_reference_key(category_code, item, index):
    raw_id = _stable_key(item.get("id"), "")
    if raw_id and (raw_id.startswith(f"{category_code}-") or CMSPublicationDocument.objects.filter(stable_key=raw_id).exists()):
        return raw_id
    item_key = raw_id or _stable_key(item.get("title"), f"document-{index}")
    return _stable_key(f"{category_code}-{item_key}", f"{category_code}-document-{index}")


def publication_membership(content):
    for category_index, row in enumerate(content.get("categories") or [], 1):
        if not isinstance(row, dict):
            continue
        code = _stable_key(row.get("code") or row.get("id") or row.get("title"), f"category-{category_index}")[:80]
        documents = {
            _document_reference_key(code, item, index): item
            for index, item in enumerate(row.get("documents") or [], 1)
            if isinstance(item, dict)
        }
        yield code, row, documents


def _referenced_keys(page, published=False):
    result = {"carousel": set(), "categories": set(), "documents": set(), "resolutions": set()}
    for section_key, content in _section_content_rows(page, published=published):
        if page.slug == "home" and section_key == "hero-carousel":
            for index, row in enumerate(content.get("slides") or [], 1):
                if isinstance(row, dict):
                    result["carousel"].add(_stable_key(row.get("id") or row.get("key") or row.get("title"), f"slide-{index}"))
        elif page.slug == "publications" and section_key == "publication-catalog":
            for code, _, documents in publication_membership(content):
                result["categories"].add(code)
                result["documents"].update(documents)
        elif page.slug == "about-rdc" and section_key == "resolutions-archive":
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
    referenced = _referenced_keys(page)
    for model, key_field, keys in _managed_page_groups(page, referenced):
        model.objects.filter(
            **{f"{key_field}__in": keys}, has_unpublished_changes=True,
        ).exclude(status="archived").update(status="submitted", submitted_by=user, review_notes="")


def _managed_page_groups(page, referenced):
    if page.slug == "home":
        return [(CMSCarouselItem, "stable_key", referenced["carousel"])]
    if page.slug == "publications":
        return [
            (CMSPublicationCategory, "code", referenced["categories"]),
            (CMSPublicationDocument, "stable_key", referenced["documents"]),
        ]
    if page.slug == "about-rdc":
        return [(CMSResolution, "stable_key", referenced["resolutions"])]
    return []


def publish_normalized_page_content(page, user=None):
    referenced = _referenced_keys(page)
    now = timezone.now()
    for model, key_field, keys in _managed_page_groups(page, referenced):
        content_type = model._meta.verbose_name_plural
        queryset = model.objects.select_for_update()
        available_keys = set(
            queryset.filter(**{f"{key_field}__in": keys})
            .exclude(status="archived")
            .values_list(key_field, flat=True)
        )
        missing_keys = sorted(keys - available_keys)
        if missing_keys:
            raise serializers.ValidationError({
                "detail": f"Some {content_type} could not be prepared for publishing. Save the section and try again.",
                "code": "normalized_content_missing",
                "content_type": content_type,
                "items": [{"id": key, "label": key} for key in missing_keys[:20]],
            })
        for obj in queryset.filter(**{f"{key_field}__in": keys}).exclude(status="archived"):
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
