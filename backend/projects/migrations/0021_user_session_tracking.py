from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0020_project_revisions"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="last_session_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="last_session_ip",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="user",
            name="last_session_user_agent",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="session_version",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
