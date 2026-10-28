import hashlib

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


APPROVED_AGENCIES = [
    ("MMDA", "Metropolitan Manila Development Authority"),
    ("DPWH", "Department of Public Works and Highways"),
    ("DENR", "Department of Environment and Natural Resources"),
    ("RDC-NCR", "Regional Development Council National Capital Region"),
    ("DILG", "Department of the Interior and Local Government"),
    ("DEPDev", "Department of Economy, Planning, and Development"),
    ("DBM", "Department of Budget and Management"),
    ("DA", "Department of Agriculture"),
    ("DAR", "Department of Agrarian Reform"),
    ("DepEd", "Department of Education"),
    ("DOH", "Department of Health"),
    ("DHSUD", "Department of Human Settlements and Urban Development"),
    ("DICT", "Department of Information and Communications Technology"),
    ("DOLE", "Department of Labor and Employment"),
    ("DOST", "Department of Science and Technology"),
    ("DSWD", "Department of Social Welfare and Development"),
    ("DOT", "Department of Tourism"),
    ("DTI", "Department of Trade and Industry"),
    ("DOTr", "Department of Transportation"),
    ("TESDA", "Technical Education and Skills Development Authority"),
    ("CHED", "Commission on Higher Education"),
    ("PSA", "Philippine Statistics Authority"),
]


def seed_agencies_and_primary_links(apps, schema_editor):
    Agency = apps.get_model("projects", "Agency")
    Project = apps.get_model("projects", "Project")
    canonical = {}
    for code, name in APPROVED_AGENCIES:
        agency, _ = Agency.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": True, "is_legacy": False},
        )
        canonical[code.casefold()] = agency
        canonical[name.casefold()] = agency

    for project in Project.objects.select_related("created_by").iterator():
        profile = project.profile_data if isinstance(project.profile_data, dict) else {}
        simplified = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
        candidates = [
            project.agency,
            simplified.get("agencyName"),
            project.implementing_agency,
            getattr(project.created_by, "agency", "") if project.created_by_id else "",
        ]
        raw = next((" ".join(str(value or "").split()) for value in candidates if str(value or "").strip()), "")
        if not raw:
            continue
        agency = canonical.get(raw.casefold())
        if agency is None:
            legacy_code = f"LEGACY-{hashlib.sha256(raw.casefold().encode('utf-8')).hexdigest()[:16].upper()}"
            agency, _ = Agency.objects.get_or_create(
                code=legacy_code,
                defaults={"name": raw, "is_active": False, "is_legacy": True},
            )
        project.primary_agency_id = agency.id
        project.save(update_fields=["primary_agency"])


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0043_user_invitation_and_revision_form_migration"),
    ]

    operations = [
        migrations.CreateModel(
            name="Agency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("is_legacy", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "agencies", "ordering": ["code"]},
        ),
        migrations.AddField(
            model_name="project",
            name="primary_agency",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="primary_projects",
                to="projects.agency",
            ),
        ),
        migrations.CreateModel(
            name="ProjectCollaboratingAgency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("added_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="project_collaborations_added", to=settings.AUTH_USER_MODEL)),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="project_collaboration_links", to="projects.agency")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="collaborating_agency_links", to="projects.project")),
            ],
            options={"ordering": ["agency__code"]},
        ),
        migrations.AddConstraint(
            model_name="projectcollaboratingagency",
            constraint=models.UniqueConstraint(fields=("project", "agency"), name="unique_project_collaborating_agency"),
        ),
        migrations.AddField(
            model_name="project",
            name="collaborating_agencies",
            field=models.ManyToManyField(blank=True, related_name="collaborating_projects", through="projects.ProjectCollaboratingAgency", to="projects.agency"),
        ),
        migrations.CreateModel(
            name="PasswordResetChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email_fingerprint", models.CharField(db_index=True, max_length=64)),
                ("otp_digest", models.CharField(blank=True, max_length=255)),
                ("reset_token_digest", models.CharField(blank=True, db_index=True, max_length=64)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("verified", "Verified"), ("used", "Used"), ("superseded", "Superseded"), ("locked", "Locked"), ("expired", "Expired")], db_index=True, default="pending", max_length=20)),
                ("delivery_status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("not_applicable", "Not applicable")], default="pending", max_length=20)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("expires_at", models.DateTimeField()),
                ("resend_available_at", models.DateTimeField()),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("superseded_at", models.DateTimeField(blank=True, null=True)),
                ("requested_ip", models.CharField(blank=True, max_length=64)),
                ("requested_user_agent", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="password_reset_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="passwordresetchallenge",
            index=models.Index(fields=["email_fingerprint", "-created_at"], name="pwdreset_email_created_idx"),
        ),
        migrations.AddIndex(
            model_name="passwordresetchallenge",
            index=models.Index(fields=["requested_ip", "-created_at"], name="pwdreset_ip_created_idx"),
        ),
        migrations.RunPython(seed_agencies_and_primary_links, migrations.RunPython.noop),
    ]
