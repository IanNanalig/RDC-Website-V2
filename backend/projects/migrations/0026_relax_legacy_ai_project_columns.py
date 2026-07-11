from django.db import migrations


def relax_legacy_ai_columns(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'projects_project'
              AND column_name = 'ai_analysis_notes'
            """
        )
        if cursor.fetchone() is None:
            return

        cursor.execute(
            """
            ALTER TABLE projects_project
            ALTER COLUMN ai_analysis_notes DROP NOT NULL,
            ALTER COLUMN ai_analysis_notes SET DEFAULT ''
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0025_alter_useractivity_event_publicpagecontent"),
    ]

    operations = [
        migrations.RunPython(relax_legacy_ai_columns, migrations.RunPython.noop),
    ]
