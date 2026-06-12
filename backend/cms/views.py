from django.db import transaction
from django.http import Http404
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection, CMSRevision
from cms.serializers import (
    CMSArticleSerializer,
    CMSMediaAssetSerializer,
    CMSPageSectionSerializer,
    CMSPageSerializer,
    CMSRevisionSerializer,
)
from cms.services.media_validation import validate_media_upload
from cms.services.publishing import (
    create_article_update_revision,
    create_page_update_revision,
    create_revision,
    create_section_update_revision,
    mark_article_changed,
    mark_page_changed,
    publish_article,
    publish_page,
    reorder_page_sections,
)
from projects.models import UserActivity


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
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


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


def _with_public_cache(response):
    response["Cache-Control"] = "public, max-age=300"
    return response


def _published_snapshots(queryset):
    for obj in queryset:
        snapshot = obj.published_snapshot_json or {}
        if snapshot:
            yield obj, snapshot


class AdminCMSPageViewSet(viewsets.ModelViewSet):
    serializer_class = CMSPageSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get_queryset(self):
        queryset = CMSPage.objects.prefetch_related("sections").select_related("created_by", "updated_by")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset.order_by("slug")

    def perform_create(self, serializer):
        page = serializer.save(created_by=self.request.user, updated_by=self.request.user, has_unpublished_changes=True)
        create_revision(
            CMSRevision.CONTENT_PAGE,
            page.pk,
            CMSRevision.ACTION_CREATE,
            {
                "title": page.title,
                "slug": page.slug,
                "status": page.status,
            },
            user=self.request.user,
            status_after=page.status,
        )
        _log_cms_activity(
            self.request,
            "cms_content_created",
            {"content_type": "page", "id": page.pk, "slug": page.slug},
        )

    def perform_update(self, serializer):
        page = serializer.save(updated_by=self.request.user, has_unpublished_changes=True)
        create_page_update_revision(page, user=self.request.user)
        _log_cms_activity(
            self.request,
            "cms_content_updated",
            {"content_type": "page", "id": page.pk, "slug": page.slug},
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        page = self.get_object()
        page = publish_page(page, user=request.user)
        _log_cms_activity(
            request,
            "cms_content_published",
            {"content_type": "page", "id": page.pk, "slug": page.slug},
        )
        return Response(CMSPageSerializer(page, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def reorder_sections(self, request, pk=None):
        page = self.get_object()
        section_ids = request.data.get("section_ids") or request.data.get("sections")
        if not isinstance(section_ids, list) or not section_ids:
            raise serializers.ValidationError({"section_ids": "Provide the final ordered list of section IDs."})
        page = reorder_page_sections(page, section_ids, user=request.user)
        _log_cms_activity(
            request,
            "cms_content_updated",
            {"content_type": "page", "id": page.pk, "slug": page.slug, "action": "reorder_sections"},
        )
        return Response(CMSPageSerializer(page, context={"request": request}).data)


class AdminCMSPageSectionViewSet(viewsets.ModelViewSet):
    serializer_class = CMSPageSectionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get_queryset(self):
        queryset = CMSPageSection.objects.select_related("page")
        page_id = self.request.query_params.get("page")
        if page_id:
            queryset = queryset.filter(page_id=page_id)
        return queryset.order_by("page_id", "order", "id")

    def perform_create(self, serializer):
        section = serializer.save()
        mark_page_changed(section.page, self.request.user)
        create_section_update_revision(section, user=self.request.user, action=CMSRevision.ACTION_CREATE)
        _log_cms_activity(
            self.request,
            "cms_content_updated",
            {
                "content_type": "section",
                "id": section.pk,
                "page": section.page_id,
                "section_key": section.section_key,
                "action": "create",
            },
        )

    def perform_update(self, serializer):
        section = serializer.save()
        mark_page_changed(section.page, self.request.user)
        create_section_update_revision(section, user=self.request.user)
        _log_cms_activity(
            self.request,
            "cms_content_updated",
            {
                "content_type": "section",
                "id": section.pk,
                "page": section.page_id,
                "section_key": section.section_key,
                "action": "update",
            },
        )


class AdminCMSArticleViewSet(viewsets.ModelViewSet):
    serializer_class = CMSArticleSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get_queryset(self):
        queryset = CMSArticle.objects.select_related("thumbnail", "created_by", "updated_by")
        status_filter = self.request.query_params.get("status")
        category = self.request.query_params.get("category")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if category:
            queryset = queryset.filter(category__iexact=category)
        return queryset.order_by("-updated_at")

    def perform_create(self, serializer):
        article = serializer.save(created_by=self.request.user, updated_by=self.request.user, has_unpublished_changes=True)
        create_revision(
            CMSRevision.CONTENT_ARTICLE,
            article.pk,
            CMSRevision.ACTION_CREATE,
            {
                "title": article.title,
                "slug": article.slug,
                "status": article.status,
            },
            user=self.request.user,
            status_after=article.status,
        )
        _log_cms_activity(
            self.request,
            "cms_content_created",
            {"content_type": "article", "id": article.pk, "slug": article.slug},
        )

    def perform_update(self, serializer):
        article = serializer.save(updated_by=self.request.user, has_unpublished_changes=True)
        create_article_update_revision(article, user=self.request.user)
        _log_cms_activity(
            self.request,
            "cms_content_updated",
            {"content_type": "article", "id": article.pk, "slug": article.slug},
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCMSAdmin])
    def publish(self, request, pk=None):
        article = self.get_object()
        article = publish_article(article, user=request.user)
        _log_cms_activity(
            request,
            "cms_content_published",
            {"content_type": "article", "id": article.pk, "slug": article.slug},
        )
        return Response(CMSArticleSerializer(article, context={"request": request}).data)


class AdminCMSMediaAssetViewSet(viewsets.ModelViewSet):
    serializer_class = CMSMediaAssetSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get_queryset(self):
        queryset = CMSMediaAsset.objects.select_related("uploaded_by")
        include_archived = self.request.query_params.get("include_archived") in {"1", "true", "yes"}
        if not include_archived:
            queryset = queryset.filter(is_archived=False)
        file_type = self.request.query_params.get("file_type")
        if file_type:
            queryset = queryset.filter(file_type=file_type)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        metadata = validate_media_upload(serializer.validated_data["file"])
        media = serializer.save(uploaded_by=self.request.user, **metadata)
        create_revision(
            CMSRevision.CONTENT_MEDIA,
            media.pk,
            CMSRevision.ACTION_CREATE,
            {
                "file": media.file.name,
                "fileType": media.file_type,
                "mimeType": media.mime_type,
                "size": media.size,
            },
            user=self.request.user,
        )
        _log_cms_activity(
            self.request,
            "cms_content_created",
            {"content_type": "media", "id": media.pk, "file_type": media.file_type},
        )

    def perform_update(self, serializer):
        extra = {}
        if "file" in serializer.validated_data:
            extra.update(validate_media_upload(serializer.validated_data["file"]))
        media = serializer.save(**extra)
        create_revision(
            CMSRevision.CONTENT_MEDIA,
            media.pk,
            CMSRevision.ACTION_UPDATE,
            {
                "file": media.file.name,
                "fileType": media.file_type,
                "mimeType": media.mime_type,
                "size": media.size,
                "altText": media.alt_text,
                "caption": media.caption,
            },
            user=self.request.user,
        )
        _log_cms_activity(
            self.request,
            "cms_content_updated",
            {"content_type": "media", "id": media.pk, "file_type": media.file_type},
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Media files are archived instead of hard-deleted."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        media = self.get_object()
        with transaction.atomic():
            media.is_archived = True
            media.save(update_fields=["is_archived"])
            create_revision(
                CMSRevision.CONTENT_MEDIA,
                media.pk,
                CMSRevision.ACTION_ARCHIVE,
                {"file": media.file.name, "fileType": media.file_type},
                user=request.user,
            )
        _log_cms_activity(
            request,
            "cms_content_archived",
            {"content_type": "media", "id": media.pk, "file_type": media.file_type},
        )
        return Response(CMSMediaAssetSerializer(media, context={"request": request}).data)


class AdminCMSRevisionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CMSRevisionSerializer
    permission_classes = [permissions.IsAuthenticated, IsCMSUser]

    def get_queryset(self):
        queryset = CMSRevision.objects.select_related("changed_by")
        content_type = self.request.query_params.get("content_type")
        object_id = self.request.query_params.get("object_id")
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        return queryset.order_by("-created_at", "-version_number")


class PublicCMSPageView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        for _, snapshot in _published_snapshots(CMSPage.objects.filter(status=CMSPage.STATUS_PUBLISHED)):
            if snapshot.get("slug") == slug:
                return _with_public_cache(Response(snapshot))
        raise Http404("Published page not found.")


class PublicCMSArticleListView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        category = request.query_params.get("category")
        featured = request.query_params.get("featured")
        limit = _clamp_int(request.query_params.get("limit"), default=20, min_value=1, max_value=100)
        results = []

        for _, snapshot in _published_snapshots(
            CMSArticle.objects.filter(status=CMSArticle.STATUS_PUBLISHED).order_by("-published_at", "-updated_at")
        ):
            if category and str(snapshot.get("category", "")).lower() != category.lower():
                continue
            if featured in {"1", "true", "yes"} and not snapshot.get("featured"):
                continue
            results.append(snapshot)
            if len(results) >= limit:
                break

        return _with_public_cache(Response({"results": results, "count": len(results)}))


class PublicCMSArticleDetailView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        for _, snapshot in _published_snapshots(CMSArticle.objects.filter(status=CMSArticle.STATUS_PUBLISHED)):
            if snapshot.get("slug") == slug:
                return _with_public_cache(Response(snapshot))
        raise Http404("Published article not found.")


def _clamp_int(value, default=20, min_value=1, max_value=100):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(parsed, max_value))
