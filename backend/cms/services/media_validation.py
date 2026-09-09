import mimetypes
from pathlib import Path

from rest_framework.exceptions import APIException

from cms.models import CMSMediaAsset, CMSSiteSetting


ALLOWED_TYPES_SETTING = "media-upload-allowed-types"
MAX_BYTES_SETTING = "media-upload-max-bytes"

DEFAULT_ALLOWED_TYPES = {
    "image": ["image/jpeg", "image/png", "image/webp"],
    "document": [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ],
}
DEFAULT_MAX_BYTES = {
    "image": 5 * 1024 * 1024,
    "document": 20 * 1024 * 1024,
}
EXTENSION_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class CMSMediaValidationError(APIException):
    status_code = 422
    default_code = "invalid_media_upload"

    def __init__(self, detail=None, code=None):
        self.raw_detail = detail or {}
        super().__init__(detail=detail, code=code)


def _setting_value(key, fallback):
    try:
        value = CMSSiteSetting.objects.filter(key=key).values_list("value_json", flat=True).first()
    except Exception:
        # This keeps startup and pre-migration management commands usable.
        return fallback
    return value if isinstance(value, dict) else fallback


def get_upload_policy():
    allowed = _setting_value(ALLOWED_TYPES_SETTING, DEFAULT_ALLOWED_TYPES)
    limits = _setting_value(MAX_BYTES_SETTING, DEFAULT_MAX_BYTES)
    return {
        "allowed_types": {
            "image": list(allowed.get("image") or DEFAULT_ALLOWED_TYPES["image"]),
            "document": list(allowed.get("document") or DEFAULT_ALLOWED_TYPES["document"]),
        },
        "max_bytes": {
            "image": int(limits.get("image") or DEFAULT_MAX_BYTES["image"]),
            "document": int(limits.get("document") or DEFAULT_MAX_BYTES["document"]),
        },
    }


def validate_media_upload(file_obj):
    policy = get_upload_policy()
    provided_type = str(getattr(file_obj, "content_type", "") or "").lower()
    extension = Path(str(getattr(file_obj, "name", ""))).suffix.lower()
    content_type = provided_type or EXTENSION_MIME_TYPES.get(extension) or mimetypes.guess_type(
        getattr(file_obj, "name", "")
    )[0] or ""

    # Require the extension and declared type to agree for known extensions. This
    # blocks simple content-type spoofing while allowing clients that omit MIME.
    extension_type = EXTENSION_MIME_TYPES.get(extension)
    if extension_type and provided_type and extension_type != provided_type:
        content_type = ""

    file_type = ""
    for candidate in (CMSMediaAsset.FILE_TYPE_IMAGE, CMSMediaAsset.FILE_TYPE_DOCUMENT):
        if content_type in policy["allowed_types"][candidate]:
            file_type = candidate
            break

    if not file_type:
        raise CMSMediaValidationError(
            {
                "reason": "file_type_not_allowed",
                "detail": "This file type is not allowed by the current CMS upload policy.",
                "mime_type": content_type or provided_type or "unknown",
                "allowed_types": policy["allowed_types"],
            }
        )

    size = int(getattr(file_obj, "size", 0) or 0)
    max_bytes = policy["max_bytes"][file_type]
    if size > max_bytes:
        raise CMSMediaValidationError(
            {
                "reason": "file_too_large",
                "detail": "The file exceeds the current CMS upload limit.",
                "file_type": file_type,
                "current_limit": max_bytes,
                "size": size,
            }
        )

    return {"file_type": file_type, "mime_type": content_type, "size": size}
