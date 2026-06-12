from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from cms.models import CMSArticle, CMSPage, CMSPageSection, CMSRevision
from cms.services.snapshots import (
    build_article_draft_snapshot,
    build_article_snapshot,
    build_page_draft_snapshot,
    build_page_snapshot,
)


def _next_revision_number(content_type, object_id):
    result = CMSRevision.objects.filter(content_type=content_type, object_id=object_id).aggregate(
        max_version=Max("version_number")
    )
    return (result["max_version"] or 0) + 1


def create_revision(content_type, object_id, action, snapshot, user=None, status_before="", status_after=""):
    return CMSRevision.objects.create(
        content_type=content_type,
        object_id=object_id,
        version_number=_next_revision_number(content_type, object_id),
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
        snapshot = build_page_snapshot(locked_page)
        published_at = timezone.now()

        locked_page.status = CMSPage.STATUS_PUBLISHED
        locked_page.published_snapshot_json = snapshot
        locked_page.has_unpublished_changes = False
        locked_page.published_at = published_at
        locked_page.updated_by = user if getattr(user, "is_authenticated", False) else locked_page.updated_by
        locked_page.save(
            update_fields=[
                "status",
                "published_snapshot_json",
                "has_unpublished_changes",
                "published_at",
                "updated_by",
                "updated_at",
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
        locked_article.updated_by = user if getattr(user, "is_authenticated", False) else locked_article.updated_by
        locked_article.save(
            update_fields=[
                "status",
                "published_snapshot_json",
                "has_unpublished_changes",
                "published_at",
                "updated_by",
                "updated_at",
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
        CMSRevision.CONTENT_PAGE,
        page.pk,
        CMSRevision.ACTION_UPDATE,
        build_page_draft_snapshot(page),
        user=user,
        status_before=page.status,
        status_after=page.status,
    )


def create_article_update_revision(article, user=None):
    return create_revision(
        CMSRevision.CONTENT_ARTICLE,
        article.pk,
        CMSRevision.ACTION_UPDATE,
        build_article_draft_snapshot(article),
        user=user,
        status_before=article.status,
        status_after=article.status,
    )


def create_section_update_revision(section, user=None, action=CMSRevision.ACTION_UPDATE):
    return create_revision(
        CMSRevision.CONTENT_SECTION,
        section.pk,
        action,
        {
            "page": section.page_id,
            "sectionKey": section.section_key,
            "sectionType": section.section_type,
            "order": section.order,
            "schemaVersion": section.schema_version,
            "isVisible": section.is_visible,
            "content": section.content_json or {},
        },
        user=user,
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
        temporary_base = 100000
        for index, section_id in enumerate(normalized_ids, start=1):
            section = section_by_id[section_id]
            section.order = temporary_base + index
            section.save(update_fields=["order", "updated_at"])

        for index, section_id in enumerate(normalized_ids, start=1):
            section = section_by_id[section_id]
            section.order = index
            section.save(update_fields=["order", "updated_at"])

        locked_page.has_unpublished_changes = True
        if getattr(user, "is_authenticated", False):
            locked_page.updated_by = user
        locked_page.save(update_fields=["has_unpublished_changes", "updated_by", "updated_at"])

        create_revision(
            CMSRevision.CONTENT_PAGE,
            locked_page.pk,
            CMSRevision.ACTION_REORDER,
            build_page_draft_snapshot(locked_page),
            user=user,
            status_before=locked_page.status,
            status_after=locked_page.status,
        )
        return locked_page
