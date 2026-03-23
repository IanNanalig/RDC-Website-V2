from django.db import migrations


def update_contact_content(apps, schema_editor):
    PublicContent = apps.get_model("projects", "PublicContent")

    address = (
        "16th Floor, MMDA Head Office, Dofia Julia Vargas Avenue corner Molawe St., "
        "Barangay Ugong, Pasig City"
    )

    contact_updates = [
        {
            "language": "en",
            "summary": f"Send inquiries via the Contact page. Office address: {address}.",
            "body": (
                "Use the Contact page to send a message or inquiry to RDC-NCR. "
                f"Office address: {address}. You can also email rdc.ncr@mmda.gov.ph."
            ),
            "tags": [
                "contact",
                "message",
                "inquiry",
                "email",
                "address",
                "location",
                "office",
                "map",
                "directions",
            ],
        },
        {
            "language": "tl",
            "summary": f"Magpadala ng mensahe sa Contact page. Address: {address}.",
            "body": (
                "Sa Contact page maaari kang magpadala ng mensahe o katanungan sa RDC-NCR. "
                f"Address ng opisina: {address}. Maaari ring mag-email sa rdc.ncr@mmda.gov.ph."
            ),
            "tags": [
                "contact",
                "mensahe",
                "inquiry",
                "email",
                "address",
                "location",
                "opisina",
                "map",
                "direksyon",
            ],
        },
    ]

    for update in contact_updates:
        PublicContent.objects.update_or_create(
            slug="contact",
            language=update["language"],
            defaults=update,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0011_update_public_content_tags"),
    ]

    operations = [
        migrations.RunPython(update_contact_content, migrations.RunPython.noop),
    ]

