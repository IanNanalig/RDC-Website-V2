import hashlib

from rest_framework.test import APITestCase

from .models import (
    Agency,
    Project,
    ProjectCollaboratingAgency,
    ProjectSupportingDocument,
    User,
    UserActivity,
)
from .views import _sync_project_collaborators, _validate_collaborating_agencies


class MultiAgencyProjectTests(APITestCase):
    def setUp(self):
        self.denr, _ = Agency.objects.get_or_create(
            code="DENR", defaults={"name": "Department of Environment and Natural Resources"}
        )
        self.dpwh, _ = Agency.objects.get_or_create(
            code="DPWH", defaults={"name": "Department of Public Works and Highways"}
        )
        self.doh, _ = Agency.objects.get_or_create(
            code="DOH", defaults={"name": "Department of Health"}
        )
        self.primary_user = User.objects.create_user(
            username="denr-primary",
            email="denr-primary@example.test",
            password="Password123!",
            role="staff",
            agency="DENR",
            must_change_password=False,
        )
        self.collaborator = User.objects.create_user(
            username="dpwh-collaborator",
            email="dpwh-collaborator@example.test",
            password="Password123!",
            role="staff",
            agency="DPWH",
            must_change_password=False,
        )
        self.unrelated = User.objects.create_user(
            username="doh-unrelated",
            email="doh-unrelated@example.test",
            password="Password123!",
            role="staff",
            agency="DOH",
            must_change_password=False,
        )
        self.project = Project.objects.create(
            name="Shared River Rehabilitation",
            implementing_agency="DENR",
            municipality="NCR",
            status="completed",
            cost=1_000_000,
            description="A submitted inter-agency project.",
            latitude=14.59,
            longitude=120.98,
            validated=True,
            created_by=self.primary_user,
            agency="DENR",
            primary_agency=self.denr,
            profile_data={
                "submission_type": "simplified",
                "simplified_form": {
                    "agencyName": "DENR",
                    "projectActivity": "Shared River Rehabilitation",
                    "collaboratingAgencies": ["DPWH"],
                },
            },
        )
        ProjectCollaboratingAgency.objects.create(
            project=self.project,
            agency=self.dpwh,
            added_by=self.primary_user,
        )
        content = b"%PDF-1.4\nproject evidence"
        self.document = ProjectSupportingDocument.objects.create(
            project=self.project,
            original_filename="evidence.pdf",
            content_type="application/pdf",
            extension="pdf",
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            content=content,
            extraction_status=ProjectSupportingDocument.EXTRACTION_READY,
            uploaded_by=self.primary_user,
        )

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    @staticmethod
    def rows(response):
        return response.data.get("results", []) if isinstance(response.data, dict) else response.data

    def test_collaborator_can_list_view_comments_and_download_but_cannot_write(self):
        self.as_user(self.collaborator)
        listing = self.client.get("/api/employee/projects/?view=summary")
        self.assertEqual(listing.status_code, 200, listing.data)
        rows = self.rows(listing)
        self.assertEqual([row["id"] for row in rows], [self.project.id])
        self.assertEqual(rows[0]["access_level"], "collaborator")
        self.assertFalse(rows[0]["can_edit"])
        self.assertIn("read-only", rows[0]["read_only_reason"].lower())

        detail = self.client.get(f"/api/employee/projects/{self.project.id}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data["primary_agency"]["code"], "DENR")
        self.assertEqual(detail.data["collaborating_agencies"][0]["code"], "DPWH")
        self.assertEqual(
            self.client.get(f"/api/employee/projects/{self.project.id}/comments/").status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                f"/api/employee/projects/{self.project.id}/comments/",
                {"comment": "A collaborator must not post this."},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/employee/projects/{self.project.id}/",
                {"description": "Unauthorized edit"},
                format="json",
            ).status_code,
            403,
        )

        documents = self.client.get(f"/api/project-supporting-documents/?project={self.project.id}")
        self.assertEqual(documents.status_code, 200, documents.data)
        self.assertEqual(len(self.rows(documents)), 1)
        download = self.client.get(f"/api/project-supporting-documents/{self.document.id}/download/")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(bytes(download.content), bytes(self.document.content))
        self.assertEqual(
            self.client.delete(f"/api/project-supporting-documents/{self.document.id}/").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(f"/api/project-supporting-documents/{self.document.id}/retry/").status_code,
            403,
        )

    def test_unrelated_contributor_cannot_discover_project(self):
        self.as_user(self.unrelated)
        listing = self.client.get("/api/employee/projects/?view=summary")
        rows = self.rows(listing)
        self.assertEqual(rows, [])
        self.assertEqual(
            self.client.get(f"/api/employee/projects/{self.project.id}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(f"/api/project-supporting-documents/{self.document.id}/download/").status_code,
            404,
        )

    def test_planning_drafts_are_not_visible_to_future_collaborators(self):
        draft = Project.objects.create(
            name="Private Draft",
            implementing_agency="DENR",
            municipality="NCR",
            status="planning",
            cost=100,
            latitude=14.5,
            created_by=self.primary_user,
            agency="DENR",
            primary_agency=self.denr,
            profile_data={
                "submission_type": "simplified",
                "simplified_form": {"agencyName": "DENR", "collaboratingAgencies": ["DPWH"]},
            },
        )
        ProjectCollaboratingAgency.objects.create(project=draft, agency=self.dpwh, added_by=self.primary_user)
        self.as_user(self.collaborator)
        listing = self.client.get("/api/employee/projects/?view=summary")
        rows = self.rows(listing)
        self.assertNotIn(draft.id, [row["id"] for row in rows])
        self.assertEqual(self.client.get(f"/api/employee/projects/{draft.id}/").status_code, 404)

    def test_collaborator_validation_rejects_primary_duplicates_and_inactive_agencies(self):
        duplicate = {
            "simplified_form": {"collaboratingAgencies": ["DPWH", "dpwh"]}
        }
        self.assertIn("only be selected once", _validate_collaborating_agencies(duplicate, self.denr))
        primary = {"simplified_form": {"collaboratingAgencies": ["DENR"]}}
        self.assertIn("primary agency", _validate_collaborating_agencies(primary, self.denr).lower())
        self.doh.is_active = False
        self.doh.save(update_fields=["is_active"])
        inactive = {"simplified_form": {"collaboratingAgencies": ["DOH"]}}
        self.assertIn("unknown or inactive", _validate_collaborating_agencies(inactive, self.denr).lower())

    def test_sync_updates_official_links_idempotently_and_records_audit(self):
        profile = {
            "simplified_form": {
                "agencyName": "DENR",
                "collaboratingAgencies": ["DOH"],
            }
        }
        _sync_project_collaborators(self.project, profile, self.primary_user)
        self.assertEqual(
            list(self.project.collaborating_agencies.values_list("code", flat=True)),
            ["DOH"],
        )
        activity = UserActivity.objects.get(
            event="api_action",
            details__action="project_collaborators_updated",
        )
        self.assertEqual(activity.details["before"], ["DPWH"])
        self.assertEqual(activity.details["after"], ["DOH"])
        _sync_project_collaborators(self.project, profile, self.primary_user)
        self.assertEqual(
            UserActivity.objects.filter(
                event="api_action",
                details__action="project_collaborators_updated",
            ).count(),
            1,
        )
