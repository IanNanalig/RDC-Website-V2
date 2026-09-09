from datetime import date

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection, CMSRevision
from cms.services.snapshots import (
    build_article_draft_snapshot,
    build_article_snapshot,
    build_page_draft_snapshot,
    build_page_snapshot,
)


MODEL_BY_CONTENT_KEY = {
    CMSRevision.CONTENT_PAGE: CMSPage,
    CMSRevision.CONTENT_ARTICLE: CMSArticle,
    CMSRevision.CONTENT_SECTION: CMSPageSection,
    CMSRevision.CONTENT_MEDIA: CMSMediaAsset,
}


def content_type_for(content_type):
    if isinstance(content_type, ContentType):
        return content_type
    if isinstance(content_type, type):
        model = content_type
    else:
        model = MODEL_BY_CONTENT_KEY.get(str(content_type))
    if model is None:
        raise ValueError(f"Unsupported CMS revision content type: {content_type}")
    return ContentType.objects.get_for_model(model)


def revisions_for(content_type, object_id=None):
    queryset = CMSRevision.objects.filter(content_type=content_type_for(content_type))
    return queryset.filter(object_id=object_id) if object_id is not None else queryset


def _next_revision_number(content_type, object_id):
    result = CMSRevision.objects.filter(content_type=content_type, object_id=object_id).aggregate(
        max_version=Max("version_number")
    )
    return (result["max_version"] or 0) + 1


def create_revision(content_type, object_id, action, snapshot, user=None, status_before="", status_after=""):
    django_content_type = content_type_for(content_type)
    return CMSRevision.objects.create(
        content_type=django_content_type,
        object_id=object_id,
        version_number=_next_revision_number(django_content_type, object_id),
        action=action,
        status_before=status_before or "",
        status_after=status_after or "",
        snapshot_json=snapshot or {},
        changed_by=user if getattr(user, "is_authenticated", False) else None,
    )


def publish_page(page, user=None):
    page_id = page.pk if isinstance(page, CMSPage) else page
    with transaction.atomic():
        locked_page = CMSPage.objects.select_for_update().get(pk=page_id)
        status_before = locked_page.status

        # Publishing a whole page remains a useful V1-compatible admin shortcut:
        # every non-archived section is approved in the same atomic operation.
        locked_page.sections.exclude(status="archived").update(status="published")
        snapshot = build_page_snapshot(locked_page)
        published_at = timezone.now()
        locked_page.status = CMSPage.STATUS_PUBLISHED
        locked_page.published_snapshot_json = snapshot
        locked_page.has_unpublished_changes = False
        locked_page.published_at = published_at
        locked_page.archived_at = None
        locked_page.reviewed_by = user if getattr(user, "is_authenticated", False) else locked_page.reviewed_by
        locked_page.updated_by = user if getattr(user, "is_authenticated", False) else locked_page.updated_by
        locked_page.save(
            update_fields=[
                "status", "published_snapshot_json", "has_unpublished_changes", "published_at", "archived_at",
                "reviewed_by", "updated_by", "updated_at",
            ]
        )
        create_revision(
            CMSRevision.CONTENT_PAGE,
            locked_page.pk,
            CMSRevision.ACTION_PUBLISH,
            snapshot,
            user=user,
            status_before=status_before,
            status_after=locked_page.status,
        )
        return locked_page


def publish_section(section, user=None):
    section_id = section.pk if isinstance(section, CMSPageSection) else section
    with transaction.atomic():
        locked_section = CMSPageSection.objects.select_for_update().select_related("page").get(pk=section_id)
        status_before = locked_section.status
        locked_section.status = "published"
        locked_section.lock_owner = None
        locked_section.lock_acquired_at = None
        locked_section.save(update_fields=["status", "lock_owner", "lock_acquired_at", "updated_at"])
        create_section_update_revision(
            locked_section, user=user, action=CMSRevision.ACTION_PUBLISH, status_before=status_before
        )

        page = locked_section.page
        page.status = CMSPage.STATUS_PUBLISHED
        page.published_snapshot_json = build_page_snapshot(page)
        page.published_at = page.published_at or timezone.now()
        page.has_unpublished_changes = False
        page.reviewed_by = user if getattr(user, "is_authenticated", False) else page.reviewed_by
        page.updated_by = user if getattr(user, "is_authenticated", False) else page.updated_by
        page.save(
            update_fields=[
                "status", "published_snapshot_json", "published_at", "has_unpublished_changes", "reviewed_by",
                "updated_by", "updated_at",
            ]
        )
        return locked_section


def publish_article(article, user=None):
    article_id = article.pk if isinstance(article, CMSArticle) else article
    with transaction.atomic():
        locked_article = CMSArticle.objects.select_for_update().get(pk=article_id)
        status_before = locked_article.status
        snapshot = build_article_snapshot(locked_article)
        published_at = timezone.now()
        locked_article.status = CMSArticle.STATUS_PUBLISHED
        locked_article.published_snapshot_json = snapshot
        locked_article.has_unpublished_changes = False
        locked_article.published_at = published_at
        locked_article.archived_at = None
        locked_article.reviewed_by = user if getattr(user, "is_authenticated", False) else locked_article.reviewed_by
        locked_article.updated_by = user if getattr(user, "is_authenticated", False) else locked_article.updated_by
        locked_article.save(
            update_fields=[
                "status", "published_snapshot_json", "has_unpublished_changes", "published_at", "archived_at",
                "reviewed_by", "updated_by", "updated_at",
            ]
        )
        create_revision(
            CMSRevision.CONTENT_ARTICLE,
            locked_article.pk,
            CMSRevision.ACTION_PUBLISH,
            snapshot,
            user=user,
            status_before=status_before,
            status_after=locked_article.status,
        )
        return locked_article


def mark_page_changed(page, user=None):
    page.has_unpublished_changes = True
    if getattr(user, "is_authenticated", False):
        page.updated_by = user
    page.save(update_fields=["has_unpublished_changes", "updated_by", "updated_at"])


def mark_article_changed(article, user=None):
    article.has_unpublished_changes = True
    if getattr(user, "is_authenticated", False):
        article.updated_by = user
    article.save(update_fields=["has_unpublished_changes", "updated_by", "updated_at"])


def create_page_update_revision(page, user=None):
    return create_revision(
        CMSRevision.CONTENT_PAGE, page.pk, CMSRevision.ACTION_UPDATE, build_page_draft_snapshot(page), user=user,
        status_before=page.status, status_after=page.status,
    )


def create_article_update_revision(article, user=None):
    return create_revision(
        CMSRevision.CONTENT_ARTICLE, article.pk, CMSRevision.ACTION_UPDATE, build_article_draft_snapshot(article),
        user=user, status_before=article.status, status_after=article.status,
    )


def section_snapshot(section):
    return {
        "page": section.page_id,
        "sectionKey": section.section_key,
        "sectionType": section.section_type,
        "order": section.order,
        "schemaVersion": section.schema_version,
        "isVisible": section.is_visible,
        "status": section.status,
        "content": section.content_json or {},
    }


def create_section_update_revision(
    section, user=None, action=CMSRevision.ACTION_UPDATE, status_before="", status_after=None
):
    return create_revision(
        CMSRevision.CONTENT_SECTION,
        section.pk,
        action,
        section_snapshot(section),
        user=user,
        status_before=status_before,
        status_after=section.status if status_after is None else status_after,
    )


def reorder_page_sections(page, section_ids, user=None):
    page_id = page.pk if isinstance(page, CMSPage) else page
    normalized_ids = [int(section_id) for section_id in section_ids]
    with transaction.atomic():
        locked_page = CMSPage.objects.select_for_update().get(pk=page_id)
        sections = list(CMSPageSection.objects.select_for_update().filter(page=locked_page).order_by("order", "id"))
        existing_ids = [section.id for section in sections]
        if sorted(existing_ids) != sorted(normalized_ids):
            raise serializers.ValidationError({"section_ids": "Section list must include every section on this page."})

        section_by_id = {section.id: section for section in sections}
        for index, section_id in enumerate(normalized_ids, start=1):
            CMSPageSection.objects.filter(pk=section_id).update(order=100000 + index)
        for index, section_id in enumerate(normalized_ids, start=1):
            section = section_by_id[section_id]
            section.order = index
            section.save(update_fields=["order", "updated_at"])

        mark_page_changed(locked_page, user)
        create_revision(
            CMSRevision.CONTENT_PAGE, locked_page.pk, CMSRevision.ACTION_REORDER,
            build_page_draft_snapshot(locked_page), user=user, status_before=locked_page.status,
            status_after=locked_page.status,
        )
        return locked_page


def restore_revision(revision, user=None):
    snapshot = revision.snapshot_json or {}
    key = revision.content_type_key
    with transaction.atomic():
        if key == CMSRevision.CONTENT_SECTION:
            target = _restore_section(revision, snapshot)
            if target.page.published_at:
                target.status = "published"
                target.save(update_fields=["status", "updated_at"])
                target.page.published_snapshot_json = build_page_snapshot(target.page)
                target.page.status = CMSPage.STATUS_PUBLISHED
                target.page.has_unpublished_changes = False
                target.page.save(
                    update_fields=["published_snapshot_json", "status", "has_unpublished_changes", "updated_at"]
                )
            create_section_update_revision(target, user=user, action=CMSRevision.ACTION_RESTORE)
            return target

        target = revision.content_object
        if target is None:
            raise serializers.ValidationError({"detail": "This revision's target was deleted and cannot be recreated."})

        if key == CMSRevision.CONTENT_ARTICLE:
            _restore_article(target, snapshot)
            target.updated_by = user if getattr(user, "is_authenticated", False) else target.updated_by
            target.has_unpublished_changes = False
            if target.published_at:
                target.status = CMSArticle.STATUS_PUBLISHED
                target.published_snapshot_json = build_article_snapshot(target)
            target.save()
            create_revision(
                key, target.pk, CMSRevision.ACTION_RESTORE, build_article_draft_snapshot(target), user=user,
                status_before=revision.status_after, status_after=target.status,
            )
            return target

        if key == CMSRevision.CONTENT_PAGE:
            _restore_page(target, snapshot)
            target.updated_by = user if getattr(user, "is_authenticated", False) else target.updated_by
            target.has_unpublished_changes = False
            if target.published_at:
                target.status = CMSPage.STATUS_PUBLISHED
                target.published_snapshot_json = build_page_snapshot(target)
            target.save()
            create_revision(
                key, target.pk, CMSRevision.ACTION_RESTORE, build_page_draft_snapshot(target), user=user,
                status_before=revision.status_after, status_after=target.status,
            )
            return target

        raise serializers.ValidationError({"detail": "Restoring this CMS content type is not supported."})


def _restore_article(article, snapshot):
    for field, key in (
        ("title", "title"), ("slug", "slug"), ("category", "category"), ("summary", "summary"),
        ("body", "body"), ("publication_date", "publication_date"), ("featured", "featured"), ("author", "author"),
    ):
        if key in snapshot:
            value = snapshot[key]
            if field == "publication_date" and value:
                value = date.fromisoformat(value)
            setattr(article, field, value)
    if "thumbnail" in snapshot:
        article.thumbnail_id = snapshot["thumbnail"] or None


def _restore_page(page, snapshot):
    if "title" in snapshot:
        page.title = snapshot["title"]
    if "slug" in snapshot:
        page.slug = snapshot["slug"]
    for section_data in snapshot.get("sections") or []:
        key = section_data.get("sectionKey")
        if not key:
            continue
        section = page.sections.filter(section_key=key).first()
        if section is None:
            order = _available_section_order(page, section_data.get("order"))
            section = CMSPageSection(page=page, section_key=key, order=order)
        section.section_type = section_data.get("sectionType") or section.section_type or "text"
        section.schema_version = section_data.get("schemaVersion") or 1
        section.is_visible = section_data.get("isVisible", True)
        section.status = section_data.get("status") or "published"
        section.content_json = section_data.get("content") or {}
        section.save()


def _restore_section(revision, snapshot):
    target = revision.content_object
    page_id = snapshot.get("page")
    page = CMSPage.objects.filter(pk=page_id).first()
    if page is None:
        raise serializers.ValidationError(
            {"detail": "The section cannot be restored because its parent page no longer exists."}
        )
    if target is None:
        target = CMSPageSection(page=page, order=_available_section_order(page, snapshot.get("order")))
    target.page = page
    target.section_key = snapshot.get("sectionKey") or target.section_key
    target.section_type = snapshot.get("sectionType") or target.section_type or "text"
    target.schema_version = snapshot.get("schemaVersion") or 1
    target.is_visible = snapshot.get("isVisible", True)
    target.status = snapshot.get("status") or "draft"
    target.content_json = snapshot.get("content") or {}
    target.lock_owner = None
    target.lock_acquired_at = None
    target.save()
    return target


def _available_section_order(page, requested):
    try:
        requested = int(requested)
    except (TypeError, ValueError):
        requested = 0
    if requested > 0 and not page.sections.filter(order=requested).exists():
        return requested
    return (page.sections.aggregate(value=Max("order"))["value"] or 0) + 1
