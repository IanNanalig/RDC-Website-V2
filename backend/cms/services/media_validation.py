import mimetypes
import json
import shutil
import subprocess
import tempfile
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
    "audio": ["audio/mpeg", "audio/mp4"],
    "video": ["video/mp4", "video/webm"],
}
DEFAULT_MAX_BYTES = {
    "image": 5 * 1024 * 1024,
    "document": 20 * 1024 * 1024,
    "audio": 20 * 1024 * 1024,
    "video": 50 * 1024 * 1024,
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
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
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
        "allowed_types": {key: list(allowed.get(key) or defaults) for key, defaults in DEFAULT_ALLOWED_TYPES.items()},
        "max_bytes": {key: int(limits.get(key) or default) for key, default in DEFAULT_MAX_BYTES.items()},
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
    for candidate in (CMSMediaAsset.FILE_TYPE_IMAGE, CMSMediaAsset.FILE_TYPE_DOCUMENT,
                      CMSMediaAsset.FILE_TYPE_AUDIO, CMSMediaAsset.FILE_TYPE_VIDEO):
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


def extract_media_metadata(file_obj, file_type):
    """Probe only approved uploads; preserve the stream position for Django storage."""
    result = {"original_filename": Path(str(file_obj.name)).name[:255]}
    if file_type == CMSMediaAsset.FILE_TYPE_IMAGE:
        try:
            from PIL import Image
            position = file_obj.tell()
            file_obj.seek(0)
            with Image.open(file_obj) as image:
                result.update(width=image.width, height=image.height)
            file_obj.seek(position)
        except Exception as exc:
            raise CMSMediaValidationError({"detail": "Image dimensions could not be read.", "reason": "invalid_image"}) from exc
    if file_type in {CMSMediaAsset.FILE_TYPE_AUDIO, CMSMediaAsset.FILE_TYPE_VIDEO}:
        if not shutil.which("ffprobe"):
            raise CMSMediaValidationError({"detail": "Audio/video probing is unavailable on this server.", "reason": "probe_unavailable"})
        position = file_obj.tell()
        try:
            file_obj.seek(0)
            with tempfile.TemporaryDirectory(prefix="rdc-media-probe-") as directory:
                path = Path(directory) / f"upload{Path(file_obj.name).suffix.lower()}"
                with path.open("wb") as temporary:
                    for chunk in file_obj.chunks():
                        temporary.write(chunk)
                completed = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                    capture_output=True, text=True, timeout=20, check=True,
                )
            probe = json.loads(completed.stdout)
            duration = float((probe.get("format") or {}).get("duration") or 0)
            if duration <= 0:
                raise ValueError("Missing duration")
            result["duration_seconds"] = duration
            if file_type == CMSMediaAsset.FILE_TYPE_VIDEO:
                stream = next((item for item in probe.get("streams", []) if item.get("codec_type") == "video"), {})
                result.update(width=int(stream.get("width") or 0), height=int(stream.get("height") or 0))
                if not result["width"] or not result["height"]:
                    raise ValueError("Missing video dimensions")
        except (subprocess.SubprocessError, ValueError, OSError, json.JSONDecodeError) as exc:
            raise CMSMediaValidationError({"detail": "Audio/video metadata could not be read.", "reason": "invalid_media"}) from exc
        finally:
            file_obj.seek(position)
    return result
