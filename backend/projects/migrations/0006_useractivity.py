from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0005_accessrequest"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(blank=True, max_length=20),
                ),
                (
                    "event",
                    models.CharField(
                        choices=[
                            ("login", "Login"),
                            ("project_create", "Project Create"),
                            ("project_update", "Project Update"),
                            ("project_submit", "Project Submit"),
                            ("project_approve", "Project Approve"),
                            ("project_reject", "Project Reject"),
                            ("project_archive", "Project Archive"),
                        ],
                        max_length=40,
                    ),
                ),
                ("ip_address", models.CharField(blank=True, max_length=64)),
                ("location_hint", models.CharField(blank=True, max_length=255)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="projects.project",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="projects.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
