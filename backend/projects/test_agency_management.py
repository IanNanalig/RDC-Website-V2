from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Agency, User, UserInvitation


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

    def test_admin_can_create_edit_and_cannot_change_code(self):
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
        immutable = self.client.patch(
            "/api/admin/agencies/TEST-AGENCY/", {"code": "CHANGED"}, format="json",
        )
        self.assertEqual(immutable.status_code, status.HTTP_400_BAD_REQUEST)

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

