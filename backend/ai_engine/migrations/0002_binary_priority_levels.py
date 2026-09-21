import re

from django.db import migrations, models


FEATURE_SCHEMA_VERSION = "rdc-priority-features-v2"


def _updated_priority_text(value):
    if isinstance(value, dict):
        return {key: _updated_priority_text(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_updated_priority_text(child) for child in value]
    if isinstance(value, str):
        return re.sub(r"medium priority", "low priority", value, flags=re.IGNORECASE)
    return value


def _updated_feature_snapshot(snapshot, suggested_priority):
    snapshot = dict(snapshot or {})
    values = dict(snapshot.get("values") or {})
    values.pop("rule_suggested_medium", None)
    values["rule_suggested_low"] = 1.0 if suggested_priority == "low" else 0.0
    values["rule_suggested_high"] = 1.0 if suggested_priority == "high" else 0.0
    context = dict(snapshot.get("context") or {})
    context["rule_suggested_priority"] = suggested_priority
    snapshot["schema_version"] = FEATURE_SCHEMA_VERSION
    snapshot["values"] = values
    snapshot["context"] = context
    return snapshot


def migrate_binary_training_data(apps, schema_editor):
    AITrainingRecord = apps.get_model("ai_engine", "AITrainingRecord")
    AIModelVersion = apps.get_model("ai_engine", "AIModelVersion")
    AIProjectAnalysis = apps.get_model("ai_engine", "AIProjectAnalysis")

    records = AITrainingRecord.objects.select_related("confirmation__analysis").all()
    for record in records.iterator():
        analysis = record.confirmation.analysis
        AITrainingRecord.objects.filter(pk=record.pk).update(
            target_priority=record.confirmation.final_priority,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_snapshot=_updated_feature_snapshot(
                record.feature_snapshot,
                analysis.suggested_priority,
            ),
        )

    # Three-class model parameters are not compatible with the new binary feature
    # schema. Preserve them for audit history, but require a controlled retraining.
    AIModelVersion.objects.filter(status="active").update(status="retired")

    for assessment in AIProjectAnalysis.objects.all().iterator():
        probabilities = dict(assessment.class_probabilities or {})
        if "medium" in probabilities:
            probabilities["low"] = float(probabilities.get("low") or 0) + float(
                probabilities.pop("medium") or 0
            )
        influential_features = _updated_priority_text(assessment.explanation)
        predicted_priority = (
            "low" if assessment.predicted_priority == "medium" else assessment.predicted_priority
        )
        AIProjectAnalysis.objects.filter(pk=assessment.pk).update(
            predicted_priority=predicted_priority,
            class_probabilities=probabilities,
            explanation=influential_features,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0031_binary_priority_levels"),
        ("ai_engine", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(migrate_binary_training_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="aitrainingrecord",
            name="target_priority",
            field=models.CharField(
                choices=[("high", "High Priority"), ("low", "Low Priority")],
                max_length=20,
            ),
        ),
    ]
