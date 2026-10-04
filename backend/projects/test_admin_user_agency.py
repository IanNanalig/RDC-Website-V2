from datetime import timedelta
import string
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AccessRequest, PasswordSetupToken, User, UserActivity


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

    def make_pending_user(self, suffix, *, role="staff", agency=""):
        user = User(
            username=f"pending-{suffix}",
            email=f"pending-{suffix}@example.com",
            role=role,
            agency=agency,
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
    def test_admin_creates_each_role_with_its_required_agency(self, send_setup_email):
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
            self.assertEqual(user.agency, "" if role == "contributor" else "RDC-NCR")

        self.assertEqual(send_setup_email.call_count, len(roles))

    @patch("projects.views._send_setup_email")
    def test_admin_rejects_conflicting_agency_for_internal_roles(self, send_setup_email):
        for role in ("admin", "validator", "content_editor", "content-editor"):
            email = f"conflicting-{role}@example.com"
            response = self.client.post(
                "/api/admin/users/",
                {"email": email, "role": role, "agency": "DENR"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
            self.assertIn("RDC-NCR", response.data["detail"])
            self.assertFalse(User.objects.filter(email=email).exists())
        send_setup_email.assert_not_called()

    @patch("projects.views._send_setup_email")
    def test_admin_accepts_canonical_or_full_name_rdc_agency(self, send_setup_email):
        for index, agency in enumerate(("rdc-ncr", "Regional Development Council National Capital Region")):
            response = self.client.post(
                "/api/admin/users/",
                {"email": f"rdc-{index}@example.com", "role": "validator", "agency": agency},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
            self.assertEqual(User.objects.get(email=f"rdc-{index}@example.com").agency, "RDC-NCR")
        self.assertEqual(send_setup_email.call_count, 2)

    @patch("projects.views._send_setup_email")
    def test_access_request_approval_assigns_rdc_to_validator(self, send_setup_email):
        access_request = AccessRequest.objects.create(
            full_name="New Validator",
            email="requested-validator@example.com",
            office_unit="RDC Office",
            requested_role="validator",
            justification="Validation work",
        )
        response = self.client.post(f"/api/access-requests/{access_request.id}/approve/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(User.objects.get(email=access_request.email).agency, "RDC-NCR")
        send_setup_email.assert_called_once()

    def test_internal_setup_uses_saved_agency_and_rejects_tampering(self):
        self.client.force_authenticate(user=None)
        for role in ("admin", "validator", "content_editor"):
            user, token = self.make_pending_user(f"locked-{role}", role=role, agency="RDC-NCR")
            prefill = self.client.get(f"/api/auth/setup-password/?token={token.token}")
            self.assertEqual(prefill.status_code, status.HTTP_200_OK, prefill.data)
            self.assertTrue(prefill.data["agency_locked"])
            self.assertEqual(prefill.data["profile"]["agency"], "RDC-NCR")

            changed = self.client.post(
                "/api/auth/setup-password/", self.setup_payload(token, "DENR"), format="json"
            )
            self.assertEqual(changed.status_code, status.HTTP_400_BAD_REQUEST, changed.data)
            user.refresh_from_db()
            token.refresh_from_db()
            self.assertEqual(user.agency, "RDC-NCR")
            self.assertTrue(user.must_change_password)
            self.assertIsNone(token.used_at)

            completed = self.client.post(
                "/api/auth/setup-password/", self.setup_payload(token, "RDC-NCR"), format="json"
            )
            self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
            user.refresh_from_db()
            self.assertEqual(user.agency, "RDC-NCR")
            self.assertFalse(user.must_change_password)

    def test_internal_password_reset_preserves_legacy_agency_even_when_blank(self):
        self.client.force_authenticate(user=None)
        for suffix, saved_agency in (("legacy-denr", "DENR"), ("legacy-blank", "")):
            user, token = self.make_pending_user(suffix, role="admin", agency=saved_agency)
            prefill = self.client.get(f"/api/auth/setup-password/?token={token.token}")
            self.assertTrue(prefill.data["agency_locked"])
            self.assertEqual(prefill.data["profile"]["agency"], saved_agency)

            changed = self.client.post(
                "/api/auth/setup-password/", self.setup_payload(token, "RDC-NCR"), format="json"
            )
            if saved_agency != "RDC-NCR":
                self.assertEqual(changed.status_code, status.HTTP_400_BAD_REQUEST, changed.data)

            payload = self.setup_payload(token, saved_agency)
            if not saved_agency:
                payload.pop("agency")
            completed = self.client.post("/api/auth/setup-password/", payload, format="json")
            self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
            user.refresh_from_db()
            self.assertEqual(user.agency, saved_agency)

    def test_contributor_setup_agency_stays_editable(self):
        self.client.force_authenticate(user=None)
        user, token = self.make_pending_user("editable-contributor")
        prefill = self.client.get(f"/api/auth/setup-password/?token={token.token}")
        self.assertFalse(prefill.data["agency_locked"])
        completed = self.client.post(
            "/api/auth/setup-password/", self.setup_payload(token, "DENR"), format="json"
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK, completed.data)
        user.refresh_from_db()
        self.assertEqual(user.agency, "DENR")

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

    def test_setup_accepts_keyboard_symbols_and_rejects_non_symbols(self):
        self.client.force_authenticate(user=None)
        for index, symbol in enumerate(string.punctuation):
            with self.subTest(symbol=symbol):
                user, token = self.make_pending_user(f"symbol-{index}")
                password = f"ValidSetup123{symbol}"
                payload = self.setup_payload(token, "DPWH")
                payload["new_password"] = password

                response = self.client.post("/api/auth/setup-password/", payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                user.refresh_from_db()
                self.assertTrue(user.check_password(password))

        for suffix, password in (
            ("letter-only", "WordPassword123"),
            ("space-only", "ValidSetup123 "),
        ):
            with self.subTest(password_type=suffix):
                user, token = self.make_pending_user(suffix)
                payload = self.setup_payload(token, "DPWH")
                payload["new_password"] = password

                response = self.client.post("/api/auth/setup-password/", payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data["detail"], "Password must include a symbol.")
                user.refresh_from_db()
                self.assertTrue(user.must_change_password)

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
