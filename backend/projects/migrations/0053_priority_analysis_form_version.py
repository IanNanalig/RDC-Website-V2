from django.db import migrations, models
import django.db.models.deletion


def backfill_form_versions(apps, schema_editor):
    Analysis = apps.get_model("projects", "ProjectPriorityAnalysis")
    Version = apps.get_model("cms", "CMSContributorFormVersion")
    for analysis in Analysis.objects.filter(form_version__isnull=True).iterator():
        snapshot = analysis.input_snapshot if isinstance(analysis.input_snapshot, dict) else {}
        marker = snapshot.get("form_schema") if isinstance(snapshot.get("form_schema"), dict) else {}
        if not marker and isinstance(snapshot.get("simplified_form"), dict):
            nested = snapshot["simplified_form"].get("form_schema")
            marker = nested if isinstance(nested, dict) else {}
        key, number = str(marker.get("key") or ""), marker.get("version")
        if not key or not number:
            continue
        version = Version.objects.filter(form__key=key, version_number=number).first()
        if version:
            analysis.form_version_id = version.pk
            analysis.save(update_fields=["form_version"])


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0024_generic_form_conditions"),
        ("projects", "0052_ai_processing_jobs"),
    ]
    operations = [
        migrations.AddField(
            model_name="projectpriorityanalysis",
            name="form_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="priority_analyses",
                to="cms.cmscontributorformversion",
            ),
        ),
        migrations.RunPython(backfill_form_versions, migrations.RunPython.noop),
    ]
