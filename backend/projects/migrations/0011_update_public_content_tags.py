from django.db import migrations


def update_contact_content(apps, schema_editor):
    PublicContent = apps.get_model("projects", "PublicContent")
    contact_entries = PublicContent.objects.filter(slug="contact")
    for entry in contact_entries:
        tags = set(entry.tags or [])
        tags.update(
            [
                "contact",
                "message",
                "inquiry",
                "email",
                "mensahe",
                "pakikipag-ugnayan",
                "contact form",
                "send message",
            ]
        )
        if entry.language == "tl":
            entry.summary = "Magpadala ng mensahe o inquiry gamit ang contact form ng RDC-NCR website."
            entry.body = "Sa Contact page maaaring magpadala ng mensahe at katanungan sa RDC-NCR."
        else:
            entry.summary = "Send a message or inquiry through the RDC-NCR contact form."
            entry.body = "Use the Contact page to send a message or inquiry to RDC-NCR."
        entry.tags = sorted(tags)
        entry.save(update_fields=["summary", "body", "tags"])


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0010_public_chat_content"),
    ]

    operations = [
        migrations.RunPython(update_contact_content, migrations.RunPython.noop),
    ]

