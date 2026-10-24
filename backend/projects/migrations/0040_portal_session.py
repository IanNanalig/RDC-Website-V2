from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0039_split_user_full_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_version", models.PositiveIntegerField()),
                ("refresh_token_digest", models.CharField(max_length=64, unique=True)),
                ("remember_me", models.BooleanField(default=False)),
                ("last_activity_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revocation_reason", models.CharField(blank=True, choices=[("new_login", "New device login"), ("logout", "User logout"), ("idle_timeout", "Inactivity timeout"), ("credential_change", "Credential change")], default="", max_length=20)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="portal_sessions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["user", "revoked_at"], name="projects_po_user_id_1feec9_idx")],
            },
        ),
    ]
