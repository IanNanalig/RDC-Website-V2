from django.urls import path
from rest_framework.routers import DefaultRouter

from cms.views import (
    AdminCMSArticleViewSet,
    AdminCMSMediaAssetViewSet,
    AdminCMSPageSectionViewSet,
    AdminCMSPageViewSet,
    AdminCMSRevisionViewSet,
    PublicCMSArticleDetailView,
    PublicCMSArticleListView,
    PublicCMSPageView,
)

router = DefaultRouter()
router.register("admin/cms/pages", AdminCMSPageViewSet, basename="admin-cms-pages")
router.register("admin/cms/sections", AdminCMSPageSectionViewSet, basename="admin-cms-sections")
router.register("admin/cms/articles", AdminCMSArticleViewSet, basename="admin-cms-articles")
router.register("admin/cms/media", AdminCMSMediaAssetViewSet, basename="admin-cms-media")
router.register("admin/cms/revisions", AdminCMSRevisionViewSet, basename="admin-cms-revisions")

urlpatterns = [
    path("public/cms/pages/<slug:slug>/", PublicCMSPageView.as_view(), name="public-cms-page"),
    path("public/cms/news/", PublicCMSArticleListView.as_view(), name="public-cms-news"),
    path("public/cms/news/<slug:slug>/", PublicCMSArticleDetailView.as_view(), name="public-cms-news-detail"),
]

urlpatterns += router.urls

