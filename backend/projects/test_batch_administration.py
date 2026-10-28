from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.form_schema import build_form_migration_plan
from cms.models import CMSContributorForm, CMSContributorFormVersion
from projects.form_migrations import analyze_profile_migration
from projects.models import Project, ProjectRevision, SystemSetting, User, UserInvitation


class BatchAdministrationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="batch-admin", email="batch-admin@example.com", password="Password123!", role="admin"
        )
        self.validator = User.objects.create_user(
            username="batch-validator", email="batch-validator@example.com", password="Password123!", role="validator"
        )
        self.contributor = User.objects.create_user(
            username="batch-contributor", email="batch-contributor@example.com", password="Password123!",
            role="staff", agency="DENR",
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def project(self, name, *, status_value="completed", validated=True):
        return Project.objects.create(
            name=name,
            implementing_agency="DENR",
            municipality="NCR",
            status=status_value,
            cost=50_000_000,
            description="Batch administration test project",
            latitude=14.5,
            agency="DENR",
            budget=50_000_000,
            validated=validated,
            created_by=self.contributor,
            profile_data={
                "submission_type": "simplified",
                "simplified_form": {
                    "agencyName": "DENR",
                    "projectActivity": name,
                    "location": ["Quezon City"],
                    "status": "Ongoing",
                },
            },
        )

    def test_batch_invitation_preview_send_and_permissions(self):
        entries = [
            {"email": "one@example.com", "role": "contributor", "agency": "DENR"},
            {"email": "one@example.com", "role": "validator"},
            {"email": "not-an-email", "role": "contributor"},
        ]
        self.authenticate(self.validator)
        forbidden = self.client.post(
            "/api/admin/users/batch-invitations/preview/", {"entries": entries}, format="json"
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.admin)
        preview = self.client.post(
            "/api/admin/users/batch-invitations/preview/", {"entries": entries}, format="json"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual([row["status"] for row in preview.data["rows"]], ["valid", "duplicate", "invalid"])
        with patch("projects.views._send_registration_invitation"):
            sent = self.client.post(
                "/api/admin/users/batch-invitations/send/",
                {"preview_token": preview.data["preview_token"]},
                format="json",
            )
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        self.assertEqual(sent.data["sent"], 1)
        invitation = UserInvitation.objects.get(email="one@example.com")
        self.assertEqual(invitation.agency, "DENR")
        self.assertTrue(invitation.agency_locked)
        self.assertNotIn("invite:", invitation.token_digest)

    def test_batch_invitation_limit(self):
        self.authenticate(self.admin)
        response = self.client.post(
            "/api/admin/users/batch-invitations/preview/",
            {"entries": [{"email": f"user{index}@example.com"} for index in range(101)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_invitation_accepts_utf8_bom_csv(self):
        self.authenticate(self.admin)
        upload = SimpleUploadedFile(
            "invitations.csv",
            "\ufeffemail,role,agency\r\njose@example.com,contributor,DENR\r\n".encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(
            "/api/admin/users/batch-invitations/preview/", {"file": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rows"][0]["status"], "valid")
        self.assertEqual(response.data["rows"][0]["agency"], "DENR")

    def test_batch_archive_rechecks_and_partially_succeeds(self):
        stable = self.project("Stable Project")
        pending = self.project("Pending Project", status_value="proposed", validated=False)
        self.authenticate(self.admin)
        preview = self.client.post(
            "/api/admin/projects/batch-archive-preview/",
            {"project_ids": [stable.id, pending.id]},
            format="json",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["eligible"], 1)
        executed = self.client.post(
            "/api/admin/projects/batch-archive/",
            {"preview_token": preview.data["preview_token"]},
            format="json",
        )
        self.assertEqual(executed.status_code, status.HTTP_200_OK)
        self.assertEqual(executed.data["archived"], 1)
        self.assertEqual(executed.data["skipped"], 1)
        stable.refresh_from_db()
        pending.refresh_from_db()
        self.assertTrue(stable.archived)
        self.assertFalse(pending.archived)

    def test_batch_archive_skips_active_progress_revision(self):
        project = self.project("Active Revision")
        ProjectRevision.objects.create(
            project=project,
            revision_number=1,
            revision_type="progress_update",
            state="draft",
            profile_data_snapshot=project.profile_data,
            created_by=self.contributor,
        )
        self.authenticate(self.admin)
        preview = self.client.post(
            "/api/admin/projects/batch-archive-preview/", {"project_ids": [project.id]}, format="json"
        )
        self.assertEqual(preview.data["eligible"], 0)
        self.assertIn("active progress update", preview.data["rows"][0]["reason"])

    def test_batch_archive_all_matching_is_not_limited_to_a_ui_page(self):
        first = self.project("Across Pages Alpha")
        second = self.project("Across Pages Beta")
        self.project("Different Filter")
        self.authenticate(self.admin)
        preview = self.client.post(
            "/api/admin/projects/batch-archive-preview/",
            {"all_matching": True, "search": "Across Pages"},
            format="json",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual({row["id"] for row in preview.data["rows"]}, {first.id, second.id})

    def test_validated_form_migration_prepares_non_public_draft(self):
        form = CMSContributorForm.objects.select_related("current_published_version").get(key="simplified-rdip")
        source = form.current_published_version
        target_schema = deepcopy(source.schema_json)
        target_schema["sections"][0]["fields"].append({
            "key": "custom_batch_required",
            "label": "Batch Required Field",
            "type": "text",
            "required": True,
            "visible": True,
            "help_text": "",
            "placeholder": "",
        })
        target = CMSContributorFormVersion.objects.create(
            form=form,
            version_number=source.version_number + 1,
            schema_json=target_schema,
            based_on_version=source,
            migration_plan_json=build_form_migration_plan(source.schema_json, target_schema),
            published_by=self.admin,
        )
        form.current_published_version = target
        form.draft_schema_json = target_schema
        form.save(update_fields=["current_published_version", "draft_schema_json", "updated_at"])
        project = self.project("Validated Migration")
        profile = deepcopy(project.profile_data)
        profile["form_schema"] = {"key": form.key, "version": source.version_number}
        project.profile_data = profile
        project.save(update_fields=["profile_data", "updated_at"])
        original_profile = deepcopy(project.profile_data)

        self.authenticate(self.admin)
        preview = self.client.post(
            "/api/admin/projects/form-migration-preview/", {"project_ids": [project.id]}, format="json"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["eligible"], 1)
        migrated = self.client.post(
            "/api/admin/projects/migrate-forms/",
            {"preview_token": preview.data["preview_token"]},
            format="json",
        )
        self.assertEqual(migrated.status_code, status.HTTP_200_OK)
        self.assertEqual(migrated.data["prepared"], 1)
        project.refresh_from_db()
        self.assertEqual(project.profile_data, original_profile)
        revision = ProjectRevision.objects.get(project=project, revision_type="progress_update", state="draft")
        self.assertEqual(revision.profile_data_snapshot["form_schema"]["version"], target.version_number)
        self.assertIn("custom_batch_required", revision.form_migration["attention_fields"])

        again = self.client.post(
            "/api/admin/projects/form-migration-preview/", {"project_ids": [project.id]}, format="json"
        )
        self.assertEqual(again.data["eligible"], 0)
        self.assertEqual(ProjectRevision.objects.filter(project=project, revision_type="progress_update").count(), 1)

    def test_update_period_manual_open_close_preserves_schedule(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(days=5)
        SystemSetting.objects.update_or_create(
            key="portal_progress_update_window",
            defaults={"value": f'{{"enabled": true, "start_at": "{start.isoformat()}", "end_at": "{end.isoformat()}"}}'},
        )
        self.authenticate(self.admin)
        opened = self.client.post("/api/progress-update-window/", {"action": "open"}, format="json")
        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertTrue(opened.data["is_open"])
        closed = self.client.post("/api/progress-update-window/", {"action": "close"}, format="json")
        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        self.assertFalse(closed.data["is_open"])
        self.assertEqual(closed.data["start_at"], start.isoformat())
        self.assertEqual(closed.data["end_at"], end.isoformat())

        self.authenticate(self.validator)
        forbidden = self.client.post("/api/progress-update-window/", {"action": "open"}, format="json")
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.get("/api/validator/projects/?scope=update_forms").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_form_migration_blocks_changed_field_types(self):
        form = CMSContributorForm.objects.select_related("current_published_version").get(key="simplified-rdip")
        original = form.current_published_version
        source_schema = deepcopy(original.schema_json)
        source_schema["sections"][0]["fields"].append({
            "key": "custom_switch", "label": "Switch", "type": "text", "required": False, "visible": True,
        })
        source = CMSContributorFormVersion.objects.create(
            form=form, version_number=original.version_number + 1, schema_json=source_schema,
            based_on_version=original, migration_plan_json=build_form_migration_plan(original.schema_json, source_schema),
            published_by=self.admin,
        )
        target_schema = deepcopy(source_schema)
        custom = target_schema["sections"][0]["fields"][-1]
        custom["type"] = "select"
        custom["options"] = [{"value": "yes", "label": "Yes"}]
        target = CMSContributorFormVersion.objects.create(
            form=form, version_number=source.version_number + 1, schema_json=target_schema,
            based_on_version=source, migration_plan_json=build_form_migration_plan(source_schema, target_schema),
            published_by=self.admin,
        )
        form.current_published_version = target
        form.save(update_fields=["current_published_version", "updated_at"])
        project = self.project("Unsafe Type Change")
        project.profile_data = {
            **project.profile_data,
            "form_schema": {"key": form.key, "version": source.version_number},
            "simplified_form": {**project.profile_data["simplified_form"], "custom_fields": {"custom_switch": "legacy"}},
        }
        project.save(update_fields=["profile_data", "updated_at"])
        self.authenticate(self.admin)
        preview = self.client.post(
            "/api/admin/projects/form-migration-preview/", {"project_ids": [project.id]}, format="json"
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        self.assertEqual(preview.data["eligible"], 0)
        self.assertIn("Field type changed", preview.data["rows"][0]["reason"])
        self.assertFalse(ProjectRevision.objects.filter(project=project, revision_type="progress_update").exists())

    def test_form_migration_analysis_reuses_form_version_queries(self):
        form = CMSContributorForm.objects.select_related("current_published_version").get(key="simplified-rdip")
        profile = deepcopy(self.project("Cached Version Lookup").profile_data)
        profile["form_schema"] = {"key": form.key, "version": form.current_published_version.version_number}
        version_cache = {}

        with self.assertNumQueries(2):
            first = analyze_profile_migration(profile, version_cache=version_cache)
            second = analyze_profile_migration(profile, version_cache=version_cache)

        self.assertTrue(first["already_current"])
        self.assertTrue(second["already_current"])
