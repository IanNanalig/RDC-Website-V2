import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0017_alter_project_budget"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="priority_analysis_eligible",
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="project",
            name="priority_analysis_eligible",
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name="useractivity",
            name="event",
            field=models.CharField(
                choices=[
                    ("login", "Login"),
                    ("auth_reset_request", "Auth Reset Request"),
                    ("auth_reset_approve", "Auth Reset Approve"),
                    ("auth_reset_reject", "Auth Reset Reject"),
                    ("user_create", "User Create"),
                    ("project_create", "Project Create"),
                    ("project_update", "Project Update"),
                    ("project_submit", "Project Submit"),
                    ("project_approve", "Project Approve"),
                    ("project_reject", "Project Reject"),
                    ("project_archive", "Project Archive"),
                    ("project_comment", "Project Comment"),
                    ("validator_draft", "Validator Draft"),
                    ("validator_reviewed", "Validator Reviewed"),
                    ("validator_endorsed", "Validator Endorsed"),
                    ("priority_analysis_run", "Priority Analysis Run"),
                    ("priority_analysis_reused", "Priority Analysis Reused"),
                    ("priority_analysis_confirmed", "Priority Analysis Confirmed"),
                    ("priority_analysis_overridden", "Priority Analysis Overridden"),
                ],
                max_length=40,
            ),
        ),
        migrations.CreateModel(
            name="PriorityRuleSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.CharField(max_length=40, unique=True)),
                ("algorithm_version", models.CharField(default="expert-v1", max_length=40)),
                ("is_active", models.BooleanField(default=False)),
                ("thresholds", models.JSONField(blank=True, default=dict)),
                ("sector_criteria", models.JSONField(blank=True, default=dict)),
                ("keyword_dictionaries", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ProjectPriorityAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_hash", models.CharField(db_index=True, max_length=64)),
                ("input_snapshot", models.JSONField(default=dict)),
                ("supplements", models.JSONField(blank=True, default=dict)),
                ("suggested_scores", models.JSONField(default=dict)),
                ("regional_scorecard", models.JSONField(blank=True, default=dict)),
                ("flags", models.JSONField(blank=True, default=dict)),
                ("summary", models.TextField(blank=True)),
                ("suggested_priority", models.CharField(choices=[("high", "High Priority"), ("medium", "Medium Priority"), ("low", "Low Priority"), ("incomplete", "Incomplete")], max_length=20)),
                ("base_score", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="priority_analyses", to="projects.project")),
                ("rule_set", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="analyses", to="projects.priorityruleset")),
                ("validator", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="priority_analyses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="projectpriorityanalysis",
            constraint=models.UniqueConstraint(fields=("project", "rule_set", "source_hash"), name="unique_project_priority_analysis_snapshot"),
        ),
        migrations.CreateModel(
            name="ProjectPriorityConfirmation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("adjusted_scores", models.JSONField(blank=True, default=dict)),
                ("final_priority", models.CharField(choices=[("high", "High Priority"), ("medium", "Medium Priority"), ("low", "Low Priority")], max_length=20)),
                ("override_rationale", models.TextField(blank=True)),
                ("confirmed_flags", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="confirmations", to="projects.projectpriorityanalysis")),
                ("validator", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="priority_confirmations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
