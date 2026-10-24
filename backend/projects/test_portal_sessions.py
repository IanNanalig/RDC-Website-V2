from datetime import timedelta
import hashlib

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import PortalSession, User


class PortalSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="session-user",
            email="session@example.com",
            password="ValidPassword123!",
            role="staff",
            is_active=True,
            must_change_password=False,
        )
        self.other_user = User.objects.create_user(
            username="other-session-user",
            email="other-session@example.com",
            password="ValidPassword123!",
            role="validator",
            is_active=True,
            must_change_password=False,
        )
        self.client = APIClient()

    def login(self, user=None, remember_me=False, browser_refresh=None):
        user = user or self.user
        payload = {
            "email": user.email,
            "password": "ValidPassword123!",
            "remember_me": remember_me,
        }
        if browser_refresh:
            payload["browser_refresh"] = browser_refresh
        return self.client.post("/api/auth/login/", payload, format="json")

    def authorize(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_login_creates_hashed_browser_session_and_refreshes_access(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        session = PortalSession.objects.get(user=self.user)
        self.assertFalse(session.remember_me)
        self.assertNotEqual(session.refresh_token_digest, response.data["refresh"])
        self.assertEqual(
            session.refresh_token_digest,
            hashlib.sha256(response.data["refresh"].encode("utf-8")).hexdigest(),
        )

        refreshed = self.client.post(
            "/api/token/refresh/", {"refresh": response.data["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertEqual(refreshed.data["refresh"], response.data["refresh"])
        self.assertIn("access", refreshed.data)

    def test_remembered_session_does_not_expire_from_idle(self):
        response = self.login(remember_me=True)
        session = PortalSession.objects.get(user=self.user)
        session.last_activity_at = timezone.now() - timedelta(days=45)
        session.save(update_fields=["last_activity_at"])

        self.authorize(response.data["access"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_200_OK)
        refreshed = self.client.post(
            "/api/token/refresh/", {"refresh": response.data["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)

    def test_idle_session_expires_at_twelve_hours_and_cannot_refresh(self):
        response = self.login()
        session = PortalSession.objects.get(user=self.user)
        session.last_activity_at = timezone.now() - timedelta(hours=12)
        session.save(update_fields=["last_activity_at"])

        self.authorize(response.data["access"])
        protected = self.client.get("/api/auth/me/")
        self.assertEqual(protected.status_code, status.HTTP_401_UNAUTHORIZED)
        refreshed = self.client.post(
            "/api/token/refresh/", {"refresh": response.data["refresh"]}, format="json"
        )
        self.assertEqual(refreshed.status_code, status.HTTP_401_UNAUTHORIZED)
        session.refresh_from_db()
        self.assertIsNotNone(session.revoked_at)

    def test_authenticated_activity_updates_idle_timestamp(self):
        response = self.login()
        session = PortalSession.objects.get(user=self.user)
        previous = timezone.now() - timedelta(minutes=2)
        PortalSession.objects.filter(pk=session.pk).update(last_activity_at=previous)

        self.authorize(response.data["access"])
        activity = self.client.post("/api/auth/activity/", {}, format="json")
        self.assertEqual(activity.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertGreater(session.last_activity_at, previous)

    def test_recent_user_action_header_updates_session_on_api_request(self):
        response = self.login()
        session = PortalSession.objects.get(user=self.user)
        previous = timezone.now() - timedelta(minutes=2)
        PortalSession.objects.filter(pk=session.pk).update(last_activity_at=previous)

        self.authorize(response.data["access"])
        result = self.client.get("/api/auth/me/", HTTP_X_PORTAL_USER_ACTIVITY="1")
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertGreater(session.last_activity_at, previous)

    def test_background_authenticated_request_does_not_reset_idle_timer(self):
        response = self.login()
        session = PortalSession.objects.get(user=self.user)
        previous = timezone.now() - timedelta(minutes=2)
        PortalSession.objects.filter(pk=session.pk).update(last_activity_at=previous)

        self.authorize(response.data["access"])
        result = self.client.get("/api/auth/me/")
        self.assertEqual(result.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.last_activity_at, previous)

    def test_new_device_login_revokes_previous_access_and_refresh(self):
        first = self.login()
        second = self.login()
        self.assertEqual(second.status_code, status.HTTP_200_OK)

        self.authorize(first.data["access"])
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)
        old_refresh = self.client.post(
            "/api/token/refresh/", {"refresh": first.data["refresh"]}, format="json"
        )
        self.assertEqual(old_refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_different_account_login_cannot_replace_active_browser_account(self):
        first = self.login()
        attempt = self.login(user=self.other_user, browser_refresh=first.data["refresh"])
        self.assertEqual(attempt.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(attempt.data["active_session"])
        self.assertEqual(attempt.data["user"]["email"], self.user.email)
        self.assertFalse(PortalSession.objects.filter(user=self.other_user).exists())

    def test_logout_revokes_remembered_refresh_credential(self):
        response = self.login(remember_me=True)
        self.authorize(response.data["access"])
        self.assertEqual(self.client.post("/api/auth/logout/", {}, format="json").status_code, status.HTTP_200_OK)

        refresh = self.client.post(
            "/api/token/refresh/", {"refresh": response.data["refresh"]}, format="json"
        )
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)
