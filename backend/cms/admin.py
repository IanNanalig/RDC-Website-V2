from django.contrib import admin

from cms.models import (
    CMSArticle, CMSContributorForm, CMSContributorFormVersion, CMSMediaAsset, CMSPage,
    CMSPageSection, CMSSiteSetting,
)


class CMSPageSectionInline(admin.TabularInline):
    model = CMSPageSection
    extra = 0
    fields = ["section_key", "section_type", "order", "status", "is_visible", "schema_version"]


@admin.register(CMSPage)
class CMSPageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "status", "has_unpublished_changes", "published_at", "updated_at"]
    list_filter = ["status", "has_unpublished_changes"]
    search_fields = ["title", "slug"]
    inlines = [CMSPageSectionInline]


@admin.register(CMSPageSection)
class CMSPageSectionAdmin(admin.ModelAdmin):
    list_display = ["section_key", "page", "section_type", "order", "status", "is_visible", "lock_owner", "updated_at"]
    list_filter = ["section_type", "status", "is_visible"]
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


class CMSContributorFormVersionInline(admin.TabularInline):
    model = CMSContributorFormVersion
    extra = 0
    readonly_fields = ["version_number", "schema_json", "published_by", "published_at"]
    can_delete = False


@admin.register(CMSContributorForm)
class CMSContributorFormAdmin(admin.ModelAdmin):
    list_display = ["name", "key", "status", "current_published_version", "has_unpublished_changes", "updated_at"]
    list_filter = ["status", "has_unpublished_changes"]
    readonly_fields = ["current_published_version", "published_at", "created_at", "updated_at"]
    inlines = [CMSContributorFormVersionInline]


@admin.register(CMSSiteSetting)
class CMSSiteSettingAdmin(admin.ModelAdmin):
    list_display = ["key", "description", "updated_by", "updated_at"]
    search_fields = ["key", "description"]
