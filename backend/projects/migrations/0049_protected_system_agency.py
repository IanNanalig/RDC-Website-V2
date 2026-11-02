from django.db import migrations, models


PRIMARY_AGENCY_SYSTEM_KEY = "rdc-ncr-primary"
PRIMARY_AGENCY_CODE = "RDC-NCR"
PRIMARY_AGENCY_NAME = "Regional Development Council National Capital Region"


def identify_primary_agency(apps, schema_editor):
    Agency = apps.get_model("projects", "Agency")
    code_matches = list(Agency.objects.filter(code__iexact=PRIMARY_AGENCY_CODE))
    name_matches = list(Agency.objects.filter(name__iexact=PRIMARY_AGENCY_NAME))
    if len(code_matches) == 1 and all(
        row.pk == code_matches[0].pk for row in name_matches
    ):
        agency = code_matches[0]
    elif not code_matches and len(name_matches) == 1:
        agency = name_matches[0]
    else:
        raise RuntimeError(
            "Cannot identify exactly one RDC-NCR agency. Correct the agency catalog before migrating."
        )
    agency.system_key = PRIMARY_AGENCY_SYSTEM_KEY
    agency.is_active = True
    agency.archived_at = None
    agency.save(update_fields=["system_key", "is_active", "archived_at"])


def clear_primary_agency_identity(apps, schema_editor):
    Agency = apps.get_model("projects", "Agency")
    Agency.objects.filter(system_key=PRIMARY_AGENCY_SYSTEM_KEY).update(system_key=None)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0048_account_capacity"),
    ]

    operations = [
        migrations.AddField(
            model_name="agency",
            name="system_key",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(identify_primary_agency, clear_primary_agency_identity),
        migrations.AddConstraint(
            model_name="agency",
            constraint=models.CheckConstraint(
                condition=models.Q(system_key__isnull=True) | models.Q(is_active=True),
                name="system_agency_must_be_active",
            ),
        ),
    ]
