from django.test import TestCase


class SmokeTests(TestCase):
    def test_admin_login_page_available(self):
        """Ensure the Django admin login page renders (basic smoke test)."""
        resp = self.client.get('/admin/')
        # Admin login should return 200 with login form
        self.assertEqual(resp.status_code, 200)
