"""History and validation shared by AI scoring administration endpoints."""

from django.db.models.functions import Coalesce

from .models import PriorityRuleSet
from .priority_scoring import get_active_priority_rule_set, validate_priority_rule_config


CONFIG_FIELDS = ("thresholds", "sector_criteria", "keyword_dictionaries")


def rule_config_snapshot(rule):
    return {field: getattr(rule, field) for field in CONFIG_FIELDS}


def published_rules():
    return (
        PriorityRuleSet.objects.exclude(status=PriorityRuleSet.STATUS_DRAFT)
        .select_related("activated_by", "restored_from")
        .annotate(published_at=Coalesce("activated_at", "created_at"))
        .order_by("-published_at", "-pk")
    )


def rule_history_entry(rule):
    actor = rule.activated_by
    return {
        "id": rule.pk, "version": rule.version, "algorithm_version": rule.algorithm_version,
        "status": rule.status, "is_active": rule.is_active, "based_on": rule.based_on_id,
        "restored_from": rule.restored_from_id,
        "restored_from_version": rule.restored_from.version if rule.restored_from_id else None,
        "change_note": rule.change_note, "created_at": rule.created_at, "activated_at": rule.activated_at,
        "published_at": rule.published_at,
        "activated_by": (actor.get_full_name().strip() or actor.username) if actor else None,
        "analysis_count": getattr(rule, "analysis_count", 0),
    }


def rule_changes(previous, current):
    changes = []

    def compare(old, new, path):
        if isinstance(old, dict) and isinstance(new, dict):
            for key in sorted(old.keys() | new.keys()):
                field = [*path, key]
                if key not in old:
                    changes.append({"path": field, "kind": "added", "before": None, "after": new[key]})
                elif key not in new:
                    changes.append({"path": field, "kind": "removed", "before": old[key], "after": None})
                else:
                    compare(old[key], new[key], field)
            return
        if isinstance(old, list) and isinstance(new, list) and (old or new) and all(
            isinstance(item, dict) and isinstance(item.get("key"), str) for item in [*old, *new]
        ):
            compare({item["key"]: item for item in old}, {item["key"]: item for item in new}, path)
        elif old != new:
            changes.append({"path": path, "kind": "changed", "before": old, "after": new})

    if previous:
        compare(
            {**rule_config_snapshot(previous), "input_contract": previous.input_contract},
            {**rule_config_snapshot(current), "input_contract": current.input_contract},
            [],
        )
    return changes


def validate_publication_config(config):
    config = validate_priority_rule_config(config, enforce_current_high=True)
    outcomes = [config["keyword_dictionaries"]["common_outcomes"], *config["sector_criteria"].values()]
    if any(row["match_mode"] != "contextual" for group in outcomes for row in group):
        raise ValueError("New AI scoring rule versions must use contextual sentence matching for every RDP outcome criterion.")
    return config


def lock_active_rule_set():
    # Lock a stable row before checking the active pointer. The active row
    # itself changes on publication or restoration.
    if not PriorityRuleSet.objects.exists():
        get_active_priority_rule_set()
    PriorityRuleSet.objects.select_for_update().order_by("pk").first()
    return get_active_priority_rule_set()
