from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Agency, Project, User, UserActivity, UserInvitation


class AgencyManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="catalog-admin", email="catalog-admin@example.com",
            password="StrongTest123!", role="admin",
        )
        self.editor = User.objects.create_user(
            username="catalog-editor", email="catalog-editor@example.com",
            password="StrongTest123!", role="content_editor",
        )
        self.client.force_authenticate(self.admin)

    def test_admin_can_create_and_edit_name_head_and_code(self):
        created = self.client.post(
            "/api/admin/agencies/",
            {"code": "TEST-AGENCY", "name": "Test Agency", "head_name": "Juan Dela Cruz"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        updated = self.client.patch(
            "/api/admin/agencies/TEST-AGENCY/",
            {"name": "Test Agency Updated", "head_name": "Maria Santos"},
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK, updated.data)
        changed = self.client.patch(
            "/api/admin/agencies/TEST-AGENCY/", {"code": "CHANGED"}, format="json",
        )
        self.assertEqual(changed.status_code, status.HTTP_200_OK, changed.data)
        self.assertEqual(changed.data["code"], "CHANGED")
        self.assertEqual(Agency.objects.get(pk=created.data["id"]).code, "CHANGED")

    def test_code_and_name_are_case_insensitively_unique(self):
        Agency.objects.create(code="Unique-Code", name="Unique Agency")
        duplicate_code = self.client.post(
            "/api/admin/agencies/", {"code": "unique-code", "name": "Different"}, format="json",
        )
        duplicate_name = self.client.post(
            "/api/admin/agencies/", {"code": "DIFFERENT", "name": "unique agency"}, format="json",
        )
        self.assertEqual(duplicate_code.status_code, 400)
        self.assertEqual(duplicate_name.status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Agency.objects.create(code="UNIQUE-CODE", name="Database Duplicate")

    def test_archive_preview_preserves_relationships_and_hides_new_option(self):
        agency = Agency.objects.get(code="DENR")
        user = User.objects.create_user(
            username="denr-user", email="denr@example.com", password="StrongTest123!",
            role="staff", agency="DENR", agency_record=agency,
        )
        UserInvitation.objects.create(
            email="pending-denr@example.com", role="staff", agency="DENR", agency_record=agency,
            agency_locked=True, token_digest="a" * 64, status=UserInvitation.STATUS_SENT,
            expires_at=timezone.now() + timedelta(days=1),
        )
        preview = self.client.get("/api/admin/agencies/DENR/dependencies/")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data["counts"]["users"], 1)
        self.assertEqual(preview.data["counts"]["pending_invitations"], 1)
        self.assertEqual(self.client.post("/api/admin/agencies/DENR/archive/", {}, format="json").status_code, 409)
        archived = self.client.post(
            "/api/admin/agencies/DENR/archive/", {"confirm": True}, format="json",
        )
        self.assertEqual(archived.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.agency_record, agency)
        options = self.client.get("/api/admin/users/batch-invitations/options/")
        self.assertEqual(options.status_code, 200)
        self.assertNotIn("DENR", [row["code"] for row in options.data["agencies"]])
        restored = self.client.post("/api/admin/agencies/DENR/restore/", {}, format="json")
        self.assertEqual(restored.status_code, 200)

    def test_current_catalog_head_is_authoritative_in_profile(self):
        agency = Agency.objects.get(code="DPWH")
        agency.head_name = "Configured Head"
        agency.save(update_fields=["head_name"])
        user = User.objects.create_user(
            username="profile-agency", email="profile-agency@example.com", password="StrongTest123!",
            role="staff", agency="DPWH", agency_record=agency, agency_head="Old Stored Head",
        )
        self.client.force_authenticate(user)
        response = self.client.get("/api/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["agency_head"], "Configured Head")
        rejected = self.client.patch("/api/profile/", {"agency_head": "Override"}, format="json")
        self.assertEqual(rejected.status_code, 400)

    def test_non_administrator_cannot_mutate_agencies(self):
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.get("/api/admin/agencies/").status_code, 403)
        self.assertEqual(
            self.client.post("/api/admin/agencies/", {"code": "NO", "name": "No"}, format="json").status_code,
            403,
        )

    def test_rdc_is_protected_but_remains_editable_and_hidden_from_contributor_options(self):
        rdc = Agency.objects.get(system_key="rdc-ncr-primary")
        original_id = rdc.pk
        listed = self.client.get("/api/admin/agencies/")
        row = next(item for item in listed.data if item["id"] == rdc.pk)
        self.assertTrue(row["is_protected"])
        self.assertFalse(row["can_archive"])

        archived = self.client.post(f"/api/admin/agencies/{rdc.code}/archive/", {"confirm": True}, format="json")
        deleted = self.client.delete(f"/api/admin/agencies/{rdc.code}/")
        self.assertEqual(archived.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(archived.data["code"], "protected_agency")
        self.assertEqual(deleted.status_code, status.HTTP_409_CONFLICT)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Agency.objects.filter(pk=rdc.pk).update(is_active=False)

        updated = self.client.patch(
            f"/api/admin/agencies/{rdc.code}/",
            {"code": "RDC-Metro", "name": "Regional Development Council Metro Manila"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        rdc.refresh_from_db()
        self.assertEqual(rdc.pk, original_id)
        self.assertEqual(rdc.system_key, "rdc-ncr-primary")
        self.assertEqual(rdc.code, "RDC-Metro")
        self.assertTrue(rdc.is_active)

        options = self.client.get("/api/admin/users/batch-invitations/options/")
        self.assertNotIn(rdc.code, [item["code"] for item in options.data["agencies"]])

    def test_code_change_updates_current_mirrors_without_rewriting_history(self):
        agency = Agency.objects.get(code="DENR")
        user = User.objects.create_user(
            username="mirror-user", email="mirror@example.com", password="StrongTest123!",
            role="staff", agency=agency.code, office=agency.code, agency_record=agency,
        )
        pending = UserInvitation.objects.create(
            email="mirror-pending@example.com", role="staff", agency=agency.code,
            agency_record=agency, agency_locked=True, token_digest="b" * 64,
            status=UserInvitation.STATUS_SENT, expires_at=timezone.now() + timedelta(days=1),
        )
        completed = UserInvitation.objects.create(
            email="mirror-completed@example.com", role="staff", agency=agency.code,
            agency_record=agency, agency_locked=True, token_digest="c" * 64,
            status=UserInvitation.STATUS_COMPLETED, expires_at=timezone.now() + timedelta(days=1),
        )
        project = Project.objects.create(
            name="Mirror project", implementing_agency=agency.code, municipality="Manila",
            status="planning", cost=1, latitude=14.5, agency=agency.code,
            primary_agency=agency,
            profile_data={"simplified_form": {"agencyName": agency.code}},
        )
        historical = UserActivity.objects.create(
            user=self.admin, role="admin", event="api_action",
            details={"action": "historical_snapshot", "agency_code": agency.code},
        )

        response = self.client.patch(
            f"/api/admin/agencies/{agency.code}/", {"code": "DENR-NCR"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        pending.refresh_from_db()
        completed.refresh_from_db()
        project.refresh_from_db()
        historical.refresh_from_db()
        self.assertEqual(user.agency_record_id, agency.pk)
        self.assertEqual(user.agency, "DENR-NCR")
        self.assertEqual(user.office, "DENR-NCR")
        self.assertEqual(pending.agency, "DENR-NCR")
        self.assertEqual(completed.agency, "DENR")
        self.assertEqual(project.primary_agency_id, agency.pk)
        self.assertEqual(project.agency, "DENR-NCR")
        self.assertEqual(project.implementing_agency, "DENR-NCR")
        self.assertEqual(project.profile_data["simplified_form"]["agencyName"], "DENR-NCR")
        self.assertEqual(historical.details["agency_code"], "DENR")
        update_log = UserActivity.objects.filter(details__action="agency_updated").latest("id")
        self.assertEqual(update_log.details["before"]["code"], "DENR")
        self.assertEqual(update_log.details["after"]["code"], "DENR-NCR")

    def test_code_suggestion_uses_official_and_generated_values(self):
        official = self.client.get(
            "/api/admin/agencies/suggest-code/?name=Department%20of%20Education"
        )
        generated = self.client.get(
            "/api/admin/agencies/suggest-code/?name=Metro%20Climate%20Action%20Office"
        )
        self.assertEqual(official.data, {"suggested_code": "DepEd", "source": "official"})
        self.assertEqual(generated.data, {"suggested_code": "MCAO", "source": "generated"})

