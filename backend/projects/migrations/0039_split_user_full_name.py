from django.db import migrations, models


def split_user_names(apps, schema_editor):
    User = apps.get_model("projects", "User")
    alias = schema_editor.connection.alias
    rows = User.objects.using(alias).only("pk", "full_name").iterator()
    for user in rows:
        value = (user.full_name or "").strip()
        parts = value.split(None, 1) if value else []
        first_name = parts[0] if parts else ""
        last_name = parts[1].strip() if len(parts) > 1 else ""
        if len(first_name) > 150 or len(last_name) > 150:
            raise RuntimeError(
                f"Cannot split legacy full_name for user id {user.pk}: a name part exceeds 150 characters. "
                "Correct this record before applying the migration."
            )
        User.objects.using(alias).filter(pk=user.pk).update(
            first_name=first_name,
            last_name=last_name,
        )


def join_user_names(apps, schema_editor):
    User = apps.get_model("projects", "User")
    alias = schema_editor.connection.alias
    for user in User.objects.using(alias).only("pk", "first_name", "last_name").iterator():
        full_name = " ".join(part for part in (user.first_name, user.last_name) if part).strip()
        User.objects.using(alias).filter(pk=user.pk).update(full_name=full_name)


class Migration(migrations.Migration):
    dependencies = [("projects", "0038_regional_priority_policy")]

    operations = [
        migrations.RunPython(split_user_names, join_user_names),
        migrations.RemoveField(model_name="user", name="full_name"),
    ]
