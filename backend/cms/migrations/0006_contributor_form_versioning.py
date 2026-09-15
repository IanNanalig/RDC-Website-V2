import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def seed_simplified_form(apps, schema_editor):
    from cms.form_schema import default_simplified_form_schema

    ContributorForm = apps.get_model("cms", "CMSContributorForm")
    ContributorFormVersion = apps.get_model("cms", "CMSContributorFormVersion")
    schema = default_simplified_form_schema()
    form, _ = ContributorForm.objects.get_or_create(
        key="simplified-rdip",
        defaults={
            "name": "Simplified RDIP Contributor Form",
            "description": "Versioned form used for simplified RDIP project submissions.",
            "status": "published",
            "draft_schema_json": schema,
            "has_unpublished_changes": False,
            "published_at": timezone.now(),
        },
    )
    version, _ = ContributorFormVersion.objects.get_or_create(
        form=form,
        version_number=1,
        defaults={"schema_json": schema},
    )
    form.current_published_version = version
    form.save(update_fields=["current_published_version"])


def unseed_simplified_form(apps, schema_editor):
    ContributorForm = apps.get_model("cms", "CMSContributorForm")
    form = ContributorForm.objects.filter(key="simplified-rdip").first()
    if form:
        form.current_published_version = None
        form.save(update_fields=["current_published_version"])
        form.versions.all().delete()
        form.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0005_archive_duplicate_home_carousels"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CMSContributorForm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=120, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted for review"), ("published", "Published"), ("rejected", "Rejected")], default="draft", max_length=20)),
                ("draft_schema_json", models.JSONField(default=dict)),
                ("has_unpublished_changes", models.BooleanField(default=True)),
                ("review_notes", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("lock_acquired_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_cms_contributor_forms", to=settings.AUTH_USER_MODEL)),
                ("lock_owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="locked_cms_contributor_forms", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_cms_contributor_forms", to=settings.AUTH_USER_MODEL)),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_cms_contributor_forms", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_cms_contributor_forms", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="CMSContributorFormVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version_number", models.PositiveIntegerField()),
                ("schema_json", models.JSONField(default=dict)),
                ("published_at", models.DateTimeField(auto_now_add=True)),
                ("form", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="cms.cmscontributorform")),
                ("published_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="published_cms_contributor_form_versions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-version_number"],
                "constraints": [models.UniqueConstraint(fields=("form", "version_number"), name="unique_cms_contributor_form_version")],
            },
        ),
        migrations.AddField(
            model_name="cmscontributorform",
            name="current_published_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="active_for_forms", to="cms.cmscontributorformversion"),
        ),
        migrations.AddIndex(
            model_name="cmscontributorform",
            index=models.Index(fields=["status"], name="cms_form_status_idx"),
        ),
        migrations.AddIndex(
            model_name="cmscontributorform",
            index=models.Index(fields=["lock_acquired_at"], name="cms_form_lock_idx"),
        ),
        migrations.RunPython(seed_simplified_form, unseed_simplified_form),
    ]
