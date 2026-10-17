from django.db import migrations


def normalize_page_sections(apps, schema_editor):
    Section = apps.get_model("cms", "CMSPageSection")
    Section.objects.filter(status="submitted").update(status="draft")


def remove_chatbot_setting(apps, schema_editor):
    Setting = apps.get_model("cms", "CMSSiteSetting")
    Setting.objects.filter(key="chatbot-contact-fallback-link").delete()


class Migration(migrations.Migration):
    dependencies = [("cms", "0008_media_categories_setting")]

    operations = [
        migrations.RunPython(normalize_page_sections, migrations.RunPython.noop),
        migrations.RunPython(remove_chatbot_setting, migrations.RunPython.noop),
    ]
