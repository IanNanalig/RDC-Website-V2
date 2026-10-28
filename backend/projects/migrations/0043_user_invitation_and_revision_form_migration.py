from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0042_unique_active_project_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectrevision",
            name="form_migration",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="UserInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("role", models.CharField(choices=[("admin", "Admin"), ("validator", "Validator"), ("staff", "Staff"), ("content_editor", "Content Editor")], max_length=20)),
                ("agency", models.CharField(blank=True, default="", max_length=200)),
                ("agency_locked", models.BooleanField(default=False)),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending delivery"), ("sent", "Sent"), ("completed", "Completed"), ("revoked", "Revoked"), ("delivery_failed", "Delivery failed")], default="pending", max_length=24)),
                ("batch_key", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="issued_invitations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="userinvitation",
            index=models.Index(fields=["email", "status"], name="projects_us_email_56010e_idx"),
        ),
    ]
