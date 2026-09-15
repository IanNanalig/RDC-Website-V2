from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.models import CMSContributorForm
from .models import AuditTrail, PasswordSetupToken, Project, User, UserActivity


class AuditCoverageTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="audit-admin", email="audit-admin@example.com",
            password="StrongTestPassword123!", role="admin", must_change_password=False,
        )
        self.validator = User.objects.create_user(
            username="audit-validator", email="audit-validator@example.com",
            password="StrongTestPassword123!", role="validator", must_change_password=False,
        )
        self.editor = User.objects.create_user(
            username="audit-editor", email="audit-editor@example.com",
            password="StrongTestPassword123!", role="content_editor", must_change_password=False,
        )
        self.contributor = User.objects.create_user(
            username="audit-contributor", email="audit-contributor@example.com",
            password="StrongTestPassword123!", role="staff", must_change_password=False,
            agency="MMDA",
        )

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def test_fallback_covers_all_four_roles_without_body_or_passive_gets(self):
        for user in (self.admin, self.validator, self.editor, self.contributor):
            self.as_user(user)
            before = UserActivity.objects.filter(user=user).count()
            self.assertEqual(self.client.get("/api/notifications/unread-count/").status_code, 200)
            self.assertEqual(UserActivity.objects.filter(user=user).count(), before)
            response = self.client.post("/api/notifications/mark-all-read/", {"secret": "do-not-copy"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            activity = UserActivity.objects.get(user=user, event="api_action")
            self.assertEqual(activity.role, user.role)
            self.assertEqual(activity.details["method"], "POST")
            self.assertEqual(activity.details["status_code"], 200)
            self.assertNotIn("secret", str(activity.details))

    def test_failed_action_is_audited_without_request_body(self):
        self.as_user(self.admin)
        response = self.client.post(
            f"/api/admin/users/{self.admin.id}/set_active/?token=do-not-copy",
            {"active": False, "password": "do-not-copy"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        activity = UserActivity.objects.get(user=self.admin, event="api_action_failed")
        self.assertEqual(activity.details["status_code"], 400)
        self.assertNotIn("password", str(activity.details))
        self.assertNotIn("token", str(activity.details))

    def test_account_changes_and_deleted_actor_history_remain_visible(self):
        self.as_user(self.admin)
        edited = self.client.patch(
            f"/api/admin/users/{self.contributor.id}/",
            {"role": "validator", "password": "NewStrongPassword123_"}, format="json",
        )
        self.assertEqual(edited.status_code, 200)
        edit_activity = UserActivity.objects.get(user=self.admin, event="user_update")
        self.assertTrue(edit_activity.details["password_changed"])
        self.assertNotIn("NewStrongPassword123_", str(edit_activity.details))
        status_response = self.client.post(
            f"/api/admin/users/{self.contributor.id}/set_active/", {"active": False}, format="json"
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(
            user=self.admin, event="user_status_changed", details__target_user_id=self.contributor.id
        ).exists())

        prior = UserActivity.objects.create(
            user=self.contributor, role="staff", event="project_submit", details={"source": "test"}
        )
        contributor_id = self.contributor.id
        deleted = self.client.delete(f"/api/admin/users/{contributor_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        prior.refresh_from_db()
        self.assertIsNone(prior.user_id)
        self.assertEqual(prior.actor_username, "audit-contributor")
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="user_delete").exists())
        audit_list = self.client.get("/api/admin/activity/?user=audit-contributor&include_meta=1")
        self.assertEqual(audit_list.status_code, 200)
        self.assertTrue(any(row["id"] == prior.id and row["username"] == "audit-contributor"
                            for row in audit_list.data["results"]))

    def test_project_delete_retains_snapshot_and_project_saves_use_actual_actor(self):
        project = Project.objects.create(
            name="Audit Project", implementing_agency="MMDA", municipality="NCR",
            status="planning", cost=1000, latitude=14.5, agency="MMDA", budget=1000,
            created_by=self.contributor,
        )
        self.as_user(self.admin)
        updated = self.client.patch(
            f"/api/admin/projects/{project.id}/", {"title": "Audit Project Updated"}, format="json"
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(AuditTrail.objects.filter(project=project).latest("timestamp").actor_id, self.admin.id)
        self.assertTrue(UserActivity.objects.filter(user=self.admin, project=project, event="project_update").exists())

        deleted = self.client.delete(f"/api/admin/projects/{project.id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        activity = UserActivity.objects.get(user=self.admin, event="project_delete")
        self.assertIsNone(activity.project_id)
        self.assertEqual(activity.project_id_snapshot, project.id)
        self.assertEqual(activity.project_title_snapshot, "Audit Project Updated")
        audit_list = self.client.get("/api/admin/activity/?event=project_delete")
        self.assertEqual(audit_list.data[0]["project_title"], "Audit Project Updated")

    def test_form_lock_actions_have_specific_editor_events(self):
        form = CMSContributorForm.objects.get(key="simplified-rdip")
        self.as_user(self.editor)
        locked = self.client.post(f"/api/admin/cms/forms/{form.id}/lock/", {}, format="json")
        self.assertEqual(locked.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(user=self.editor, event="cms_form_lock_acquired").exists())
        self.as_user(self.admin)
        blocked = self.client.post(f"/api/admin/cms/forms/{form.id}/lock/", {}, format="json")
        self.assertEqual(blocked.status_code, 423)
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="cms_form_lock_blocked").exists())
        access = self.client.post(f"/api/admin/cms/forms/{form.id}/request-access/", {}, format="json")
        self.assertEqual(access.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="cms_form_access_requested").exists())
        self.as_user(self.editor)
        heartbeat = self.client.post(f"/api/admin/cms/forms/{form.id}/heartbeat/", {}, format="json")
        self.assertEqual(heartbeat.status_code, 200)
        self.assertFalse(UserActivity.objects.filter(user=self.editor, event="api_action").exists())
        unlocked = self.client.post(f"/api/admin/cms/forms/{form.id}/unlock/", {}, format="json")
        self.assertEqual(unlocked.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(user=self.editor, event="cms_form_lock_released").exists())

    @override_settings(TURNSTILE_REQUIRED=False)
    def test_anonymous_password_reset_attempt_is_not_attributed_to_target_user(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/password-reset-requests/", {"email": self.contributor.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        activity = UserActivity.objects.get(event="auth_reset_request")
        self.assertIsNone(activity.user_id)
        self.assertEqual(activity.role, "unauthenticated")
        self.assertEqual(activity.details["attempted_email"], self.contributor.email)
        self.as_user(self.admin)
        audit_list = self.client.get(
            f"/api/admin/activity/?user={self.contributor.email}&event=auth_reset_request"
        )
        self.assertEqual(audit_list.status_code, 200)
        self.assertEqual(audit_list.data[0]["id"], activity.id)

    def test_login_attempt_password_setup_and_logout_are_audited(self):
        self.client.force_authenticate(user=None)
        failed = self.client.post(
            "/api/auth/login/", {"email": self.contributor.email, "password": "incorrect"}, format="json"
        )
        self.assertEqual(failed.status_code, 401)
        failure = UserActivity.objects.get(event="login_failed")
        self.assertIsNone(failure.user_id)
        self.assertNotIn("incorrect", str(failure.details))

        login = self.client.post(
            "/api/auth/login/",
            {"email": self.contributor.email, "password": "StrongTestPassword123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(user=self.contributor, event="login").exists())

        self.as_user(self.validator)
        old_version = self.validator.session_version
        logout = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200)
        self.validator.refresh_from_db()
        self.assertGreater(self.validator.session_version, old_version)
        self.assertTrue(UserActivity.objects.filter(user=self.validator, event="logout").exists())

        token = PasswordSetupToken.objects.create(
            user=self.editor, token="audit-test-setup-token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client.force_authenticate(user=None)
        setup = self.client.post(
            "/api/auth/setup-password/",
            {
                "token": token.token, "new_password": "NewStrongPassword123_",
                "full_name": "Audit Editor", "agency": "RDC", "agency_head": "RDC",
                "office": "Office", "division": "Division", "position": "Editor",
                "contact_number": "09170000000", "phone_number": "09170000000",
            },
            format="json",
        )
        self.assertEqual(setup.status_code, 200, setup.data)
        self.assertTrue(UserActivity.objects.filter(user=self.editor, event="auth_password_setup").exists())
