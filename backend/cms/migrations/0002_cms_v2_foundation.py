import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted for review"),
    ("published", "Published"),
    ("rejected", "Rejected"),
    ("archived", "Archived"),
]


def migrate_revision_targets_and_defaults(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    CMSRevision = apps.get_model("cms", "CMSRevision")
    CMSPageSection = apps.get_model("cms", "CMSPageSection")
    CMSMediaAsset = apps.get_model("cms", "CMSMediaAsset")
    CMSSiteSetting = apps.get_model("cms", "CMSSiteSetting")

    model_names = {
        "page": "cmspage",
        "article": "cmsarticle",
        "section": "cmspagesection",
        "media": "cmsmediaasset",
    }
    content_types = {
        key: ContentType.objects.get_or_create(app_label="cms", model=model_name)[0]
        for key, model_name in model_names.items()
    }
    for revision in CMSRevision.objects.all().iterator():
        revision.content_type = content_types[revision.legacy_content_type]
        revision.save(update_fields=["content_type"])

    CMSPageSection.objects.filter(page__status="published").update(status="published")
    for media in CMSMediaAsset.objects.all().iterator():
        media.storage_key = media.file.name
        media.save(update_fields=["storage_key"])

    CMSSiteSetting.objects.get_or_create(
        key="media-upload-allowed-types",
        defaults={
            "description": "Allowed MIME types grouped by CMS media category.",
            "value_json": {
                "image": ["image/jpeg", "image/png", "image/webp"],
                "document": [
                    "application/pdf",
                    "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.ms-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ],
            },
        },
    )
    CMSSiteSetting.objects.get_or_create(
        key="media-upload-max-bytes",
        defaults={
            "description": "Maximum upload size in bytes for each CMS media category.",
            "value_json": {"image": 5242880, "document": 20971520},
        },
    )
    public_defaults = {
        "site-logo": ({"url": "", "alt": "RDC-NCR"}, "Global public website logo reference."),
        "footer-text": ("Planning and coordinating sustainable development for Metro Manila.", "Footer organization text."),
        "contact-details": ({"email": "", "phone": ""}, "Public contact email and phone."),
        "social-links": ([], "Public social media links."),
        "office-address": ("", "Public office address."),
        "quick-links": ([], "Footer quick links."),
        "chatbot-contact-fallback-link": ("/contact", "Contact link used when chatbot escalation is needed."),
        "homepage-announcement-banner": ({"enabled": False, "text": "", "link": ""}, "Optional Home page announcement banner."),
    }
    for key, (value, description) in public_defaults.items():
        CMSSiteSetting.objects.get_or_create(
            key=key,
            defaults={"value_json": value, "description": description},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CMSSiteSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=160, unique=True)),
                ("value_json", models.JSONField(blank=True, default=dict)),
                ("description", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_cms_site_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.RemoveIndex(model_name="cmspagesection", name="cms_cmspage_page_id_580b7b_idx"),
        migrations.AddField(model_name="cmsarticle", name="archived_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="cmsarticle", name="review_notes", field=models.TextField(blank=True)),
        migrations.AddField(
            model_name="cmsarticle",
            name="reviewed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_cms_articles", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="cmsarticle",
            name="submitted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_cms_articles", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name="cmsmediaasset", name="public_url", field=models.URLField(blank=True, max_length=1000)),
        migrations.AddField(model_name="cmsmediaasset", name="storage_backend", field=models.CharField(default="local", max_length=20)),
        migrations.AddField(model_name="cmsmediaasset", name="storage_key", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="cmspage", name="archived_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="cmspage", name="review_notes", field=models.TextField(blank=True)),
        migrations.AddField(
            model_name="cmspage",
            name="reviewed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_cms_pages", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="cmspage",
            name="submitted_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_cms_pages", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(model_name="cmspagesection", name="lock_acquired_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="cmspagesection",
            name="lock_owner",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="locked_cms_sections", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="cmspagesection",
            name="status",
            field=models.CharField(choices=STATUS_CHOICES, default="draft", max_length=20),
        ),
        migrations.AlterField(model_name="cmsarticle", name="status", field=models.CharField(choices=STATUS_CHOICES, default="draft", max_length=20)),
        migrations.AlterField(model_name="cmspage", name="status", field=models.CharField(choices=STATUS_CHOICES, default="draft", max_length=20)),
        migrations.AlterField(
            model_name="cmsrevision",
            name="action",
            field=models.CharField(
                choices=[
                    ("create", "Create"), ("update", "Update"), ("publish", "Publish"),
                    ("archive", "Archive"), ("reorder", "Reorder"), ("submit", "Submit"),
                    ("reject", "Reject"), ("restore", "Restore"),
                ],
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(model_name="cmsrevision", name="unique_cms_revision_version_per_object"),
        migrations.RemoveIndex(model_name="cmsrevision", name="cms_cmsrevi_content_051b78_idx"),
        migrations.RenameField(model_name="cmsrevision", old_name="content_type", new_name="legacy_content_type"),
        migrations.AddField(
            model_name="cmsrevision",
            name="content_type",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cms_revisions", to="contenttypes.contenttype"),
        ),
        migrations.RunPython(migrate_revision_targets_and_defaults, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="cmsrevision",
            name="content_type",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cms_revisions", to="contenttypes.contenttype"),
        ),
        migrations.RemoveField(model_name="cmsrevision", name="legacy_content_type"),
        migrations.AddIndex(
            model_name="cmsrevision",
            index=models.Index(fields=["content_type", "object_id", "-version_number"], name="cms_cmsrevi_content_7aeeeb_idx"),
        ),
        migrations.AddConstraint(
            model_name="cmsrevision",
            constraint=models.UniqueConstraint(fields=("content_type", "object_id", "version_number"), name="unique_cms_revision_version_per_object"),
        ),
        migrations.AddIndex(
            model_name="cmspagesection",
            index=models.Index(fields=["page", "status", "is_visible", "order"], name="cms_cmspage_page_id_70910c_idx"),
        ),
        migrations.AddIndex(
            model_name="cmspagesection",
            index=models.Index(fields=["lock_acquired_at"], name="cms_cmspage_lock_ac_86de79_idx"),
        ),
    ]
