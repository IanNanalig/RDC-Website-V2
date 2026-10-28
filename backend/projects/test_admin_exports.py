import csv
import io

from django.test import TestCase
from pypdf import PdfReader
from rest_framework.test import APIClient

from .models import Project, ProjectPriorityAnalysis, ProjectPriorityConfirmation, PriorityRuleSet, User, UserActivity


class AdminExportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="export-admin", email="export-admin@example.test", password="Password123!",
            role="admin", first_name="Export", last_name="Admin", agency="RDC-NCR",
        )
        self.validator = User.objects.create_user(
            username="export-validator", email="validator@example.test", password="Password123!",
            role="validator", first_name="Project", last_name="Validator", agency="RDC-NCR",
        )
        self.contributor = User.objects.create_user(
            username="export-contributor", email="contributor@example.test", password="Password123!",
            role="staff", first_name="Juan", last_name="Dela Cruz", agency="DENR",
        )
        self.editor = User.objects.create_user(
            username="export-editor", email="editor@example.test", password="Password123!",
            role="content_editor", first_name="Content", last_name="Editor", agency="RDC-NCR",
        )

    def project(self, title, *, agency="DENR", budget=60_000_000, start="2022", end="2025",
                workflow="planning", implementation="New", archived=False, sector="SCEED",
                convergence="Water Resources Program (WRP)", funding="Agency", chapter="16 Climate"):
        return Project.objects.create(
            name=title,
            implementing_agency=agency,
            municipality="NCR",
            status=workflow,
            cost=budget,
            description=f"Description for {title}",
            latitude=14.5995,
            agency=agency,
            budget=budget,
            year=int(start),
            archived=archived,
            created_by=self.contributor,
            profile_data={
                "submission_type": "simplified",
                "simplified_form": {
                    "agencyName": agency,
                    "program": "Environmental Program",
                    "projectActivity": title,
                    "location": ["Manila", "Pasig"],
                    "description": f"Description for {title}",
                    "objective": "Improve regional outcomes",
                    "fundingRequirementTotal": budget,
                    "startYear": start,
                    "endYear": end,
                    "fundingSource": funding,
                    "status": implementation,
                    "developmentSector": sector,
                    "pcbProgram": convergence,
                    "rdpMainChapter": chapter,
                },
            },
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.admin)

    @staticmethod
    def body(response):
        if getattr(response, "streaming", False):
            return b"".join(response.streaming_content)
        return response.content

    def csv_rows(self, response):
        return list(csv.reader(io.StringIO(self.body(response).decode("utf-8-sig"))))

    def test_export_endpoints_are_administrator_only(self):
        paths = [
            "/api/admin/exports/options/?category=projects",
            "/api/admin/exports/count/?category=projects",
            "/api/admin/exports/download/?category=projects&file_format=csv",
            "/api/admin/exports/download/?category=users&file_format=pdf",
        ]
        for path in paths:
            self.client.force_authenticate(user=None)
            self.assertEqual(self.client.get(path).status_code, 401, path)
            for user in (self.validator, self.contributor, self.editor):
                self.client.force_authenticate(user=user)
                self.assertEqual(self.client.get(path).status_code, 403, f"{path} {user.role}")

    def test_dynamic_options_use_database_values_and_role_definitions(self):
        self.project("Dynamic option project", agency="DENR-NCR", sector="Unique Sector", convergence="Unique PCB")
        self.authenticate()
        projects = self.client.get("/api/admin/exports/options/?category=projects")
        self.assertEqual(projects.status_code, 200)
        options = projects.data["options"]
        self.assertIn({"value": "DENR-NCR", "label": "DENR-NCR"}, options["agencies"])
        self.assertIn({"value": "Unique Sector", "label": "Unique Sector"}, options["development_sectors"])
        self.assertIn({"value": "Unique PCB", "label": "Unique PCB"}, options["convergence_programs"])

        users = self.client.get("/api/admin/exports/options/?category=users")
        self.assertEqual(users.status_code, 200)
        self.assertIn({"value": "validator", "label": "Validator"}, users.data["options"]["roles"])
        self.assertIn({"value": "staff", "label": "Contributor"}, users.data["options"]["roles"])

    def test_project_filters_are_combined_and_not_limited_to_one_page(self):
        matching = [self.project(f"DENR matching {index:02d}") for index in range(12)]
        matching[0].agency = "STALE-NATIVE-AGENCY"
        matching[0].budget = 1
        matching[0].year = 2025
        matching[0].save(update_fields=["agency", "budget", "year"])
        self.project("Budget too low", budget=49_999_999)
        self.project("Wrong agency", agency="DPWH")
        self.project("Wrong year", start="2023")
        self.authenticate()
        query = "category=projects&agency=DENR&budget_min=50000000&start_year=2022"
        count = self.client.get(f"/api/admin/exports/count/?{query}")
        self.assertEqual(count.status_code, 200)
        self.assertEqual(count.data["count"], 12)

        response = self.client.get(f"/api/admin/exports/download/?{query}&file_format=csv")
        self.assertEqual(response.status_code, 200)
        rows = self.csv_rows(response)
        self.assertEqual(len(rows) - 1, 12)
        self.assertEqual({row[0] for row in rows[1:]}, {str(project.pk) for project in matching})
        self.assertTrue(rows[1][19].startswith("'"), "Created is exported as spreadsheet-safe text")
        self.assertTrue(rows[1][19].endswith(" PHT"), "Created identifies the portal timezone")
        self.assertTrue(rows[1][20].startswith("'"), "Updated is exported as spreadsheet-safe text")

    def test_project_status_and_archive_filters_remain_distinct(self):
        revision = self.project("Needs revision", workflow="proposed", implementation="Ongoing")
        revision.profile_data["validator_review"] = {"review_status": "reviewed"}
        revision.save(update_fields=["profile_data"])
        self.project("Validated new", workflow="completed", implementation="New")
        self.project("Archived ongoing", workflow="planning", implementation="Ongoing", archived=True)
        self.authenticate()

        needs_revision = self.client.get(
            "/api/admin/exports/count/?category=projects&workflow_status=needs_revision&implementation_status=Ongoing"
        )
        self.assertEqual(needs_revision.status_code, 200, needs_revision.data)
        self.assertEqual(needs_revision.data["count"], 1)
        self.assertEqual(self.client.get("/api/admin/exports/count/?category=projects").data["count"], 2)
        self.assertEqual(self.client.get(
            "/api/admin/exports/count/?category=projects&archive_state=archived"
        ).data["count"], 1)
        self.assertEqual(self.client.get(
            "/api/admin/exports/count/?category=projects&archive_state=all"
        ).data["count"], 3)

    def test_all_project_filters_and_priority_are_exported(self):
        project = self.project("Complete filter project")
        rules = PriorityRuleSet.objects.create(version="export-v1", is_active=True)
        analysis = ProjectPriorityAnalysis.objects.create(
            project=project, validator=self.validator, rule_set=rules, source_hash="a" * 64,
            suggested_priority="high", base_score=80,
        )
        ProjectPriorityConfirmation.objects.create(
            analysis=analysis, validator=self.validator, final_priority="high",
        )
        self.authenticate()
        query = (
            "category=projects&end_year=2025&development_sector=SCEED"
            "&convergence_program=Water%20Resources%20Program%20%28WRP%29"
            "&funding_source=Agency&rdp_main_chapter=16%20Climate"
        )
        response = self.client.get(f"/api/admin/exports/download/?{query}&file_format=csv")
        self.assertEqual(response.status_code, 200)
        rows = self.csv_rows(response)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][15], "Priority")

    def test_user_role_agency_and_status_filters(self):
        inactive_validator = User.objects.create_user(
            username="inactive-validator", email="inactive@example.test", password="Password123!",
            role="validator", agency="DENR", is_active=False,
        )
        self.authenticate()
        response = self.client.get(
            "/api/admin/exports/download/?category=users&role=validator&agency=DENR&account_status=inactive&file_format=csv"
        )
        self.assertEqual(response.status_code, 200)
        rows = self.csv_rows(response)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], str(inactive_validator.pk))
        self.assertEqual(rows[1][4], "Validator")
        self.assertEqual(rows[1][12], "Inactive")

        contributor_count = self.client.get(
            "/api/admin/exports/count/?category=users&role=contributor"
        )
        self.assertEqual(contributor_count.status_code, 200)
        self.assertEqual(contributor_count.data["count"], 1)

    def test_csv_supports_unicode_escaping_and_formula_injection(self):
        project = self.project('=SUM(1,2), "Lungsod" ñ')
        project.profile_data["simplified_form"]["description"] = "+malicious\nFilipino text: Parañaque"
        project.save(update_fields=["profile_data"])
        self.authenticate()
        response = self.client.get("/api/admin/exports/download/?category=projects&file_format=csv")
        raw = self.body(response)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
        exported = next(row for row in rows[1:] if row[0] == str(project.pk))
        self.assertTrue(exported[1].startswith("'="))
        self.assertTrue(exported[7].startswith("'+"))
        self.assertIn("Parañaque", exported[7])

    def test_user_exports_exclude_credentials_and_session_metadata(self):
        self.validator.last_session_ip = "SECRET-IP-203.0.113.9"
        self.validator.last_session_user_agent = "SECRET-SESSION-AGENT"
        self.validator.session_version = 987654
        self.validator.save(update_fields=["last_session_ip", "last_session_user_agent", "session_version"])
        password_hash = self.validator.password
        self.authenticate()
        response = self.client.get("/api/admin/exports/download/?category=users&file_format=csv")
        data = self.body(response).decode("utf-8-sig")
        self.assertNotIn(password_hash, data)
        self.assertNotIn("SECRET-IP-203.0.113.9", data)
        self.assertNotIn("SECRET-SESSION-AGENT", data)
        self.assertNotIn("session_version", data)

    def test_pdf_is_readable_and_spans_multiple_pages(self):
        for index in range(45):
            self.project(f"PDF Project {index:03d}")
        self.authenticate()
        response = self.client.get("/api/admin/exports/download/?category=projects&file_format=pdf")
        self.assertEqual(response.status_code, 200)
        data = self.body(response)
        self.assertTrue(data.startswith(b"%PDF-"))
        reader = PdfReader(io.BytesIO(data))
        self.assertGreater(len(reader.pages), 1)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("RDC-NCR Projects Export", text)
        self.assertIn("PDF Project 000", text)
        self.assertIn("PDF Project 044", text)

    def test_empty_invalid_and_audited_exports(self):
        self.authenticate()
        empty = self.client.get(
            "/api/admin/exports/download/?category=projects&agency=NoSuchAgency&file_format=csv"
        )
        self.assertEqual(empty.status_code, 400)
        self.assertIn("No records", empty.data["detail"])
        invalid_range = self.client.get(
            "/api/admin/exports/count/?category=projects&budget_min=10&budget_max=5"
        )
        self.assertEqual(invalid_range.status_code, 400)
        invalid_year = self.client.get(
            "/api/admin/exports/count/?category=projects&start_year=1800"
        )
        self.assertEqual(invalid_year.status_code, 400)
        unknown = self.client.get(
            "/api/admin/exports/count/?category=projects&unsafe_filter=value"
        )
        self.assertEqual(unknown.status_code, 400)

        self.project("Audited export")
        success = self.client.get("/api/admin/exports/download/?category=projects&file_format=csv")
        self.assertEqual(success.status_code, 200)
        self.body(success)
        activity = UserActivity.objects.filter(user=self.admin, event="api_action").latest("created_at")
        self.assertEqual(activity.details["action"], "data_export")
        self.assertEqual(activity.details["category"], "projects")
        self.assertEqual(activity.details["format"], "csv")
        self.assertEqual(activity.details["record_count"], 1)
        self.assertNotIn("Audited export", str(activity.details))
