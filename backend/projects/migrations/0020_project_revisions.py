from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_initial_public_revisions(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    ProjectRevision = apps.get_model("projects", "ProjectRevision")
    try:
        from projects.public_summary import build_public_summary
    except Exception:
        build_public_summary = None

    for project in Project.objects.filter(validated=True, archived=False, is_active=True):
        if ProjectRevision.objects.filter(project=project).exists():
            continue
        profile = project.profile_data if isinstance(project.profile_data, dict) else {}
        if build_public_summary and isinstance(profile.get("simplified_form"), dict):
            profile = dict(profile)
            profile["public_summary"] = build_public_summary(profile["simplified_form"])
        public_summary = profile.get("public_summary") if isinstance(profile.get("public_summary"), dict) else {}
        when = project.updated_at or project.created_at
        ProjectRevision.objects.create(
            project=project,
            revision_number=1,
            revision_type="initial_submission",
            state="endorsed",
            profile_data_snapshot=profile,
            public_summary_snapshot=public_summary,
            changed_fields=[],
            is_public_current=True,
            created_by=project.created_by,
            submitted_by=project.created_by,
            submitted_at=when,
            reviewed_at=when,
            endorsed_at=when,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0019_alter_useractivity_event"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("revision_number", models.PositiveIntegerField()),
                (
                    "revision_type",
                    models.CharField(
                        choices=[
                            ("initial_submission", "Initial Submission"),
                            ("progress_update", "Progress Update"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("submitted", "Submitted"),
                            ("validator_draft", "Validator Draft"),
                            ("reviewed", "Reviewed"),
                            ("endorsed", "Endorsed"),
                            ("rejected", "Rejected"),
                            ("superseded", "Superseded"),
                        ],
                        default="draft",
                        max_length=30,
                    ),
                ),
                ("profile_data_snapshot", models.JSONField(blank=True, default=dict)),
                ("public_summary_snapshot", models.JSONField(blank=True, default=dict)),
                ("changed_fields", models.JSONField(blank=True, default=list)),
                ("public_note", models.TextField(blank=True)),
                ("is_public_current", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("endorsed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_project_revisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "endorsed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="endorsed_project_revisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
                        to="projects.project",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_project_revisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submitted_project_revisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddConstraint(
            model_name="projectrevision",
            constraint=models.UniqueConstraint(
                fields=("project", "revision_number"),
                name="unique_project_revision_number",
            ),
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
                    ("public_summary_overridden", "Public Summary Overridden"),
                    ("encoding_window_updated", "Encoding Window Updated"),
                    ("progress_window_updated", "Progress Update Window Updated"),
                    ("project_revision_created", "Project Revision Created"),
                    ("project_revision_updated", "Project Revision Updated"),
                    ("project_revision_submitted", "Project Revision Submitted"),
                    ("project_revision_reviewed", "Project Revision Reviewed"),
                    ("project_revision_endorsed", "Project Revision Endorsed"),
                    ("project_revision_rejected", "Project Revision Rejected"),
                ],
                max_length=40,
            ),
        ),
        migrations.RunPython(backfill_initial_public_revisions, migrations.RunPython.noop),
    ]
