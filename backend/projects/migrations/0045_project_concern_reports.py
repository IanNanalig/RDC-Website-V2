import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0044_password_reset_challenge_and_multi_agency"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectConcernReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference_code", models.CharField(db_index=True, max_length=40, unique=True)),
                ("project_id_snapshot", models.PositiveIntegerField()),
                ("project_title_snapshot", models.CharField(max_length=200)),
                ("project_agency_snapshot", models.CharField(blank=True, default="", max_length=255)),
                ("reporting_mode", models.CharField(choices=[("anonymous", "Anonymous"), ("email", "Email-enabled")], max_length=16)),
                ("reporter_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("category_code", models.SlugField(max_length=80)),
                ("category_label_snapshot", models.CharField(max_length=200)),
                ("description", models.TextField()),
                ("client_submission_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("abuse_fingerprint", models.CharField(db_index=True, max_length=64)),
                ("receiver_delivery_status", models.CharField(choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed"), ("not_applicable", "Not applicable")], db_index=True, default="pending", max_length=20)),
                ("acknowledgement_delivery_status", models.CharField(choices=[("pending", "Pending"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed"), ("not_applicable", "Not applicable")], db_index=True, default="not_applicable", max_length=20)),
                ("receiver_delivery_attempts", models.PositiveSmallIntegerField(default=0)),
                ("acknowledgement_delivery_attempts", models.PositiveSmallIntegerField(default=0)),
                ("receiver_sent_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledgement_sent_at", models.DateTimeField(blank=True, null=True)),
                ("receiver_last_error", models.CharField(blank=True, default="", max_length=300)),
                ("acknowledgement_last_error", models.CharField(blank=True, default="", max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="public_concern_reports", to="projects.project")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ProjectConcernEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_filename", models.CharField(max_length=255)),
                ("storage_name", models.CharField(max_length=100, unique=True)),
                ("content_type", models.CharField(max_length=120)),
                ("extension", models.CharField(max_length=12)),
                ("size_bytes", models.PositiveIntegerField()),
                ("checksum_sha256", models.CharField(max_length=64)),
                ("content", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_files", to="projects.projectconcernreport")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddIndex(
            model_name="projectconcernreport",
            index=models.Index(fields=["project", "-created_at"], name="concern_project_created_idx"),
        ),
        migrations.AddIndex(
            model_name="projectconcernreport",
            index=models.Index(fields=["abuse_fingerprint", "-created_at"], name="concern_abuse_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="projectconcernevidence",
            constraint=models.UniqueConstraint(fields=("report", "checksum_sha256"), name="unique_concern_evidence_hash"),
        ),
    ]
