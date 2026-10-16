from django.db import migrations


def add_media_categories(apps, schema_editor):
    Setting = apps.get_model("cms", "CMSSiteSetting")
    Setting.objects.using(schema_editor.connection.alias).get_or_create(
        key="media-categories",
        defaults={"value_json": {"categories": ["General"]}, "description": "Editorial categories available for CMS media."},
    )


class Migration(migrations.Migration):
    dependencies = [("cms", "0007_cmsmediaasset_category_and_more")]
    operations = [migrations.RunPython(add_media_categories, migrations.RunPython.noop)]
