import re
import secrets
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import PasswordResetChallenge, PasswordResetRequest, PasswordSetupToken, User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    TURNSTILE_REQUIRED=False,
    FRONTEND_BASE_URL="https://portal.example.test",
)
class PasswordResetFlowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="reset-admin",
            email="reset-admin@example.test",
            password="AdminPassword123!",
            role="admin",
            must_change_password=False,
        )
        self.user = User.objects.create_user(
            username="reset-user",
            email=f"reset-user-{self._testMethodName}@example.test",
            password="OldPassword123!",
            role="staff",
            must_change_password=False,
            first_name="Original",
            last_name="Name",
            agency="DENR",
            office="Original Office",
        )

    def request_reset(self, email=None, ip=None):
        self.client.force_authenticate(user=None)
        return self.client.post(
            "/api/auth/password-reset/request/",
            {"email": email or self.user.email},
            format="json",
            HTTP_X_FORWARDED_FOR=ip or f"192.0.2.{PasswordResetChallenge.objects.count() + 1}",
        )

    def code_from_latest_email(self):
        self.assertTrue(mail.outbox)
        message = mail.outbox[-1]
        self.assertIn("Password Reset Code", message.subject)
        match = re.search(r"\b(\d{6})\b", message.body)
        self.assertIsNotNone(match)
        return match.group(1)

    def verify(self, email, code):
        return self.client.post(
            "/api/auth/password-reset/verify/",
            {"email": email, "otp": code},
            format="json",
        )

    def complete(self, token, password="NewPassword123!"):
        return self.client.post(
            "/api/auth/password-reset/complete/",
            {
                "reset_token": token,
                "new_password": password,
                "confirm_password": password,
            },
            format="json",
        )

    def issue_verified_token(self, user=None):
        target = user or self.user
        response = self.request_reset(target.email)
        self.assertEqual(response.status_code, 202, response.data)
        verified = self.verify(target.email, self.code_from_latest_email())
        self.assertEqual(verified.status_code, 200, verified.data)
        return verified.data["reset_token"]

    def test_known_and_unknown_requests_have_identical_public_response(self):
        known = self.request_reset(ip="192.0.2.10")
        unknown = self.request_reset("unregistered@example.test", ip="192.0.2.11")

        self.assertEqual(known.status_code, 202)
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(PasswordResetChallenge.objects.count(), 2)
        self.assertEqual(PasswordResetChallenge.objects.filter(user__isnull=True).count(), 1)
        self.assertEqual(PasswordResetRequest.objects.count(), 0)
        self.assertEqual(PasswordSetupToken.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        unknown_challenge = PasswordResetChallenge.objects.get(user__isnull=True)
        self.assertEqual(unknown_challenge.delivery_status, "not_applicable")

    def test_otp_reset_preserves_profile_and_invalidates_sessions(self):
        session_client = APIClient()
        login = session_client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": "OldPassword123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        session_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        original_profile = (self.user.first_name, self.user.last_name, self.user.agency, self.user.office)

        token = self.issue_verified_token()
        changed = self.complete(token)
        self.assertEqual(changed.status_code, 200, changed.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword123!"))
        self.assertEqual(
            (self.user.first_name, self.user.last_name, self.user.agency, self.user.office),
            original_profile,
        )
        self.assertEqual(session_client.get("/api/auth/me/").status_code, 401)
        self.assertEqual(self.complete(token).status_code, 400)
        challenge = PasswordResetChallenge.objects.get(user=self.user)
        self.assertEqual(challenge.status, PasswordResetChallenge.STATUS_USED)
        self.assertEqual(challenge.otp_digest, "")
        self.assertEqual(challenge.reset_token_digest, "")

    def test_invalid_codes_lock_after_five_attempts(self):
        issued = self.request_reset()
        self.assertEqual(issued.status_code, 202)
        for attempt in range(1, 6):
            response = self.verify(self.user.email, "000000")
            self.assertEqual(response.status_code, 429 if attempt == 5 else 400)
        challenge = PasswordResetChallenge.objects.get(user=self.user)
        self.assertEqual(challenge.failed_attempts, 5)
        self.assertEqual(challenge.status, PasswordResetChallenge.STATUS_LOCKED)
        self.assertEqual(challenge.otp_digest, "")

    def test_expired_otp_and_expired_reset_token_are_rejected(self):
        self.assertEqual(self.request_reset().status_code, 202)
        code = self.code_from_latest_email()
        challenge = PasswordResetChallenge.objects.get(user=self.user)
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save(update_fields=["expires_at"])
        self.assertEqual(self.verify(self.user.email, code).status_code, 400)

        challenge.resend_available_at = timezone.now() - timedelta(seconds=1)
        challenge.save(update_fields=["resend_available_at"])
        token = self.issue_verified_token()
        challenge = PasswordResetChallenge.objects.get(
            user=self.user,
            status=PasswordResetChallenge.STATUS_VERIFIED,
        )
        challenge.expires_at = timezone.now() - timedelta(seconds=1)
        challenge.save(update_fields=["expires_at"])
        self.assertEqual(self.complete(token).status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))

    def test_new_code_supersedes_previous_code(self):
        self.assertEqual(self.request_reset().status_code, 202)
        first_code = self.code_from_latest_email()
        first = PasswordResetChallenge.objects.get(user=self.user)
        first.resend_available_at = timezone.now() - timedelta(seconds=1)
        first.save(update_fields=["resend_available_at"])

        self.assertEqual(self.request_reset(ip="192.0.2.88").status_code, 202)
        second_code = self.code_from_latest_email()
        first.refresh_from_db()
        self.assertEqual(first.status, PasswordResetChallenge.STATUS_SUPERSEDED)
        self.assertEqual(self.verify(self.user.email, first_code).status_code, 400)
        self.assertEqual(self.verify(self.user.email, second_code).status_code, 200)

    def test_code_is_bound_to_the_requested_account(self):
        other = User.objects.create_user(
            username="reset-other",
            email="reset-other@example.test",
            password="OtherPassword123!",
            role="validator",
            must_change_password=False,
        )
        self.assertEqual(self.request_reset().status_code, 202)
        code = self.code_from_latest_email()
        self.assertEqual(self.verify(other.email, code).status_code, 400)
        verified = self.verify(self.user.email, code)
        self.assertEqual(verified.status_code, 200, verified.data)

    def test_locked_challenge_queries_do_not_join_the_nullable_user(self):
        self.assertEqual(self.request_reset().status_code, 202)
        code = self.code_from_latest_email()
        with CaptureQueriesContext(connection) as verify_queries:
            verified = self.verify(self.user.email, code)
        self.assertEqual(verified.status_code, 200, verified.data)

        with CaptureQueriesContext(connection) as complete_queries:
            completed = self.complete(verified.data["reset_token"])
        self.assertEqual(completed.status_code, 200, completed.data)

        for captured in (verify_queries.captured_queries, complete_queries.captured_queries):
            challenge_selects = [
                query["sql"]
                for query in captured
                if query["sql"].lstrip().upper().startswith("SELECT")
                and "projects_passwordresetchallenge" in query["sql"].lower()
            ]
            self.assertTrue(challenge_selects)
            self.assertTrue(all('JOIN "projects_user"' not in sql for sql in challenge_selects))

    def test_password_policy_is_enforced_after_otp_verification(self):
        token = self.issue_verified_token()
        rejected = self.complete(token, password="short")
        self.assertEqual(rejected.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))
        accepted = self.complete(token)
        self.assertEqual(accepted.status_code, 200, accepted.data)

    def test_all_roles_and_inactive_accounts_can_reset_without_activation_change(self):
        accounts = (
            ("active-admin", "admin", True),
            ("inactive-admin", "admin", False),
            ("validator", "validator", True),
            ("contributor", "staff", True),
            ("content-editor", "content_editor", False),
        )
        for index, (label, role, is_active) in enumerate(accounts, start=20):
            user = User.objects.create_user(
                username=f"role-reset-{label}",
                email=f"role-reset-{label}@example.test",
                password="OldPassword123!",
                role=role,
                must_change_password=False,
                is_active=is_active,
                agency="DENR" if role == "staff" else "RDC-NCR",
            )
            response = self.request_reset(user.email, ip=f"192.0.2.{index}")
            self.assertEqual(response.status_code, 202, response.data)
            verified = self.verify(user.email, self.code_from_latest_email())
            self.assertEqual(verified.status_code, 200, verified.data)
            self.assertEqual(self.complete(verified.data["reset_token"]).status_code, 200)
            user.refresh_from_db()
            self.assertTrue(user.check_password("NewPassword123!"))
            self.assertEqual(user.is_active, is_active)

    def test_legacy_approval_and_admin_send_routes_are_unavailable(self):
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(
            self.client.post(f"/api/admin/users/{self.user.id}/reset_password/", {}, format="json").status_code,
            404,
        )
        self.assertEqual(
            self.client.post("/api/password-reset-requests/", {"email": self.user.email}, format="json").status_code,
            404,
        )
        self.assertEqual(PasswordResetRequest.objects.count(), 0)

    def test_delivery_failure_does_not_create_an_approval_request(self):
        with patch("projects.views.send_mail", side_effect=RuntimeError("SMTP unavailable")):
            response = self.request_reset()
        self.assertEqual(response.status_code, 202, response.data)
        challenge = PasswordResetChallenge.objects.get(user=self.user)
        self.assertEqual(challenge.delivery_status, PasswordResetChallenge.DELIVERY_FAILED)
        self.assertEqual(PasswordResetRequest.objects.count(), 0)
        self.assertEqual(PasswordSetupToken.objects.count(), 0)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPassword123!"))

    def test_legacy_unexpired_reset_link_remains_compatible(self):
        token = f"reset_{secrets.token_urlsafe(24)}"
        PasswordSetupToken.objects.create(
            user=self.user,
            token=token,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        prefill = self.client.get(f"/api/auth/setup-password/?token={token}")
        self.assertEqual(prefill.status_code, 200, prefill.data)
        completed = self.client.post(
            "/api/auth/setup-password/",
            {"token": token, "new_password": "LegacyNewPassword123!"},
            format="json",
        )
        self.assertEqual(completed.status_code, 200, completed.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("LegacyNewPassword123!"))
