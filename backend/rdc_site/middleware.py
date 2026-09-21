import logging
import time

from django.conf import settings
from django.middleware.gzip import GZipMiddleware


logger = logging.getLogger("rdc.performance")


class StrongETagGZipMiddleware(GZipMiddleware):
    """Compress API bodies while preserving their application-level strong validator."""

    max_random_bytes = 0

    def process_response(self, request, response):
        response = super().process_response(request, response)
        etag = response.get("ETag", "")
        cache_control = response.get("Cache-Control", "")
        if request.path.startswith("/api/") and "no-cache" in cache_control and etag.startswith("W/\""):
            response["ETag"] = etag[2:]
        return response


class CMSRequestTimingMiddleware:
    """Expose CMS server time so slow browser requests can be separated from network delay."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = self.get_response(request)
        if request.path.startswith("/api/admin/cms/"):
            duration_ms = (time.perf_counter() - started_at) * 1000
            response["Server-Timing"] = f"app;dur={duration_ms:.1f}"
            response["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
            warning_ms = getattr(settings, "CMS_SLOW_REQUEST_MS", 1000)
            if duration_ms >= warning_ms:
                logger.warning(
                    "Slow CMS request method=%s path=%s status=%s duration_ms=%.1f",
                    request.method,
                    request.path,
                    response.status_code,
                    duration_ms,
                )
        return response
