"""Presentation and filter rules for simplified RDIP implementation statuses."""

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
    return status
