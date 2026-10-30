from datetime import date
from urllib.parse import urlsplit
from uuid import uuid4

from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers

from cms.models import (
    CMSCarouselItem,
    CMSLegacyMigrationIssue,
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
        if candidate and model.objects.filter(**{field: candidate}).exists():
            return candidate
    if position is not None and title_field and str(title or "").strip():
        matches = model.objects.filter(
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


def _upsert(model, lookup, defaults, user=None):
    obj = model.objects.filter(**lookup).first()
    if obj and obj.status == "archived":
        raise serializers.ValidationError({
            "detail": f'"{obj}" is archived. Restore it from Archived Content before adding it again.',
            "code": "archived_content_requires_restore",
        })
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


def affected_page_slugs(obj):
    if isinstance(obj, CMSCarouselItem):
        return {"home"}
    if isinstance(obj, (CMSPublicationCategory, CMSPublicationDocument)):
        slugs = {"publications"}
        code = obj.code if isinstance(obj, CMSPublicationCategory) else obj.category.code
        if any(
            (section.content_json or {}).get("featuredCategoryCode") == code
            for section in _page_sections("home")
        ):
            slugs.add("home")
        return slugs
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


def remove_managed_content_from_draft(obj, user=None):
    """Remove an explicitly archived normalized item from its owning draft JSON."""
    target = None
    if isinstance(obj, CMSCarouselItem):
        target = ("home", "hero-carousel")
    elif isinstance(obj, (CMSPublicationCategory, CMSPublicationDocument)):
        target = ("publications", "publication-catalog")
    elif isinstance(obj, CMSResolution):
        target = ("about-rdc", "resolutions-archive")
    if not target:
        return
    section = _page_sections(target[0]).filter(section_key=target[1]).first()
    if not section:
        return
    content = dict(section.content_json or {})
    changed = False
    if isinstance(obj, CMSCarouselItem):
        rows = list(content.get("slides") or [])
        kept = [
            row for index, row in enumerate(rows, 1)
            if not isinstance(row, dict)
            or _stable_key(row.get("id") or row.get("key") or row.get("title"), f"slide-{index}") != obj.stable_key
        ]
        changed = len(kept) != len(rows)
        content["slides"] = kept
    elif isinstance(obj, CMSPublicationCategory):
        rows = list(content.get("categories") or [])
        kept = [
            row for index, row in enumerate(rows, 1)
            if not isinstance(row, dict)
            or _stable_key(row.get("code") or row.get("id") or row.get("title"), f"category-{index}") != obj.code
        ]
        changed = len(kept) != len(rows)
        content["categories"] = kept
    elif isinstance(obj, CMSPublicationDocument):
        categories = list(content.get("categories") or [])
        for category_index, category_row in enumerate(categories, 1):
            if not isinstance(category_row, dict):
                continue
            code = _stable_key(
                category_row.get("code") or category_row.get("id") or category_row.get("title"),
                f"category-{category_index}",
            )
            documents = list(category_row.get("documents") or [])
            kept = [
                row for document_index, row in enumerate(documents, 1)
                if not isinstance(row, dict)
                or _document_reference_key(code, row, document_index) != obj.stable_key
            ]
            if len(kept) != len(documents):
                category_row["documents"] = kept
                changed = True
        content["categories"] = categories
    elif isinstance(obj, CMSResolution):
        years = list(content.get("years") or [])
        for year_row in years:
            if not isinstance(year_row, dict):
                continue
            key = "resolutions" if isinstance(year_row.get("resolutions"), list) else (
                "items" if isinstance(year_row.get("items"), list) else "documents"
            )
            rows = list(year_row.get(key) or [])
            kept = [
                row for index, row in enumerate(rows, 1)
                if not isinstance(row, dict)
                or _stable_key(
                    row.get("id") or f"{obj.year}-{row.get('number') or row.get('resolutionNumber') or row.get('title') or index}",
                    f"resolution-{obj.year}-{index}",
                ) != obj.stable_key
            ]
            if len(kept) != len(rows):
                year_row[key] = kept
                changed = True
        content["years"] = years
    if changed:
        section.content_json = content
        section.status = "draft"
        section.save(update_fields=["content_json", "status", "updated_at"])
    mark_managed_content_pages_changed(obj, user)


def restore_managed_content_to_draft(obj, user=None):
    """Restore archived content to a safe draft position without deleting history."""
    snapshot = managed_content_snapshot(obj)
    if isinstance(obj, CMSCarouselItem):
        section = _page_sections("home").filter(section_key="hero-carousel").first()
        if section:
            content = dict(section.content_json or {})
            rows = list(content.get("slides") or [])
            if not any(isinstance(row, dict) and row.get("id") == obj.stable_key for row in rows):
                rows.append(snapshot)
                content["slides"] = rows
                section.content_json = content
                section.status = "draft"
                section.save(update_fields=["content_json", "status", "updated_at"])
    elif isinstance(obj, CMSPublicationCategory):
        section = _page_sections("publications").filter(section_key="publication-catalog").first()
        if section:
            content = dict(section.content_json or {})
            rows = list(content.get("categories") or [])
            if not any(isinstance(row, dict) and (row.get("code") or row.get("id")) == obj.code for row in rows):
                snapshot["documents"] = []
                rows.append(snapshot)
                content["categories"] = rows
                section.content_json = content
                section.status = "draft"
                section.save(update_fields=["content_json", "status", "updated_at"])
    elif isinstance(obj, CMSPublicationDocument):
        section = _page_sections("publications").filter(section_key="publication-catalog").first()
        if section:
            content = dict(section.content_json or {})
            rows = list(content.get("categories") or [])
            for category in rows:
                if isinstance(category, dict) and (category.get("code") or category.get("id")) == obj.category.code:
                    documents = list(category.get("documents") or [])
                    if not any(isinstance(row, dict) and row.get("id") == obj.stable_key for row in documents):
                        documents.append(snapshot)
                        category["documents"] = documents
                        section.content_json = content
                        section.status = "draft"
                        section.save(update_fields=["content_json", "status", "updated_at"])
                    break
    elif isinstance(obj, CMSResolution):
        section = _page_sections("about-rdc").filter(section_key="resolutions-archive").first()
        if section:
            content = dict(section.content_json or {})
            years = list(content.get("years") or [])
            year_row = next((row for row in years if isinstance(row, dict) and str(row.get("year")) == str(obj.year)), None)
            if year_row is None:
                year_row = {"year": obj.year, "resolutions": []}
                years.append(year_row)
            rows = list(year_row.get("resolutions") or [])
            if not any(isinstance(row, dict) and row.get("id") == obj.stable_key for row in rows):
                rows.append(snapshot)
                year_row["resolutions"] = rows
                content["years"] = years
                section.content_json = content
                section.status = "draft"
                section.save(update_fields=["content_json", "status", "updated_at"])
    mark_managed_content_pages_changed(obj, user)


def reassign_publication_documents_in_draft(source_code, target_code, user=None):
    section = _page_sections("publications").filter(section_key="publication-catalog").first()
    if not section:
        return
    content = dict(section.content_json or {})
    categories = list(content.get("categories") or [])
    source = next((row for row in categories if isinstance(row, dict) and (row.get("code") or row.get("id")) == source_code), None)
    target = next((row for row in categories if isinstance(row, dict) and (row.get("code") or row.get("id")) == target_code), None)
    if not source or not target:
        return
    existing_ids = {
        str(row.get("id")) for row in (target.get("documents") or []) if isinstance(row, dict)
    }
    moved = [
        row for row in (source.get("documents") or [])
        if not isinstance(row, dict) or str(row.get("id")) not in existing_ids
    ]
    target["documents"] = list(target.get("documents") or []) + moved
    source["documents"] = []
    content["categories"] = categories
    section.content_json = content
    section.status = "draft"
    section.save(update_fields=["content_json", "status", "updated_at"])
    page = section.page
    page.status = "draft"
    page.has_unpublished_changes = True
    if user and getattr(user, "is_authenticated", False):
        page.updated_by = user
    page.save(update_fields=["status", "has_unpublished_changes", "updated_by", "updated_at"])


def sync_normalized_section_draft(section, user=None):
    """Mirror fixed-section collection editors into normalized draft records."""
    content = section.content_json if isinstance(section.content_json, dict) else {}
    common = {"updated_by": user, "has_unpublished_changes": True, "status": "draft"}
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
            if row.get("id") != code or row.get("code") != code:
                row["id"] = code
                row["code"] = code
                identity_changed = True
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
                raw_id = _stable_key(item.get("id"), "")
                legacy_item_key = _stable_key(item.get("title"), f"document-{document_index}")
                composite = _stable_key(f"{code}-{raw_id or legacy_item_key}", f"{code}-document-{document_index}")
                key = _existing_key(
                    CMSPublicationDocument,
                    "stable_key",
                    [raw_id, composite],
                    position=document_index,
                    title_field="title",
                    title=item.get("title"),
                ) or (composite if raw_id else _generated_key(CMSPublicationDocument, "stable_key", f"{code}-document"))
                if item.get("id") != key:
                    item["id"] = key
                    identity_changed = True
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


def _referenced_keys(page, published=False):
    result = {"carousel": set(), "categories": set(), "documents": set(), "resolutions": set()}
    for section_key, content in _section_content_rows(page, published=published):
        if page.slug == "home" and section_key == "hero-carousel":
            for index, row in enumerate(content.get("slides") or [], 1):
                if isinstance(row, dict):
                    result["carousel"].add(_stable_key(row.get("id") or row.get("key") or row.get("title"), f"slide-{index}"))
        elif page.slug == "publications" and section_key == "publication-catalog":
            for category_index, row in enumerate(content.get("categories") or [], 1):
                if not isinstance(row, dict):
                    continue
                code = _stable_key(row.get("id") or row.get("code") or row.get("title"), f"category-{category_index}")
                result["categories"].add(code)
                for document_index, item in enumerate(row.get("documents") or [], 1):
                    if isinstance(item, dict):
                        result["documents"].add(_document_reference_key(code, item, document_index))
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
    previously_published = _referenced_keys(page, published=True)
    now = timezone.now()
    groups = []
    if page.slug == "home":
        groups = [(
            CMSCarouselItem, "stable_key", referenced["carousel"],
            previously_published["carousel"], "carousel items",
        )]
    elif page.slug == "publications":
        groups = [
            (
                CMSPublicationCategory, "code", referenced["categories"],
                previously_published["categories"], "publication categories",
            ),
            (
                CMSPublicationDocument, "stable_key", referenced["documents"],
                previously_published["documents"], "publication documents",
            ),
        ]
    elif page.slug == "about-rdc":
        groups = [(
            CMSResolution, "stable_key", referenced["resolutions"],
            previously_published["resolutions"], "resolutions",
        )]
    for model, key_field, keys, previous_keys, content_type in groups:
        queryset = model.objects.select_for_update()
        removed_keys = previous_keys - keys
        omitted = queryset.filter(**{f"{key_field}__in": removed_keys}).exclude(status="archived").filter(published_at__isnull=False)
        if omitted.exists():
            rows = list(omitted[:20])
            labels = ", ".join(str(item) for item in rows[:5])
            raise serializers.ValidationError({
                "detail": f"Archive removed {content_type} through its archive action before publishing: {labels}.",
                "code": "published_content_requires_archive",
                "content_type": content_type,
                "items": [
                    {"id": getattr(item, key_field), "label": str(item)}
                    for item in rows
                ],
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
