import re
from decimal import Decimal

from django.db import migrations, models


HIGH_PRIORITY_MINIMUM = Decimal("81")


def _updated_priority_text(value):
    if not isinstance(value, str):
        return value
    return re.sub(r"medium priority", "low priority", value, flags=re.IGNORECASE)


def _updated_scores(value):
    if isinstance(value, dict):
        return {key: _updated_scores(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_updated_scores(child) for child in value]
    return _updated_priority_text(value)


def apply_binary_priority_levels(apps, schema_editor):
    PriorityRuleSet = apps.get_model("projects", "PriorityRuleSet")
    ProjectPriorityAnalysis = apps.get_model("projects", "ProjectPriorityAnalysis")
    ProjectPriorityConfirmation = apps.get_model("projects", "ProjectPriorityConfirmation")

    for rule_set in PriorityRuleSet.objects.all().iterator():
        thresholds = dict(rule_set.thresholds or {})
        thresholds["high"] = 81
        thresholds.pop("medium", None)
        rule_set.thresholds = thresholds
        rule_set.save(update_fields=["thresholds"])

    for analysis in ProjectPriorityAnalysis.objects.all().iterator():
        updates = {
            "summary": _updated_priority_text(analysis.summary),
            "suggested_scores": _updated_scores(analysis.suggested_scores),
        }
        if analysis.suggested_priority != "incomplete":
            updates["suggested_priority"] = (
                "high" if Decimal(str(analysis.base_score or 0)) >= HIGH_PRIORITY_MINIMUM else "low"
            )
        ProjectPriorityAnalysis.objects.filter(pk=analysis.pk).update(**updates)

    confirmations = ProjectPriorityConfirmation.objects.select_related("analysis").all()
    for confirmation in confirmations.iterator():
        final_priority = (
            "high"
            if Decimal(str(confirmation.analysis.base_score or 0)) >= HIGH_PRIORITY_MINIMUM
            else "low"
        )
        ProjectPriorityConfirmation.objects.filter(pk=confirmation.pk).update(
            final_priority=final_priority
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0030_useractivity_actor_full_name_and_more"),
    ]

    operations = [
        migrations.RunPython(apply_binary_priority_levels, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="projectpriorityanalysis",
            name="suggested_priority",
            field=models.CharField(
                choices=[
                    ("high", "High Priority"),
                    ("low", "Low Priority"),
                    ("incomplete", "Incomplete"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="projectpriorityconfirmation",
            name="final_priority",
            field=models.CharField(
                choices=[("high", "High Priority"), ("low", "Low Priority")],
                max_length=20,
            ),
        ),
    ]
