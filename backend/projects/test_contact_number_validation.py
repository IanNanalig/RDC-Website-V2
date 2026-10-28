import re
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import unquote

from django.utils import timezone
from rest_framework.test import APITestCase

from projects.models import ProfileEditRequest, User


class ContactNumberValidationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="contact-admin", email="contact-admin@example.com",
            password="StrongTestPassword123!", role="admin", is_staff=True,
        )
        self.client.force_authenticate(self.admin)

    def _invite_token(self):
        with patch("projects.views.send_mail") as send_mail:
            response = self.client.post(
                "/api/admin/users/",
                {"email": "contact-invite@example.com", "role": "contributor"},
                format="json",
            )
        self.assertEqual(response.status_code, 202, response.data)
        token_match = re.search(r"token=([^\s]+)", send_mail.call_args.args[1])
        self.assertIsNotNone(token_match)
        return unquote(token_match.group(1))

    @staticmethod
    def _registration_payload(token):
        return {
            "token": token,
            "new_password": "ValidSetup123!",
            "first_name": "Contact",
            "last_name": "Test User",
            "agency": "DENR",
            "office": "Main Office",
            "division": "Planning",
            "position": "Officer",
            "contact_number": "0212345678",
            "phone_number": "09171234567",
        }

    def test_registration_rejects_invalid_numbers_and_stores_valid_digits(self):
        token = self._invite_token()
        self.client.force_authenticate(user=None)
        for field, value in (
            ("contact_number", "0312345678"),
            ("contact_number", "02 1234 5678"),
            ("contact_number", "021234567"),
            ("contact_number", "٠٢١٢٣٤٥٦٧٨"),
            ("phone_number", "08171234567"),
            ("phone_number", "0917 123 4567"),
            ("phone_number", "0917123456"),
            ("phone_number", "٠٩١٧١٢٣٤٥٦٧"),
        ):
            payload = self._registration_payload(token)
            payload[field] = value
            response = self.client.post("/api/auth/setup-password/", payload, format="json")
            self.assertEqual(response.status_code, 400, (field, value, response.data))
            self.assertIn(field, response.data)
        self.assertFalse(User.objects.filter(email="contact-invite@example.com").exists())

        response = self.client.post(
            "/api/auth/setup-password/", self._registration_payload(token), format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        user = User.objects.get(email="contact-invite@example.com")
        self.assertEqual(user.contact_number, "0212345678")
        self.assertEqual(user.phone_number, "09171234567")

    def test_profile_edit_rejects_invalid_numbers_and_stores_valid_digits(self):
        user = User.objects.create_user(
            username="contact-profile", email="contact-profile@example.com",
            password="StrongTestPassword123!", role="staff",
            contact_number="0211111111", phone_number="09111111111",
        )
        ProfileEditRequest.objects.create(
            user=user,
            status=ProfileEditRequest.STATUS_APPROVED,
            reviewed_by=self.admin,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.client.force_authenticate(user)
        for field, value in (
            ("contact_number", "0312345678"),
            ("contact_number", "02 1234 5678"),
            ("contact_number", "٠٢١٢٣٤٥٦٧٨"),
            ("phone_number", "08171234567"),
            ("phone_number", "0917 123 4567"),
            ("phone_number", "0917123456"),
            ("phone_number", "٠٩١٧١٢٣٤٥٦٧"),
        ):
            response = self.client.patch("/api/profile/", {field: value}, format="json")
            self.assertEqual(response.status_code, 400, (field, value, response.data))
            self.assertIn(field, response.data)

        response = self.client.patch(
            "/api/profile/",
            {"contact_number": "0212345678", "phone_number": "09171234567"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertEqual(user.contact_number, "0212345678")
        self.assertEqual(user.phone_number, "09171234567")
