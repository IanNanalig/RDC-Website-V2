from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import hashlib


def link_agency_records(apps, schema_editor):
    Agency = apps.get_model("projects", "Agency")
    User = apps.get_model("projects", "User")
    UserInvitation = apps.get_model("projects", "UserInvitation")

    agencies = list(Agency.objects.all())
    lookup = {}
    for agency in agencies:
        lookup[str(agency.code or "").strip().casefold()] = agency
        lookup.setdefault(str(agency.name or "").strip().casefold(), agency)

    for model in (User, UserInvitation):
        for row in model.objects.filter(agency_record__isnull=True).iterator():
            raw = " ".join(str(row.agency or "").strip().split())
            agency = lookup.get(raw.casefold())
            if not agency and raw:
                legacy_code = f"LEGACY-{hashlib.sha256(raw.casefold().encode('utf-8')).hexdigest()[:12].upper()}"
                agency, _ = Agency.objects.get_or_create(
                    code=legacy_code,
                    defaults={"name": raw, "is_active": False, "is_legacy": True},
                )
                lookup[raw.casefold()] = agency
                lookup[legacy_code.casefold()] = agency
            if agency:
                row.agency_record_id = agency.pk
                row.save(update_fields=["agency_record"])


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0045_project_concern_reports"),
    ]

    operations = [
        migrations.AddField(
            model_name="agency",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agency",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_agencies", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="agency",
            name="head_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="agency",
            name="updated_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_agencies", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="user",
            name="agency_record",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="users", to="projects.agency"),
        ),
        migrations.AddField(
            model_name="userinvitation",
            name="agency_record",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="invitations", to="projects.agency"),
        ),
        migrations.RunPython(link_agency_records, migrations.RunPython.noop),
    ]

