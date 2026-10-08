import re
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import unquote

from django.core import signing
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import AccessRequest, Notification, PasswordSetupToken, User, UserActivity


class RegistrationInvitationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="inviting-admin", email="inviting-admin@example.com",
            password="StrongTestPassword123!", role="admin", must_change_password=False,
            is_staff=True,
        )
        self.client.force_authenticate(user=self.admin)

    def invite(self, email="invited@example.com", role="contributor"):
        with patch("projects.views.send_mail") as send_mail:
            response = self.client.post("/api/admin/users/", {"email": email, "role": role}, format="json")
        if response.status_code != 202:
            return response, None
        match = re.search(r"token=([^\s]+)", send_mail.call_args.args[1])
        self.assertIsNotNone(match)
        return response, unquote(match.group(1))

    @staticmethod
    def profile(token, agency="DENR"):
        return {
            "token": token,
            "new_password": "ValidSetup123!",
            "full_name": "Invited Person",
            "agency": agency,
            "agency_head": "Agency Head",
            "office": "Main Office",
            "division": "Planning",
            "position": "Officer",
            "contact_number": "09170000000",
            "phone_number": "09170000000",
        }

    def test_invite_is_audit_only_until_completed_and_admin_activates(self):
        response, token = self.invite()
        self.assertEqual(response.status_code, 202, response.data)
        self.assertTrue(response.data["invitation_sent"])
        self.assertFalse(User.objects.filter(email="invited@example.com").exists())
        self.assertEqual(PasswordSetupToken.objects.count(), 0)
        sent = UserActivity.objects.get(event="registration_invitation_sent")
        self.assertEqual(sent.user_id, self.admin.id)
        self.assertEqual(sent.details["email"], "invited@example.com")
        self.assertEqual(sent.details["role"], "staff")
        self.assertNotIn(token, str(sent.details))
        audit = self.client.get("/api/admin/activity/?user=invited@example.com")
        self.assertEqual(audit.status_code, 200)
        self.assertIn(sent.id, [row["id"] for row in audit.data])

        self.client.force_authenticate(user=None)
        prefill = self.client.get(f"/api/auth/setup-password/?token={token}")
        self.assertEqual(prefill.status_code, 200, prefill.data)
        self.assertEqual(prefill.data["setup_type"], "invitation")
        self.assertFalse(prefill.data["agency_locked"])
        completed = self.client.post("/api/auth/setup-password/", self.profile(token), format="json")
        self.assertEqual(completed.status_code, 200, completed.data)
        self.assertTrue(completed.data["requires_admin_activation"])
        user = User.objects.get(email="invited@example.com")
        self.assertEqual(user.role, "staff")
        self.assertEqual(user.agency, "DENR")
        self.assertEqual(user.created_by_id, self.admin.id)
        self.assertFalse(user.is_active)
        self.assertFalse(user.must_change_password)
        self.assertTrue(user.check_password("ValidSetup123!"))
        self.assertTrue(UserActivity.objects.filter(user=user, event="registration_completed").exists())
        notification = Notification.objects.get(event_type="registration_awaiting_activation")
        self.assertEqual(notification.recipient_id, self.admin.id)
        self.assertEqual(notification.link_path, "/admin/users?tab=system-users")

        blocked = self.client.post(
            "/api/auth/login/", {"email": user.email, "password": "ValidSetup123!"}, format="json"
        )
        self.assertEqual(blocked.status_code, 403)
        self.client.force_authenticate(user=self.admin)
        activated = self.client.post(f"/api/admin/users/{user.id}/set_active/", {"active": True}, format="json")
        self.assertEqual(activated.status_code, 200, activated.data)
        self.client.force_authenticate(user=None)
        login = self.client.post(
            "/api/auth/login/", {"email": user.email, "password": "ValidSetup123!"}, format="json"
        )
        self.assertEqual(login.status_code, 200, login.data)

    def test_email_failure_creates_no_account_or_sent_audit(self):
        with patch("projects.views.send_mail", side_effect=RuntimeError("SMTP unavailable")):
            response = self.client.post(
                "/api/admin/users/", {"email": "failed@example.com", "role": "validator"}, format="json"
            )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(User.objects.filter(email="failed@example.com").exists())
        self.assertFalse(UserActivity.objects.filter(event="registration_invitation_sent").exists())

        with patch("projects.views.send_mail", return_value=0):
            undelivered = self.client.post(
                "/api/admin/users/", {"email": "undelivered@example.com", "role": "validator"}, format="json"
            )
        self.assertEqual(undelivered.status_code, 500)
        self.assertFalse(User.objects.filter(email="undelivered@example.com").exists())
        self.assertFalse(UserActivity.objects.filter(event="registration_invitation_sent").exists())

    def test_resend_replaces_old_link_and_completion_is_one_time(self):
        _, first = self.invite()
        _, second = self.invite()
        self.assertNotEqual(first, second)
        self.client.force_authenticate(user=None)
        old = self.client.get(f"/api/auth/setup-password/?token={first}")
        self.assertEqual(old.status_code, 400)
        old_submit = self.client.post("/api/auth/setup-password/", self.profile(first), format="json")
        self.assertEqual(old_submit.status_code, 400)
        self.assertFalse(User.objects.filter(email="invited@example.com").exists())
        current = self.client.post("/api/auth/setup-password/", self.profile(second), format="json")
        self.assertEqual(current.status_code, 200, current.data)
        repeated = self.client.post("/api/auth/setup-password/", self.profile(second), format="json")
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(User.objects.filter(email="invited@example.com").count(), 1)
        self.assertEqual(Notification.objects.filter(event_type="registration_awaiting_activation").count(), 1)
        User.objects.filter(email="invited@example.com").delete()
        self.assertEqual(
            self.client.post("/api/auth/setup-password/", self.profile(second), format="json").status_code,
            400,
            "A used link must stay unusable even if its account is later deleted",
        )

    def test_invalid_expired_or_incomplete_invitation_creates_no_account(self):
        _, token = self.invite()
        self.client.force_authenticate(user=None)
        tampered = self.client.get(f"/api/auth/setup-password/?token={token}changed")
        self.assertEqual(tampered.status_code, 400)
        bad_agency = self.client.post("/api/auth/setup-password/", self.profile(token, "Unknown"), format="json")
        self.assertEqual(bad_agency.status_code, 400)
        incomplete = self.profile(token)
        incomplete["full_name"] = ""
        self.assertEqual(self.client.post("/api/auth/setup-password/", incomplete, format="json").status_code, 400)
        weak_password = self.profile(token)
        weak_password["new_password"] = "weak"
        self.assertEqual(self.client.post("/api/auth/setup-password/", weak_password, format="json").status_code, 400)
        with patch("projects.views.signing.loads", side_effect=signing.SignatureExpired("expired")):
            expired = self.client.post("/api/auth/setup-password/", self.profile(token), format="json")
        self.assertEqual(expired.status_code, 400)
        self.assertFalse(User.objects.filter(email="invited@example.com").exists())

    def test_signed_invitation_expires_after_24_hours(self):
        with patch("django.core.signing.time.time", return_value=1_700_000_000):
            _, token = self.invite(email="expired@example.com")
        self.client.force_authenticate(user=None)
        response = self.client.get(f"/api/auth/setup-password/?token={token}")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="expired@example.com").exists())

    def test_internal_invitation_rejects_agency_tampering(self):
        _, token = self.invite(role="validator")
        self.client.force_authenticate(user=None)
        prefill = self.client.get(f"/api/auth/setup-password/?token={token}")
        self.assertTrue(prefill.data["agency_locked"])
        self.assertEqual(prefill.data["profile"]["agency"], "RDC-NCR")
        tampered = self.client.post("/api/auth/setup-password/", self.profile(token, "DENR"), format="json")
        self.assertEqual(tampered.status_code, 400)
        self.assertFalse(User.objects.filter(email="invited@example.com").exists())

    def test_access_request_email_failure_keeps_request_pending(self):
        access_request = AccessRequest.objects.create(
            full_name="Legacy Applicant", email="legacy-applicant@example.com",
            office_unit="RDC", requested_role="validator",
        )
        with patch("projects.views.send_mail", side_effect=RuntimeError("SMTP unavailable")):
            response = self.client.post(f"/api/access-requests/{access_request.id}/approve/", {}, format="json")
        self.assertEqual(response.status_code, 500)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, "pending")
        self.assertFalse(User.objects.filter(email=access_request.email).exists())
        self.assertFalse(UserActivity.objects.filter(event="registration_invitation_sent").exists())

    def test_legacy_setup_link_preserves_existing_inactive_account(self):
        user = User.objects.create_user(
            username="legacy-inactive", email="legacy-inactive@example.com", role="staff",
            password="OldStrongPassword123!", is_active=False, must_change_password=True,
        )
        token = PasswordSetupToken.objects.create(
            user=user, token="legacy-setup-link", expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client.force_authenticate(user=None)
        prefill = self.client.get(f"/api/auth/setup-password/?token={token.token}")
        self.assertEqual(prefill.data["setup_type"], "existing_account")
        completed = self.client.post("/api/auth/setup-password/", self.profile(token.token), format="json")
        self.assertEqual(completed.status_code, 200, completed.data)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertFalse(user.must_change_password)
