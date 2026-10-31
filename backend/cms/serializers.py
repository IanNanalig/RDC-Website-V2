from datetime import date, timedelta

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
from cms.services.locking import lock_is_active
from cms.services.media_usage import get_media_usage_map, get_media_usages
from cms.services.media_validation import validate_media_upload


def _user_display(user):
    if not user:
        return ""
    return user.get_full_name() or user.get_username()


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
            "original_filename", "width", "height", "duration_seconds", "category", "tags",
        ]
        read_only_fields = [
            "storage_backend", "storage_key", "public_url", "file_type", "mime_type", "size",
            "uploaded_by", "uploaded_by_name", "used_by", "usage_count", "can_archive", "created_at",
            "original_filename", "width", "height", "duration_seconds",
        ]

    def validate_category(self, value):
        from cms.models import CMSSiteSetting
        setting = CMSSiteSetting.objects.filter(key="media-categories").values_list("value_json", flat=True).first() or {}
        choices = setting.get("categories") if isinstance(setting, dict) else None
        allowed = ["General"] + (choices if isinstance(choices, list) else [])
        if value not in allowed and value != getattr(self.instance, "category", None):
            raise serializers.ValidationError("Choose a category from Site Settings.")
        return value

    def validate_tags(self, value):
        if not isinstance(value, list) or len(value) > 10 or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 40 for tag in value):
            raise serializers.ValidationError("Use up to 10 nonempty tags, 40 characters each.")
        return list(dict.fromkeys(tag.strip() for tag in value))

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
            "page", "section_key", "section_type", "order", "schema_version", "is_visible",
            "status", "lock_owner", "lock_owner_name", "lock_acquired_at", "lock_expires_at",
            "is_locked", "locked_by_me", "created_at", "updated_at",
        ]

    def validate_content_json(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Section content must be a JSON object.")
        page_slug = getattr(getattr(self.instance, "page", None), "slug", "")
        section_key = getattr(self.instance, "section_key", "")

        if page_slug == "about-rdc" and section_key == "committees":
            expected = {"executive", "sectoral", "special", "affiliate", "advisory"}
            items = value.get("items")
            if not isinstance(items, list):
                raise serializers.ValidationError("The five fixed committee entries are required.")
            codes = [str(item.get("id") or "") for item in items if isinstance(item, dict)]
            if len(codes) != 5 or set(codes) != expected:
                raise serializers.ValidationError(
                    "Committee structure is fixed. Keep executive, sectoral, special, affiliate, and advisory exactly once."
                )

        if page_slug == "about-rdc" and section_key == "organization-structure":
            expected = {
                "chairperson", "vice-chair", "secretariat", "secretary", "executive-committee",
                "voting-members", "non-voting-members", "special-non-voting", "sectoral-committees",
                "special-committees", "affiliate-committees", "advisory-committee",
            }
            nodes = value.get("nodes")
            if not isinstance(nodes, list):
                raise serializers.ValidationError({"nodes": "The fixed organization positions are required."})
            codes = [str(node.get("id") or "") for node in nodes if isinstance(node, dict)]
            if len(codes) != len(expected) or set(codes) != expected:
                raise serializers.ValidationError({
                    "nodes": "Organization structure is fixed. Keep each approved position exactly once."
                })
            for index, node in enumerate(nodes):
                items = node.get("items") if isinstance(node, dict) else None
                if items is not None and not isinstance(items, list):
                    raise serializers.ValidationError({"nodes": {index: {"items": "Child labels must be a list."}}})

        if page_slug == "about-rdc" and section_key == "resolutions-archive":
            years = value.get("years")
            if years is not None and not isinstance(years, list):
                raise serializers.ValidationError({"years": "Resolution years must be a list."})
            seen_years = set()
            year_errors = {}
            current_year = timezone.now().year
            for year_index, year_row in enumerate(years or []):
                if not isinstance(year_row, dict):
                    year_errors[year_index] = "Each resolution year must be an object."
                    continue
                raw_year = str(year_row.get("year") or "").strip()
                if not raw_year.isdigit() or len(raw_year) != 4:
                    year_errors[year_index] = {"year": "Enter a four-digit resolution year."}
                    continue
                year = int(raw_year)
                if year < 1900 or year > current_year + 5:
                    year_errors[year_index] = {"year": "Enter a valid resolution year."}
                    continue
                if year in seen_years:
                    year_errors[year_index] = {"year": "Each resolution year may appear only once."}
                    continue
                seen_years.add(year)
                resolutions = year_row.get("resolutions", year_row.get("items", []))
                if not isinstance(resolutions, list):
                    year_errors[year_index] = {"resolutions": "Resolutions must be a list."}
                    continue
                resolution_errors = {}
                for resolution_index, resolution in enumerate(resolutions):
                    if isinstance(resolution, str):
                        if not resolution.strip():
                            resolution_errors[resolution_index] = "Resolution title cannot be blank."
                        continue
                    if not isinstance(resolution, dict):
                        resolution_errors[resolution_index] = "Each resolution must be an object."
                        continue
                    if not str(resolution.get("title") or resolution.get("number") or "").strip():
                        resolution_errors[resolution_index] = {"title": "Resolution title is required."}
                    raw_date = str(resolution.get("date") or "").strip()
                    if raw_date:
                        try:
                            parsed_date = date.fromisoformat(raw_date)
                            if parsed_date.year != year:
                                raise ValueError
                        except ValueError:
                            resolution_errors[resolution_index] = {
                                "date": "Use YYYY-MM-DD and match the selected resolution year."
                            }
                    media_id = resolution.get("mediaAssetId") or resolution.get("documentAssetId") or resolution.get("attachment")
                    if media_id:
                        try:
                            media = CMSMediaAsset.objects.filter(pk=media_id, is_archived=False).first()
                        except (TypeError, ValueError):
                            media = None
                        if not media or media.file_type != CMSMediaAsset.FILE_TYPE_DOCUMENT:
                            current = resolution_errors.get(resolution_index, {})
                            resolution_errors[resolution_index] = {
                                **(current if isinstance(current, dict) else {}),
                                "mediaAssetId": "Choose an active document from the Media Library.",
                            }
                if resolution_errors:
                    existing = year_errors.get(year_index, {})
                    year_errors[year_index] = {**existing, "resolutions": resolution_errors}
            if year_errors:
                raise serializers.ValidationError({"years": year_errors})
            for field in ("legendItems", "categoryItems"):
                if field in value and not isinstance(value[field], list):
                    raise serializers.ValidationError({field: "This value must be a list."})

        if page_slug == "contact" and section_key == "main-office":
            email = str(value.get("email") or "").strip()
            if email:
                serializers.EmailField().run_validation(email)
            phones = value.get("phones")
            if phones is not None and not isinstance(phones, list):
                raise serializers.ValidationError({"phones": "Phone numbers must be a list."})

        if page_slug == "contact" and section_key == "location-map":
            prohibited = {"embedHtml", "embed_html", "embedUrl", "embed_url", "apiKey", "api_key"}
            if prohibited.intersection(value):
                raise serializers.ValidationError("Map HTML, embed URLs, and API keys are not accepted.")
            query = str(value.get("mapQuery") or value.get("address") or "").strip()
            if len(query) > 500:
                raise serializers.ValidationError({"mapQuery": "Map address must be 500 characters or fewer."})
            latitude = str(value.get("latitude") or "").strip()
            longitude = str(value.get("longitude") or "").strip()
            if bool(latitude) != bool(longitude):
                raise serializers.ValidationError("Provide both latitude and longitude, or leave both blank.")
            if latitude and longitude:
                try:
                    lat_value = float(latitude)
                    lng_value = float(longitude)
                except (TypeError, ValueError):
                    raise serializers.ValidationError("Latitude and longitude must be numeric.")
                if not -90 <= lat_value <= 90 or not -180 <= lng_value <= 180:
                    raise serializers.ValidationError("Latitude or longitude is outside its valid range.")
                value = {**value, "latitude": lat_value, "longitude": lng_value}

        if page_slug == "regional-profile" and section_key == "regional-overview":
            numeric_fields = {
                "population": "Population",
                "gdpShare": "GDP share",
                "landArea": "Land area",
                "cityCount": "City count",
                "municipalityCount": "Municipality count",
            }
            errors = {}
            for field, label in numeric_fields.items():
                raw = value.get(field)
                if raw in (None, ""):
                    continue
                try:
                    float(raw)
                except (TypeError, ValueError):
                    errors[field] = f"{label} must contain only a numeric value; put the unit in its display-unit field."
            data_year = value.get("dataYear")
            if data_year not in (None, ""):
                try:
                    year = int(data_year)
                    if not 1900 <= year <= 2200:
                        raise ValueError
                except (TypeError, ValueError):
                    errors["dataYear"] = "Data year must be between 1900 and 2200."
            if errors:
                raise serializers.ValidationError(errors)

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


def _validate_public_link(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith("/") and not value.startswith("//"):
        return value
    from urllib.parse import urlsplit
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise serializers.ValidationError("Use a relative site path or an http/https URL.")
    return value


class CMSManagedContentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    def _name(self, value):
        return _user_display(value)

    def get_created_by_name(self, obj):
        return self._name(obj.created_by)

    def get_updated_by_name(self, obj):
        return self._name(obj.updated_by)

    def get_submitted_by_name(self, obj):
        return self._name(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return self._name(obj.reviewed_by)

    @property
    def workflow_fields(self):
        return [
            "status", "published_snapshot_json", "has_unpublished_changes", "review_notes",
            "created_by_name", "updated_by_name", "submitted_by_name", "reviewed_by_name",
            "published_at", "archived_at", "created_at", "updated_at",
        ]


class CMSCarouselItemSerializer(CMSManagedContentSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CMSCarouselItem
        fields = [
            "id", "stable_key", "title", "description", "image", "image_url", "legacy_image_url",
            "primary_label", "primary_url", "secondary_label", "secondary_url", "sort_order",
            "status", "published_snapshot_json", "has_unpublished_changes", "review_notes",
            "created_by_name", "updated_by_name", "submitted_by_name", "reviewed_by_name",
            "published_at", "archived_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "published_snapshot_json", "has_unpublished_changes", "review_notes",
            "created_by_name", "updated_by_name", "submitted_by_name", "reviewed_by_name",
            "published_at", "archived_at", "created_at", "updated_at",
        ]

    def get_image_url(self, obj):
        return obj.image.resolved_public_url if obj.image and not obj.image.is_archived else obj.legacy_image_url

    def validate_stable_key(self, value):
        if self.instance and value != self.instance.stable_key:
            raise serializers.ValidationError("The stable key cannot be changed.")
        return value

    def validate_image(self, value):
        if value and (value.is_archived or value.file_type != CMSMediaAsset.FILE_TYPE_IMAGE):
            raise serializers.ValidationError("Choose an active image from the media library.")
        return value

    def validate_primary_url(self, value):
        return _validate_public_link(value)

    def validate_secondary_url(self, value):
        return _validate_public_link(value)


class CMSPublicationCategorySerializer(CMSManagedContentSerializer):
    document_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = CMSPublicationCategory
        fields = [
            "id", "code", "name", "description", "icon", "color", "sort_order", "document_count",
            "status", "published_snapshot_json", "has_unpublished_changes", "review_notes",
            "created_by_name", "updated_by_name", "submitted_by_name", "reviewed_by_name",
            "published_at", "archived_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "document_count", "status", "published_snapshot_json",
            "has_unpublished_changes", "review_notes", "created_by_name", "updated_by_name",
            "submitted_by_name", "reviewed_by_name", "published_at", "archived_at", "created_at", "updated_at",
        ]

    def validate_code(self, value):
        if self.instance and value != self.instance.code:
            raise serializers.ValidationError("Publication category codes cannot be changed.")
        return value

class CMSPublicationDocumentSerializer(CMSManagedContentSerializer):
    attachment_url = serializers.SerializerMethodField()
    category_code = serializers.CharField(source="category.code", read_only=True)

    class Meta:
        model = CMSPublicationDocument
        fields = [
            "id", "stable_key", "category", "category_code", "title", "description", "publication_date",
            "document_type", "attachment", "attachment_url", "external_url", "legacy_file_size", "sort_order",
            "status", "published_snapshot_json", "has_unpublished_changes", "review_notes", "created_by_name",
            "updated_by_name", "submitted_by_name", "reviewed_by_name", "published_at", "archived_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "category_code", "attachment_url", "status", "published_snapshot_json",
            "has_unpublished_changes", "review_notes", "created_by_name", "updated_by_name",
            "submitted_by_name", "reviewed_by_name", "published_at", "archived_at", "created_at", "updated_at",
        ]

    def get_attachment_url(self, obj):
        return obj.attachment.resolved_public_url if obj.attachment and not obj.attachment.is_archived else ""

    def validate_stable_key(self, value):
        if self.instance and value != self.instance.stable_key:
            raise serializers.ValidationError("The stable key cannot be changed.")
        return value

    def validate_category(self, value):
        if value.status == "archived" and (not self.instance or value.pk != self.instance.category_id):
            raise serializers.ValidationError("Choose an active publication category.")
        return value

    def validate_attachment(self, value):
        if value and (value.is_archived or value.file_type != CMSMediaAsset.FILE_TYPE_DOCUMENT):
            raise serializers.ValidationError("Choose an active document from the media library.")
        return value

    def validate_external_url(self, value):
        return _validate_public_link(value)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attachment = attrs.get("attachment", getattr(self.instance, "attachment", None))
        external_url = attrs.get("external_url", getattr(self.instance, "external_url", ""))
        if not attachment and not external_url:
            raise serializers.ValidationError("Choose a document attachment or provide a document URL.")
        return attrs


class CMSResolutionSerializer(CMSManagedContentSerializer):
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = CMSResolution
        fields = [
            "id", "stable_key", "resolution_number", "title", "description", "year", "resolution_date",
            "attachment", "attachment_url", "external_url", "sort_order", "status", "published_snapshot_json",
            "has_unpublished_changes", "review_notes", "created_by_name", "updated_by_name",
            "submitted_by_name", "reviewed_by_name", "published_at", "archived_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "attachment_url", "status", "published_snapshot_json", "has_unpublished_changes",
            "review_notes", "created_by_name", "updated_by_name", "submitted_by_name", "reviewed_by_name",
            "published_at", "archived_at", "created_at", "updated_at",
        ]

    def get_attachment_url(self, obj):
        return obj.attachment.resolved_public_url if obj.attachment and not obj.attachment.is_archived else ""

    def validate_stable_key(self, value):
        if self.instance and value != self.instance.stable_key:
            raise serializers.ValidationError("The stable key cannot be changed.")
        return value

    def validate_year(self, value):
        if value < 1900 or value > timezone.now().year + 5:
            raise serializers.ValidationError("Enter a valid resolution year.")
        return value

    def validate_attachment(self, value):
        if value and (value.is_archived or value.file_type != CMSMediaAsset.FILE_TYPE_DOCUMENT):
            raise serializers.ValidationError("Choose an active document from the media library.")
        return value

    def validate_external_url(self, value):
        return _validate_public_link(value)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        year = attrs.get("year", getattr(self.instance, "year", None))
        resolution_date = attrs.get("resolution_date", getattr(self.instance, "resolution_date", None))
        if resolution_date and resolution_date.year != year:
            raise serializers.ValidationError({"resolution_date": "Resolution date must match the selected year."})
        return attrs


class CMSContributorFormVersionSerializer(serializers.ModelSerializer):
    published_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSContributorFormVersion
        fields = [
            "id", "form", "version_number", "schema_json", "based_on_version",
            "migration_plan_json", "published_by_name", "published_at",
        ]
        read_only_fields = fields

    def get_published_by_name(self, obj):
        return _user_display(obj.published_by)


class CMSContributorFormVersionSummarySerializer(serializers.ModelSerializer):
    """Version history metadata without returning every complete form snapshot."""

    published_by_name = serializers.SerializerMethodField()
    schema_summary = serializers.SerializerMethodField()
    field_origins = serializers.SerializerMethodField()

    class Meta:
        model = CMSContributorFormVersion
        fields = [
            "id", "form", "version_number", "published_by_name", "published_at",
            "schema_summary", "field_origins", "based_on_version", "migration_plan_json",
        ]
        read_only_fields = fields

    def get_published_by_name(self, obj):
        return _user_display(obj.published_by)

    def get_schema_summary(self, obj):
        sections = [
            section for section in (obj.schema_json or {}).get("sections", [])
            if isinstance(section, dict) and not section.get("admin_only")
        ]
        fields = [
            field for section in sections for field in section.get("fields", [])
            if isinstance(field, dict)
        ]
        return {
            "section_count": len(sections),
            "field_count": len(fields),
            "custom_field_count": sum(
                1 for field in fields
                if str(field.get("key") or "").startswith("custom_")
                and field.get("type") != "document_upload"
            ),
        }

    def get_field_origins(self, obj):
        origins = {}
        for section_index, section in enumerate((obj.schema_json or {}).get("sections", [])):
            if not isinstance(section, dict) or section.get("admin_only"):
                continue
            for field_index, field in enumerate(section.get("fields", [])):
                if not isinstance(field, dict):
                    continue
                key = str(field.get("key") or "")
                if not key.startswith("custom_"):
                    continue
                saved_origin = field.get("retired_from")
                if section.get("key") == "retired_fields":
                    if isinstance(saved_origin, dict) and saved_origin.get("section_key"):
                        origins[key] = saved_origin
                    continue
                origins[key] = {
                    "section_key": str(section.get("key") or ""),
                    "section_title": str(section.get("title") or "Untitled section"),
                    "section_description": str(section.get("description") or ""),
                    "section_visible": section.get("visible", True) is not False,
                    "section_order": section_index,
                    "field_order": field_index,
                    "field_required": bool(field.get("required")),
                }
        return origins


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
    current_published_schema_json = serializers.SerializerMethodField()
    versions_summary = serializers.SerializerMethodField()
    expected_updated_at = serializers.DateTimeField(write_only=True, required=False)
    edit_mode = serializers.ChoiceField(choices=["update", "change"], write_only=True, required=False, default="update")

    class Meta:
        model = CMSContributorForm
        fields = [
            "id", "key", "name", "description", "status", "draft_schema_json",
            "current_published_version", "current_published_version_number", "has_unpublished_changes",
            "created_by_name", "updated_by_name", "submitted_by_name", "reviewed_by_name", "review_notes",
            "published_at", "lock_owner", "lock_owner_name", "lock_acquired_at", "lock_expires_at",
            "is_locked", "locked_by_me", "current_published_schema_json", "versions_summary",
            "created_at", "updated_at", "expected_updated_at", "edit_mode",
        ]
        read_only_fields = [
            "key", "status", "current_published_version", "current_published_version_number",
            "has_unpublished_changes", "created_by_name", "updated_by_name", "submitted_by_name",
            "reviewed_by_name", "review_notes", "published_at", "lock_owner", "lock_owner_name",
            "lock_acquired_at", "lock_expires_at", "is_locked", "locked_by_me", "created_at", "updated_at",
            "current_published_schema_json", "versions_summary",
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

    def get_current_published_schema_json(self, obj):
        return obj.current_published_version.schema_json if obj.current_published_version_id else None

    def get_versions_summary(self, obj):
        versions = getattr(obj, "cms_version_summaries", None)
        if versions is None:
            return []
        return CMSContributorFormVersionSummarySerializer(versions, many=True).data

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
            "is_archived", "created_at", "original_filename", "width", "height", "duration_seconds",
            "category", "tags", "uploaded_by_name",
        ]
        read_only_fields = fields

    uploaded_by_name = serializers.SerializerMethodField()

    def get_uploaded_by_name(self, obj):
        return _user_display(obj.uploaded_by)

    def get_url(self, obj):
        url = obj.resolved_public_url
        if not url:
            return ""
        request = self.context.get("request")
        if request and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url


class CMSSiteSettingSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CMSSiteSetting
        fields = ["id", "key", "value_json", "description", "updated_by", "updated_by_name", "updated_at"]
        read_only_fields = ["updated_by", "updated_by_name", "updated_at"]

    def get_updated_by_name(self, obj):
        return _user_display(obj.updated_by)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        key = instance.key if instance else attrs.get("key")
        if "value_json" not in attrs:
            return attrs
        if key == "project-concern-categories":
            from projects.concern_categories import CODE_PATTERN
            from projects.models import ProjectConcernReport

            value = attrs["value_json"]
            raw_categories = value.get("categories") if isinstance(value, dict) else None
            if not isinstance(raw_categories, list) or not raw_categories:
                raise serializers.ValidationError({"value_json": "Add at least one project concern category."})
            categories = []
            seen = set()
            for item in raw_categories:
                if not isinstance(item, dict):
                    raise serializers.ValidationError({"value_json": "Every concern category must include a code and label."})
                code = str(item.get("code") or "").strip().lower()
                label = " ".join(str(item.get("label") or "").split())
                if not CODE_PATTERN.fullmatch(code):
                    raise serializers.ValidationError({"value_json": "Category codes may contain lowercase letters, numbers, and underscores."})
                if code in seen:
                    raise serializers.ValidationError({"value_json": f"Category code {code} is duplicated."})
                if not label or len(label) > 200:
                    raise serializers.ValidationError({"value_json": "Category labels must contain 1 to 200 characters."})
                seen.add(code)
                categories.append({"code": code, "label": label, "active": bool(item.get("active", True))})
            if not any(item["active"] for item in categories):
                raise serializers.ValidationError({"value_json": "Keep at least one concern category active."})
            if instance:
                old = instance.value_json if isinstance(instance.value_json, dict) else {}
                old_codes = {
                    str(item.get("code") or "").strip().lower()
                    for item in old.get("categories", [])
                    if isinstance(item, dict)
                }
                removed_used = set(
                    ProjectConcernReport.objects.filter(category_code__in=old_codes - seen)
                    .values_list("category_code", flat=True)
                    .distinct()
                )
                if removed_used:
                    raise serializers.ValidationError(
                        {"value_json": "Used concern category codes cannot be removed; deactivate them instead."}
                    )
            attrs["value_json"] = {**value, "categories": categories}
            return attrs
        if key != "media-categories":
            return attrs
        value = attrs["value_json"]
        if not isinstance(value, dict) or not isinstance(value.get("categories", []), list):
            raise serializers.ValidationError({"value_json": "Media categories must be a list of names."})
        categories = [str(item).strip() for item in value.get("categories", []) if isinstance(item, str) and str(item).strip()]
        categories = list(dict.fromkeys(["General", *categories]))
        old_value = instance.value_json if isinstance(instance.value_json, dict) else {}
        old_categories = [str(item).strip() for item in old_value.get("categories", []) if isinstance(item, str) and str(item).strip()]
        removed = set(old_categories) - set(categories)
        if removed:
            used = list(
                CMSMediaAsset.objects.filter(category__in=removed)
                .values_list("category", flat=True)
                .distinct()
            )
            if used:
                names = ", ".join(sorted(used))
                raise serializers.ValidationError({"value_json": f"Reassign media using {names} before removing or renaming those categories."})
        attrs["value_json"] = {**value, "categories": categories}
        return attrs
