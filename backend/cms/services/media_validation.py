import mimetypes

from django.conf import settings
from rest_framework import serializers

from cms.models import CMSMediaAsset


ALLOWED_MIME_TYPES = {
    "image/jpeg": CMSMediaAsset.FILE_TYPE_IMAGE,
    "image/png": CMSMediaAsset.FILE_TYPE_IMAGE,
    "image/webp": CMSMediaAsset.FILE_TYPE_IMAGE,
    "image/gif": CMSMediaAsset.FILE_TYPE_IMAGE,
    "application/pdf": CMSMediaAsset.FILE_TYPE_DOCUMENT,
}


def validate_media_upload(file_obj):
    max_bytes = getattr(settings, "CMS_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    size = getattr(file_obj, "size", 0) or 0
    if size > max_bytes:
        raise serializers.ValidationError(
            {"file": f"File is too large. Maximum allowed size is {max_bytes // (1024 * 1024)} MB."}
        )

    content_type = getattr(file_obj, "content_type", "") or ""
    if not content_type:
        content_type = mimetypes.guess_type(getattr(file_obj, "name", ""))[0] or ""

    file_type = ALLOWED_MIME_TYPES.get(content_type)
    if not file_type:
        allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
        raise serializers.ValidationError({"file": f"Unsupported file type. Allowed types: {allowed}."})

    return {
        "file_type": file_type,
        "mime_type": content_type,
        "size": size,
    }

