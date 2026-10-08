from unittest.mock import patch
from datetime import datetime, timezone

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from .models import Project, User, UserActivity
from .views import _manila_funding_year, _validate_contributor_simplified_write


class ContributorFundingRuleTests(SimpleTestCase):
    def test_manila_new_year_boundary(self):
        with patch("projects.views.timezone.now", return_value=datetime(2026, 12, 31, 15, 59, tzinfo=timezone.utc)):
            self.assertEqual(_manila_funding_year(), 2026)
        with patch("projects.views.timezone.now", return_value=datetime(2026, 12, 31, 16, 1, tzinfo=timezone.utc)):
            self.assertEqual(_manila_funding_year(), 2027)

    def test_past_years_stay_editable_after_manila_year_rollover(self):
        user = User(role="staff", agency="DENR")
        existing = {
            "simplified_form": {
                "agencyName": "DENR",
                "actualFundingByYear": {"2025": "10", "2026": "20", "2027": "30"},
            }
        }
        incoming = {
            "simplified_form": {
                "agencyName": "DENR",
                "actualFundingByYear": {"2025": "11", "2026": "20", "2027": "30"},
            }
        }
        project = Project(agency="DENR")
        with patch("projects.views._manila_funding_year", return_value=2026):
            self.assertIsNone(_validate_contributor_simplified_write(
                user, incoming, project=project, existing_profile=existing, incoming_agency="DENR"
            ))
        with patch("projects.views._manila_funding_year", return_value=2027):
            self.assertIsNone(_validate_contributor_simplified_write(
                user, incoming, project=project, existing_profile=existing, incoming_agency="DENR"
            ))

        future = {"simplified_form": {"agencyName": "DENR", "actualFundingByYear": {
            "2025": "10", "2026": "20", "2027": "31",
        }}}
        with patch("projects.views._manila_funding_year", return_value=2026):
            self.assertIn("2027 is read-only", _validate_contributor_simplified_write(
                user, future, project=project, existing_profile=existing, incoming_agency="DENR"
            ))
        with patch("projects.views._manila_funding_year", return_value=2027):
            self.assertIsNone(_validate_contributor_simplified_write(
                user, future, project=project, existing_profile=existing, incoming_agency="DENR"
            ))

        prior = {"simplified_form": {"agencyName": "DENR", "actualFundingByYear": {"2022_prior": "10"}}}
        changed_prior = {"simplified_form": {"agencyName": "DENR", "actualFundingByYear": {"2022_prior": "11"}}}
        with patch("projects.views._manila_funding_year", return_value=2026):
            self.assertIsNone(_validate_contributor_simplified_write(
                user, changed_prior, project=project, existing_profile=prior, incoming_agency="DENR"
            ))


class ContributorFundingDashboardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="contributor-rules", email="contributor-rules@example.com",
            password="TestPassword123!", role="staff", agency="DENR",
        )
        self.other = User.objects.create_user(
            username="another-contributor", email="another-contributor@example.com",
            password="TestPassword123!", role="staff", agency="DENR",
        )
        self.client.force_authenticate(user=self.user)

    def profile(self, agency="DENR", actual=None):
        return {"simplified_form": {
            "agencyName": agency,
            "startYear": "2024",
            "endYear": "2027",
            "actualFundingByYear": actual or {},
            "fundingRequirementByYear": {},
        }}

    def project(self, agency, owner, status="planning", actual=None):
        return Project.objects.create(
            name="Funding Test Project", implementing_agency=agency, municipality="NCR",
            status=status, cost=0, latitude=14.5, agency=agency, created_by=owner,
            profile_data=self.profile(agency, actual),
        )

    @patch("projects.views._resolve_encoding_window_state", return_value={"is_open": True, "message": ""})
    @patch("projects.views._manila_funding_year", return_value=2026)
    def test_new_project_requires_account_agency_and_rejects_future_actual_years(self, _year, _window):
        payload = {"title": "New Project", "agency": "DENR", "profile_data": self.profile(
            actual={"2024": "5", "2025": "10", "2026": "20"},
        )}
        created = self.client.post("/api/employee/projects/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        project = Project.objects.get(pk=created.data["id"])
        self.assertEqual(project.agency, "DENR")
        self.assertEqual(project.profile_data["simplified_form"]["actualFundingByYear"]["2024"], "5")
        self.assertEqual(project.profile_data["simplified_form"]["actualFundingByYear"]["2025"], "10")

        prior = self.profile(actual={"2022_prior": "15"})
        prior["simplified_form"]["startYear"] = "2022"
        prior_response = self.client.post("/api/employee/projects/", {
            "title": "Past Funding", "agency": "DENR", "profile_data": prior,
        }, format="json")
        self.assertEqual(prior_response.status_code, 201, prior_response.data)

        invalid = self.profile(actual={"2027": "5"})
        response = self.client.post("/api/employee/projects/", {
            "title": "Invalid Funding", "agency": "DENR", "profile_data": invalid,
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("2027 is read-only", response.data["detail"])

        wrong_agency = self.client.post("/api/employee/projects/", {
            "title": "Wrong Agency", "agency": "DPWH", "profile_data": self.profile("DPWH"),
        }, format="json")
        self.assertEqual(wrong_agency.status_code, 400)
        self.assertIn("account agency", wrong_agency.data["detail"])

        self.user.agency = ""
        self.user.save(update_fields=["agency"])
        missing = self.client.post("/api/employee/projects/", payload, format="json")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("account has no agency", missing.data["detail"])

    @patch("projects.views._resolve_encoding_window_state", return_value={"is_open": True, "message": ""})
    @patch("projects.views._manila_funding_year", return_value=2026)
    def test_existing_protected_amounts_and_agency_are_preserved(self, _year, _window):
        actual = {"2024": "100", "2025": "200", "2026": "300", "2027": "400"}
        project = self.project("DPWH", self.user, actual=actual)
        payload = {"title": "Funding Test Project", "agency": "DPWH", "profile_data": self.profile("DPWH", actual)}

        allowed = self.profile("DPWH", {**actual, "2024": "150", "2025": "250"})
        response = self.client.put(f"/api/employee/projects/{project.id}/", {
            **payload, "profile_data": allowed,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        project.refresh_from_db()
        self.assertEqual(project.agency, "DPWH")
        self.assertEqual(project.profile_data["simplified_form"]["actualFundingByYear"]["2024"], "150")

        for changed in ({**actual, "2027": "401"}, {k: v for k, v in actual.items() if k != "2027"}):
            with self.subTest(changed=changed):
                denied = self.client.put(f"/api/employee/projects/{project.id}/", {
                    **payload, "profile_data": self.profile("DPWH", changed),
                }, format="json")
                self.assertEqual(denied.status_code, 400)
                self.assertIn("read-only", denied.data["detail"])

        for modified in (
            {**payload, "agency": "DENR"},
            {**payload, "profile_data": self.profile("DENR", actual)},
        ):
            with self.subTest(modified=modified):
                denied = self.client.put(f"/api/employee/projects/{project.id}/", modified, format="json")
                self.assertEqual(denied.status_code, 400)
                self.assertIn("locked", denied.data["detail"])

        removed_form = self.client.patch(f"/api/employee/projects/{project.id}/", {
            "profile_data": {},
        }, format="json")
        self.assertEqual(removed_form.status_code, 400)
        self.assertIn("cannot be removed", removed_form.data["detail"])

        shifted_period = self.profile("DPWH", actual)
        shifted_period["simplified_form"]["startYear"] = "2025"
        kept_historical = self.client.patch(f"/api/employee/projects/{project.id}/", {
            "profile_data": shifted_period,
        }, format="json")
        self.assertEqual(kept_historical.status_code, 400)
        self.assertIn("out-of-range key", str(kept_historical.data))
        project.refresh_from_db()
        self.assertEqual(project.profile_data["simplified_form"]["actualFundingByYear"]["2024"], "150")

    def test_dashboard_and_activity_match_project_list_scope(self):
        owned_other_agency = self.project("DPWH", self.user, status="planning")
        same_agency = self.project("DENR", self.other, status="proposed")
        owned_same_agency = self.project("DENR", self.user, status="completed")
        excluded = self.project("DPWH", self.other, status="planning")
        for project in (owned_other_agency, same_agency, owned_same_agency, excluded):
            UserActivity.objects.create(user=self.user, event="project_create", project=project)

        listed = self.client.get("/api/employee/projects/")
        self.assertEqual(listed.status_code, 200)
        listed_ids = {item["id"] for item in (listed.data.get("results", []) if isinstance(listed.data, dict) else listed.data)}
        self.assertEqual(listed_ids, {owned_other_agency.id, same_agency.id, owned_same_agency.id})

        dashboard = self.client.get("/api/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["my_projects"], 3)
        self.assertEqual(dashboard.data["draft_projects"], 1)
        self.assertEqual(dashboard.data["submitted_projects"], 1)
        self.assertEqual(dashboard.data["approved_projects"], 1)
        self.assertEqual(dashboard["Cache-Control"], "private, no-store")

        activity = self.client.get("/api/agency/activity/?include_meta=true")
        self.assertEqual(activity.status_code, 200)
        self.assertEqual(activity.data["count"], 3)
        self.assertEqual({item["project"] for item in activity.data["results"]}, listed_ids)
        self.assertEqual(activity["Cache-Control"], "private, no-store")

    @patch("projects.views._manila_funding_year", return_value=2026)
    def test_general_project_endpoint_cannot_bypass_contributor_locks(self, _year):
        project = self.project("DENR", self.user, actual={"2024": "100", "2026": "300", "2027": "400"})
        changed_funding = self.client.patch(f"/api/projects/{project.id}/", {
            "profile_data": self.profile(actual={"2024": "100", "2026": "300", "2027": "401"}),
        }, format="json")
        self.assertEqual(changed_funding.status_code, 400)
        self.assertIn("read-only", changed_funding.data["detail"])

        changed_agency = self.client.patch(f"/api/projects/{project.id}/", {
            "agency": "DPWH",
        }, format="json")
        self.assertEqual(changed_agency.status_code, 400)
        self.assertIn("locked", changed_agency.data["detail"])

        created = self.client.post("/api/projects/", {
            "title": "Wrong Agency", "agency": "DPWH", "profile_data": self.profile("DPWH"),
        }, format="json")
        self.assertEqual(created.status_code, 400)
        self.assertIn("account agency", created.data["detail"])
