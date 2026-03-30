from django.db import migrations, models


def force_profile_setup(apps, schema_editor):
    User = apps.get_model("projects", "User")
    User.objects.exclude(role="admin").update(must_change_password=True)


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0013_update_public_content_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="full_name",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="agency",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="agency_head",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="office",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="division",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="position",
            field=models.CharField(max_length=200, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="contact_number",
            field=models.CharField(max_length=50, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_number",
            field=models.CharField(max_length=50, blank=True, default=""),
        ),
        migrations.RunPython(force_profile_setup, reverse_code=migrations.RunPython.noop),
    ]
