import re

from cms.models import CMSSiteSetting


SETTING_KEY = "project-concern-categories"
CODE_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
DEFAULT_CATEGORIES = [
    {"code": "delay_discrepancy", "label": "Suspected project delay or discrepancy", "active": True},
    {"code": "reported_accomplishment", "label": "Concern involving reported project accomplishments", "active": True},
    {"code": "published_information", "label": "Inconsistency in project descriptions or published information", "active": True},
    {"code": "budget_funding", "label": "Concern involving reported budgets or funding", "active": True},
    {"code": "implementation_compliance", "label": "Potential implementation or compliance issue", "active": True},
    {"code": "other", "label": "Other project-related concern", "active": True},
]


def normalize_categories(value, *, require_active=False):
    raw_categories = value.get("categories") if isinstance(value, dict) else None
    raw_categories = raw_categories if isinstance(raw_categories, list) else []
    normalized = []
    seen = set()
    for item in raw_categories:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower()
        label = " ".join(str(item.get("label") or "").split())
        active = bool(item.get("active", True))
        if not code or not CODE_PATTERN.fullmatch(code) or not label or len(label) > 200 or code in seen:
            continue
        if require_active and not active:
            continue
        seen.add(code)
        normalized.append({"code": code, "label": label, "active": active})
    return normalized


def configured_categories(*, active_only=False):
    value = CMSSiteSetting.objects.filter(key=SETTING_KEY).values_list("value_json", flat=True).first()
    categories = normalize_categories(value or {}, require_active=active_only)
    if not categories:
        categories = [dict(item) for item in DEFAULT_CATEGORIES if not active_only or item["active"]]
    return categories
