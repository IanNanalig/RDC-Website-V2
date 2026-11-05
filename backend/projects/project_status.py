"""Presentation and filter rules for simplified RDIP implementation statuses."""

from functools import lru_cache

CURRENT_IMPLEMENTATION_STATUSES = (
    "New", "Not Implemented", "Ongoing", "Completed", "On Hold", "Cancelled",
)

NOT_IMPLEMENTED_LEGACY_VALUES = ("Discontinued", "Dropped")
_NOT_IMPLEMENTED_LEGACY_KEYS = frozenset(item.casefold() for item in NOT_IMPLEMENTED_LEGACY_VALUES)
ONGOING_LEGACY_VALUES = ("Updated",)
_ONGOING_LEGACY_KEYS = frozenset(item.casefold() for item in ONGOING_LEGACY_VALUES)


def canonical_implementation_status(value):
    status = str(value or "").strip()
    if status.casefold() in _NOT_IMPLEMENTED_LEGACY_KEYS:
        return "Not Implemented"
    if status.casefold() in _ONGOING_LEGACY_KEYS:
        return "Ongoing"
    for official in CURRENT_IMPLEMENTATION_STATUSES:
        if status.casefold() == official.casefold():
            return official
    return status


@lru_cache(maxsize=256)
def _form_status_labels(form_key, version_number):
    """Return immutable status value-to-label mappings for one published form version."""
    try:
        from cms.models import CMSContributorFormVersion

        schema = CMSContributorFormVersion.objects.filter(
            form__key=form_key,
            version_number=version_number,
        ).values_list("schema_json", flat=True).first()
    except Exception:
        # Status presentation must never make project lists unavailable if CMS
        # data is temporarily inaccessible.
        return {}
    if not isinstance(schema, dict):
        return {}
    for section in schema.get("sections", []):
        if not isinstance(section, dict):
            continue
        for field in section.get("fields", []):
            if not isinstance(field, dict) or field.get("key") != "status":
                continue
            return {
                str(option.get("value")): str(option.get("label"))
                for option in field.get("options", [])
                if isinstance(option, dict)
                and str(option.get("value") or "").strip()
                and str(option.get("label") or "").strip()
            }
    return {}


def display_implementation_status(value, form_schema_marker=None):
    """Return the contributor-facing label for a stored status choice.

    CMS options use immutable values (for example ``option_1``) and editable
    labels (for example ``Test``).  Projects retain the value with their
    pinned form version, so presentation must resolve the label from that
    immutable version rather than expose an internal option key.
    """
    status = str(value or "").strip()
    if not status:
        return ""
    marker = form_schema_marker if isinstance(form_schema_marker, dict) else {}
    form_key = str(marker.get("key") or "simplified-rdip").strip() or "simplified-rdip"
    try:
        version_number = int(marker.get("version") or 0)
    except (TypeError, ValueError):
        version_number = 0
    if version_number > 0:
        label = _form_status_labels(form_key, version_number).get(status)
        if label:
            return label
    return canonical_implementation_status(status)


@lru_cache(maxsize=256)
def stored_status_values_for_label(label):
    """Find immutable stored values for a contributor-facing status label.

    The public API filters by stored JSON values, while its UI displays the
    corresponding CMS label.  Search all immutable form versions so a project
    remains findable after the status field is edited in a newer version.
    """
    target = str(label or "").strip().casefold()
    if not target:
        return frozenset()
    try:
        from cms.models import CMSContributorFormVersion

        schemas = CMSContributorFormVersion.objects.values_list("schema_json", flat=True)
    except Exception:
        return frozenset()
    values = set()
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        for section in schema.get("sections", []):
            if not isinstance(section, dict):
                continue
            for field in section.get("fields", []):
                if not isinstance(field, dict) or field.get("key") != "status":
                    continue
                values.update(
                    str(option.get("value"))
                    for option in field.get("options", [])
                    if isinstance(option, dict)
                    and str(option.get("value") or "").strip()
                    and str(option.get("label") or "").strip().casefold() == target
                )
                break
            else:
                continue
            break
    return frozenset(values)


def clear_status_presentation_cache():
    """Clear immutable-form lookup caches after a new form version is published."""
    _form_status_labels.cache_clear()
    stored_status_values_for_label.cache_clear()
