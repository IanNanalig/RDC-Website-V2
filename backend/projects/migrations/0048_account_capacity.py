from django.db import migrations, models
import projects.models


def backfill_account_states(apps, schema_editor):
    User = apps.get_model("projects", "User")
    User.objects.filter(is_active=True).update(account_state="active")
    User.objects.filter(is_active=False).update(account_state="disabled")


def seed_capacity_lock(apps, schema_editor):
    AccountCapacityLock = apps.get_model("projects", "AccountCapacityLock")
    AccountCapacityLock.objects.get_or_create(key="global-admin")


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0047_agency_case_insensitive_uniqueness"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="account_state",
            field=models.CharField(
                choices=[
                    ("pending_activation", "Pending activation"),
                    ("active", "Active"),
                    ("disabled", "Disabled"),
                ],
                db_index=True,
                default="active",
                max_length=24,
            ),
        ),
        migrations.RunPython(backfill_account_states, migrations.RunPython.noop),
        migrations.CreateModel(
            name="AccountCapacityLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=80, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.RunPython(seed_capacity_lock, migrations.RunPython.noop),
        migrations.AlterModelManagers(
            name="user",
            managers=[("objects", projects.models.UserManager())],
        ),
    ]
