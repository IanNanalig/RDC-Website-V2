from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import PasswordSetupToken, User, UserActivity


class AccountSetupAgencyTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="agency-admin",
            email="agency-admin@example.com",
            password="StrongTestPassword123!",
            role="admin",
            must_change_password=False,
        )
        self.client.force_authenticate(user=self.admin)

    def make_pending_user(self, suffix):
        user = User(
            username=f"pending-{suffix}",
            email=f"pending-{suffix}@example.com",
            role="staff",
            must_change_password=True,
        )
        user.set_unusable_password()
        user.save()
        token = PasswordSetupToken.objects.create(
            user=user,
            token=f"agency-setup-token-{suffix}",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        return user, token

    @staticmethod
    def setup_payload(token, agency):
        return {
            "token": token.token,
            "new_password": "ValidSetup123_",
            "full_name": "Agency User",
            "agency": agency,
            "agency_head": "Agency Head",
            "office": "Main Office",
            "division": "Planning",
            "position": "Officer",
            "contact_number": "09170000000",
            "phone_number": "09170000000",
        }

    @patch("projects.views._send_setup_email")
    def test_admin_creates_each_role_without_selecting_an_agency(self, send_setup_email):
        roles = ("contributor", "validator", "content_editor", "admin")

        for role in roles:
            email = f"new-{role}@example.com"
            response = self.client.post(
                "/api/admin/users/",
                {"email": email, "role": role},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            user = User.objects.get(email=email)
            self.assertEqual(user.role, "staff" if role == "contributor" else role)
            self.assertEqual(user.agency, "")

        self.assertEqual(send_setup_email.call_count, len(roles))

    def test_setup_accepts_and_normalizes_each_approved_agency(self):
        self.client.force_authenticate(user=None)
        agencies = (
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
        )
        entries = tuple(
            entry
            for code, full_name in agencies
            for entry in ((code.lower(), code), (full_name, code))
        )

        for index, (submitted, expected) in enumerate(entries):
            user, token = self.make_pending_user(str(index))
            response = self.client.post(
                "/api/auth/setup-password/",
                self.setup_payload(token, submitted),
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            user.refresh_from_db()
            self.assertEqual(user.agency, expected)
            self.assertFalse(user.must_change_password)
            activity = UserActivity.objects.get(user=user, event="auth_password_setup")
            self.assertEqual(activity.details["agency"], expected)

    def test_setup_rejects_missing_blank_and_unsupported_agencies(self):
        self.client.force_authenticate(user=None)
        entries = (("missing", None), ("blank", "   "), ("unsupported", "MMDA"))

        for suffix, agency in entries:
            user, token = self.make_pending_user(suffix)
            payload = self.setup_payload(token, agency)
            if agency is None:
                payload.pop("agency")
            response = self.client.post("/api/auth/setup-password/", payload, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            if agency == "MMDA":
                self.assertEqual(
                    response.data["detail"],
                    "This is an invalid Agency",
                )
            else:
                self.assertIn("agency", response.data["detail"])
            user.refresh_from_db()
            token.refresh_from_db()
            self.assertEqual(user.agency, "")
            self.assertTrue(user.must_change_password)
            self.assertIsNone(token.used_at)

    @patch("projects.views._send_setup_email")
    def test_duplicate_email_behavior_is_unchanged(self, send_setup_email):
        User.objects.create_user(
            username="existing-agency-user",
            email="existing-agency@example.com",
            password="StrongTestPassword123!",
            role="staff",
            agency="DPWH",
        )

        response = self.client.post(
            "/api/admin/users/",
            {"email": "EXISTING-AGENCY@example.com", "role": "staff"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Email already exists.")
        send_setup_email.assert_not_called()
