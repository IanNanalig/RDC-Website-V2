import re
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import PasswordResetRequest, PasswordSetupToken, User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TURNSTILE_REQUIRED=False,
    FRONTEND_BASE_URL="https://portal.example.test",
)
class PasswordResetFlowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="reset-admin", email="reset-admin@example.test",
            password="AdminPassword123!", role="admin", must_change_password=False,
        )
        self.user = User.objects.create_user(
            username="reset-user", email=f"reset-user-{self._testMethodName}@example.test",
            password="OldPassword123!", role="staff", must_change_password=False,
            first_name="Original", last_name="Name", agency="DENR", office="Original Office",
        )

    def request_reset(self, email=None):
        self.client.force_authenticate(user=None)
        return self.client.post(
            "/api/password-reset-requests/", {"email": email or self.user.email}, format="json",
            HTTP_X_FORWARDED_FOR=f"reset-flow-{self._testMethodName}",
        )

    def approve(self, reset_request):
        self.client.force_authenticate(user=self.admin)
        return self.client.post(f"/api/password-reset-requests/{reset_request.id}/approve/", {}, format="json")

    def reset_token_from_email(self):
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("Password Reset", message.subject)
        self.assertIn("/reset-password?token=", message.body)
        self.assertNotIn("complete your profile", message.body.lower())
        return re.search(r"token=([^\s]+)", message.body).group(1)

    def test_unknown_email_gets_same_response_without_request_or_email(self):
        registered = self.request_reset()
        unknown = self.request_reset("unregistered@example.test")
        self.assertEqual(registered.status_code, 201)
        self.assertEqual(unknown.status_code, 201)
        self.assertEqual(registered.data, unknown.data)
        self.assertEqual(PasswordResetRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_approved_request_sends_password_only_link_and_preserves_profile(self):
        self.request_reset()
        reset_request = PasswordResetRequest.objects.get()
        original_session_version = self.user.session_version
        response = self.approve(reset_request)
        self.assertEqual(response.status_code, 200, response.data)
        reset_request.refresh_from_db()
        self.assertEqual(reset_request.status, "approved")
        token = self.reset_token_from_email()
        self.assertTrue(token.startswith("reset_"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))
        self.assertEqual(self.user.session_version, original_session_version)

        self.client.force_authenticate(user=None)
        prefill = self.client.get(f"/api/auth/setup-password/?token={token}")
        self.assertEqual(prefill.status_code, 200, prefill.data)
        self.assertEqual(prefill.data, {"email": self.user.email, "setup_type": "password_reset"})
        invalid = self.client.post(
            "/api/auth/setup-password/", {"token": token, "new_password": "short"}, format="json",
        )
        self.assertEqual(invalid.status_code, 400)
        changed = self.client.post(
            "/api/auth/setup-password/",
            {"token": token, "new_password": "NewPassword123!", "first_name": "Tampered", "last_name": "Name", "agency": "DPWH"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword123!"))
        self.assertFalse(self.user.check_password("OldPassword123!"))
        self.assertEqual((self.user.first_name, self.user.last_name), ("Original", "Name"))
        self.assertEqual(self.user.agency, "DENR")
        self.assertEqual(self.user.office, "Original Office")
        self.assertEqual(self.user.session_version, original_session_version + 1)
        self.assertIsNotNone(PasswordSetupToken.objects.get(token=token).used_at)
        reused = self.client.post(
            "/api/auth/setup-password/", {"token": token, "new_password": "AnotherPassword123!"}, format="json",
        )
        self.assertEqual(reused.status_code, 400)

    def test_direct_reset_and_email_failures_leave_old_password_usable(self):
        self.client.force_authenticate(user=self.admin)
        with patch("projects.views.send_mail", side_effect=RuntimeError("SMTP unavailable")):
            failed = self.client.post(f"/api/admin/users/{self.user.id}/reset_password/", {}, format="json")
        self.assertEqual(failed.status_code, 503)
        self.assertFalse(PasswordSetupToken.objects.filter(user=self.user).exists())
        successful = self.client.post(f"/api/admin/users/{self.user.id}/reset_password/", {}, format="json")
        self.assertEqual(successful.status_code, 200, successful.data)
        self.reset_token_from_email()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))
        self.assertFalse(self.user.must_change_password)

    def test_password_only_reset_works_for_each_account_role(self):
        self.client.force_authenticate(user=self.admin)
        for role in ("admin", "validator", "staff", "content_editor"):
            user = User.objects.create_user(
                username=f"role-reset-{role}", email=f"role-reset-{role}@example.test",
                password="OldPassword123!", role=role, must_change_password=False,
                first_name="Original", last_name=role.title(), agency="RDC-NCR" if role != "staff" else "DENR",
            )
            sent = self.client.post(f"/api/admin/users/{user.id}/reset_password/", {}, format="json")
            self.assertEqual(sent.status_code, 200, sent.data)
            token = PasswordSetupToken.objects.get(user=user).token
            self.client.force_authenticate(user=None)
            completed = self.client.post(
                "/api/auth/setup-password/", {"token": token, "new_password": "NewPassword123!"}, format="json",
            )
            self.assertEqual(completed.status_code, 200, completed.data)
            user.refresh_from_db()
            self.assertEqual(user.role, role)
            self.assertEqual((user.first_name, user.last_name), ("Original", role.title()))
            self.assertTrue(user.check_password("NewPassword123!"))
            self.client.force_authenticate(user=self.admin)

    def test_failed_approval_stays_pending_and_does_not_revoke_sessions(self):
        self.request_reset()
        reset_request = PasswordResetRequest.objects.get()
        self.client.force_authenticate(user=self.admin)
        with patch("projects.views.send_mail", return_value=0):
            failed = self.client.post(f"/api/password-reset-requests/{reset_request.id}/approve/", {}, format="json")
        self.assertEqual(failed.status_code, 503)
        reset_request.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(reset_request.status, "pending")
        self.assertTrue(self.user.check_password("OldPassword123!"))
        self.assertFalse(PasswordSetupToken.objects.filter(user=self.user).exists())
        approved = self.client.post(f"/api/password-reset-requests/{reset_request.id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200, approved.data)

    def test_expired_token_is_rejected_and_session_ends_only_after_change(self):
        session_client = APIClient()
        login = session_client.post(
            "/api/auth/login/", {"email": self.user.email, "password": "OldPassword123!"}, format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        session_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.client.force_authenticate(user=self.admin)
        issued = self.client.post(f"/api/admin/users/{self.user.id}/reset_password/", {}, format="json")
        self.assertEqual(issued.status_code, 200, issued.data)
        token = self.reset_token_from_email()
        self.assertEqual(session_client.get("/api/auth/me/").status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))

        record = PasswordSetupToken.objects.get(token=token)
        record.expires_at = timezone.now() - timedelta(seconds=1)
        record.save(update_fields=["expires_at"])
        self.client.force_authenticate(user=None)
        expired = self.client.post(
            "/api/auth/setup-password/", {"token": token, "new_password": "NewPassword123!"}, format="json",
        )
        self.assertEqual(expired.status_code, 400)
        self.assertEqual(session_client.get("/api/auth/me/").status_code, 200)

        record.expires_at = timezone.now() + timedelta(hours=1)
        record.save(update_fields=["expires_at"])
        completed = self.client.post(
            "/api/auth/setup-password/", {"token": token, "new_password": "NewPassword123!"}, format="json",
        )
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertEqual(session_client.get("/api/auth/me/").status_code, 401)
