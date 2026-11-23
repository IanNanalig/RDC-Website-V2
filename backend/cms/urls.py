from django.urls import path
from rest_framework.routers import DefaultRouter

from cms.views import (
    AdminCMSArticleViewSet,
    AdminCMSCarouselItemViewSet,
    AdminCMSContributorFormViewSet,
    AdminCMSMediaAssetViewSet,
    AdminCMSPageSectionViewSet,
    AdminCMSPageViewSet,
    AdminCMSPublicationCategoryViewSet,
    AdminCMSPublicationDocumentViewSet,
    AdminCMSResolutionViewSet,
    AdminCMSModuleListView,
    AdminCMSModuleDetailView,
    AdminCMSModuleActionView,
    AdminCMSReviewQueueView,
    AdminAIHistoricalReferencesView,
    AdminAIPriorityCMSView,
    AdminAIPriorityDraftView,
    AdminAIPriorityDraftPublishView,
    AdminAIPriorityDraftPreviewView,
    AdminAIPriorityHistoryView,
    AdminAIPriorityRestoreView,
    AdminCMSSiteSettingViewSet,
    PublicCMSArticleDetailView,
    PublicCMSArticleListView,
    PublicCMSPageView,
    ContributorFormCurrentView,
    ContributorFormVersionView,
    PublicCMSSiteSettingsView,
)
from projects.views import AdminEventViewSet, PublicEventViewSet
from cms.form_catalog_views import CommitteeCatalogView, ContributorFormCatalogView, LocationCatalogView

router = DefaultRouter()
router.register("admin/cms/pages", AdminCMSPageViewSet, basename="admin-cms-pages")
router.register("admin/cms/sections", AdminCMSPageSectionViewSet, basename="admin-cms-sections")
router.register("admin/cms/articles", AdminCMSArticleViewSet, basename="admin-cms-articles")
router.register("admin/cms/carousel-items", AdminCMSCarouselItemViewSet, basename="admin-cms-carousel-items")
router.register("admin/cms/publication-categories", AdminCMSPublicationCategoryViewSet, basename="admin-cms-publication-categories")
router.register("admin/cms/publication-documents", AdminCMSPublicationDocumentViewSet, basename="admin-cms-publication-documents")
router.register("admin/cms/resolutions", AdminCMSResolutionViewSet, basename="admin-cms-resolutions")
router.register("admin/cms/forms", AdminCMSContributorFormViewSet, basename="admin-cms-forms")
router.register("admin/cms/news", AdminCMSArticleViewSet, basename="admin-cms-news")
router.register("admin/cms/media", AdminCMSMediaAssetViewSet, basename="admin-cms-media")
router.register("admin/cms/settings", AdminCMSSiteSettingViewSet, basename="admin-cms-settings")
router.register("admin/cms/events", AdminEventViewSet, basename="admin-cms-events")

urlpatterns = [
    path("admin/contributor-form-catalogs/", ContributorFormCatalogView.as_view(), name="contributor-form-catalogs"),
    path("admin/contributor-form-catalogs/locations/<slug:code>/", LocationCatalogView.as_view(), name="contributor-form-location"),
    path("admin/contributor-form-catalogs/committees/", CommitteeCatalogView.as_view(), name="contributor-form-committees"),
    path("admin/contributor-form-catalogs/committees/<slug:code>/", CommitteeCatalogView.as_view(), name="contributor-form-committee"),
    path("admin/cms/modules/", AdminCMSModuleListView.as_view(), name="admin-cms-modules"),
    path("admin/cms/modules/<slug:slug>/", AdminCMSModuleDetailView.as_view(), name="admin-cms-module-detail"),
    path("admin/cms/modules/<slug:slug>/<slug:operation>/", AdminCMSModuleActionView.as_view(), name="admin-cms-module-action"),
    path("contributor-forms/<slug:key>/current/", ContributorFormCurrentView.as_view(), name="contributor-form-current"),
    path("contributor-forms/<slug:key>/versions/<int:version_number>/", ContributorFormVersionView.as_view(), name="contributor-form-version"),
    path("public/cms/pages/<slug:slug>/", PublicCMSPageView.as_view(), name="public-cms-page"),
    path("public/cms/news/", PublicCMSArticleListView.as_view(), name="public-cms-news"),
    path("public/cms/news/<slug:slug>/", PublicCMSArticleDetailView.as_view(), name="public-cms-news-detail"),
    path("public/cms/events/", PublicEventViewSet.as_view({"get": "list"}), name="public-cms-events"),
    path("public/cms/site-settings/", PublicCMSSiteSettingsView.as_view(), name="public-cms-site-settings"),
    path("admin/cms/review-queue/", AdminCMSReviewQueueView.as_view(), name="admin-cms-review-queue"),
    path("admin/cms/ai-scoring/", AdminAIPriorityCMSView.as_view(), name="admin-cms-ai-scoring"),
    path("admin/cms/ai-scoring/drafts/", AdminAIPriorityDraftView.as_view(), name="admin-cms-ai-scoring-drafts"),
    path("admin/cms/ai-scoring/drafts/<int:pk>/", AdminAIPriorityDraftView.as_view(), name="admin-cms-ai-scoring-draft-detail"),
    path("admin/cms/ai-scoring/drafts/<int:pk>/publish/", AdminAIPriorityDraftPublishView.as_view(), name="admin-cms-ai-scoring-draft-publish"),
    path("admin/cms/ai-scoring/drafts/<int:pk>/preview/", AdminAIPriorityDraftPreviewView.as_view(), name="admin-cms-ai-scoring-draft-preview"),
    path("admin/cms/ai-scoring/historical-references/", AdminAIHistoricalReferencesView.as_view(), name="admin-ai-historical-references"),
    path("admin/cms/ai-scoring/versions/", AdminAIPriorityHistoryView.as_view(), name="admin-ai-scoring-versions"),
    path("admin/cms/ai-scoring/versions/<int:pk>/", AdminAIPriorityHistoryView.as_view(), name="admin-ai-scoring-version-detail"),
    path("admin/cms/ai-scoring/versions/<int:pk>/restore/", AdminAIPriorityRestoreView.as_view(), name="admin-ai-scoring-restore"),
]

urlpatterns += router.urls

