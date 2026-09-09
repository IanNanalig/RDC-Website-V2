from django.middleware.gzip import GZipMiddleware


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
