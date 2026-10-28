import hashlib
import json
import math

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.fields.json import KeyTextTransform
from django.http import Http404
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_engine.models import AIModelVersion
from ai_engine.serializers import AIModelVersionSerializer
from ai_engine.services import get_active_model, sync_training_record, training_dataset_summary

from cms.form_schema import FormSchemaError, SIMPLIFIED_FORM_KEY, default_simplified_form_schema
from cms.models import (
    CMSArticle,
    CMSCarouselItem,
    CMSContributorForm,
    CMSContributorFormVersion,
    CMSMediaAsset,
    CMSPage,
    CMSPageSection,
    CMSPublicationCategory,
    CMSPublicationDocument,
    CMSResolution,
    CMSSiteSetting,
)
from cms.serializers import (
    CMSArticleEditorSerializer,
    CMSArticleSerializer,
    CMSArticleSummarySerializer,
    CMSCarouselItemSerializer,
    CMSContributorFormSerializer,
    CMSContributorFormVersionSummarySerializer,
    CMSContributorFormVersionSerializer,
    CMSMediaAssetSerializer,
    CMSMediaAssetSummarySerializer,
    CMSPageEditorSerializer,
    CMSPageSectionSerializer,
    CMSPageSectionSummarySerializer,
    CMSPageSerializer,
    CMSPageSummarySerializer,
    CMSPublicationCategorySerializer,
    CMSPublicationDocumentSerializer,
    CMSResolutionSerializer,
    CMSSiteSettingSerializer,
)
from cms.registry import FIXED_CMS_PAGE_REGISTRY, fixed_page_definition, fixed_section_definition
from cms.services.locking import (
    acquire_form_lock,
    acquire_section_lock,
    heartbeat_form_lock,
    heartbeat_section_lock,
    lock_is_active,
    release_form_lock,
    release_section_lock,
)
from cms.services.media_usage import get_media_usages
from cms.services.media_validation import CMSMediaValidationError, extract_media_metadata, validate_media_upload
from cms.services.publishing import (
    mark_article_changed,
    mark_page_changed,
    publish_article,
    publish_contributor_form,
    publish_page,
    reorder_page_sections,
    restore_contributor_form_version,
)
from projects.models import (
    Notification,
    PriorityRuleSet,
    ProjectPriorityConfirmation,
    PublicEvent,
    User,
    UserActivity,
)
from projects.priority_scoring import (
    contextual_priority_rule_draft,
    get_active_priority_rule_set,
    priority_rule_config,
    validate_priority_rule_config,
)
from projects.serializers import PublicEventSerializer


class IsCMSUser(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", "") in {"admin", "content_editor"})


class IsCMSAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", "") == "admin")


class CMSSummaryPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        page_size = self.get_page_size(self.request) or self.page_size
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "page": self.page.number,
                "page_size": page_size,
                "total_pages": math.ceil(self.page.paginator.count / page_size) if page_size else 1,
                "results": data,
            }
        )


class CMSMediaPagination(CMSSummaryPagination):
    page_size = 10
    page_size_query_param = None


class CMSSummaryListMixin:
    """Enable the additive `?view=summary` contract without changing legacy lists."""

    summary_serializer_class = None
    pagination_class = CMSSummaryPagination

    def _summary_requested(self):
        return self.action == "list" and self.request.query_params.get("view") == "summary"

    def get_serializer_class(self):
        if self._summary_requested() and self.summary_serializer_class:
            return self.summary_serializer_class
        return super().get_serializer_class()

    def paginate_queryset(self, queryset):
        if not self._summary_requested():
            return None
        return super().paginate_queryset(queryset)


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR", "")


def _log_cms_activity(request, event, details=None):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None
    return UserActivity.objects.create(
        user=user,
        role=getattr(user, "role", ""),
        event=event,
        ip_address=_client_ip(request),
        details=details or {},
    )


def _notify_form_users(users, *, actor, form, event_type, title, message, dedupe_event):
    for recipient in users:
        if actor and recipient.pk == actor.pk:
            continue
        Notification.objects.update_or_create(
            dedupe_key=f"cms-form:{form.pk}:{dedupe_event}:user:{recipient.pk}",
            defaults={
                "recipient": recipient,
                "actor": actor,
                "event_type": event_type,
                "title": title,
                "message": message,
                "link_path": "/admin/forms",
            },
        )


def _form_editor_recipients(form):
    recipient_ids = {
        user_id
        for user_id in (form.submitted_by_id, form.updated_by_id)
        if user_id
    }
    return User.objects.filter(pk__in=recipient_ids, is_active=True)


def _with_public_cache(request, payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    etag = f'"{hashlib.sha256(canonical.encode("utf-8")).hexdigest()}"'
    candidates = [value.strip() for value in request.META.get("HTTP_IF_NONE_MATCH", "").split(",")]
    response = Response(status=status.HTTP_304_NOT_MODIFIED) if etag in candidates else Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "public, no-cache, must-revalidate"
    return response


def _with_private_cache(request, payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    etag = f'"{hashlib.sha256(canonical.encode("utf-8")).hexdigest()}"'
    candidates = [value.strip() for value in request.META.get("HTTP_IF_NONE_MATCH", "").split(",")]
    response = Response(status=status.HTTP_304_NOT_MODIFIED) if etag in candidates else Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "private, no-cache, must-revalidate"
    return response


def _published_snapshots(queryset):
    for obj in queryset:
        snapshot = obj.published_snapshot_json or {}
        if snapshot:
            yield obj, snapshot


class CMSWorkflowMixin:
    content_type_key = None

    def _serialize(self, obj):
        return self.get_serializer(obj).data

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        obj = self.get_object()
        if isinstance(obj, CMSPageSection):
            return Response({"detail": "Submit page sections together from the parent page."}, status=409)
        if obj.status not in {"draft", "rejected", "published"}:
            return Response({"detail": "Only draft, rejected, or edited published content can be submitted."}, status=400)
        if isinstance(obj, CMSPage):
            locked_elsewhere = [
                section for section in obj.sections.select_related("lock_owner")
                if lock_is_active(section) and section.lock_owner_id != request.user.id
            ]
            if locked_elsewhere:
                owners = sorted({section.lock_owner.get_full_name() or section.lock_owner.username for section in locked_elsewhere if section.lock_owner})
                return Response(
                    {"detail": f"Cannot submit while page sections are being edited by {', '.join(owners) or 'another editor'}. Save or release those section locks first."},
                    status=423,
                )
        obj.status = "submitted"
        if hasattr(obj, "submitted_by"):
            obj.submitted_by = request.user
        if hasattr(obj, "review_notes"):
            obj.review_notes = ""
        fields = ["status", "updated_at"]
        fields += [field for field in ("submitted_by", "review_notes") if hasattr(obj, field)]
        obj.save(update_fields=fields)
        if isinstance(obj, CMSPage):
            from cms.services.collections import submit_normalized_page_content
            submit_normalized_page_content(obj, request.user)
            for section_id in obj.sections.values_list("id", flat=True):
                release_section_lock(section_id, request.user, force=True)
        elif isinstance(obj, CMSPageSection):
            release_section_lock(obj.pk, request.user, force=getattr(request.user, "role", "") == "admin")
            mark_page_changed(obj.page, request.user)
        elif isinstance(obj, CMSContributorForm):
            release_form_lock(obj.pk, request.user, force=getattr(request.user, "role", "") == "admin")
        if isinstance(obj, CMSContributorForm):
            _notify_form_users(
                User.objects.filter(role="admin", is_active=True),
                actor=request.user,
                form=obj,
                event_type="cms_form_submitted",
                title="Contributor form awaiting review",
                message=f"{obj.name} was submitted for administrator review.",
                dedupe_event=f"submitted:{obj.updated_at.isoformat()}",
            )
        _log_cms_activity(request, "cms_content_submitted", {"content_type": self.content_type_key, "id": obj.pk})
        obj.refresh_from_db()
        return Response(self._serialize(obj))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def reject(self, request, pk=None):
        obj = self.get_object()
        if isinstance(obj, CMSPageSection):
            return Response({"detail": "Review page sections together from the parent page."}, status=409)
        if obj.status not in {"submitted", "draft"}:
            return Response({"detail": "Only submitted or draft content can be rejected."}, status=400)
        obj.status = "rejected"
        if hasattr(obj, "reviewed_by"):
            obj.reviewed_by = request.user
        if hasattr(obj, "review_notes"):
            obj.review_notes = str(request.data.get("remarks") or request.data.get("review_notes") or "Rejected by admin review.").strip()
        fields = ["status", "updated_at"]
        fields += [field for field in ("reviewed_by", "review_notes") if hasattr(obj, field)]
        obj.save(update_fields=fields)
        if isinstance(obj, CMSPageSection):
            release_section_lock(obj.pk, request.user, force=True)
        elif isinstance(obj, CMSContributorForm):
            release_form_lock(obj.pk, request.user, force=True)
        if isinstance(obj, CMSContributorForm):
            _notify_form_users(
                _form_editor_recipients(obj),
                actor=request.user,
                form=obj,
                event_type="cms_form_rejected",
                title="Contributor form changes requested",
                message=f"{obj.name} was returned for revision. {obj.review_notes}",
                dedupe_event=f"rejected:{obj.updated_at.isoformat()}",
            )
        _log_cms_activity(request, "cms_content_rejected", {"content_type": self.content_type_key, "id": obj.pk})
        obj.refresh_from_db()
        return Response(self._serialize(obj))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def archive(self, request, pk=None):
        obj = self.get_object()
        if obj.status == "archived":
            return Response({"detail": "Already archived."}, status=400)
        obj.status = "archived"
        fields = ["status", "updated_at"]
        if hasattr(obj, "archived_at"):
            obj.archived_at = timezone.now()
            fields.append("archived_at")
        if isinstance(obj, (CMSPage, CMSArticle)):
            obj.published_at = None
            fields.append("published_at")
        if isinstance(obj, CMSContributorForm):
            obj.current_published_version = None
            fields.append("current_published_version")
        obj.save(update_fields=fields)
        if isinstance(obj, CMSPageSection):
            release_section_lock(obj.pk, request.user, force=True)
            page = obj.page
            if page.published_at:
                page.published_snapshot_json = _page_snapshot(page)
                page.save(update_fields=["published_snapshot_json", "updated_at"])
        _log_cms_activity(request, "cms_content_archived", {"content_type": self.content_type_key, "id": obj.pk})
        obj.refresh_from_db()
        return Response(self._serialize(obj))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def restore(self, request, pk=None):
        obj = self.get_object()
        if obj.status != "archived":
            return Response({"detail": "Only archived items can be restored."}, status=400)
        obj.status = "draft"
        fields = ["status", "updated_at"]
        if hasattr(obj, "archived_at"):
            obj.archived_at = None
            fields.append("archived_at")
        obj.save(update_fields=fields)
        if isinstance(obj, CMSPageSection):
            mark_page_changed(obj.page, request.user)
        _log_cms_activity(request, "cms_content_restored", {"content_type": self.content_type_key, "id": obj.pk})
        return Response(self._serialize(obj))


def _page_snapshot(page):
    # Imported lazily to keep all public snapshot construction in one service.
    from cms.services.snapshots import build_page_snapshot

    return build_page_snapshot(page)


class AdminCMSPageViewSet(CMSSummaryListMixin, CMSWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = CMSPageSerializer
    summary_serializer_class = CMSPageSummarySerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    content_type_key = "page"

    def get_serializer_class(self):
        if self.action != "list" and self.request.query_params.get("view") == "editor":
            return CMSPageEditorSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        if self._summary_requested():
            queryset = CMSPage.objects.annotate(
                section_count=Count("sections", distinct=True),
                published_slug=KeyTextTransform("slug", "published_snapshot_json"),
            ).only(
                "id", "title", "slug", "status", "has_unpublished_changes", "review_notes",
                "published_at", "archived_at", "updated_at",
            )
        else:
            queryset = CMSPage.objects.prefetch_related("sections").select_related(
                "created_by", "updated_by", "submitted_by", "reviewed_by"
            )
            if self.action == "retrieve" and self.request.query_params.get("view") == "editor":
                queryset = queryset.defer("published_snapshot_json")
        queryset = queryset.filter(slug__in=FIXED_CMS_PAGE_REGISTRY)
        status_filter = self.request.query_params.get("status")
        if self.action == "list" and not status_filter:
            queryset = queryset.filter(status="archived") if self.request.query_params.get("archived") == "1" else queryset.exclude(status="archived")
        search = str(self.request.query_params.get("q") or "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(slug__icontains=search))
        return queryset.order_by("slug")

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Public pages are fixed by the application and cannot be created."}, status=405)

    def update(self, request, *args, **kwargs):
        return Response({"detail": "Page titles, slugs, and structure are fixed by the application."}, status=405)

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "CMS pages are archived instead of hard-deleted."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        page = self.get_object()
        if page.status == "archived":
            return Response({"detail": "Archived pages cannot be published."}, status=400)
        page = publish_page(page, user=request.user)
        _log_cms_activity(request, "cms_content_published", {"content_type": "page", "id": page.pk, "slug": page.slug})
        return Response(self._serialize(page))

    @action(detail=True, methods=["post"])
    def reorder_sections(self, request, pk=None):
        return Response({"detail": "Page section order is fixed by the application."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def archive(self, request, pk=None):
        return Response({"detail": "Fixed public pages cannot be archived."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def restore(self, request, pk=None):
        return Response({"detail": "Fixed public pages cannot be restored or replaced."}, status=405)


class AdminCMSPageSectionViewSet(CMSWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = CMSPageSectionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    content_type_key = "section"

    def get_queryset(self):
        queryset = CMSPageSection.objects.select_related("page", "lock_owner")
        allowed = Q(pk__in=[])
        for slug, definition in FIXED_CMS_PAGE_REGISTRY.items():
            allowed |= Q(page__slug=slug, section_key__in=[row[0] for row in definition["sections"]])
        queryset = queryset.filter(allowed)
        page_id = self.request.query_params.get("page")
        status_filter = self.request.query_params.get("status")
        if self.action == "list" and not status_filter:
            queryset = queryset.filter(status="archived") if self.request.query_params.get("archived") == "1" else queryset.exclude(status="archived")
        if page_id:
            queryset = queryset.filter(page_id=page_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by("page_id", "order", "id")

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Page sections are fixed by the application and cannot be created."}, status=405)

    def update(self, request, *args, **kwargs):
        section = self.get_object()
        definition = fixed_section_definition(section.page.slug, section.section_key)
        if not definition:
            return Response({"detail": "This is not an editable fixed page section."}, status=404)
        for field, current in (
            ("page", section.page_id), ("section_key", section.section_key),
            ("section_type", definition["type"]), ("order", definition["order"]),
            ("is_visible", True),
        ):
            if field in request.data and request.data.get(field) != current:
                return Response({field: "This structural field is fixed by the application."}, status=400)
        if section.status == "archived":
            raise PermissionDenied("Archived sections cannot be edited.")
        if section.page.status == "submitted" and getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Sections in a submitted page can only be changed after the page is returned for revision.")
        if section.status == "submitted" and getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted sections can only be changed by an administrator.")
        if lock_is_active(section) and section.lock_owner_id != request.user.id:
            return Response(
                {"detail": f"Currently being edited by {section.lock_owner.get_full_name() or section.lock_owner.username}.", "lock_owner": section.lock_owner_id},
                status=423,
            )
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        section = serializer.save(status="draft", lock_owner=None, lock_acquired_at=None)
        from cms.services.collections import sync_normalized_section_draft
        sync_normalized_section_draft(section, self.request.user)
        mark_page_changed(section.page, self.request.user)
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "section", "id": section.pk, "page": section.page_id})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Fixed page sections cannot be deleted."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def archive(self, request, pk=None):
        return Response({"detail": "Fixed page sections cannot be archived."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def restore(self, request, pk=None):
        return Response({"detail": "Fixed page sections cannot be restored or replaced."}, status=405)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        section = self.get_object()
        old_owner_id = section.lock_owner_id if lock_is_active(section) else None
        old_owner_name = (section.lock_owner.get_full_name() or section.lock_owner.username) if old_owner_id and section.lock_owner else ""
        is_admin = getattr(request.user, "role", "") == "admin"
        if old_owner_id and old_owner_id != request.user.id and is_admin and not request.data.get("override_confirmed"):
            return Response({"detail": "Confirm the section lock override before taking over this section."}, status=409)
        section, acquired = acquire_section_lock(pk, request.user, force=is_admin)
        event = "cms_section_lock_overridden" if acquired and old_owner_id and old_owner_id != request.user.id else (
            "cms_section_lock_acquired" if acquired else "cms_section_lock_blocked"
        )
        _log_cms_activity(
            request, event,
            {
                "section_id": section.pk,
                "lock_owner": section.lock_owner_id,
                "previous_lock_owner": old_owner_id,
                "previous_lock_owner_name": old_owner_name,
            },
        )
        return Response(self.get_serializer(section).data, status=200 if acquired else 423)

    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        section, released = release_section_lock(pk, request.user, force=getattr(request.user, "role", "") == "admin")
        if not released:
            return Response({"detail": "Only the lock owner or an administrator can release this lock."}, status=423)
        _log_cms_activity(request, "cms_section_lock_released", {"section_id": section.pk})
        return Response(self.get_serializer(section).data)

    @action(detail=True, methods=["post"])
    def heartbeat(self, request, pk=None):
        section, refreshed = heartbeat_section_lock(pk, request.user)
        if not refreshed:
            return Response({"detail": "The section lock is no longer owned by this user."}, status=409)
        return Response(self.get_serializer(section).data)

    @action(detail=True, methods=["post"], url_path="request-access")
    def request_access(self, request, pk=None):
        section = self.get_object()
        if not lock_is_active(section) or not section.lock_owner_id or section.lock_owner_id == request.user.id:
            return Response({"detail": "This section is not locked by another editor."}, status=400)
        Notification.objects.update_or_create(
            dedupe_key=f"cms-section-access-{section.pk}-{request.user.pk}-{section.lock_owner_id}",
            defaults={
                "recipient": section.lock_owner,
                "actor": request.user,
                "event_type": "cms_section_access_requested",
                "title": "CMS section access requested",
                "message": f"{request.user.get_full_name() or request.user.username} requested access to {section.page.title}: {section.section_key}.",
                "link_path": "/employee/cms/pages/" + section.page.slug,
            },
        )
        _log_cms_activity(request, "cms_section_access_requested", {"section_id": section.pk, "owner": section.lock_owner_id})
        return Response({"detail": "Access request sent to the current editor."})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        self.get_object()
        return Response({"detail": "Publish page sections together from the parent page."}, status=409)


class AdminCMSArticleViewSet(CMSSummaryListMixin, CMSWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = CMSArticleSerializer
    summary_serializer_class = CMSArticleSummarySerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    content_type_key = "article"

    def get_serializer_class(self):
        if self.action != "list" and self.request.query_params.get("view") == "editor":
            return CMSArticleEditorSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        if self._summary_requested():
            queryset = CMSArticle.objects.select_related("thumbnail").annotate(
                published_slug=KeyTextTransform("slug", "published_snapshot_json"),
            ).only(
                "id", "title", "slug", "category", "summary", "thumbnail", "author",
                "publication_date", "featured", "status", "has_unpublished_changes", "review_notes",
                "published_at", "archived_at", "updated_at", "thumbnail__is_archived",
                "thumbnail__public_url", "thumbnail__file",
            )
        else:
            queryset = CMSArticle.objects.select_related(
                "thumbnail", "created_by", "updated_by", "submitted_by", "reviewed_by"
            )
            if self.action == "retrieve" and self.request.query_params.get("view") == "editor":
                queryset = queryset.defer("published_snapshot_json")
        if self.action == "list" and not self.request.query_params.get("status"):
            queryset = queryset.filter(status="archived") if self.request.query_params.get("archived") == "1" else queryset.exclude(status="archived")
        for key, lookup in (("status", "status"), ("category", "category__iexact")):
            value = self.request.query_params.get(key)
            if value:
                queryset = queryset.filter(**{lookup: value})
        search = str(self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(slug__icontains=search)
                | Q(summary__icontains=search)
                | Q(author__icontains=search)
            )
        return queryset.order_by("-updated_at")

    def perform_create(self, serializer):
        article = serializer.save(created_by=self.request.user, updated_by=self.request.user, has_unpublished_changes=True)
        _log_cms_activity(self.request, "cms_content_created", {"content_type": "article", "id": article.pk, "slug": article.slug})

    def perform_update(self, serializer):
        if serializer.instance.status == "archived":
            raise PermissionDenied("Archived articles cannot be edited.")
        if serializer.instance.status == "submitted" and getattr(self.request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted or archived articles can only be changed by an administrator.")
        article = serializer.save(updated_by=self.request.user, has_unpublished_changes=True, status="draft")
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "article", "id": article.pk, "slug": article.slug})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "CMS news articles are archived instead of hard-deleted."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        article = self.get_object()
        if article.status == "archived":
            return Response({"detail": "Archived articles cannot be published."}, status=400)
        article = publish_article(article, user=request.user)
        _log_cms_activity(request, "cms_content_published", {"content_type": "article", "id": article.pk, "slug": article.slug})
        return Response(self._serialize(article))


from cms.services.collections import managed_content_snapshot


class CMSManagedContentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    search_fields = ()
    content_type_key = "content"

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            "created_by", "updated_by", "submitted_by", "reviewed_by"
        )
        if self.action == "list" and not self.request.query_params.get("status"):
            queryset = queryset.filter(status="archived") if self.request.query_params.get("archived") == "1" else queryset.exclude(status="archived")
        status_filter = str(self.request.query_params.get("status") or "").strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        search = str(self.request.query_params.get("q") or "").strip()
        if search and self.search_fields:
            criteria = Q()
            for field in self.search_fields:
                criteria |= Q(**{f"{field}__icontains": search})
            queryset = queryset.filter(criteria)
        return queryset

    def perform_create(self, serializer):
        obj = serializer.save(
            status="draft", created_by=self.request.user, updated_by=self.request.user,
            has_unpublished_changes=True,
        )
        _log_cms_activity(self.request, "cms_content_created", {"content_type": self.content_type_key, "id": obj.pk})

    def perform_update(self, serializer):
        obj = serializer.instance
        if obj.status == "archived":
            raise PermissionDenied("Archived content must be restored before editing.")
        if obj.status == "submitted" and getattr(self.request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted content can only be changed after administrator review.")
        obj = serializer.save(
            status="draft", updated_by=self.request.user, has_unpublished_changes=True,
        )
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": self.content_type_key, "id": obj.pk})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "CMS content is archived instead of hard-deleted."}, status=405)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        obj = self.get_object()
        if obj.status not in {"draft", "rejected", "published"}:
            return Response({"detail": "Only draft, rejected, or edited published content can be submitted."}, status=400)
        obj.status = "submitted"
        obj.submitted_by = request.user
        obj.review_notes = ""
        obj.save(update_fields=["status", "submitted_by", "review_notes", "updated_at"])
        _log_cms_activity(request, "cms_content_submitted", {"content_type": self.content_type_key, "id": obj.pk})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        with transaction.atomic():
            obj = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if obj.status == "archived":
                return Response({"detail": "Archived content cannot be published."}, status=400)
            obj.published_snapshot_json = managed_content_snapshot(obj)
            obj.status = "published"
            obj.has_unpublished_changes = False
            obj.published_at = timezone.now()
            obj.archived_at = None
            obj.reviewed_by = request.user
            obj.updated_by = request.user
            obj.review_notes = str(request.data.get("review_notes") or "").strip()
            obj.save(update_fields=[
                "published_snapshot_json", "status", "has_unpublished_changes", "published_at",
                "archived_at", "reviewed_by", "updated_by", "review_notes", "updated_at",
            ])
        _log_cms_activity(request, "cms_content_published", {"content_type": self.content_type_key, "id": obj.pk})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def reject(self, request, pk=None):
        obj = self.get_object()
        if obj.status not in {"submitted", "draft"}:
            return Response({"detail": "Only submitted or draft content can be rejected."}, status=400)
        obj.status = "rejected"
        obj.reviewed_by = request.user
        obj.review_notes = str(request.data.get("review_notes") or request.data.get("remarks") or "Changes requested.").strip()
        obj.save(update_fields=["status", "reviewed_by", "review_notes", "updated_at"])
        _log_cms_activity(request, "cms_content_rejected", {"content_type": self.content_type_key, "id": obj.pk})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def archive(self, request, pk=None):
        obj = self.get_object()
        if obj.status == "archived":
            return Response({"detail": "Content is already archived."}, status=409)
        obj.status = "archived"
        obj.archived_at = timezone.now()
        obj.reviewed_by = request.user
        obj.save(update_fields=["status", "archived_at", "reviewed_by", "updated_at"])
        _log_cms_activity(request, "cms_content_archived", {"content_type": self.content_type_key, "id": obj.pk})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def restore(self, request, pk=None):
        obj = self.get_queryset().model.objects.filter(pk=pk).first()
        if not obj:
            raise Http404("Content not found.")
        if obj.status != "archived":
            return Response({"detail": "Only archived content can be restored."}, status=409)
        obj.status = "draft"
        obj.archived_at = None
        obj.has_unpublished_changes = True
        obj.updated_by = request.user
        obj.save(update_fields=["status", "archived_at", "has_unpublished_changes", "updated_by", "updated_at"])
        _log_cms_activity(request, "cms_content_restored", {"content_type": self.content_type_key, "id": obj.pk})
        return Response(self.get_serializer(obj).data)


class AdminCMSCarouselItemViewSet(CMSManagedContentViewSet):
    queryset = CMSCarouselItem.objects.select_related("image")
    serializer_class = CMSCarouselItemSerializer
    search_fields = ("title", "description")
    content_type_key = "carousel_item"


class AdminCMSPublicationCategoryViewSet(CMSManagedContentViewSet):
    queryset = CMSPublicationCategory.objects.annotate(document_count=Count("documents", distinct=True))
    serializer_class = CMSPublicationCategorySerializer
    search_fields = ("code", "name", "description")
    content_type_key = "publication_category"

    @action(detail=True, methods=["get"])
    def dependencies(self, request, pk=None):
        category = self.get_object()
        serializer = self.get_serializer(category)
        return Response({
            "category": {"id": category.pk, "code": category.code, "name": category.name},
            "documents": category.documents.values("status").annotate(count=Count("id")).order_by("status"),
            "featured_slots": serializer.data["featured_slots"],
        })

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def archive(self, request, pk=None):
        category = self.get_object()
        serialized = self.get_serializer(category).data
        featured_slots = serialized["featured_slots"]
        replacement_code = str(request.data.get("replacement_category") or "").strip()
        replacement = None
        if featured_slots:
            replacement = CMSPublicationCategory.objects.filter(
                code__iexact=replacement_code, status="published",
            ).exclude(pk=category.pk).first()
            if not replacement:
                return Response({
                    "detail": "Choose a different published category to replace this Home page feature.",
                    "featured_slots": featured_slots,
                }, status=409)

        active_documents = category.documents.exclude(status="archived")
        if active_documents.exists():
            resolution = str(request.data.get("document_resolution") or "").strip()
            if resolution == "reassign":
                target = CMSPublicationCategory.objects.filter(
                    code__iexact=str(request.data.get("target_category") or "").strip()
                ).exclude(pk=category.pk).exclude(status="archived").first()
                if not target:
                    return Response({"detail": "Choose an active target category for the documents."}, status=409)
                active_documents.update(category=target, updated_by=request.user, has_unpublished_changes=True)
            elif resolution == "archive_documents":
                active_documents.update(status="archived", archived_at=timezone.now(), reviewed_by=request.user)
            else:
                return Response({
                    "detail": "Reassign or archive the associated documents before archiving this category.",
                    "document_count": active_documents.count(),
                }, status=409)

        if replacement:
            home = CMSPage.objects.filter(slug="home").first()
            if home:
                for section in home.sections.filter(section_key__in=featured_slots):
                    content = dict(section.content_json or {})
                    content["featuredCategoryCode"] = replacement.code
                    section.content_json = content
                    section.status = "published"
                    section.save(update_fields=["content_json", "status", "updated_at"])
                publish_page(home, user=request.user)
        return super().archive(request, pk=pk)


class AdminCMSPublicationDocumentViewSet(CMSManagedContentViewSet):
    queryset = CMSPublicationDocument.objects.select_related("category", "attachment")
    serializer_class = CMSPublicationDocumentSerializer
    search_fields = ("stable_key", "title", "description", "category__name")
    content_type_key = "publication_document"

    def get_queryset(self):
        queryset = super().get_queryset()
        category = str(self.request.query_params.get("category") or "").strip()
        return queryset.filter(category__code=category) if category else queryset


class AdminCMSResolutionViewSet(CMSManagedContentViewSet):
    queryset = CMSResolution.objects.select_related("attachment")
    serializer_class = CMSResolutionSerializer
    search_fields = ("stable_key", "resolution_number", "title", "description")
    content_type_key = "resolution"

    def get_queryset(self):
        queryset = super().get_queryset()
        year = str(self.request.query_params.get("year") or "").strip()
        return queryset.filter(year=year) if year.isdigit() else queryset


def _fixed_module_page(slug):
    definition = fixed_page_definition(slug)
    if not definition:
        raise Http404("Content module not found.")
    page = CMSPage.objects.prefetch_related("sections").select_related(
        "created_by", "updated_by", "submitted_by", "reviewed_by"
    ).filter(slug=slug).first()
    if not page:
        raise Http404("The fixed content module has not been provisioned.")
    return page


class AdminCMSModuleListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get(self, request):
        pages = {
            page.slug: page for page in CMSPage.objects.filter(slug__in=FIXED_CMS_PAGE_REGISTRY)
        }
        return Response([
            {
                "slug": slug, "title": definition["title"],
                "status": pages[slug].status if slug in pages else "missing",
                "has_unpublished_changes": pages[slug].has_unpublished_changes if slug in pages else False,
                "updated_at": pages[slug].updated_at if slug in pages else None,
                "section_keys": [item[0] for item in definition["sections"]],
            }
            for slug, definition in FIXED_CMS_PAGE_REGISTRY.items()
        ])


class AdminCMSModuleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get(self, request, slug):
        page = _fixed_module_page(slug)
        return Response(CMSPageEditorSerializer(page, context={"request": request}).data)

    def patch(self, request, slug):
        page = _fixed_module_page(slug)
        if page.status == "submitted" and getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted content must be returned before it can be edited.")
        sections_payload = request.data.get("sections")
        if not isinstance(sections_payload, dict) or not sections_payload:
            return Response({"sections": "Provide one or more fixed section content objects."}, status=400)
        definition = fixed_page_definition(slug)
        allowed = {item[0]: {"type": item[1], "order": index} for index, item in enumerate(definition["sections"], 1)}
        unknown = sorted(set(sections_payload) - set(allowed))
        if unknown:
            return Response({"sections": f"Unknown fixed section keys: {', '.join(unknown)}"}, status=400)
        with transaction.atomic():
            locked_page = CMSPage.objects.select_for_update().get(pk=page.pk)
            expected = str(request.data.get("expected_updated_at") or "").strip()
            if expected and expected != locked_page.updated_at.isoformat().replace("+00:00", "Z") and expected != locked_page.updated_at.isoformat():
                return Response({"detail": "This module changed after it was loaded. Refresh before saving."}, status=409)
            section_rows = {row.section_key: row for row in CMSPageSection.objects.select_for_update().filter(page=locked_page)}
            for key, content in sections_payload.items():
                if not isinstance(content, dict):
                    return Response({"sections": {key: "Section content must be an object."}}, status=400)
                row = section_rows.get(key)
                if not row:
                    return Response({"sections": {key: "The fixed section record is missing."}}, status=409)
                if lock_is_active(row) and row.lock_owner_id != request.user.id:
                    return Response({"detail": f"{key} is currently being edited by another user."}, status=423)
                section_serializer = CMSPageSectionSerializer(
                    row, data={"content_json": content}, partial=True, context={"request": request},
                )
                section_serializer.is_valid(raise_exception=True)
                row = section_serializer.save(content_json=content)
                row.section_type = allowed[key]["type"]
                row.order = allowed[key]["order"]
                row.is_visible = True
                row.status = "draft"
                row.lock_owner = None
                row.lock_acquired_at = None
                row.save(update_fields=[
                    "content_json", "section_type", "order", "is_visible", "status",
                    "lock_owner", "lock_acquired_at", "updated_at",
                ])
                from cms.services.collections import sync_normalized_section_draft
                sync_normalized_section_draft(row, request.user)
            locked_page.status = "draft"
            locked_page.has_unpublished_changes = True
            locked_page.updated_by = request.user
            locked_page.save(update_fields=["status", "has_unpublished_changes", "updated_by", "updated_at"])
        _log_cms_activity(request, "cms_content_updated", {"content_type": "module", "slug": slug, "sections": sorted(sections_payload)})
        return Response(CMSPageEditorSerializer(_fixed_module_page(slug), context={"request": request}).data)


class AdminCMSModuleActionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def post(self, request, slug, operation):
        page = _fixed_module_page(slug)
        if operation == "submit":
            if page.status not in {"draft", "rejected", "published"}:
                return Response({"detail": "This module cannot be submitted in its current state."}, status=409)
            page.status = "submitted"
            page.submitted_by = request.user
            page.review_notes = ""
            page.save(update_fields=["status", "submitted_by", "review_notes", "updated_at"])
            from cms.services.collections import submit_normalized_page_content
            submit_normalized_page_content(page, request.user)
        elif operation == "publish":
            if getattr(request.user, "role", "") != "admin":
                raise PermissionDenied("Only Administrators can publish public content.")
            page = publish_page(page, user=request.user)
        elif operation == "reject":
            if getattr(request.user, "role", "") != "admin":
                raise PermissionDenied("Only Administrators can reject public content.")
            if page.status not in {"submitted", "draft"}:
                return Response({"detail": "Only submitted or draft modules can be rejected."}, status=409)
            page.status = "rejected"
            page.reviewed_by = request.user
            page.review_notes = str(request.data.get("review_notes") or "Changes requested.").strip()
            page.save(update_fields=["status", "reviewed_by", "review_notes", "updated_at"])
        else:
            raise Http404("Unsupported module action.")
        _log_cms_activity(request, f"cms_content_{operation}", {"content_type": "module", "slug": slug})
        return Response(CMSPageEditorSerializer(page, context={"request": request}).data)


class AdminCMSContributorFormViewSet(CMSWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = CMSContributorFormSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSAdmin]
    content_type_key = "form"
    http_method_names = ["get", "patch", "put", "post", "head", "options"]

    def get_queryset(self):
        queryset = CMSContributorForm.objects.select_related(
            "current_published_version", "created_by", "updated_by", "submitted_by", "reviewed_by", "lock_owner"
        )
        if self.action == "list":
            queryset = queryset.filter(status="archived") if self.request.query_params.get("archived") == "1" else queryset.exclude(status="archived")
        if self.request.query_params.get("include_versions") == "summary":
            queryset = queryset.prefetch_related(
                Prefetch(
                    "versions",
                    queryset=CMSContributorFormVersion.objects.select_related("published_by").only(
                        "id", "form_id", "version_number", "schema_json", "published_by_id", "published_at",
                        "published_by__username", "published_by__first_name", "published_by__last_name",
                    ).order_by("-version_number"),
                    to_attr="cms_version_summaries",
                )
            )
        return queryset.order_by("name")

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Contributor form definitions are provisioned by the system."}, status=405)

    def update(self, request, *args, **kwargs):
        form = self.get_object()
        if form.status == CMSContributorForm.STATUS_SUBMITTED and getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted forms can only be changed by an administrator.")
        if not lock_is_active(form) or form.lock_owner_id != request.user.id:
            return Response({"detail": "Acquire the form editing lock before saving."}, status=423)
        try:
            return super().update(request, *args, **kwargs)
        except serializers.ValidationError as exc:
            if "detail" in getattr(exc, "detail", {}):
                return Response(exc.detail, status=409)
            raise

    def perform_update(self, serializer):
        form = serializer.save(
            updated_by=self.request.user,
            has_unpublished_changes=True,
            status=CMSContributorForm.STATUS_DRAFT,
            review_notes="",
            lock_owner=None,
            lock_acquired_at=None,
        )
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "form", "id": form.pk, "key": form.key})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Contributor forms cannot be deleted or archived."}, status=405)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only administrators can archive contributor forms.")
        return CMSWorkflowMixin.archive(self, request, pk)

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        current = self.get_object()
        previous_owner_id = current.lock_owner_id if lock_is_active(current) else None
        previous_owner_name = (
            current.lock_owner.get_full_name() or current.lock_owner.username
            if previous_owner_id and current.lock_owner
            else ""
        )
        force = request.data.get("force") is True
        if force and previous_owner_id and previous_owner_id != request.user.id:
            if getattr(request.user, "role", "") != "admin":
                raise PermissionDenied("Only administrators can take over another editor's form lock.")
            if request.data.get("confirm_takeover") is not True:
                return Response({"detail": "Confirm the form lock takeover first."}, status=400)
        form, acquired = acquire_form_lock(pk, request.user, force=force)
        overridden = bool(acquired and previous_owner_id and previous_owner_id != request.user.id)
        _log_cms_activity(
            request,
            "cms_form_lock_overridden" if overridden else "cms_form_lock_acquired" if acquired else "cms_form_lock_blocked",
            {
                "form_id": form.pk,
                "lock_owner": form.lock_owner_id,
                "previous_lock_owner": previous_owner_id,
                "previous_lock_owner_name": previous_owner_name,
            },
        )
        return Response(self.get_serializer(form).data, status=200 if acquired else 423)

    @action(detail=True, methods=["post"])
    def unlock(self, request, pk=None):
        form, released = release_form_lock(pk, request.user, force=getattr(request.user, "role", "") == "admin")
        if not released:
            return Response({"detail": "Only the lock owner or an administrator can release this lock."}, status=423)
        _log_cms_activity(request, "cms_form_lock_released", {"form_id": form.pk})
        return Response(self.get_serializer(form).data)

    @action(detail=True, methods=["post"])
    def heartbeat(self, request, pk=None):
        form, refreshed = heartbeat_form_lock(pk, request.user)
        if not refreshed:
            return Response({"detail": "The form lock is no longer owned by this user."}, status=409)
        return Response(self.get_serializer(form).data)

    @action(detail=True, methods=["post"], url_path="request-access")
    def request_access(self, request, pk=None):
        form = self.get_object()
        if not lock_is_active(form) or not form.lock_owner_id or form.lock_owner_id == request.user.id:
            return Response({"detail": "This form is not locked by another editor."}, status=400)
        Notification.objects.update_or_create(
            dedupe_key=f"cms-form-access-{form.pk}-{request.user.pk}-{form.lock_owner_id}",
            defaults={
                "recipient": form.lock_owner,
                "actor": request.user,
                "event_type": "cms_form_access_requested",
                "title": "Contributor form access requested",
                "message": f"{request.user.get_full_name() or request.user.username} requested access to {form.name}.",
                "link_path": "/admin/forms",
            },
        )
        _log_cms_activity(
            request, "cms_form_access_requested",
            {"form_id": form.pk, "lock_owner": form.lock_owner_id},
        )
        return Response({"detail": "Access request sent to the current editor."})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        target = self.get_object()
        if not target.has_unpublished_changes:
            return Response({"detail": "This contributor form has no unpublished changes."}, status=400)
        editor_recipients = list(_form_editor_recipients(target))
        try:
            form = publish_contributor_form(target, user=request.user)
        except FormSchemaError as exc:
            return Response({"detail": str(exc)}, status=400)
        _notify_form_users(
            editor_recipients,
            actor=request.user,
            form=form,
            event_type="cms_form_published",
            title="Contributor form published",
            message=(
                f"{form.name} version {form.current_published_version.version_number} was published."
            ),
            dedupe_event=f"published:{form.current_published_version.version_number}",
        )
        _log_cms_activity(request, "cms_content_published", {"content_type": "form", "id": form.pk, "key": form.key})
        return Response(self._serialize(form))

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        form = self.get_object()
        versions = form.versions.select_related("published_by").all()
        version_id = request.query_params.get("version_id")
        if version_id:
            version = versions.filter(pk=version_id).first()
            if version is None:
                return Response({"detail": "Published form version not found."}, status=404)
            return Response(CMSContributorFormVersionSerializer(version).data)
        serializer_class = (
            CMSContributorFormVersionSummarySerializer
            if request.query_params.get("view") == "summary"
            else CMSContributorFormVersionSerializer
        )
        return Response(serializer_class(versions, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsCMSAdmin],
        url_path="restore-version",
    )
    def restore_version(self, request, pk=None):
        form = self.get_object()
        try:
            version_id = int(request.data.get("version_id") or 0)
        except (TypeError, ValueError):
            version_id = 0
        version = form.versions.filter(pk=version_id).first()
        if version is None:
            return Response({"detail": "Published form version not found."}, status=404)
        try:
            form = restore_contributor_form_version(form, version, user=request.user)
        except FormSchemaError as exc:
            return Response({"detail": str(exc)}, status=400)
        _log_cms_activity(
            request, "cms_content_restored",
            {"content_type": "form", "id": form.pk, "restored_from_version": version.version_number},
        )
        return Response(self._serialize(form))


class ContributorFormCurrentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, key):
        form = CMSContributorForm.objects.select_related("current_published_version").filter(key=key).first()
        if form and form.status == "archived":
            raise Http404("Contributor form is archived.")
        if not form or not form.current_published_version:
            if key != SIMPLIFIED_FORM_KEY:
                raise Http404("Published contributor form not found.")
            payload = {"key": key, "name": "Simplified RDIP Contributor Form", "version": 1, "schema": default_simplified_form_schema()}
        else:
            version = form.current_published_version
            payload = {
                "key": form.key,
                "name": form.name,
                "version": version.version_number,
                "schema": version.schema_json,
                "published_at": version.published_at,
            }
        return _with_private_cache(request, payload)


class ContributorFormVersionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, key, version_number):
        version = CMSContributorFormVersion.objects.select_related("form").filter(
            form__key=key, version_number=version_number,
        ).first()
        if version is None:
            if key != SIMPLIFIED_FORM_KEY or version_number != 1:
                raise Http404("Contributor form version not found.")
            payload = {"key": key, "name": "Simplified RDIP Contributor Form", "version": 1, "schema": default_simplified_form_schema()}
        else:
            payload = {
                "key": version.form.key,
                "name": version.form.name,
                "version": version.version_number,
                "schema": version.schema_json,
                "published_at": version.published_at,
            }
        return _with_private_cache(request, payload)


def _priority_reference_payload(limit=200):
    active = get_active_priority_rule_set()
    active_model = get_active_model()
    groq_enabled = bool(getattr(settings, "GROQ_ENABLED", False))
    history = PriorityRuleSet.objects.annotate(analysis_count=Count("analyses")).order_by("-created_at")[:20]
    confirmations = ProjectPriorityConfirmation.objects.select_related(
        "analysis__project",
        "analysis__rule_set",
        "validator",
        "ai_training_record",
    ).order_by("-created_at")[:limit]
    active_reference_record_ids = set(
        active_model.dataset_memberships.values_list("training_record_id", flat=True)
    ) if active_model else set()
    historical_projects = []
    for confirmation in confirmations:
        analysis = confirmation.analysis
        project = analysis.project
        try:
            training_record = confirmation.ai_training_record
        except ObjectDoesNotExist:
            # Older/imported confirmations may predate automatic record creation.
            # Repair only the missing row being displayed instead of rescanning the dataset.
            training_record = sync_training_record(confirmation)
        snapshot = analysis.input_snapshot if isinstance(analysis.input_snapshot, dict) else {}
        form = snapshot.get("simplified_form")
        if not isinstance(form, dict):
            form = snapshot
        historical_projects.append(
            {
                "confirmation_id": confirmation.pk,
                "project_id": project.pk,
                "project_title": project.name,
                "agency": project.agency or project.implementing_agency,
                "sector": str(form.get("developmentSector") or form.get("mainInfrastructureSector") or ""),
                "submission_type": str(snapshot.get("submission_type") or ("simplified" if "simplified_form" in snapshot else "detailed")),
                "project_status": project.status,
                "suggested_priority": analysis.suggested_priority,
                "final_priority": confirmation.final_priority,
                "base_score": float(analysis.base_score),
                "rule_version": analysis.rule_set.version,
                "validator_name": (
                    confirmation.validator.get_full_name().strip()
                    or confirmation.validator.username
                ) if confirmation.validator else "",
                "override_rationale": confirmation.override_rationale,
                "confirmed_at": confirmation.created_at,
                "training_record_id": training_record.pk if training_record else None,
                "training_eligible": training_record.is_eligible if training_record else False,
                "in_active_reference": bool(
                    training_record and training_record.pk in active_reference_record_ids
                ),
                "exclusion_reason": training_record.exclusion_reason if training_record else "Pending dataset synchronization.",
            }
        )
    training_dataset = training_dataset_summary()
    return {
        "system_type": "groq_rag_rules" if groq_enabled else "hybrid_rules_similarity_ml",
        "learns_from_historical_projects": True,
        "learning_explanation": (
            "The active CMS rules and current project evidence remain the primary scoring method. An administrator can "
            "curate validator-confirmed projects and rebuild a versioned historical reference model. Groq then receives "
            "the most similar projects, their rule scores, and their human-confirmed outcomes as secondary calibration "
            "context. This is retrieval-augmented generation, not fine-tuning of the hosted Groq model, and the validator "
            "always makes the final decision."
            if groq_enabled else
            "The engine applies the active versioned rules first, then an administrator can train a separate, "
            "versioned model using only validator-confirmed project outcomes. It also compares each project with "
            "confirmed historical projects. The learned prediction remains advisory and never changes a validator's final decision."
        ),
        "ai_provider": {
            "name": "groq" if groq_enabled else "local",
            "enabled": groq_enabled,
            "primary_model": getattr(settings, "GROQ_PRIMARY_MODEL", "") if groq_enabled else "",
            "backup_model": getattr(settings, "GROQ_BACKUP_MODEL", "") if groq_enabled else "",
            "historical_mode": "versioned_rag_calibration" if groq_enabled else "trained_local_model",
        },
        "rag_pipeline": {
            "rules_primary": True,
            "hosted_model_fine_tuned": False,
            "retrieval_limit": 6,
            "reference_model_version": active_model.version if active_model else "",
            "dataset_version": training_dataset["dataset_version"],
            "reference_dataset_current": training_dataset["is_current"],
            "requires_retraining": training_dataset["requires_retraining"],
            "steps": [
                {
                    "key": "confirm",
                    "title": "Human-confirmed projects",
                    "description": "Only projects with a validator-confirmed final priority can become references.",
                },
                {
                    "key": "curate",
                    "title": "Administrator curation",
                    "description": "Administrators include suitable records or exclude unreliable and duplicate records.",
                },
                {
                    "key": "rebuild",
                    "title": "Versioned rebuild",
                    "description": "A rebuild snapshots the eligible dataset and trains the local advisory calibration model.",
                },
                {
                    "key": "retrieve",
                    "title": "Retrieve similar projects",
                    "description": "For each proposal, the system retrieves up to six similar projects from the active snapshot.",
                },
                {
                    "key": "analyze",
                    "title": "Rules-first Groq analysis",
                    "description": "Groq applies the approved criteria first and uses historical scores only as secondary context.",
                },
                {
                    "key": "decide",
                    "title": "Validator decision",
                    "description": "The validator reviews the explanation and remains responsible for the final priority.",
                },
            ],
        },
        "active_rule_set": {
            "id": active.pk,
            "version": active.version,
            "algorithm_version": active.algorithm_version,
            "created_at": active.created_at,
            "config": priority_rule_config(active),
            "draft_config": contextual_priority_rule_draft(active),
        },
        "rule_versions": [
            {
                "id": rule.pk,
                "version": rule.version,
                "algorithm_version": rule.algorithm_version,
                "is_active": rule.is_active,
                "analysis_count": rule.analysis_count,
                "created_at": rule.created_at,
            }
            for rule in history
        ],
        "historical_projects": historical_projects,
        "historical_count": ProjectPriorityConfirmation.objects.count(),
        "training_dataset": training_dataset,
        "active_model": AIModelVersionSerializer(active_model).data if active_model else None,
        "model_versions": AIModelVersionSerializer(
            AIModelVersion.objects.select_related("trained_by").all()[:20], many=True
        ).data,
    }


class AdminAIPriorityCMSView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCMSAdmin]

    def get(self, request):
        try:
            limit = min(500, max(1, int(request.query_params.get("limit", 200))))
        except (TypeError, ValueError):
            limit = 200
        return Response(_priority_reference_payload(limit))

    def post(self, request):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only administrators can activate new AI scoring rules.")
        try:
            config = validate_priority_rule_config(request.data.get("config"), enforce_current_high=True)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        outcome_rules = [*config["keyword_dictionaries"]["common_outcomes"]]
        for sector_rules in config["sector_criteria"].values():
            outcome_rules.extend(sector_rules)
        if any(rule.get("match_mode") != "contextual" for rule in outcome_rules):
            return Response(
                {
                    "detail": (
                        "New AI scoring rule versions must use contextual sentence matching "
                        "for every RDP outcome criterion."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        change_note = str(request.data.get("change_note") or "").strip()[:500]
        timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        version_base = f"rdc-priority-{timestamp}"
        version = version_base
        suffix = 2
        while PriorityRuleSet.objects.filter(version=version).exists():
            version = f"{version_base}-{suffix}"
            suffix += 1

        with transaction.atomic():
            PriorityRuleSet.objects.select_for_update().filter(is_active=True).update(is_active=False)
            active = PriorityRuleSet.objects.create(
                version=version,
                algorithm_version="expert-v4-regional-eligibility",
                is_active=True,
                thresholds=config["thresholds"],
                sector_criteria=config["sector_criteria"],
                keyword_dictionaries=config["keyword_dictionaries"],
            )
        _log_cms_activity(
            request,
            "cms_content_updated",
            {
                "content_type": "ai_priority_rules",
                "rule_set_id": active.pk,
                "version": active.version,
                "change_note": change_note,
            },
        )
        return Response(
            {
                "detail": "A new AI scoring rule version is active. Existing analyses remain unchanged; pending projects require a new analysis under this version.",
                **_priority_reference_payload(),
            },
            status=status.HTTP_201_CREATED,
        )


class AdminCMSMediaAssetViewSet(CMSSummaryListMixin, viewsets.ModelViewSet):
    serializer_class = CMSMediaAssetSerializer
    summary_serializer_class = CMSMediaAssetSummarySerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    pagination_class = CMSMediaPagination

    def get_queryset(self):
        queryset = CMSMediaAsset.objects.select_related("uploaded_by")
        if self.action == "list":
            queryset = queryset.filter(is_archived=self.request.query_params.get("archived") in {"1", "true", "yes"})
        file_type = self.request.query_params.get("file_type")
        if file_type:
            queryset = queryset.filter(file_type=file_type)
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)
        tag = self.request.query_params.get("tag")
        if tag:
            queryset = queryset.filter(tags__contains=[tag]) if connection.vendor == "postgresql" else queryset.filter(tags__icontains=f'"{tag}"')
        search = str(self.request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(file__icontains=search) | Q(original_filename__icontains=search) |
                Q(alt_text__icontains=search) | Q(caption__icontains=search)
            )
        return queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        try:
            validate_media_upload(request.FILES.get("file"))
        except CMSMediaValidationError as exc:
            return Response(exc.raw_detail, status=422)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        metadata = validate_media_upload(serializer.validated_data["file"])
        metadata.update(extract_media_metadata(serializer.validated_data["file"], metadata["file_type"]))
        backend = str(getattr(settings, "CMS_STORAGE_BACKEND", "local")).lower()
        media = serializer.save(uploaded_by=self.request.user, storage_backend=backend, **metadata)
        media.storage_key = media.file.name
        if backend == "r2":
            media.public_url = media.file.url
        media.save(update_fields=["storage_key", "public_url"])
        _log_cms_activity(self.request, "cms_content_created", {"content_type": "media", "id": media.pk})

    def perform_update(self, serializer):
        extra = validate_media_upload(serializer.validated_data["file"]) if "file" in serializer.validated_data else {}
        if extra:
            extra.update(extract_media_metadata(serializer.validated_data["file"], extra["file_type"]))
        media = serializer.save(**extra)
        if "file" in serializer.validated_data:
            media.storage_key = media.file.name
            media.public_url = media.file.url if media.storage_backend == "r2" else ""
            media.save(update_fields=["storage_key", "public_url"])
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "media", "id": media.pk})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Media files are archived instead of hard-deleted."}, status=405)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        media = self.get_object()
        usages = get_media_usages(media)
        if usages:
            return Response(
                {"detail": "This media file is still used by CMS content. Remove or replace it before archiving.", "used_by": usages},
                status=400,
            )
        media._cms_usage_cache = usages
        media.is_archived = True
        media.save(update_fields=["is_archived"])
        _log_cms_activity(request, "cms_content_archived", {"content_type": "media", "id": media.pk})
        return Response(self.get_serializer(media).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def restore(self, request, pk=None):
        media = self.get_object()
        if not media.is_archived:
            return Response({"detail": "Media is not archived."}, status=400)
        media.is_archived = False
        media.save(update_fields=["is_archived"])
        _log_cms_activity(request, "cms_content_restored", {"content_type": "media", "id": media.pk})
        return Response(self.get_serializer(media).data)


class AdminCMSSiteSettingViewSet(viewsets.ModelViewSet):
    serializer_class = CMSSiteSettingSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    queryset = CMSSiteSetting.objects.select_related("updated_by").all().order_by("key")
    lookup_field = "key"

    def get_permissions(self):
        if self.request.method not in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated(), IsCMSAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        setting = serializer.save(updated_by=self.request.user)
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "site_setting", "key": setting.key})

    def perform_update(self, serializer):
        setting = serializer.save(updated_by=self.request.user)
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "site_setting", "key": setting.key})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "CMS settings cannot be deleted; update their value instead."}, status=405)


class AdminCMSReviewQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get(self, request):
        summary = request.query_params.get("view") == "summary"
        page_serializer = CMSPageSummarySerializer if summary else CMSPageSerializer
        section_serializer = CMSPageSectionSummarySerializer if summary else CMSPageSectionSerializer
        article_serializer = CMSArticleSummarySerializer if summary else CMSArticleSerializer

        pages = CMSPage.objects.filter(status="submitted")
        articles = CMSArticle.objects.filter(status="submitted").select_related("thumbnail")
        if summary:
            pages = pages.annotate(
                section_count=Count("sections", distinct=True),
                published_slug=KeyTextTransform("slug", "published_snapshot_json"),
            )
            articles = articles.annotate(published_slug=KeyTextTransform("slug", "published_snapshot_json"))
            # Page sections are never an independent review item. Legacy submitted
            # rows are normalized to drafts by the data migration below.
            sections = CMSPageSection.objects.none()
            events = list(
                PublicEvent.objects.filter(status="submitted").values(
                    "id", "title", "status", "updated_at"
                )
            )
        else:
            pages = pages.prefetch_related("sections").select_related(
                "created_by", "updated_by", "submitted_by", "reviewed_by"
            )
            articles = articles.select_related("created_by", "updated_by", "submitted_by", "reviewed_by")
            # Sections are reviewed as part of their parent page, never independently.
            sections = CMSPageSection.objects.none()
            events = PublicEventSerializer(
                PublicEvent.objects.filter(status="submitted").select_related(
                    "created_by", "submitted_by", "reviewed_by"
                ),
                many=True,
            ).data

        return Response(
            {
                "pages": page_serializer(pages, many=True, context={"request": request}).data,
                "sections": section_serializer(
                    sections,
                    many=True,
                    context={"request": request},
                ).data,
                "news": article_serializer(articles, many=True, context={"request": request}).data,
                # Contributor form administration lives outside the public-content CMS.
                # Keep the key for older clients, but never expose form records here.
                "forms": [],
                "events": events,
            }
        )


class PublicCMSPageView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        if slug not in FIXED_CMS_PAGE_REGISTRY:
            raise Http404("Published page not found.")
        page = (
            CMSPage.objects.filter(
                slug=slug,
                published_at__isnull=False,
                published_snapshot_json__slug=slug,
            )
            .exclude(status=CMSPage.STATUS_ARCHIVED)
            .only("slug", "published_snapshot_json")
            .first()
        )
        if page and page.published_snapshot_json:
            from cms.services.snapshots import compose_public_page_snapshot
            return _with_public_cache(request, compose_public_page_snapshot(page))
        raise Http404("Published page not found.")


class PublicCMSArticleListView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        category = request.query_params.get("category")
        featured = request.query_params.get("featured")
        limit = _clamp_int(request.query_params.get("limit"), default=20, min_value=1, max_value=100)
        results = []
        queryset = CMSArticle.objects.filter(published_at__isnull=False).exclude(status=CMSArticle.STATUS_ARCHIVED).order_by(
            "-publication_date", "-published_at", "-updated_at"
        )
        for _, snapshot in _published_snapshots(queryset):
            if category and str(snapshot.get("category", "")).lower() != category.lower():
                continue
            if featured in {"1", "true", "yes"} and not snapshot.get("featured"):
                continue
            results.append(snapshot)
            if len(results) >= limit:
                break
        return _with_public_cache(request, {"results": results, "count": len(results)})


class PublicCMSArticleDetailView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        article = (
            CMSArticle.objects.filter(published_at__isnull=False, published_snapshot_json__slug=slug)
            .exclude(status=CMSArticle.STATUS_ARCHIVED)
            .only("published_snapshot_json")
            .first()
        )
        if article and article.published_snapshot_json:
            return _with_public_cache(request, article.published_snapshot_json)
        raise Http404("Published article not found.")


class PublicCMSSiteSettingsView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        settings_payload = {
            row.key: row.value_json
            for row in CMSSiteSetting.objects.exclude(key__startswith="media-upload-").order_by("key")
        }
        return _with_public_cache(request, settings_payload)


def _clamp_int(value, default=20, min_value=1, max_value=100):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))
