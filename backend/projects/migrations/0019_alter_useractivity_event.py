from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0018_priority_analysis"),
    ]

    operations = [
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
                    ("encoding_window_updated", "Encoding Window Updated"),
                ],
                max_length=40,
            ),
        ),
    ]
