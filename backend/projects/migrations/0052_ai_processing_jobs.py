import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0051_separate_document_upload_and_processing"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectAIProcessingJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("correlation_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("source_hash", models.CharField(db_index=True, max_length=64)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed"), ("stalled", "Stalled")], db_index=True, default="queued", max_length=20)),
                ("stage", models.CharField(choices=[("queued", "Queued"), ("dispatch", "Dispatching"), ("extraction", "Extracting document text"), ("assessment", "Assessing documents"), ("scoring", "Scoring project"), ("completed", "Completed"), ("failed", "Failed"), ("stalled", "Stalled")], db_index=True, default="queued", max_length=20)),
                ("celery_task_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("requested_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("heartbeat_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("safe_error_code", models.CharField(blank=True, max_length=80)),
                ("safe_error_message", models.TextField(blank=True)),
                ("project", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="ai_processing_jobs", to="projects.project")),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="requested_ai_processing_jobs", to="projects.user")),
            ],
            options={"ordering": ["-requested_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="projectaiprocessingjob",
            index=models.Index(fields=["project", "status", "-requested_at"], name="project_ai_job_active_idx"),
        ),
        migrations.AddField(
            model_name="projectsupportingdocument",
            name="processing_job",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="documents", to="projects.projectaiprocessingjob"),
        ),
        migrations.AddField(
            model_name="projectdocumentassessment",
            name="processing_job",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="assessments", to="projects.projectaiprocessingjob"),
        ),
        migrations.CreateModel(
            name="ProjectAIProcessingEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(max_length=64)),
                ("stage", models.CharField(blank=True, max_length=20)),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("assessment", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to="projects.projectdocumentassessment")),
                ("document", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, to="projects.projectsupportingdocument")),
                ("job", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="events", to="projects.projectaiprocessingjob")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="projectaiprocessingevent",
            index=models.Index(fields=["job", "created_at"], name="ai_job_event_time_idx"),
        ),
    ]
