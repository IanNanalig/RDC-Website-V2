from copy import deepcopy

from django.db import migrations


REGIONAL_CRITERIA = {
    "cost": {
        "thresholds": {
            "at_least_5b": 5_000_000_000,
            "over_3b": 3_000_000_000,
            "over_1b": 1_000_000_000,
            "over_500m": 500_000_000,
        },
        "scores": {
            "at_least_5b": 10,
            "over_3b": 8,
            "over_1b": 6,
            "over_500m": 4,
            "otherwise": 2,
        },
    },
    "spatial_coverage": {
        "scores": {
            "interregional": 10,
            "region_wide": 8,
            "eight_to_twelve_lgus": 6,
            "single_city": 4,
        }
    },
    "outcome_contribution": {
        "thresholds": {
            "at_least_7": 7,
            "at_least_5": 5,
            "at_least_3": 3,
            "at_least_2": 2,
            "at_least_1": 1,
        },
        "scores": {
            "at_least_7": 10,
            "at_least_5": 8,
            "at_least_3": 6,
            "at_least_2": 4,
            "at_least_1": 2,
            "otherwise": 0,
        },
    },
    "beneficiaries": {
        "thresholds": {"over_3m": 3_000_000, "over_1m": 1_000_000, "at_least_1": 1},
        "scores": {"over_3m": 10, "over_1m": 6, "at_least_1": 3, "otherwise": 0},
    },
}


def activate_regional_priority_policy(apps, schema_editor):
    RuleSet = apps.get_model("projects", "PriorityRuleSet")
    active = RuleSet.objects.filter(is_active=True).order_by("-created_at", "-pk").first()
    if active is None:
        return

    thresholds = deepcopy(active.thresholds or {})
    thresholds["high"] = 70
    thresholds["regional_project_cost"] = 200_000_000
    thresholds["regional_criteria"] = REGIONAL_CRITERIA
    active.is_active = False
    active.save(update_fields=["is_active"])

    version = "rdc-priority-regional-70-v1"
    suffix = 2
    while RuleSet.objects.filter(version=version).exists():
        version = f"rdc-priority-regional-70-v{suffix}"
        suffix += 1

    RuleSet.objects.create(
        version=version,
        algorithm_version="expert-v4-regional-eligibility",
        is_active=True,
        thresholds=thresholds,
        sector_criteria=deepcopy(active.sector_criteria or {}),
        keyword_dictionaries=deepcopy(active.keyword_dictionaries or {}),
    )


class Migration(migrations.Migration):
    dependencies = [("projects", "0037_remove_publicchatinteraction_matched_content_and_more")]

    operations = [migrations.RunPython(activate_regional_priority_policy, migrations.RunPython.noop)]
