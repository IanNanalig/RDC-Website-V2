from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0040_portal_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="supporting_document_policy",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="ProjectSupportingDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("field_key", models.CharField(default="custom_supporting_documents", max_length=120)),
                ("form_key", models.CharField(default="simplified-rdip", max_length=120)),
                ("form_version", models.PositiveIntegerField(default=1)),
                ("original_filename", models.CharField(max_length=255)),
                ("content_type", models.CharField(max_length=120)),
                ("extension", models.CharField(max_length=12)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("checksum_sha256", models.CharField(db_index=True, max_length=64)),
                ("content", models.BinaryField()),
                ("extraction_status", models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("ready", "Ready"), ("failed", "Failed")], db_index=True, default="queued", max_length=20)),
                ("extracted_text", models.TextField(blank=True)),
                ("extraction_metadata", models.JSONField(blank=True, default=dict)),
                ("processing_error", models.TextField(blank=True)),
                ("removed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="supporting_documents", to="projects.project")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_project_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="projectsupportingdocument",
            index=models.Index(fields=["project", "removed_at"], name="project_doc_active_idx"),
        ),
        migrations.CreateModel(
            name="ProjectDocumentAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_hash", models.CharField(db_index=True, max_length=64)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("processing", "Processing"), ("pass", "Pass"), ("fail", "Fail"), ("unavailable", "Unavailable")], db_index=True, default="queued", max_length=20)),
                ("document_results", models.JSONField(blank=True, default=list)),
                ("collective_sufficient", models.BooleanField(default=False)),
                ("summary", models.TextField(blank=True)),
                ("provider", models.CharField(blank=True, max_length=40)),
                ("model", models.CharField(blank=True, max_length=120)),
                ("used_backup_model", models.BooleanField(default=False)),
                ("policy_snapshot", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="document_assessments", to="projects.project")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "constraints": [models.UniqueConstraint(fields=("project", "source_hash"), name="unique_project_document_assessment_source")],
            },
        ),
        migrations.AddField(
            model_name="projectpriorityconfirmation",
            name="document_assessment",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="priority_confirmations", to="projects.projectdocumentassessment"),
        ),
        migrations.AddField(
            model_name="projectpriorityconfirmation",
            name="document_override",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="projectpriorityconfirmation",
            name="document_override_rationale",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="useractivity",
            name="event",
            field=models.CharField(choices=[('login', 'Login'), ('login_failed', 'Login Failed'), ('logout', 'Logout'), ('auth_password_setup', 'Password Setup Completed'), ('registration_invitation_sent', 'Registration Invitation Sent'), ('registration_completed', 'Registration Completed'), ('auth_reset_request', 'Auth Reset Request'), ('auth_reset_approve', 'Auth Reset Approve'), ('auth_reset_reject', 'Auth Reset Reject'), ('user_create', 'User Create'), ('user_update', 'User Update'), ('user_status_changed', 'User Status Changed'), ('user_delete', 'User Delete'), ('project_create', 'Project Create'), ('project_update', 'Project Update'), ('project_delete', 'Project Delete'), ('project_submit', 'Project Submit'), ('project_approve', 'Project Approve'), ('project_reject', 'Project Reject'), ('project_archive', 'Project Archive'), ('project_comment', 'Project Comment'), ('validator_draft', 'Validator Draft'), ('validator_reviewed', 'Validator Reviewed'), ('validator_endorsed', 'Validator Endorsed'), ('priority_analysis_run', 'Priority Analysis Run'), ('priority_analysis_reused', 'Priority Analysis Reused'), ('priority_analysis_confirmed', 'Priority Analysis Confirmed'), ('priority_analysis_overridden', 'Priority Analysis Overridden'), ('public_summary_overridden', 'Public Summary Overridden'), ('encoding_window_updated', 'Encoding Window Updated'), ('progress_window_updated', 'Progress Update Window Updated'), ('project_revision_created', 'Project Revision Created'), ('project_revision_updated', 'Project Revision Updated'), ('project_revision_submitted', 'Project Revision Submitted'), ('project_revision_reviewed', 'Project Revision Reviewed'), ('project_revision_endorsed', 'Project Revision Endorsed'), ('project_revision_rejected', 'Project Revision Rejected'), ('cms_event_created', 'CMS Event Created'), ('cms_event_updated', 'CMS Event Updated'), ('cms_event_submitted', 'CMS Event Submitted'), ('cms_event_published', 'CMS Event Published'), ('cms_event_rejected', 'CMS Event Rejected'), ('cms_event_archived', 'CMS Event Archived'), ('cms_event_unarchived', 'CMS Event Unarchived'), ('cms_event_deleted', 'CMS Event Deleted'), ('cms_content_created', 'CMS Content Created'), ('cms_content_updated', 'CMS Content Updated'), ('cms_content_submitted', 'CMS Content Submitted'), ('cms_content_published', 'CMS Content Published'), ('cms_content_rejected', 'CMS Content Rejected'), ('cms_content_archived', 'CMS Content Archived'), ('cms_content_restored', 'CMS Content Restored'), ('cms_section_lock_acquired', 'CMS Section Lock Acquired'), ('cms_section_lock_blocked', 'CMS Section Lock Blocked'), ('cms_section_lock_released', 'CMS Section Lock Released'), ('cms_section_lock_overridden', 'CMS Section Lock Overridden'), ('cms_section_access_requested', 'CMS Section Access Requested'), ('cms_form_lock_acquired', 'CMS Form Lock Acquired'), ('cms_form_lock_blocked', 'CMS Form Lock Blocked'), ('cms_form_lock_released', 'CMS Form Lock Released'), ('cms_form_lock_overridden', 'CMS Form Lock Overridden'), ('cms_form_access_requested', 'CMS Form Access Requested'), ('supporting_document_uploaded', 'Supporting Document Uploaded'), ('supporting_document_removed', 'Supporting Document Removed'), ('supporting_document_extraction_failed', 'Supporting Document Extraction Failed'), ('document_assessment_completed', 'Document Assessment Completed'), ('document_assessment_overridden', 'Document Assessment Overridden'), ('notification_read', 'Notification Read'), ('notification_read_all', 'All Notifications Read'), ('access_request_approved', 'Access Request Approved'), ('access_request_rejected', 'Access Request Rejected'), ('api_action', 'API Action'), ('api_action_failed', 'API Action Failed')], max_length=40),
        ),
    ]
