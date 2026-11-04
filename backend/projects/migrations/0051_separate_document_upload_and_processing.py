from django.db import migrations, models


def backfill_upload_status(apps, schema_editor):
    SupportingDocument = apps.get_model("projects", "ProjectSupportingDocument")
    for document in SupportingDocument.objects.all().iterator():
        status = "uploaded" if document.removed_at is None and bool(document.content) else "upload_failed"
        if document.upload_status != status:
            document.upload_status = status
            document.save(update_fields=["upload_status"])


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0050_scoring_contracts_and_public_contact_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectsupportingdocument",
            name="upload_status",
            field=models.CharField(
                choices=[("uploaded", "Uploaded"), ("upload_failed", "Upload Failed")],
                db_index=True,
                default="uploaded",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="projectsupportingdocument",
            name="extraction_status",
            field=models.CharField(
                choices=[
                    ("not_processed", "Not Processed"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("ready", "Ready"),
                    ("failed", "Failed"),
                ],
                db_index=True,
                default="not_processed",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_upload_status, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="useractivity",
            name="event",
            field=models.CharField(
                choices=[
                    ("login", "Login"), ("login_failed", "Login Failed"), ("logout", "Logout"),
                    ("auth_password_setup", "Password Setup Completed"),
                    ("registration_invitation_sent", "Registration Invitation Sent"),
                    ("registration_completed", "Registration Completed"),
                    ("auth_reset_request", "Auth Reset Request"), ("auth_reset_approve", "Auth Reset Approve"),
                    ("auth_reset_reject", "Auth Reset Reject"), ("user_create", "User Create"),
                    ("user_update", "User Update"), ("user_status_changed", "User Status Changed"),
                    ("user_delete", "User Delete"), ("project_create", "Project Create"),
                    ("project_update", "Project Update"), ("project_delete", "Project Delete"),
                    ("project_submit", "Project Submit"), ("project_approve", "Project Approve"),
                    ("project_reject", "Project Reject"), ("project_archive", "Project Archive"),
                    ("project_comment", "Project Comment"), ("validator_draft", "Validator Draft"),
                    ("validator_reviewed", "Validator Reviewed"), ("validator_endorsed", "Validator Endorsed"),
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
                    ("cms_event_created", "CMS Event Created"), ("cms_event_updated", "CMS Event Updated"),
                    ("cms_event_submitted", "CMS Event Submitted"), ("cms_event_published", "CMS Event Published"),
                    ("cms_event_rejected", "CMS Event Rejected"), ("cms_event_archived", "CMS Event Archived"),
                    ("cms_event_unarchived", "CMS Event Unarchived"), ("cms_event_deleted", "CMS Event Deleted"),
                    ("cms_content_created", "CMS Content Created"), ("cms_content_updated", "CMS Content Updated"),
                    ("cms_content_submitted", "CMS Content Submitted"), ("cms_content_published", "CMS Content Published"),
                    ("cms_content_rejected", "CMS Content Rejected"), ("cms_content_archived", "CMS Content Archived"),
                    ("cms_content_restored", "CMS Content Restored"),
                    ("cms_section_lock_acquired", "CMS Section Lock Acquired"),
                    ("cms_section_lock_blocked", "CMS Section Lock Blocked"),
                    ("cms_section_lock_released", "CMS Section Lock Released"),
                    ("cms_section_lock_overridden", "CMS Section Lock Overridden"),
                    ("cms_section_access_requested", "CMS Section Access Requested"),
                    ("cms_form_lock_acquired", "CMS Form Lock Acquired"),
                    ("cms_form_lock_blocked", "CMS Form Lock Blocked"),
                    ("cms_form_lock_released", "CMS Form Lock Released"),
                    ("cms_form_lock_overridden", "CMS Form Lock Overridden"),
                    ("cms_form_access_requested", "CMS Form Access Requested"),
                    ("supporting_document_uploaded", "Supporting Document Uploaded"),
                    ("supporting_document_removed", "Supporting Document Removed"),
                    ("supporting_document_processing_started", "Supporting Document Processing Started"),
                    ("supporting_document_processing_retried", "Supporting Document Processing Retried"),
                    ("supporting_document_extraction_failed", "Supporting Document Extraction Failed"),
                    ("document_assessment_completed", "Document Assessment Completed"),
                    ("document_assessment_overridden", "Document Assessment Overridden"),
                    ("notification_read", "Notification Read"), ("notification_read_all", "All Notifications Read"),
                    ("access_request_approved", "Access Request Approved"),
                    ("access_request_rejected", "Access Request Rejected"),
                    ("api_action", "API Action"), ("api_action_failed", "API Action Failed"),
                ],
                max_length=40,
            ),
        ),
    ]
