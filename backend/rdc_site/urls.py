import re

from django.contrib import admin
from django.conf import settings
from django.urls import path, include, re_path
from django.views.static import serve
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def media_urlpatterns():
    if not settings.SERVE_MEDIA_FILES:
        return []

    media_url = settings.MEDIA_URL
    if not media_url.startswith("/") or "://" in media_url:
        return []

    media_prefix = media_url.lstrip("/")
    if not media_prefix.endswith("/"):
        media_prefix = f"{media_prefix}/"

    return [
        re_path(
            rf"^{re.escape(media_prefix)}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        )
    ]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('projects.urls')),
    path('api/', include('cms.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

urlpatterns += media_urlpatterns()
