from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from projects.models import Project, SystemSetting, User


class SimplifiedOnlyProjectApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.contributor = User.objects.create_user(
            username="simplified-only-contributor",
            email="simplified-only@example.test",
            password="test-password",
            role="staff",
            agency="DENR",
        )
        self.client.force_authenticate(self.contributor)
        start_at = timezone.now() - timedelta(hours=1)
        end_at = timezone.now() + timedelta(hours=1)
        SystemSetting.objects.create(
            key="portal_encoding_window",
            value=f'{{"enabled": true, "start_at": "{start_at.isoformat()}", "end_at": "{end_at.isoformat()}"}}',
        )

    def _payload(self, profile):
        return {
            "title": "Test RDIP project",
            "agency": "DENR",
            "budget": 1000,
            "status": "planning",
            "latitude": 14.5,
            "profile_data": profile,
        }

    def test_new_detailed_format_is_rejected(self):
        response = self.client.post(
            "/api/employee/projects/",
            self._payload({"submission_type": "detailed", "projectTitle": "Legacy format"}),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("profile_data", response.data)
        self.assertEqual(Project.objects.count(), 0)

    def test_unmarked_flat_detailed_payload_is_rejected(self):
        response = self.client.post(
            "/api/employee/projects/",
            self._payload({"projectTitle": "Legacy format", "totalProjectCost": "1000"}),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Project.objects.count(), 0)

    def test_simplified_payload_is_saved_with_canonical_type(self):
        response = self.client.post(
            "/api/employee/projects/",
            self._payload({
                "simplified_form": {
                    "agencyName": "DENR",
                    "projectActivity": "Accessible public transport facilities",
                    "startYear": "2026",
                    "endYear": "2026",
                    "fundingRequirementByYear": {"2026": "1000"},
                    "actualFundingByYear": {},
                },
            }),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        project = Project.objects.get(pk=response.data["id"])
        self.assertEqual(project.profile_data["submission_type"], "simplified")
        self.assertEqual(response.data["submission_type"], "simplified")

    def test_detailed_payload_cannot_replace_a_simplified_project(self):
        project = Project.objects.create(
            name="Existing simplified project",
            implementing_agency="DENR",
            municipality="NCR",
            status="planning",
            cost=1000,
            latitude=14.5,
            agency="DENR",
            created_by=self.contributor,
            profile_data={
                "submission_type": "simplified",
                "simplified_form": {"agencyName": "DENR", "projectActivity": "Existing"},
            },
        )
        response = self.client.patch(
            f"/api/employee/projects/{project.id}/",
            {"profile_data": {"submission_type": "detailed", "projectTitle": "Replacement"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        project.refresh_from_db()
        self.assertEqual(project.profile_data["simplified_form"]["projectActivity"], "Existing")

