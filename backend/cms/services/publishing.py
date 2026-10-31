from copy import deepcopy
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from cms.models import (
    CMSArticle,
    CMSContributorForm,
    CMSContributorFormVersion,
    CMSPage,
    CMSPageSection,
)
from cms.form_schema import (
    FormSchemaError,
    build_form_migration_plan,
    normalize_system_managed_sections,
    validate_form_schema,
)
from cms.services.snapshots import (
    build_article_snapshot,
    build_page_snapshot,
)


def publish_page(page, user=None):
    page_id = page.pk if isinstance(page, CMSPage) else page
    with transaction.atomic():
        locked_page = CMSPage.objects.select_for_update().get(pk=page_id)
        from cms.services.collections import reconcile_normalized_page_content
        reconcile_normalized_page_content(locked_page, user)
        if locked_page.slug == "home":
            # These fields were introduced by the legacy Home-to-Publications
            # coupling. Home document cards are now authored directly in their
            # fixed CMS sections, so a Home publish must neither depend on nor
            # re-inject the old publication catalog.
            for section in locked_page.sections.filter(section_key__in=(
                "development-plans", "investment-programming", "monitoring-evaluation",
            )):
                content = dict(section.content_json or {})
                changed = False
                for key in ("featuredCategoryCode", "featuredCategory"):
                    if key in content:
                        content.pop(key, None)
                        changed = True
                if changed:
                    section.content_json = content
                    section.save(update_fields=["content_json", "updated_at"])
        # Publishing a whole page remains a useful V1-compatible admin shortcut:
        # every non-archived section is approved in the same atomic operation.
        locked_page.sections.exclude(status="archived").update(
            status="published", lock_owner=None, lock_acquired_at=None,
        )
        from cms.services.collections import publish_normalized_page_content
        publish_normalized_page_content(locked_page, user)
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
        return locked_page


def publish_article(article, user=None):
    article_id = article.pk if isinstance(article, CMSArticle) else article
    with transaction.atomic():
        locked_article = CMSArticle.objects.select_for_update().get(pk=article_id)
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
        return locked_article


def publish_contributor_form(form, user=None):
    form_id = form.pk if isinstance(form, CMSContributorForm) else form
    with transaction.atomic():
        locked_form = CMSContributorForm.objects.select_for_update().get(pk=form_id)
        if not locked_form.has_unpublished_changes:
            raise FormSchemaError("This contributor form has no unpublished changes.")
        published_schema = (
            locked_form.current_published_version.schema_json
            if locked_form.current_published_version_id
            else None
        )
        schema = validate_form_schema(locked_form.draft_schema_json, published_schema=published_schema)
        next_number = (
            locked_form.versions.aggregate(max_version=Max("version_number"))["max_version"] or 0
        ) + 1
        version = CMSContributorFormVersion.objects.create(
            form=locked_form,
            version_number=next_number,
            schema_json=schema,
            based_on_version=locked_form.current_published_version,
            migration_plan_json=(
                build_form_migration_plan(published_schema, schema)
                if isinstance(published_schema, dict)
                else {"format": 1, "rules": [], "attention_fields": [], "incompatible_changes": []}
            ),
            published_by=user if getattr(user, "is_authenticated", False) else None,
        )
        locked_form.status = CMSContributorForm.STATUS_PUBLISHED
        locked_form.current_published_version = version
        locked_form.has_unpublished_changes = False
        locked_form.review_notes = ""
        locked_form.reviewed_by = user if getattr(user, "is_authenticated", False) else locked_form.reviewed_by
        locked_form.updated_by = user if getattr(user, "is_authenticated", False) else locked_form.updated_by
        locked_form.published_at = version.published_at
        locked_form.lock_owner = None
        locked_form.lock_acquired_at = None
        locked_form.save(update_fields=[
            "status", "current_published_version", "has_unpublished_changes", "review_notes", "reviewed_by",
            "updated_by", "published_at", "lock_owner", "lock_acquired_at", "updated_at",
        ])
        return locked_form


def _field_origin(section, section_index, field_index, field):
    """Describe where a retired custom field belongs in the contributor form."""
    return {
        "section_key": str(section.get("key") or ""),
        "section_title": str(section.get("title") or "Untitled section"),
        "section_description": str(section.get("description") or ""),
        "section_visible": section.get("visible", True) is not False,
        "section_order": section_index,
        "field_order": field_index,
        "field_required": bool(field.get("required")),
    }


def _historical_field_origin(form, field_key):
    """Recover a legacy retired field's last contributor-facing location."""
    for historical_version in form.versions.order_by("-version_number"):
        schema = historical_version.schema_json
        if not isinstance(schema, dict):
            continue
        for section_index, section in enumerate(schema.get("sections", [])):
            if not isinstance(section, dict) or section.get("admin_only"):
                continue
            for field_index, field in enumerate(section.get("fields", [])):
                if not isinstance(field, dict) or field.get("key") != field_key:
                    continue
                saved_origin = field.get("retired_from")
                if section.get("key") == "retired_fields":
                    if isinstance(saved_origin, dict) and saved_origin.get("section_key"):
                        return deepcopy(saved_origin)
                    continue
                return _field_origin(section, section_index, field_index, field)
    return None


def restore_contributor_form_version(form, version, user=None):
    form_id = form.pk if isinstance(form, CMSContributorForm) else form
    version_id = version.pk if isinstance(version, CMSContributorFormVersion) else version
    with transaction.atomic():
        locked_form = CMSContributorForm.objects.select_for_update().get(pk=form_id)
        selected = CMSContributorFormVersion.objects.get(pk=version_id, form=locked_form)
        reset_to_live = selected.pk == locked_form.current_published_version_id
        restored_schema = deepcopy(selected.schema_json)
        published_schema = (
            locked_form.current_published_version.schema_json
            if locked_form.current_published_version_id
            else None
        )
        if isinstance(published_schema, dict):
            restored_keys = {
                field.get("key")
                for section in restored_schema.get("sections", [])
                if isinstance(section, dict)
                for field in section.get("fields", [])
                if isinstance(field, dict)
            }
            retired_fields = []
            for section_index, section in enumerate(published_schema.get("sections", [])):
                if not isinstance(section, dict) or section.get("admin_only"):
                    continue
                for field_index, field in enumerate(section.get("fields", [])):
                    field_key = field.get("key") if isinstance(field, dict) else None
                    if (
                        not isinstance(field, dict)
                        or field_key in restored_keys
                        or not str(field_key or "").startswith("custom_")
                        or field.get("type") == "document_upload"
                    ):
                        continue
                    retired_field = deepcopy(field)
                    origin = retired_field.get("retired_from")
                    if not isinstance(origin, dict) or not origin.get("section_key"):
                        origin = (
                            _historical_field_origin(locked_form, field_key)
                            if section.get("key") == "retired_fields"
                            else _field_origin(section, section_index, field_index, field)
                        )
                    if origin:
                        retired_field["retired_from"] = origin
                    retired_field["visible"] = False
                    retired_field["required"] = False
                    retired_fields.append(retired_field)
            if retired_fields:
                restored_sections = restored_schema.setdefault("sections", [])
                retired_section = next(
                    (
                        section for section in restored_sections
                        if isinstance(section, dict) and section.get("key") == "retired_fields"
                    ),
                    None,
                )
                if retired_section is None:
                    retired_section = {
                        "key": "retired_fields",
                        "title": "Retired fields",
                        "description": "Preserved for historical compatibility.",
                        "visible": False,
                        "fields": [],
                    }
                    restored_sections.append(retired_section)
                retired_section.setdefault("fields", []).extend(retired_fields)
            restored_schema = normalize_system_managed_sections(restored_schema, published_schema)
        validate_form_schema(restored_schema, published_schema=published_schema)
        locked_form.draft_schema_json = restored_schema
        locked_form.name = str(restored_schema.get("title") or locked_form.name)
        locked_form.description = str(restored_schema.get("description") or locked_form.description)
        locked_form.status = (
            CMSContributorForm.STATUS_PUBLISHED if reset_to_live else CMSContributorForm.STATUS_DRAFT
        )
        locked_form.has_unpublished_changes = not reset_to_live
        locked_form.review_notes = ""
        locked_form.updated_by = user if getattr(user, "is_authenticated", False) else locked_form.updated_by
        locked_form.lock_owner = None
        locked_form.lock_acquired_at = None
        locked_form.save(update_fields=[
            "draft_schema_json", "name", "description", "status", "has_unpublished_changes", "review_notes",
            "updated_by", "lock_owner", "lock_acquired_at", "updated_at",
        ])
        return locked_form


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
        return locked_page
