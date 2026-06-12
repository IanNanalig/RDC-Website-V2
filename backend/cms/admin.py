from django.contrib import admin

from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection, CMSRevision


class CMSPageSectionInline(admin.TabularInline):
    model = CMSPageSection
    extra = 0
    fields = ["section_key", "section_type", "order", "is_visible", "schema_version"]


@admin.register(CMSPage)
class CMSPageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "status", "has_unpublished_changes", "published_at", "updated_at"]
    list_filter = ["status", "has_unpublished_changes"]
    search_fields = ["title", "slug"]
    inlines = [CMSPageSectionInline]


@admin.register(CMSPageSection)
class CMSPageSectionAdmin(admin.ModelAdmin):
    list_display = ["section_key", "page", "section_type", "order", "is_visible", "updated_at"]
    list_filter = ["section_type", "is_visible"]
    search_fields = ["section_key", "page__title", "page__slug"]


@admin.register(CMSArticle)
class CMSArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "category", "status", "featured", "has_unpublished_changes", "published_at"]
    list_filter = ["status", "category", "featured", "has_unpublished_changes"]
    search_fields = ["title", "slug", "summary"]


@admin.register(CMSMediaAsset)
class CMSMediaAssetAdmin(admin.ModelAdmin):
    list_display = ["file", "file_type", "mime_type", "size", "is_archived", "created_at"]
    list_filter = ["file_type", "is_archived"]
    search_fields = ["file", "alt_text", "caption"]


@admin.register(CMSRevision)
class CMSRevisionAdmin(admin.ModelAdmin):
    list_display = ["content_type", "object_id", "version_number", "action", "changed_by", "created_at"]
    list_filter = ["content_type", "action"]
    search_fields = ["object_id", "changed_by__username", "changed_by__full_name"]
    readonly_fields = ["snapshot_json", "created_at"]
