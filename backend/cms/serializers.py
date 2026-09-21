from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from cms.form_schema import (
    FormSchemaError,
    normalize_system_managed_sections,
    validate_form_schema,
    validate_update_mode,
)
from cms.models import (
    CMSArticle,
    CMSContributorForm,
    CMSContributorFormVersion,
    CMSMediaAsset,
    CMSPage,
    CMSPageSection,
    CMSRevision,
    CMSSiteSetting,
)
from cms.services.locking import lock_is_active
from cms.services.media_usage import get_media_usage_map, get_media_usages
from cms.services.media_validation import validate_media_upload


def _user_display(user):
    if not user:
        return ""
    return getattr(user, "full_name", "") or user.get_username()


class CMSMediaAssetListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        instances = list(data.all() if hasattr(data, "all") else data)
        usage_map = get_media_usage_map(instances)
        for media in instances:
            media._cms_usage_cache = usage_map.get(media.pk, [])
        return super().to_representation(instances)


class CMSMediaAssetSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    used_by = serializers.SerializerMethodField()
    usage_count = serializers.SerializerMethodField()
    can_archive = serializers.SerializerMethodField()

    class Meta:
        model = CMSMediaAsset
        list_serializer_class = CMSMediaAssetListSerializer
        fields = [
            "id", "file", "url", "storage_backend", "storage_key", "public_url",
            "file_type", "mime_type", "size", "alt_text", "caption", "uploaded_by",
            "uploaded_by_name", "is_archived", "used_by", "usage_count", "can_archive", "created_at",
        ]
        read_only_fields = [
            "storage_backend", "storage_key", "public_url", "file_type", "mime_type", "size",
            "uploaded_by", "uploaded_by_name", "used_by", "usage_count", "can_archive", "created_at",
        ]

    def get_url(self, obj):
        url = obj.resolved_public_url
        if not url:
            return ""
        request = self.context.get("request")
        if request and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url

    def get_uploaded_by_name(self, obj):
        return _user_display(obj.uploaded_by)

    def get_used_by(self, obj):
        return self._media_usages(obj)

    def get_usage_count(self, obj):
        return len(self._media_usages(obj))

    def get_can_archive(self, obj):
        return not self._media_usages(obj)

    def _media_usages(self, obj):
        if not hasattr(obj, "_cms_usage_cache"):
            obj._cms_usage_cache = get_media_usages(obj)
        return obj._cms_usage_cache

    def validate_file(self, value):
        validate_media_upload(value)
        return value


class CMSPageSectionSerializer(serializers.ModelSerializer):
    lock_owner_name = serializers.SerializerMethodField()
    lock_expires_at = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    locked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = CMSPageSection
        fields = [
            "id", "page", "section_key", "section_type", "order", "content_json", "schema_version",
            "is_visible", "status", "lock_owner", "lock_owner_name", "lock_acquired_at",
            "lock_expires_at", "is_locked", "locked_by_me", "created_at", "updated_at",
        ]
        read_only_fields = [
            "status", "lock_owner", "lock_owner_name", "lock_acquired_at", "lock_expires_at",
            "is_locked", "locked_by_me", "created_at", "updated_at",
        ]

    def validate_content_json(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Section content must be a JSON object.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        page = attrs.get("page") or getattr(self.instance, "page", None)
        section_type = attrs.get("section_type", getattr(self.instance, "section_type", ""))
        if page and page.slug == "home" and section_type == "hero_carousel":
            duplicates = CMSPageSection.objects.filter(
                page=page,
                section_type="hero_carousel",
            ).exclude(status="archived")
            if self.instance:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError(
                    {"section_type": "The Home page can only have one hero carousel. Edit the existing carousel instead."}
                )
        return attrs

    def _lock_active(self, obj):
        if not obj.lock_owner_id or not obj.lock_acquired_at:
            return False
        timeout = getattr(settings, "CMS_SECTION_LOCK_SECONDS", 600)
        return obj.lock_acquired_at >= timezone.now() - timedelta(seconds=timeout)

    def get_lock_owner_name(self, obj):
        return _user_display(obj.lock_owner) if self._lock_active(obj) else ""

    def get_lock_expires_at(self, obj):
        if not self._lock_active(obj):
            return None
        timeout = getattr(settings, "CMS_SECTION_LOCK_SECONDS", 600)
        return obj.lock_acquired_at + timedelta(seconds=timeout)

    def get_is_locked(self, obj):
        return self._lock_active(obj)

    def get_locked_by_me(self, obj):
        request = self.context.get("request")
        return bool(self._lock_active(obj) and request and request.user.id == obj.lock_owner_id)


class CMSPageSectionSummarySerializer(serializers.ModelSerializer):
    """Section review row without the section content document."""

    class Meta:
        model = CMSPageSection
        fields = [
            "id", "page", "section_key", "section_type", "order", "schema_version",
            "is_visible", "status", "created_at", "updated_at",
        ]
        read_only_fields = fields


class CMSPageSerializer(serializers.ModelSerializer):
    sections = CMSPageSectionSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSPage
        fields = [
            "id", "title", "slug", "status", "published_snapshot_json", "has_unpublished_changes",
            "sections", "created_by", "created_by_name", "updated_by", "updated_by_name", "submitted_by",
            "submitted_by_name", "reviewed_by", "reviewed_by_name", "review_notes", "published_at",
            "archived_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "status", "published_snapshot_json", "has_unpublished_changes", "created_by", "created_by_name",
            "updated_by", "updated_by_name", "submitted_by", "submitted_by_name", "reviewed_by",
            "reviewed_by_name", "review_notes", "published_at", "archived_at", "created_at", "updated_at",
        ]

    def get_created_by_name(self, obj):
        return _user_display(obj.created_by)

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)

    def get_submitted_by_name(self, obj):
        return _user_display(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return _user_display(obj.reviewed_by)

    def validate_slug(self, value):
        if self.instance and self.instance.published_at and value != self.instance.slug:
            raise serializers.ValidationError("Slug is locked after publishing to avoid breaking shared links.")
        return value


class CMSPageSummarySerializer(serializers.ModelSerializer):
    """Compact page row used by the CMS index; retrieve still returns the full draft."""

    published_slug = serializers.CharField(read_only=True, allow_blank=True)
    section_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CMSPage
        fields = [
            "id", "title", "slug", "status", "has_unpublished_changes", "published_slug",
            "section_count", "review_notes", "published_at", "archived_at", "updated_at",
        ]
        read_only_fields = fields


class CMSPageEditorSerializer(CMSPageSerializer):
    """Full page draft for editing without duplicating the published snapshot."""

    class Meta(CMSPageSerializer.Meta):
        fields = [
            field for field in CMSPageSerializer.Meta.fields
            if field != "published_snapshot_json"
        ]
        read_only_fields = [
            field for field in CMSPageSerializer.Meta.read_only_fields
            if field != "published_snapshot_json"
        ]


class CMSArticleSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSArticle
        fields = [
            "id", "title", "slug", "category", "summary", "body", "thumbnail", "thumbnail_url", "author",
            "publication_date", "featured", "status", "published_snapshot_json", "has_unpublished_changes", "created_by",
            "created_by_name", "updated_by", "updated_by_name", "submitted_by", "submitted_by_name",
            "reviewed_by", "reviewed_by_name", "review_notes", "published_at", "archived_at", "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status", "published_snapshot_json", "has_unpublished_changes", "created_by", "created_by_name",
            "updated_by", "updated_by_name", "submitted_by", "submitted_by_name", "reviewed_by",
            "reviewed_by_name", "review_notes", "published_at", "archived_at", "created_at", "updated_at",
        ]

    def get_thumbnail_url(self, obj):
        return obj.thumbnail.resolved_public_url if obj.thumbnail and not obj.thumbnail.is_archived else ""

    def get_created_by_name(self, obj):
        return _user_display(obj.created_by)

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)

    def get_submitted_by_name(self, obj):
        return _user_display(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return _user_display(obj.reviewed_by)

    def validate_slug(self, value):
        if self.instance and self.instance.published_at and value != self.instance.slug:
            raise serializers.ValidationError("Slug is locked after publishing to avoid breaking shared links.")
        return value


class CMSArticleSummarySerializer(serializers.ModelSerializer):
    """Article metadata without the body or duplicated published snapshot."""

    thumbnail_url = serializers.SerializerMethodField()
    published_slug = serializers.CharField(read_only=True, allow_blank=True)

    class Meta:
        model = CMSArticle
        fields = [
            "id", "title", "slug", "category", "summary", "thumbnail", "thumbnail_url",
            "author", "publication_date", "featured", "status", "has_unpublished_changes",
            "published_slug", "review_notes", "published_at", "archived_at", "updated_at",
        ]
        read_only_fields = fields

    def get_thumbnail_url(self, obj):
        return obj.thumbnail.resolved_public_url if obj.thumbnail and not obj.thumbnail.is_archived else ""


class CMSArticleEditorSerializer(CMSArticleSerializer):
    """Full article draft for editing without duplicating the published snapshot."""

    class Meta(CMSArticleSerializer.Meta):
        fields = [
            field for field in CMSArticleSerializer.Meta.fields
            if field != "published_snapshot_json"
        ]
        read_only_fields = [
            field for field in CMSArticleSerializer.Meta.read_only_fields
            if field != "published_snapshot_json"
        ]


class CMSContributorFormVersionSerializer(serializers.ModelSerializer):
    published_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSContributorFormVersion
        fields = ["id", "form", "version_number", "schema_json", "published_by_name", "published_at"]
        read_only_fields = fields

    def get_published_by_name(self, obj):
        return _user_display(obj.published_by)


class CMSContributorFormSerializer(serializers.ModelSerializer):
    current_published_version_number = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    lock_owner_name = serializers.SerializerMethodField()
    lock_expires_at = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()
    locked_by_me = serializers.SerializerMethodField()
    expected_updated_at = serializers.DateTimeField(write_only=True, required=False)
    edit_mode = serializers.ChoiceField(choices=["update", "change"], write_only=True, required=False, default="update")

    class Meta:
        model = CMSContributorForm
        fields = [
            "id", "key", "name", "description", "status", "draft_schema_json",
            "current_published_version", "current_published_version_number", "has_unpublished_changes",
            "created_by_name", "updated_by_name", "submitted_by_name", "reviewed_by_name", "review_notes",
            "published_at", "lock_owner", "lock_owner_name", "lock_acquired_at", "lock_expires_at",
            "is_locked", "locked_by_me", "created_at", "updated_at", "expected_updated_at", "edit_mode",
        ]
        read_only_fields = [
            "key", "status", "current_published_version", "current_published_version_number",
            "has_unpublished_changes", "created_by_name", "updated_by_name", "submitted_by_name",
            "reviewed_by_name", "review_notes", "published_at", "lock_owner", "lock_owner_name",
            "lock_acquired_at", "lock_expires_at", "is_locked", "locked_by_me", "created_at", "updated_at",
        ]

    def get_current_published_version_number(self, obj):
        return obj.current_published_version.version_number if obj.current_published_version_id else None

    def get_created_by_name(self, obj):
        return _user_display(obj.created_by)

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)

    def get_submitted_by_name(self, obj):
        return _user_display(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return _user_display(obj.reviewed_by)

    def get_lock_owner_name(self, obj):
        return _user_display(obj.lock_owner) if lock_is_active(obj) else ""

    def get_lock_expires_at(self, obj):
        return obj.lock_acquired_at + timedelta(seconds=getattr(settings, "CMS_SECTION_LOCK_SECONDS", 600)) if lock_is_active(obj) else None

    def get_is_locked(self, obj):
        return lock_is_active(obj)

    def get_locked_by_me(self, obj):
        request = self.context.get("request")
        return bool(lock_is_active(obj) and request and request.user.id == obj.lock_owner_id)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        schema = attrs.get("draft_schema_json", getattr(self.instance, "draft_schema_json", {}))
        published_schema = None
        if self.instance and self.instance.current_published_version_id:
            published_schema = self.instance.current_published_version.schema_json
        try:
            validate_form_schema(schema, published_schema=published_schema)
            if self.instance and attrs.get("edit_mode", "update") == "update":
                previous_schema = normalize_system_managed_sections(
                    self.instance.draft_schema_json or {}, published_schema
                )
                validate_update_mode(previous_schema, schema)
        except FormSchemaError as exc:
            raise serializers.ValidationError({"draft_schema_json": str(exc)}) from exc
        expected = attrs.get("expected_updated_at")
        if self.instance and expected and expected != self.instance.updated_at:
            raise serializers.ValidationError({"detail": "This form changed after you opened it. Reload before saving."})
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop("expected_updated_at", None)
        validated_data.pop("edit_mode", None)
        schema = validated_data.get("draft_schema_json")
        if isinstance(schema, dict):
            validated_data["name"] = str(schema.get("title") or instance.name).strip()
            validated_data["description"] = str(schema.get("description") or "").strip()
        return super().update(instance, validated_data)


class CMSContributorFormSummarySerializer(serializers.ModelSerializer):
    """Review-queue row without the potentially large draft form schema."""

    current_published_version_number = serializers.SerializerMethodField()

    class Meta:
        model = CMSContributorForm
        fields = [
            "id", "key", "name", "description", "status", "current_published_version",
            "current_published_version_number", "has_unpublished_changes", "review_notes",
            "published_at", "updated_at",
        ]
        read_only_fields = fields

    def get_current_published_version_number(self, obj):
        return obj.current_published_version.version_number if obj.current_published_version_id else None


class CMSMediaAssetSummarySerializer(serializers.ModelSerializer):
    """Media index row that deliberately avoids a full CMS reference scan."""

    url = serializers.SerializerMethodField()

    class Meta:
        model = CMSMediaAsset
        fields = [
            "id", "file", "url", "file_type", "mime_type", "size", "alt_text", "caption",
            "is_archived", "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        url = obj.resolved_public_url
        if not url:
            return ""
        request = self.context.get("request")
        if request and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url


class CMSRevisionSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()
    is_target_deleted = serializers.SerializerMethodField()

    class Meta:
        model = CMSRevision
        fields = [
            "id", "content_type", "object_id", "version_number", "action", "status_before", "status_after",
            "snapshot_json", "changed_by", "changed_by_name", "is_target_deleted", "created_at",
        ]
        read_only_fields = fields

    def get_changed_by_name(self, obj):
        return _user_display(obj.changed_by)

    def get_content_type(self, obj):
        return obj.content_type_key

    def get_is_target_deleted(self, obj):
        return obj.content_object is None


class CMSRevisionSummaryListSerializer(serializers.ListSerializer):
    """Resolve deleted-target flags in one query per target model, not one per revision."""

    def to_representation(self, data):
        instances = list(data.all() if hasattr(data, "all") else data)
        grouped = {}
        for revision in instances:
            grouped.setdefault(revision.content_type, set()).add(revision.object_id)
        for content_type, object_ids in grouped.items():
            model = content_type.model_class()
            existing = set(model.objects.filter(pk__in=object_ids).values_list("pk", flat=True)) if model else set()
            for revision in instances:
                if revision.content_type_id == content_type.pk:
                    revision._cms_target_deleted = revision.object_id not in existing
        return super().to_representation(instances)


class CMSRevisionSummarySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    content_type = serializers.SerializerMethodField()
    is_target_deleted = serializers.SerializerMethodField()

    class Meta:
        model = CMSRevision
        list_serializer_class = CMSRevisionSummaryListSerializer
        fields = [
            "id", "content_type", "object_id", "version_number", "action", "status_before",
            "status_after", "changed_by_name", "is_target_deleted", "created_at",
        ]
        read_only_fields = fields

    def get_changed_by_name(self, obj):
        return _user_display(obj.changed_by)

    def get_content_type(self, obj):
        return obj.content_type_key

    def get_is_target_deleted(self, obj):
        if hasattr(obj, "_cms_target_deleted"):
            return obj._cms_target_deleted
        return obj.content_object is None


class CMSSiteSettingSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSSiteSetting
        fields = ["id", "key", "value_json", "description", "updated_by", "updated_by_name", "updated_at"]
        read_only_fields = ["updated_by", "updated_by_name", "updated_at"]

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)
