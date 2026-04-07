from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0014_user_profile_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(blank=True, max_length=20)),
                ("agency", models.CharField(blank=True, max_length=200)),
                ("comment", models.TextField()),
                ("created_at", models.DateTimeField(db_index=True, default=timezone.now)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="projects.project")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_comments", to="projects.user")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
