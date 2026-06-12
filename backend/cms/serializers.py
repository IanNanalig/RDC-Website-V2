from rest_framework import serializers

from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection, CMSRevision
from cms.services.media_validation import validate_media_upload


class CMSMediaAssetSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSMediaAsset
        fields = [
            "id",
            "file",
            "url",
            "file_type",
            "mime_type",
            "size",
            "alt_text",
            "caption",
            "uploaded_by",
            "uploaded_by_name",
            "is_archived",
            "created_at",
        ]
        read_only_fields = ["file_type", "mime_type", "size", "uploaded_by", "uploaded_by_name", "created_at"]

    def get_url(self, obj):
        return obj.public_url

    def get_uploaded_by_name(self, obj):
        user = obj.uploaded_by
        if not user:
            return ""
        return getattr(user, "full_name", "") or user.get_username()

    def validate_file(self, value):
        validate_media_upload(value)
        return value


class CMSPageSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CMSPageSection
        fields = [
            "id",
            "page",
            "section_key",
            "section_type",
            "order",
            "content_json",
            "schema_version",
            "is_visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_content_json(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Section content must be a JSON object.")
        return value


class CMSPageSerializer(serializers.ModelSerializer):
    sections = CMSPageSectionSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSPage
        fields = [
            "id",
            "title",
            "slug",
            "status",
            "published_snapshot_json",
            "has_unpublished_changes",
            "sections",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "published_snapshot_json",
            "has_unpublished_changes",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "published_at",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        return _user_display(obj.created_by)

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)


class CMSArticleSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSArticle
        fields = [
            "id",
            "title",
            "slug",
            "category",
            "summary",
            "body",
            "thumbnail",
            "thumbnail_url",
            "author",
            "featured",
            "status",
            "published_snapshot_json",
            "has_unpublished_changes",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "published_snapshot_json",
            "has_unpublished_changes",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "published_at",
            "created_at",
            "updated_at",
        ]

    def get_thumbnail_url(self, obj):
        return obj.thumbnail.public_url if obj.thumbnail and not obj.thumbnail.is_archived else ""

    def get_created_by_name(self, obj):
        return _user_display(obj.created_by)

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)


class CMSRevisionSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSRevision
        fields = [
            "id",
            "content_type",
            "object_id",
            "version_number",
            "action",
            "status_before",
            "status_after",
            "snapshot_json",
            "changed_by",
            "changed_by_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_changed_by_name(self, obj):
        return _user_display(obj.changed_by)


def _user_display(user):
    if not user:
        return ""
    return getattr(user, "full_name", "") or user.get_username()
