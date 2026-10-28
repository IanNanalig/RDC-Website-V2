import uuid
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from cms.models import CMSSiteSetting
from projects.concern_categories import DEFAULT_CATEGORIES, SETTING_KEY
from projects.models import Project, ProjectConcernEvidence, ProjectConcernReport, User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PROJECT_CONCERN_RECEIVER_EMAIL="concerns@example.test",
    TURNSTILE_REQUIRED=False,
    CELERY_TASK_ALWAYS_EAGER=False,
    PROJECT_CONCERN_RATE_LIMIT_HOURLY=5,
    PROJECT_CONCERN_RATE_LIMIT_DAILY=20,
)
class ProjectConcernAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="concern-admin",
            email="concern-admin@example.test",
            password="Password123!",
            role="admin",
        )
        self.validator = User.objects.create_user(
            username="concern-validator",
            email="concern-validator@example.test",
            password="Password123!",
            role="validator",
        )
        self.project = Project.objects.create(
            name="Public Flood Control Project",
            implementing_agency="DPWH",
            municipality="NCR",
            status="completed",
            cost=50_000_000,
            latitude=14.6,
            longitude=121.0,
            validated=True,
            archived=False,
            is_active=True,
            agency="DPWH",
            budget=50_000_000,
        )
        self.private_project = Project.objects.create(
            name="Planning Draft",
            implementing_agency="DENR",
            municipality="NCR",
            status="planning",
            cost=1,
            latitude=14.6,
            validated=False,
            archived=False,
            is_active=True,
            agency="DENR",
        )
        CMSSiteSetting.objects.update_or_create(
            key=SETTING_KEY,
            defaults={"value_json": {"categories": DEFAULT_CATEGORIES}},
        )

    def payload(self, **overrides):
        values = {
            "submission_id": str(uuid.uuid4()),
            "project_id": str(self.project.id),
            "reporting_mode": "anonymous",
            "category": "delay_discrepancy",
            "description": "The published completion date appears inconsistent with the observed work.",
        }
        values.update(overrides)
        return values

    def test_anonymous_report_is_stored_and_receiver_is_emailed(self):
        response = self.client.post("/api/public/project-concerns/", self.payload(email="ignored@example.test"), format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        report = ProjectConcernReport.objects.get()
        self.assertIsNone(report.reporter_email)
        self.assertEqual(report.project_id_snapshot, self.project.id)
        self.assertTrue(report.reference_code.startswith("PCR-"))
        self.assertEqual(report.receiver_delivery_status, "sent")
        self.assertEqual(report.acknowledgement_delivery_status, "not_applicable")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["concerns@example.test"])
        self.assertEqual(mail.outbox[0].reply_to, [])
        self.assertNotIn("ignored@example.test", mail.outbox[0].body)

    def test_email_enabled_report_sends_receiver_and_acknowledgement(self):
        response = self.client.post(
            "/api/public/project-concerns/",
            self.payload(reporting_mode="email", email="reporter@example.test"),
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        report = ProjectConcernReport.objects.get()
        self.assertEqual(report.reporter_email, "reporter@example.test")
        self.assertEqual(report.acknowledgement_delivery_status, "sent")
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].reply_to, ["reporter@example.test"])
        self.assertEqual(mail.outbox[1].to, ["reporter@example.test"])
        self.assertIn(report.reference_code, mail.outbox[1].body)

    def test_valid_attachment_is_private_and_attached_with_safe_name(self):
        upload = SimpleUploadedFile("photo ü.png", b"\x89PNG\r\n\x1a\nimage", content_type="image/png")
        response = self.client.post(
            "/api/public/project-concerns/",
            self.payload(evidence=upload),
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        evidence = ProjectConcernEvidence.objects.get()
        self.assertEqual(evidence.original_filename, "photo ü.png")
        self.assertNotIn("photo", evidence.storage_name)
        self.assertEqual(mail.outbox[0].attachments[0][0], "Evidence-01.png")
        public_download = self.client.get(
            f"/api/admin/project-concerns/{evidence.report.reference_code}/evidence/{evidence.id}/download/"
        )
        self.assertEqual(public_download.status_code, 401)

    def test_malformed_and_non_public_project_are_rejected(self):
        bad_file = SimpleUploadedFile("fake.pdf", b"not a pdf", content_type="application/pdf")
        bad_upload = self.client.post(
            "/api/public/project-concerns/",
            self.payload(evidence=bad_file),
            format="multipart",
        )
        self.assertEqual(bad_upload.status_code, 400)
        hidden = self.client.post(
            "/api/public/project-concerns/",
            self.payload(project_id=str(self.private_project.id)),
            format="multipart",
        )
        self.assertEqual(hidden.status_code, 400)
        self.assertEqual(ProjectConcernReport.objects.count(), 0)

    def test_submission_identifier_is_idempotent(self):
        submission_id = str(uuid.uuid4())
        first = self.client.post(
            "/api/public/project-concerns/",
            self.payload(submission_id=submission_id),
            format="multipart",
        )
        second = self.client.post(
            "/api/public/project-concerns/",
            self.payload(submission_id=submission_id),
            format="multipart",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.data["reference"], second.data["reference"])
        self.assertEqual(ProjectConcernReport.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(PROJECT_CONCERN_RATE_LIMIT_HOURLY=1, PROJECT_CONCERN_RATE_LIMIT_DAILY=2)
    def test_database_backed_network_rate_limit(self):
        first = self.client.post("/api/public/project-concerns/", self.payload(), format="multipart")
        second = self.client.post("/api/public/project-concerns/", self.payload(), format="multipart")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(ProjectConcernReport.objects.count(), 1)

    @patch("projects.project_concerns.dispatch_project_concern_delivery", return_value=True)
    @patch("projects.concern_delivery.EmailMessage.send", side_effect=RuntimeError("smtp secret detail"))
    def test_email_failure_keeps_report_and_returns_pending(self, _send, dispatch):
        response = self.client.post("/api/public/project-concerns/", self.payload(), format="multipart")
        self.assertEqual(response.status_code, 202, response.data)
        report = ProjectConcernReport.objects.get()
        self.assertEqual(report.receiver_delivery_status, "failed")
        self.assertNotIn("smtp secret detail", report.receiver_last_error)
        self.assertNotIn("smtp secret detail", str(response.data))
        dispatch.assert_called_once_with(report.id)

    def test_admin_only_list_detail_retry_and_download(self):
        upload = SimpleUploadedFile("proof.csv", b"item,value\nstatus,delayed\n", content_type="text/csv")
        created = self.client.post(
            "/api/public/project-concerns/",
            self.payload(evidence=upload),
            format="multipart",
        )
        report = ProjectConcernReport.objects.get()
        evidence = report.evidence_files.get()

        self.client.force_authenticate(self.validator)
        self.assertEqual(self.client.get("/api/admin/project-concerns/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/api/admin/project-concerns/{report.reference_code}/").status_code,
            403,
        )

        self.client.force_authenticate(self.admin)
        listing = self.client.get("/api/admin/project-concerns/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 1)
        detail = self.client.get(f"/api/admin/project-concerns/{report.reference_code}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["description"], report.description)
        download = self.client.get(
            f"/api/admin/project-concerns/{report.reference_code}/evidence/{evidence.id}/download/"
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        retry = self.client.post(f"/api/admin/project-concerns/{report.reference_code}/retry/", {}, format="json")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(ProjectConcernReport.objects.count(), 1)

    def test_options_only_return_active_categories_and_policy(self):
        setting = CMSSiteSetting.objects.get(key=SETTING_KEY)
        setting.value_json = {
            "categories": [
                {"code": "active", "label": "Active category", "active": True},
                {"code": "inactive", "label": "Inactive category", "active": False},
            ]
        }
        setting.save(update_fields=["value_json"])
        response = self.client.get("/api/public/project-concerns/options/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["categories"], [{"code": "active", "label": "Active category"}])
        self.assertEqual(response.data["upload_policy"]["max_files"], 5)
        self.assertFalse(response.data["upload_policy"]["malware_scanned"])

    def test_used_category_may_be_deactivated_but_not_removed(self):
        created = self.client.post("/api/public/project-concerns/", self.payload(), format="multipart")
        self.assertEqual(created.status_code, 201)
        setting = CMSSiteSetting.objects.get(key=SETTING_KEY)
        self.client.force_authenticate(self.admin)

        removed = [item for item in DEFAULT_CATEGORIES if item["code"] != "delay_discrepancy"]
        rejected = self.client.patch(
            f"/api/admin/cms/settings/{SETTING_KEY}/",
            {"value_json": {"categories": removed}},
            format="json",
        )
        self.assertEqual(rejected.status_code, 400, rejected.data)

        deactivated = [
            {**item, "active": False} if item["code"] == "delay_discrepancy" else item
            for item in DEFAULT_CATEGORIES
        ]
        accepted = self.client.patch(
            f"/api/admin/cms/settings/{SETTING_KEY}/",
            {"value_json": {"categories": deactivated}},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200, accepted.data)
        setting.refresh_from_db()
        self.assertFalse(
            next(item for item in setting.value_json["categories"] if item["code"] == "delay_discrepancy")["active"]
        )
