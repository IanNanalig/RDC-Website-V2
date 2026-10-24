from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from projects.models import ProfileEditRequest, Project, User


class ProfileWorkflowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="profile-admin", email="admin@example.com", password="pass", role="admin", is_active=True)
        self.other_admin = User.objects.create_user(username="profile-admin-2", email="admin2@example.com", password="pass", role="admin", is_active=True)
        self.contributor = User.objects.create_user(username="profile-user", email="user@example.com", password="pass", role="staff", is_active=True)

    def test_approval_allows_one_owner_edit_but_not_email_or_another_edit(self):
        self.client.force_authenticate(self.contributor)
        self.assertEqual(self.client.patch("/api/profile/", {"first_name": "Before"}, format="json").status_code, 403)
        requested = self.client.post("/api/profile/edit-requests/", {}, format="json")
        self.assertEqual(requested.status_code, 201)
        self.client.force_authenticate(self.admin)
        approved = self.client.post(f"/api/admin/profile-edit-requests/{requested.data['id']}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200)
        self.client.force_authenticate(self.contributor)
        self.assertEqual(self.client.patch("/api/profile/", {"email": "new@example.com"}, format="json").status_code, 400)
        invalid_name = self.client.patch("/api/profile/", {"first_name": "Updated1"}, format="json")
        self.assertEqual(invalid_name.status_code, 400)
        saved = self.client.patch("/api/profile/", {"first_name": "Updated", "last_name": "Name", "office": "NCR Office"}, format="json")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.data["first_name"], "Updated")
        self.assertEqual(saved.data["last_name"], "Name")
        self.assertNotIn("full_name", saved.data)
        self.assertEqual(self.client.patch("/api/profile/", {"first_name": "Again"}, format="json").status_code, 403)
        self.contributor.refresh_from_db()
        self.assertEqual((self.contributor.first_name, self.contributor.last_name), ("Updated", "Name"))
        self.assertEqual(self.contributor.email, "user@example.com")
        self.assertEqual(ProfileEditRequest.objects.get(pk=requested.data["id"]).status, "consumed")

    def test_expired_approval_and_admin_profile_permissions(self):
        ProfileEditRequest.objects.create(user=self.contributor, status="approved", reviewed_by=self.admin, expires_at=timezone.now() - timedelta(seconds=1))
        self.client.force_authenticate(self.contributor)
        self.assertEqual(self.client.patch("/api/profile/", {"office": "No"}, format="json").status_code, 403)
        self.assertEqual(self.client.get(f"/api/admin/profiles/{self.admin.pk}/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"/api/admin/profiles/{self.contributor.pk}/").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/admin/profiles/{self.contributor.pk}/", {"office": "No"}, format="json").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/admin/users/{self.contributor.pk}/", {"office": "No"}, format="json").status_code, 403)

    def test_admin_self_approval_requires_sole_active_admin(self):
        item = ProfileEditRequest.objects.create(user=self.admin)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f"/api/admin/profile-edit-requests/{item.pk}/approve/", {}, format="json").status_code, 403)
        self.other_admin.is_active = False
        self.other_admin.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(f"/api/admin/profile-edit-requests/{item.pk}/approve/", {}, format="json").status_code, 200)


class ProjectArchiveConfirmationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="archive-admin", email="archive@example.com", password="pass", role="admin")
        self.client.force_authenticate(self.admin)
        self.project = Project.objects.create(name="Project", implementing_agency="DOH", municipality="NCR", status="completed", cost=100, description="", latitude=14.5, profile_data={"simplified_form": {"status": "Ongoing"}})

    def test_confirmation_and_stale_status_are_enforced_and_restore_works(self):
        url = f"/api/admin/projects/{self.project.pk}/archive/"
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"confirm_archive": True, "expected_implementation_status": "Completed"}, format="json").status_code, 409)
        self.assertEqual(self.client.post(url, {"confirm_archive": True, "expected_implementation_status": "Ongoing"}, format="json").status_code, 200)
        self.assertEqual(self.client.get("/api/admin/projects/?view=summary").data, [])
        self.assertEqual(len(self.client.get("/api/admin/projects/?view=summary&archived=1").data), 1)
        self.assertEqual(self.client.post(f"/api/admin/projects/{self.project.pk}/unarchive/", {}, format="json").status_code, 200)
        self.project.refresh_from_db()
        self.assertFalse(self.project.archived)
        self.assertEqual(self.project.profile_data["simplified_form"]["status"], "Ongoing")
