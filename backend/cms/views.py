import hashlib
import json

from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection, CMSRevision, CMSSiteSetting
from cms.serializers import (
    CMSArticleSerializer,
    CMSMediaAssetSerializer,
    CMSPageSectionSerializer,
    CMSPageSerializer,
    CMSRevisionSerializer,
    CMSSiteSettingSerializer,
)
from cms.services.chatbot_sync import sync_cms_content
from cms.services.locking import (
    acquire_section_lock,
    heartbeat_section_lock,
    lock_is_active,
    release_section_lock,
)
from cms.services.media_usage import get_media_usages
from cms.services.media_validation import CMSMediaValidationError, validate_media_upload
from cms.services.publishing import (
    content_type_for,
    create_article_update_revision,
    create_page_update_revision,
    create_revision,
    create_section_update_revision,
    mark_article_changed,
    mark_page_changed,
    publish_article,
    publish_page,
    publish_section,
    reorder_page_sections,
    restore_revision,
)
from projects.models import Notification, PublicEvent, UserActivity
from projects.serializers import PublicEventSerializer


class IsCMSUser(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", "") in {"admin", "content_editor"})


class IsCMSAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "role", "") == "admin")


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


def _sync_without_blocking(request, obj, operation):
    try:
        sync_cms_content(obj)
    except Exception as exc:  # CMS remains the source of truth if chatbot indexing fails.
        _log_cms_activity(
            request,
            "cms_chatbot_sync_failed",
            {
                "content_type": obj._meta.model_name,
                "id": obj.pk,
                "operation": operation,
                "error": str(exc)[:1000],
            },
        )


def _with_public_cache(request, payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    etag = f'"{hashlib.sha256(canonical.encode("utf-8")).hexdigest()}"'
    candidates = [value.strip() for value in request.META.get("HTTP_IF_NONE_MATCH", "").split(",")]
    response = Response(status=status.HTTP_304_NOT_MODIFIED) if etag in candidates else Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = "public, no-cache, must-revalidate"
    return response


def _published_snapshots(queryset):
    for obj in queryset:
        snapshot = obj.published_snapshot_json or {}
        if snapshot:
            yield obj, snapshot


def _workflow_snapshot(obj):
    if isinstance(obj, CMSPage):
        return {"title": obj.title, "slug": obj.slug, "status": obj.status}
    if isinstance(obj, CMSArticle):
        return {"title": obj.title, "slug": obj.slug, "status": obj.status}
    return {
        "page": obj.page_id,
        "sectionKey": obj.section_key,
        "sectionType": obj.section_type,
        "order": obj.order,
        "schemaVersion": obj.schema_version,
        "isVisible": obj.is_visible,
        "status": obj.status,
        "content": obj.content_json or {},
    }


class CMSWorkflowMixin:
    content_type_key = None

    def _serialize(self, obj):
        return self.get_serializer(obj).data

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        obj = self.get_object()
        if obj.status not in {"draft", "rejected", "published"}:
            return Response({"detail": "Only draft, rejected, or edited published content can be submitted."}, status=400)
        before = obj.status
        obj.status = "submitted"
        if hasattr(obj, "submitted_by"):
            obj.submitted_by = request.user
        if hasattr(obj, "review_notes"):
            obj.review_notes = ""
        fields = ["status", "updated_at"]
        fields += [field for field in ("submitted_by", "review_notes") if hasattr(obj, field)]
        obj.save(update_fields=fields)
        if isinstance(obj, CMSPageSection):
            release_section_lock(obj.pk, request.user, force=getattr(request.user, "role", "") == "admin")
            mark_page_changed(obj.page, request.user)
        create_revision(
            self.content_type_key, obj.pk, CMSRevision.ACTION_SUBMIT, _workflow_snapshot(obj), user=request.user,
            status_before=before, status_after=obj.status,
        )
        _log_cms_activity(request, "cms_content_submitted", {"content_type": self.content_type_key, "id": obj.pk})
        obj.refresh_from_db()
        return Response(self._serialize(obj))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def reject(self, request, pk=None):
        obj = self.get_object()
        if obj.status not in {"submitted", "draft"}:
            return Response({"detail": "Only submitted or draft content can be rejected."}, status=400)
        before = obj.status
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
        create_revision(
            self.content_type_key, obj.pk, CMSRevision.ACTION_REJECT, _workflow_snapshot(obj), user=request.user,
            status_before=before, status_after=obj.status,
        )
        _log_cms_activity(request, "cms_content_rejected", {"content_type": self.content_type_key, "id": obj.pk})
        obj.refresh_from_db()
        return Response(self._serialize(obj))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def archive(self, request, pk=None):
        obj = self.get_object()
        before = obj.status
        obj.status = "archived"
        fields = ["status", "updated_at"]
        if hasattr(obj, "archived_at"):
            obj.archived_at = timezone.now()
            fields.append("archived_at")
        obj.save(update_fields=fields)
        if isinstance(obj, CMSPageSection):
            release_section_lock(obj.pk, request.user, force=True)
            page = obj.page
            if page.published_at:
                page.published_snapshot_json = _page_snapshot(page)
                page.save(update_fields=["published_snapshot_json", "updated_at"])
                _sync_without_blocking(request, page, "archive_section")
        else:
            _sync_without_blocking(request, obj, "archive")
        create_revision(
            self.content_type_key, obj.pk, CMSRevision.ACTION_ARCHIVE, _workflow_snapshot(obj), user=request.user,
            status_before=before, status_after=obj.status,
        )
        _log_cms_activity(request, "cms_content_archived", {"content_type": self.content_type_key, "id": obj.pk})
        obj.refresh_from_db()
        return Response(self._serialize(obj))


def _page_snapshot(page):
    # Imported lazily to keep all public snapshot construction in one service.
    from cms.services.snapshots import build_page_snapshot

    return build_page_snapshot(page)


class AdminCMSPageViewSet(CMSWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = CMSPageSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    content_type_key = CMSRevision.CONTENT_PAGE

    def get_queryset(self):
        queryset = CMSPage.objects.prefetch_related("sections").select_related(
            "created_by", "updated_by", "submitted_by", "reviewed_by"
        )
        status_filter = self.request.query_params.get("status")
        return queryset.filter(status=status_filter).order_by("slug") if status_filter else queryset.order_by("slug")

    def perform_create(self, serializer):
        page = serializer.save(created_by=self.request.user, updated_by=self.request.user, has_unpublished_changes=True)
        create_revision(self.content_type_key, page.pk, CMSRevision.ACTION_CREATE, _workflow_snapshot(page), user=self.request.user)
        _log_cms_activity(self.request, "cms_content_created", {"content_type": "page", "id": page.pk, "slug": page.slug})

    def perform_update(self, serializer):
        if serializer.instance.status == "archived":
            raise PermissionDenied("Archived pages cannot be edited.")
        if serializer.instance.status == "submitted" and getattr(self.request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted or archived pages can only be changed by an administrator.")
        page = serializer.save(updated_by=self.request.user, has_unpublished_changes=True, status="draft")
        create_page_update_revision(page, user=self.request.user)
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "page", "id": page.pk, "slug": page.slug})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "CMS pages are archived instead of hard-deleted."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        page = self.get_object()
        if page.status == "archived":
            return Response({"detail": "Archived pages cannot be published."}, status=400)
        page = publish_page(page, user=request.user)
        _sync_without_blocking(request, page, "publish")
        _log_cms_activity(request, "cms_content_published", {"content_type": "page", "id": page.pk, "slug": page.slug})
        return Response(self._serialize(page))

    @action(detail=True, methods=["post"])
    def reorder_sections(self, request, pk=None):
        section_ids = request.data.get("section_ids") or request.data.get("sections")
        if not isinstance(section_ids, list) or not section_ids:
            raise serializers.ValidationError({"section_ids": "Provide the final ordered list of section IDs."})
        page = reorder_page_sections(self.get_object(), section_ids, user=request.user)
        _log_cms_activity(request, "cms_content_updated", {"content_type": "page", "id": page.pk, "action": "reorder_sections"})
        return Response(self._serialize(page))


class AdminCMSPageSectionViewSet(CMSWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = CMSPageSectionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    content_type_key = CMSRevision.CONTENT_SECTION

    def get_queryset(self):
        queryset = CMSPageSection.objects.select_related("page", "lock_owner")
        page_id = self.request.query_params.get("page")
        status_filter = self.request.query_params.get("status")
        if page_id:
            queryset = queryset.filter(page_id=page_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by("page_id", "order", "id")

    def perform_create(self, serializer):
        section = serializer.save(status="draft")
        mark_page_changed(section.page, self.request.user)
        create_section_update_revision(section, user=self.request.user, action=CMSRevision.ACTION_CREATE)
        _log_cms_activity(self.request, "cms_content_created", {"content_type": "section", "id": section.pk, "page": section.page_id})

    def update(self, request, *args, **kwargs):
        section = self.get_object()
        if section.status == "archived":
            raise PermissionDenied("Archived sections cannot be edited.")
        if section.status == "submitted" and getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted sections can only be changed by an administrator.")
        if lock_is_active(section) and section.lock_owner_id != request.user.id:
            return Response(
                {"detail": f"Currently being edited by {section.lock_owner.full_name or section.lock_owner.username}.", "lock_owner": section.lock_owner_id},
                status=423,
            )
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        section = serializer.save(status="draft", lock_owner=None, lock_acquired_at=None)
        mark_page_changed(section.page, self.request.user)
        create_section_update_revision(section, user=self.request.user)
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "section", "id": section.pk, "page": section.page_id})

    def perform_destroy(self, instance):
        page = instance.page
        section_id = instance.pk
        snapshot = _workflow_snapshot(instance)
        snapshot["deleted"] = True
        with transaction.atomic():
            instance.delete()
            mark_page_changed(page, self.request.user)
            create_revision(self.content_type_key, section_id, CMSRevision.ACTION_UPDATE, snapshot, user=self.request.user)
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "section", "id": section_id, "action": "delete"})

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        section, acquired = acquire_section_lock(pk, request.user)
        _log_cms_activity(
            request, "cms_section_lock_acquired" if acquired else "cms_section_lock_blocked",
            {"section_id": section.pk, "lock_owner": section.lock_owner_id},
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
                "message": f"{request.user.full_name or request.user.username} requested access to {section.page.title}: {section.section_key}.",
                "link_path": "/employee/cms/pages/" + section.page.slug,
            },
        )
        _log_cms_activity(request, "cms_section_access_requested", {"section_id": section.pk, "owner": section.lock_owner_id})
        return Response({"detail": "Access request sent to the current editor."})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        section = self.get_object()
        if section.status == "archived":
            return Response({"detail": "Archived sections cannot be published."}, status=400)
        section = publish_section(section, user=request.user)
        _sync_without_blocking(request, section.page, "publish_section")
        _log_cms_activity(request, "cms_content_published", {"content_type": "section", "id": section.pk})
        return Response(self._serialize(section))


class AdminCMSArticleViewSet(CMSWorkflowMixin, viewsets.ModelViewSet):
    serializer_class = CMSArticleSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]
    content_type_key = CMSRevision.CONTENT_ARTICLE

    def get_queryset(self):
        queryset = CMSArticle.objects.select_related(
            "thumbnail", "created_by", "updated_by", "submitted_by", "reviewed_by"
        )
        for key, lookup in (("status", "status"), ("category", "category__iexact")):
            value = self.request.query_params.get(key)
            if value:
                queryset = queryset.filter(**{lookup: value})
        return queryset.order_by("-updated_at")

    def perform_create(self, serializer):
        article = serializer.save(created_by=self.request.user, updated_by=self.request.user, has_unpublished_changes=True)
        create_revision(self.content_type_key, article.pk, CMSRevision.ACTION_CREATE, _workflow_snapshot(article), user=self.request.user)
        _log_cms_activity(self.request, "cms_content_created", {"content_type": "article", "id": article.pk, "slug": article.slug})

    def perform_update(self, serializer):
        if serializer.instance.status == "archived":
            raise PermissionDenied("Archived articles cannot be edited.")
        if serializer.instance.status == "submitted" and getattr(self.request.user, "role", "") != "admin":
            raise PermissionDenied("Submitted or archived articles can only be changed by an administrator.")
        article = serializer.save(updated_by=self.request.user, has_unpublished_changes=True, status="draft")
        create_article_update_revision(article, user=self.request.user)
        _log_cms_activity(self.request, "cms_content_updated", {"content_type": "article", "id": article.pk, "slug": article.slug})

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "CMS news articles are archived instead of hard-deleted."}, status=405)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        article = self.get_object()
        if article.status == "archived":
            return Response({"detail": "Archived articles cannot be published."}, status=400)
        article = publish_article(article, user=request.user)
        _sync_without_blocking(request, article, "publish")
        _log_cms_activity(request, "cms_content_published", {"content_type": "article", "id": article.pk, "slug": article.slug})
        return Response(self._serialize(article))


class AdminCMSMediaAssetViewSet(viewsets.ModelViewSet):
    serializer_class = CMSMediaAssetSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get_queryset(self):
        queryset = CMSMediaAsset.objects.select_related("uploaded_by")
        if self.request.query_params.get("include_archived") not in {"1", "true", "yes"}:
            queryset = queryset.filter(is_archived=False)
        file_type = self.request.query_params.get("file_type")
        return queryset.filter(file_type=file_type).order_by("-created_at") if file_type else queryset.order_by("-created_at")

    def create(self, request, *args, **kwargs):
        try:
            validate_media_upload(request.FILES.get("file"))
        except CMSMediaValidationError as exc:
            return Response(exc.raw_detail, status=422)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        metadata = validate_media_upload(serializer.validated_data["file"])
        backend = str(getattr(settings, "CMS_STORAGE_BACKEND", "local")).lower()
        media = serializer.save(uploaded_by=self.request.user, storage_backend=backend, **metadata)
        media.storage_key = media.file.name
        if backend == "r2":
            media.public_url = media.file.url
        media.save(update_fields=["storage_key", "public_url"])
        create_revision(
            CMSRevision.CONTENT_MEDIA, media.pk, CMSRevision.ACTION_CREATE,
            {"file": media.file.name, "fileType": media.file_type, "mimeType": media.mime_type, "size": media.size},
            user=self.request.user,
        )
        _log_cms_activity(self.request, "cms_content_created", {"content_type": "media", "id": media.pk})

    def perform_update(self, serializer):
        extra = validate_media_upload(serializer.validated_data["file"]) if "file" in serializer.validated_data else {}
        media = serializer.save(**extra)
        if "file" in serializer.validated_data:
            media.storage_key = media.file.name
            media.public_url = media.file.url if media.storage_backend == "r2" else ""
            media.save(update_fields=["storage_key", "public_url"])
        create_revision(
            CMSRevision.CONTENT_MEDIA, media.pk, CMSRevision.ACTION_UPDATE,
            {"file": media.file.name, "fileType": media.file_type, "altText": media.alt_text, "caption": media.caption},
            user=self.request.user,
        )
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
        media.is_archived = True
        media.save(update_fields=["is_archived"])
        create_revision(CMSRevision.CONTENT_MEDIA, media.pk, CMSRevision.ACTION_ARCHIVE, {"file": media.file.name}, user=request.user)
        _log_cms_activity(request, "cms_content_archived", {"content_type": "media", "id": media.pk})
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


class AdminCMSRevisionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CMSRevisionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get_queryset(self):
        queryset = CMSRevision.objects.select_related("changed_by", "content_type")
        content_type = self.request.query_params.get("content_type")
        object_id = self.request.query_params.get("object_id")
        if content_type:
            try:
                queryset = queryset.filter(content_type=content_type_for(content_type))
            except ValueError:
                return queryset.none()
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        return queryset.order_by("-created_at", "-version_number")

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin], url_path="restore-revision")
    def restore_revision(self, request, pk=None):
        revision = self.get_object()
        restored = restore_revision(revision, user=request.user)
        if isinstance(restored, CMSPageSection):
            _sync_without_blocking(request, restored.page, "restore")
        elif isinstance(restored, (CMSPage, CMSArticle)):
            _sync_without_blocking(request, restored, "restore")
        _log_cms_activity(
            request, "cms_content_restored",
            {"revision_id": revision.pk, "content_type": revision.content_type_key, "restored_id": restored.pk},
        )
        return Response(
            {"detail": "Revision restored.", "content_type": revision.content_type_key, "object_id": restored.pk},
        )


class AdminCMSReviewQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get(self, request):
        return Response(
            {
                "pages": CMSPageSerializer(CMSPage.objects.filter(status="submitted"), many=True, context={"request": request}).data,
                "sections": CMSPageSectionSerializer(
                    CMSPageSection.objects.filter(status="submitted").select_related("page", "lock_owner"),
                    many=True,
                    context={"request": request},
                ).data,
                "news": CMSArticleSerializer(
                    CMSArticle.objects.filter(status="submitted").select_related("thumbnail"),
                    many=True,
                    context={"request": request},
                ).data,
                "events": PublicEventSerializer(PublicEvent.objects.filter(status="submitted"), many=True).data,
            }
        )


class PublicCMSPageView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        page = (
            CMSPage.objects.filter(published_at__isnull=False, published_snapshot_json__slug=slug)
            .exclude(status=CMSPage.STATUS_ARCHIVED)
            .only("published_snapshot_json")
            .first()
        )
        if page and page.published_snapshot_json:
            return _with_public_cache(request, page.published_snapshot_json)
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
