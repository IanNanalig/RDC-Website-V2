from django.db import migrations


def enable_extensions(apps, schema_editor):
    # Only run on PostgreSQL backends; SQLite will skip these statements.
    conn = schema_editor.connection
    if conn.vendor != 'postgresql':
        return
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(enable_extensions, reverse_code=migrations.RunPython.noop),
    ]
