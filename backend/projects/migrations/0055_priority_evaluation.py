from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0054_accountstatusemail"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectpriorityconfirmation",
            name="validator_remarks",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="projectpriorityconfirmation",
            name="effective_score",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name="projectpriorityconfirmation",
            name="regional_effective_score",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.CreateModel(
            name="ProjectPriorityEvaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("adjusted_scores", models.JSONField(blank=True, default=dict)),
                ("validator_remarks", models.JSONField(blank=True, default=dict)),
                ("effective_score", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("regional_effective_score", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("calculated_priority", models.CharField(choices=[("high", "High Priority"), ("low", "Low Priority"), ("incomplete", "Incomplete")], max_length=20)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("analysis", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="evaluation", to="projects.projectpriorityanalysis")),
                ("validator", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="priority_evaluations", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
