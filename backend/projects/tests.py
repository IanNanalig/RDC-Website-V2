import json
from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import (
    Notification,
    PriorityRuleSet,
    Project,
    ProjectPriorityAnalysis,
    ProjectRevision,
    SystemSetting,
    User,
    UserActivity,
)


class PortalWorkflowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin_t", password="password", role="admin", email="admin_t@example.com"
        )
        self.validator = User.objects.create_user(
            username="validator_t", password="password", role="validator", email="validator_t@example.com"
        )
        # Employee-equivalent role in current schema.
        self.employee = User.objects.create_user(
            username="employee_t", password="password", role="staff", email="employee_t@example.com"
        )
        # Ensure test users can log in immediately (clear must_change_password flag)
        for u in (self.admin, self.validator, self.employee):
            u.must_change_password = False
            u.save(update_fields=["must_change_password"]) 
        self._set_encoding_window(timezone.now() - timedelta(hours=1), timezone.now() + timedelta(hours=1))

    def _as(self, user):
        self.client.force_authenticate(user=user)

    def _set_encoding_window(self, start_at, end_at, enabled=True):
        SystemSetting.objects.update_or_create(
            key="portal_encoding_window",
            defaults={
                "value": (
                    '{"enabled": false, "start_at": "", "end_at": ""}'
                    if not enabled
                    else f'{{"enabled": true, "start_at": "{start_at.isoformat()}", "end_at": "{end_at.isoformat()}"}}'
                )
            },
        )

    def _set_progress_window(self, start_at, end_at):
        SystemSetting.objects.update_or_create(
            key="portal_progress_update_window",
            defaults={
                "value": (
                    f'{{"enabled": true, "start_at": "{start_at.isoformat()}", '
                    f'"end_at": "{end_at.isoformat()}"}}'
                )
            },
        )

    def test_employee_to_validator_to_admin_flow(self):
        self._as(self.employee)
        create_res = self.client.post(
            "/api/employee/projects/",
            {
                "title": "Workflow Project",
                "agency": "MMDA",
                "budget": 100000,
                "completion": 0,
                "status": "draft",
                "description": "Integration flow",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        project_id = create_res.data["id"]
        # The general workflow test uses the supported exemption path; priority scoring has its own flow.
        project = Project.objects.get(id=project_id)
        project.priority_analysis_eligible = False
        project.save(update_fields=["priority_analysis_eligible"])

        submit_res = self.client.post(f"/api/employee/projects/{project_id}/submit/", {}, format="json")
        self.assertEqual(submit_res.status_code, status.HTTP_200_OK)

        self._as(self.validator)
        validator_list = self.client.get("/api/validator/projects/")
        self.assertEqual(validator_list.status_code, status.HTTP_200_OK)
        self.assertTrue(any(p["id"] == project_id for p in validator_list.data))

        approve_res = self.client.post(
            f"/api/validator/projects/{project_id}/validate/",
            {"action": "endorse"},
            format="json",
        )
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)

        self._as(self.admin)
        admin_list = self.client.get("/api/admin/projects/")
        self.assertEqual(admin_list.status_code, status.HTTP_200_OK)
        self.assertTrue(any(p["id"] == project_id for p in admin_list.data))

        dashboard = self.client.get("/api/dashboard/")
        self.assertEqual(dashboard.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(dashboard.data.get("approved_projects", 0), 1)

    def test_general_project_create_notifies_for_contributor_draft_or_direct_submission(self):
        self._as(self.employee)
        draft = self.client.post(
            "/api/projects/",
            {"title": "General API Draft", "agency": "MMDA", "budget": 1, "status": "draft"},
            format="json",
        )
        submitted = self.client.post(
            "/api/projects/",
            {"title": "General API Submitted", "agency": "MMDA", "budget": 1, "status": "proposed"},
            format="json",
        )
        self.assertEqual(draft.status_code, status.HTTP_201_CREATED)
        self.assertEqual(submitted.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Notification.objects.filter(
            project_id=draft.data["id"], recipient=self.admin,
            event_type="contributor_project_draft_created",
        ).count(), 1)
        self.assertEqual(Notification.objects.filter(
            project_id=submitted.data["id"], recipient=self.validator,
            event_type="project_submitted",
        ).count(), 1)

    def test_submit_creates_employee_and_validator_notifications_once(self):
        self._as(self.employee)
        create_res = self.client.post(
            "/api/employee/projects/",
            {
                "title": "Notify Submit",
                "agency": "MMDA",
                "budget": 100000,
                "completion": 0,
                "status": "draft",
                "description": "notification flow",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        project_id = create_res.data["id"]

        self.assertEqual(
            Notification.objects.filter(
                project_id=project_id, recipient=self.admin, event_type="contributor_project_draft_created"
            ).count(),
            1,
        )

        first = self.client.post(f"/api/employee/projects/{project_id}/submit/", {}, format="json")
        second = self.client.post(f"/api/employee/projects/{project_id}/submit/", {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)

        project = Project.objects.get(id=project_id)
        self.assertEqual(
            Notification.objects.filter(project=project, recipient=self.employee, event_type="project_submit_confirmation").count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(project=project, recipient=self.validator, event_type="project_submitted").count(),
            1,
        )

    def test_project_notification_links_use_the_saved_form_type(self):
        from .views import _project_link

        project = Project.objects.create(
            name="Form Type Notification Project",
            implementing_agency="MMDA",
            municipality="NCR",
            status="proposed",
            cost=0,
            latitude=14.5,
            agency="MMDA",
            created_by=self.employee,
            profile_data={"simplified_form": {"projectActivity": "Form Type Notification Project"}},
        )
        self.assertEqual(
            _project_link(project, self.validator),
            f"/validator/projects/{project.id}/review/simplified",
        )
        self.assertEqual(
            _project_link(project, self.admin),
            f"/admin/projects/{project.id}/view/simplified",
        )
        legacy_notification = Notification.objects.create(
            recipient=self.validator,
            project=project,
            event_type="legacy_form_link",
            title="Legacy review link",
            link_path=f"/validator/projects/{project.id}/review",
        )
        self._as(self.validator)
        notifications = self.client.get("/api/notifications/?limit=10")
        self.assertEqual(notifications.status_code, status.HTTP_200_OK)
        self.assertEqual(
            next(item for item in notifications.data if item["id"] == legacy_notification.id)["submission_type"],
            "simplified",
        )
        project.profile_data = {"submission_type": "detailed"}
        self.assertEqual(
            _project_link(project, self.validator),
            f"/validator/projects/{project.id}/review",
        )

    def test_validator_draft_and_validation_create_notifications(self):
        other_admin = User.objects.create_user(
            username="notification_admin_2", password="password", role="admin",
            email="notification_admin_2@example.com",
        )
        inactive_admin = User.objects.create_user(
            username="notification_admin_inactive", password="password", role="admin",
            email="notification_admin_inactive@example.com", is_active=False,
        )
        project = Project.objects.create(
            name="Validator Notification Project",
            implementing_agency="MMDA",
            municipality="NCR",
            status="proposed",
            cost=100000,
            latitude=14.5,
            agency="MMDA",
            budget=100000,
            created_by=self.employee,
            priority_analysis_eligible=False,
        )

        self._as(self.validator)
        draft = self.client.post(
            f"/api/validator/projects/{project.id}/validate/",
            {"action": "save_draft", "edited_profile_data": {}},
            format="json",
        )
        self.assertEqual(draft.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(
                project=project,
                recipient=self.validator,
                event_type="validator_review_draft_saved",
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                project=project, recipient=self.admin, event_type="validator_review_draft_saved_admin"
            ).count(),
            1,
        )
        self.assertEqual(Notification.objects.filter(
            project=project, recipient=other_admin, event_type="validator_review_draft_saved_admin"
        ).count(), 1)
        self.assertFalse(Notification.objects.filter(
            project=project, recipient=inactive_admin, event_type="validator_review_draft_saved_admin"
        ).exists())

        validated = self.client.post(
            f"/api/validator/projects/{project.id}/validate/",
            {"action": "validate", "edited_profile_data": {}},
            format="json",
        )
        self.assertEqual(validated.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(
                project=project,
                recipient=self.validator,
                event_type="validator_project_validated",
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(project=project, recipient=self.admin, event_type="project_endorsed_admin").count(),
            1,
        )
        self.assertEqual(Notification.objects.filter(
            project=project, recipient=other_admin, event_type="project_endorsed_admin"
        ).count(), 1)
        self.assertFalse(Notification.objects.filter(
            project=project, recipient=inactive_admin, event_type="project_endorsed_admin"
        ).exists())
        self.assertEqual(
            Notification.objects.filter(project=project, recipient=self.employee, event_type="project_validated").count(),
            1,
        )

    def test_validator_progress_draft_and_validation_create_notifications(self):
        profile = {
            "simplified_form": {
                "projectActivity": "Validator Progress Notification",
                "startYear": "2026",
                "endYear": "2027",
            }
        }
        project = Project.objects.create(
            name="Validator Progress Notification",
            implementing_agency="MMDA",
            municipality="NCR",
            status="ongoing",
            validated=True,
            cost=100000,
            latitude=14.5,
            agency="MMDA",
            budget=100000,
            created_by=self.employee,
            profile_data=profile,
        )
        ProjectRevision.objects.create(
            project=project,
            revision_number=1,
            revision_type="initial_submission",
            state="endorsed",
            profile_data_snapshot=profile,
            is_public_current=True,
            created_by=self.employee,
            submitted_by=self.employee,
            reviewed_by=self.validator,
            endorsed_by=self.validator,
        )
        progress = ProjectRevision.objects.create(
            project=project,
            revision_number=2,
            revision_type="progress_update",
            state="submitted",
            profile_data_snapshot=profile,
            created_by=self.employee,
            submitted_by=self.employee,
        )

        self._as(self.validator)
        draft = self.client.post(
            f"/api/project-revisions/{progress.id}/review/",
            {"action": "save_draft", "edited_profile_data": profile},
            format="json",
        )
        self.assertEqual(draft.status_code, status.HTTP_200_OK)
        draft_notification = Notification.objects.get(
            project=project,
            recipient=self.validator,
            event_type="validator_progress_draft_saved",
        )
        self.assertEqual(
            draft_notification.link_path,
            f"/validator/projects/{project.id}/review/simplified?revision={progress.id}",
        )
        self.assertEqual(
            Notification.objects.filter(
                project=project, recipient=self.admin, event_type="validator_progress_draft_saved_admin"
            ).count(),
            1,
        )

        validated = self.client.post(
            f"/api/project-revisions/{progress.id}/review/",
            {"action": "validate", "edited_profile_data": profile},
            format="json",
        )
        self.assertEqual(validated.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(
                project=project,
                recipient=self.validator,
                event_type="validator_progress_validated",
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                project=project, recipient=self.admin, event_type="progress_update_endorsed_admin"
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(
                project=project, recipient=self.employee, event_type="progress_update_validated"
            ).count(),
            1,
        )

    def test_progress_revision_request_notifies_only_the_submitting_contributor(self):
        other_contributor = User.objects.create_user(
            username="other_mmda_contributor", password="password", role="staff",
            email="other_mmda_contributor@example.com", agency="MMDA",
        )
        project = Project.objects.create(
            name="Progress Request Notifications",
            implementing_agency="MMDA",
            municipality="NCR",
            status="ongoing",
            validated=True,
            cost=100000,
            latitude=14.5,
            agency="MMDA",
            budget=100000,
            created_by=self.employee,
            profile_data={
                "simplified_form": {
                    "projectActivity": "Progress Request", "startYear": "2026", "endYear": "2027"
                }
            },
        )
        revision = ProjectRevision.objects.create(
            project=project,
            revision_number=2,
            revision_type="progress_update",
            state="submitted",
            profile_data_snapshot=project.profile_data,
            created_by=self.employee,
            submitted_by=self.employee,
        )
        self._as(self.validator)
        requested = self.client.post(
            f"/api/project-revisions/{revision.id}/review/",
            {"action": "save_reviewed", "notes": "Please verify the accomplishment figures."},
            format="json",
        )
        self.assertEqual(requested.status_code, status.HTTP_200_OK, requested.data)
        notification = Notification.objects.get(
            project=project, recipient=self.employee, event_type="progress_update_needs_revision"
        )
        self.assertEqual(notification.message, "Please verify the accomplishment figures.")
        self.assertFalse(Notification.objects.filter(
            project=project, recipient=other_contributor, event_type="progress_update_needs_revision"
        ).exists())

    def test_contributor_progress_draft_and_submission_notify_admin_and_validators(self):
        self._set_progress_window(timezone.now() - timedelta(hours=1), timezone.now() + timedelta(hours=1))
        self.employee.agency = "MMDA"
        self.employee.save(update_fields=["agency"])
        other_validator = User.objects.create_user(
            username="validator_progress_2", password="password", role="validator",
            email="validator_progress_2@example.com",
        )
        inactive_validator = User.objects.create_user(
            username="validator_progress_inactive", password="password", role="validator",
            email="validator_progress_inactive@example.com", is_active=False,
        )
        project = Project.objects.create(
            name="Contributor Progress Notifications",
            implementing_agency="MMDA",
            municipality="NCR",
            status="ongoing",
            validated=True,
            cost=100000,
            latitude=14.5,
            agency="MMDA",
            budget=100000,
            created_by=self.employee,
            profile_data={"simplified_form": {"projectActivity": "Progress Notifications"}},
        )
        self._as(self.employee)
        started = self.client.post(f"/api/employee/projects/{project.id}/start-update/", {}, format="json")
        self.assertEqual(started.status_code, status.HTTP_201_CREATED)
        revision_id = started.data["id"]
        self.assertEqual(
            Notification.objects.filter(
                project=project, recipient=self.admin, event_type="contributor_progress_draft_created"
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.get(
                project=project, recipient=self.admin, event_type="contributor_progress_draft_created"
            ).link_path,
            f"/admin/projects/{project.id}/view/simplified?revision={revision_id}",
        )
        reopened = self.client.post(f"/api/employee/projects/{project.id}/start-update/", {}, format="json")
        self.assertEqual(reopened.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(project=project, event_type="contributor_progress_draft_created").count(),
            1,
        )
        submitted = self.client.post(f"/api/project-revisions/{revision_id}/submit/", {}, format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        for validator in (self.validator, other_validator):
            notification = Notification.objects.get(
                project=project, recipient=validator, event_type="progress_update_submitted"
            )
            self.assertEqual(
                notification.link_path,
                f"/validator/projects/{project.id}/review/simplified?revision={revision_id}",
            )
        self.assertFalse(
            Notification.objects.filter(
                project=project, recipient=inactive_validator, event_type="progress_update_submitted"
            ).exists()
        )

    def test_needs_revision_requires_comment_unlocks_edit_and_notifies(self):
        self._as(self.employee)
        create_res = self.client.post(
            "/api/employee/projects/",
            {"title": "Revision Project", "agency": "MMDA", "budget": 1, "status": "draft"},
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        project_id = create_res.data["id"]
        project = Project.objects.get(id=project_id)
        project.priority_analysis_eligible = False
        project.save(update_fields=["priority_analysis_eligible"])
        self.assertEqual(self.client.post(f"/api/employee/projects/{project_id}/submit/", {}, format="json").status_code, 200)

        self._as(self.validator)
        missing_comment = self.client.post(
            f"/api/validator/projects/{project_id}/validate/",
            {"action": "save_reviewed"},
            format="json",
        )
        self.assertEqual(missing_comment.status_code, status.HTTP_400_BAD_REQUEST)
        needs_revision = self.client.post(
            f"/api/validator/projects/{project_id}/validate/",
            {"action": "save_reviewed", "notes": "Please attach the project proposal."},
            format="json",
        )
        self.assertEqual(needs_revision.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(project_id=project_id, recipient=self.employee, event_type="project_needs_revision").count(),
            1,
        )

        repeated_request = self.client.post(
            f"/api/validator/projects/{project_id}/validate/",
            {"action": "save_reviewed", "notes": "Please also confirm the proposal details."},
            format="json",
        )
        self.assertEqual(repeated_request.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(project_id=project_id, recipient=self.employee, event_type="project_needs_revision").count(),
            2,
        )

        self._set_encoding_window(timezone.now(), timezone.now(), enabled=False)
        self._as(self.employee)
        update_res = self.client.put(
            f"/api/employee/projects/{project_id}/",
            {
                "title": "Revision Project Updated",
                "agency": "MMDA",
                "budget": 2,
                "status": "draft",
                "profile_data": {"revision_note": "Proposal attached."},
            },
            format="json",
        )
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        resubmit = self.client.post(f"/api/employee/projects/{project_id}/submit/", {}, format="json")
        self.assertEqual(resubmit.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(project_id=project_id, recipient=self.validator, event_type="project_revision_resubmitted").count(),
            1,
        )
        refreshed = Project.objects.get(id=project_id)
        self.assertEqual(refreshed.status, "proposed")
        self.assertEqual(refreshed.profile_data.get("validator_review", {}).get("review_status"), "draft")

    def test_notification_list_and_mark_read_are_scoped_to_recipient(self):
        project = Project.objects.create(
            name="Scoped Notification",
            implementing_agency="MMDA",
            municipality="NCR",
            status="proposed",
            cost=1,
            latitude=14.5,
            agency="MMDA",
            budget=1,
            created_by=self.employee,
        )
        mine = Notification.objects.create(
            recipient=self.employee,
            actor=self.validator,
            project=project,
            event_type="project_message",
            title="Mine",
            message="Visible",
        )
        Notification.objects.create(
            recipient=self.validator,
            actor=self.employee,
            project=project,
            event_type="project_message",
            title="Theirs",
            message="Hidden",
        )

        self._as(self.employee)
        list_res = self.client.get("/api/notifications/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["id"], mine.id)
        meta_res = self.client.get("/api/notifications/?include_meta=1")
        self.assertEqual(meta_res.status_code, status.HTTP_200_OK)
        self.assertEqual(meta_res.data["unread_count"], 1)
        self.assertEqual(meta_res.data["results"][0]["id"], mine.id)
        count_res = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(count_res.data["unread_count"], 1)
        mark_res = self.client.post(f"/api/notifications/{mine.id}/mark-read/", {}, format="json")
        self.assertEqual(mark_res.status_code, status.HTTP_200_OK)
        self.assertTrue(mark_res.data["is_read"])
        self.assertEqual(self.client.get("/api/notifications/unread-count/").data["unread_count"], 0)

    def test_priority_confirmation_notifies_from_official_decision(self):
        project = Project.objects.create(
            name="Priority Official",
            implementing_agency="MMDA",
            municipality="NCR",
            status="proposed",
            cost=1,
            latitude=14.5,
            agency="MMDA",
            budget=1,
            created_by=self.employee,
            profile_data={"simplified_form": {"startYear": "2026", "endYear": "2026"}},
        )
        rules = PriorityRuleSet.objects.create(version="test-rules", is_active=True)
        analysis = ProjectPriorityAnalysis.objects.create(
            project=project,
            validator=self.validator,
            rule_set=rules,
            source_hash="abc",
            input_snapshot={},
            suggested_scores={"missing_facts": []},
            suggested_priority="low",
            base_score=10,
        )

        self._as(self.validator)
        confirm = self.client.post(
            f"/api/validator/projects/{project.id}/priority-analysis/{analysis.id}/confirm/",
            {"final_priority": "high", "override_rationale": "Official validator decision."},
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Notification.objects.filter(project=project, recipient=self.employee, event_type="classification_priority").count(),
            1,
        )
        filtered = self.client.get("/api/validator/projects/?workflow=priority")
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["id"] == project.id for item in filtered.data))

    def test_validator_can_run_priority_analysis_for_detailed_form(self):
        detailed_profile = {
            "submission_type": "detailed",
            "projectTitle": "Metro Manila Circular Waste Facilities",
            "programOrProject": "Project",
            "description": "Regional solid waste recovery, recycling, and climate mitigation facilities.",
            "objective": "Reduce landfill waste and improve environmental resilience.",
            "mainPdpChapter": "Chapter 15 Accelerate Climate Action and Strengthen Disaster Resilience",
            "mainInfrastructureSector": "Social Infrastructure",
            "mainInfrastructureSubsector": "Solid Waste Management",
            "costLocalities": "Manila, Quezon City, Pasig, Marikina",
            "spatialCoverageByImpact": "Region-wide NCR environmental benefits",
            "physicalFinancialStatus": "Proposed project",
            "totalProjectCost": "480,000,000",
        }
        project = Project.objects.create(
            name=detailed_profile["projectTitle"],
            implementing_agency="DENR",
            municipality="NCR",
            status="proposed",
            cost=480000000,
            latitude=14.5,
            agency="DENR",
            budget=480000000,
            created_by=self.employee,
            profile_data=detailed_profile,
        )

        self._as(self.validator)
        response = self.client.post(
            f"/api/validator/projects/{project.id}/priority-analysis/run/",
            {
                "edited_profile_data": detailed_profile,
                "supplements": {
                    "readinessLevel": "ongoing_documents",
                    "gadResponsiveness": "gender_sensitive",
                    "spatialCoverageScope": "region_wide",
                    "sceeedTrack": "environment",
                    "beneficiaryCount": "2500000",
                    "regionalSpatialCategory": "region_wide",
                    "contributedOutcomeCount": "2",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        analysis = response.data["analysis"]
        self.assertEqual(analysis["suggested_scores"]["missing_facts"], [])
        self.assertEqual(analysis["suggested_scores"]["rdp_track"], "environment")
        self.assertTrue(analysis["regional_scorecard"]["applicable"])
        stored_analysis = ProjectPriorityAnalysis.objects.get(pk=analysis["id"])
        self.assertEqual(stored_analysis.input_snapshot["submission_type"], "detailed")

    def test_role_access_restrictions(self):
        # Employee cannot access admin and validator list endpoints.
        self._as(self.employee)
        self.assertEqual(self.client.get("/api/admin/projects/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/validator/projects/").status_code, status.HTTP_403_FORBIDDEN)

        # Validator cannot access admin users endpoint.
        self._as(self.validator)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_archive_project(self):
        project = Project.objects.create(
            name="Archive Candidate",
            implementing_agency="MMDA",
            municipality="NCR",
            status="proposed",
            cost=5000,
            description="to archive",
            latitude=14.5,
            agency="MMDA",
            budget=5000,
            completion=10,
            created_by=self.employee,
        )

        self._as(self.admin)
        res = self.client.post(f"/api/admin/projects/{project.id}/archive/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertTrue(project.archived)
        self.assertFalse(project.is_active)

    def test_employee_write_blocked_when_encoding_closed(self):
        self._set_encoding_window(timezone.now(), timezone.now(), enabled=False)

        self._as(self.employee)
        create_res = self.client.post(
            "/api/employee/projects/",
            {
                "title": "Blocked Project",
                "agency": "MMDA",
                "budget": 100000,
                "completion": 0,
                "status": "draft",
                "description": "should fail",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_encoding_window(self):
        self._as(self.admin)
        start_at = timezone.now() - timedelta(minutes=5)
        end_at = timezone.now() + timedelta(hours=2)
        res = self.client.post(
            "/api/encoding-window/",
            {"enabled": True, "start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        get_res = self.client.get("/api/encoding-window/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertTrue(get_res.data.get("is_open"))
        self.assertEqual(get_res.data.get("status_code"), "scheduled_open")
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="encoding_window_updated").exists())

    def test_encoding_window_is_closed_when_not_configured(self):
        SystemSetting.objects.filter(key="portal_encoding_window").delete()
        self._as(self.employee)
        state = self.client.get("/api/encoding-window/")
        self.assertEqual(state.status_code, status.HTTP_200_OK)
        self.assertFalse(state.data.get("is_open"))
        self.assertFalse(state.data.get("can_encode"))
        self.assertEqual(state.data.get("status_code"), "schedule_not_configured")
        create_res = self.client.post(
            "/api/employee/projects/",
            {"title": "Blocked Until Scheduled", "agency": "MMDA", "budget": 1, "status": "draft"},
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_save_incomplete_encoding_schedule(self):
        self._as(self.admin)
        res = self.client.post(
            "/api/encoding-window/",
            {"enabled": True, "start_at": "", "end_at": ""},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_encoding_window_reports_upcoming_and_ended_states(self):
        self._as(self.employee)
        self._set_encoding_window(timezone.now() + timedelta(hours=1), timezone.now() + timedelta(hours=2))
        upcoming = self.client.get("/api/encoding-window/")
        self.assertFalse(upcoming.data.get("can_encode"))
        self.assertEqual(upcoming.data.get("status_code"), "scheduled_not_started")

        self._set_encoding_window(timezone.now() - timedelta(hours=2), timezone.now() - timedelta(hours=1))
        ended = self.client.get("/api/encoding-window/")
        self.assertFalse(ended.data.get("can_encode"))
        self.assertEqual(ended.data.get("status_code"), "scheduled_ended")

    def test_comments_remain_available_when_encoding_closed(self):
        self.employee.agency = "MMDA"
        self.employee.save(update_fields=["agency"])
        project = Project.objects.create(
            name="Comment While Closed",
            implementing_agency="MMDA",
            municipality="NCR",
            status="planning",
            cost=1,
            latitude=14.5,
            agency="MMDA",
            budget=1,
            created_by=self.employee,
        )
        self._set_encoding_window(timezone.now(), timezone.now(), enabled=False)
        self._as(self.employee)
        self.assertEqual(
            self.client.get(f"/api/employee/projects/{project.id}/comments/").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(
                f"/api/employee/projects/{project.id}/comments/",
                {"comment": "Collaboration remains available."},
                format="json",
            ).status_code,
            status.HTTP_201_CREATED,
        )

    def test_employee_cannot_edit_after_submit(self):
        self._as(self.employee)
        create_res = self.client.post(
            "/api/employee/projects/",
            {
                "title": "Lock After Submit",
                "agency": "MMDA",
                "budget": 50000,
                "completion": 0,
                "status": "draft",
                "description": "before submit",
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        project_id = create_res.data["id"]
        self.assertEqual(
            self.client.post(f"/api/employee/projects/{project_id}/submit/", {}, format="json").status_code,
            status.HTTP_200_OK,
        )
        update_res = self.client.put(
            f"/api/employee/projects/{project_id}/",
            {"title": "Edited after submit", "agency": "MMDA", "budget": 50000},
            format="json",
        )
        self.assertEqual(update_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_admin_can_delete_project(self):
        project = Project.objects.create(
            name="Delete Candidate",
            implementing_agency="MMDA",
            municipality="NCR",
            status="planning",
            cost=1000,
            description="candidate",
            latitude=14.5,
            agency="MMDA",
            budget=1000,
            completion=0,
            created_by=self.employee,
        )

        self._as(self.employee)
        self.assertEqual(
            self.client.delete(f"/api/employee/projects/{project.id}/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self._as(self.validator)
        self.assertEqual(
            self.client.delete(f"/api/validator/projects/{project.id}/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self._as(self.admin)
        self.assertEqual(
            self.client.delete(f"/api/admin/projects/{project.id}/").status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_real_login_endpoint_works_for_db_users(self):
        res = self.client.post(
            "/api/auth/login/",
            {"email": "employee_t@example.com", "password": "password"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["user"]["role"], "employee")
        self.assertTrue("access" in res.data)

    def test_admin_can_view_activity_feed(self):
        self._as(self.employee)
        create_res = self.client.post(
            "/api/employee/projects/",
            {"title": "Activity Project", "agency": "MMDA", "budget": 1, "status": "draft"},
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserActivity.objects.filter(user=self.employee, event="project_create").exists())

        self._as(self.admin)
        feed_res = self.client.get("/api/admin/activity/?limit=10")
        self.assertEqual(feed_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(feed_res.data), 1)

    def test_employee_can_save_rich_profile_data_json(self):
        self._as(self.employee)
        payload = {
            "title": "Profile Data Project",
            "agency": "MMDA",
            "budget": 150000,
            "completion": 0,
            "status": "draft",
            "profile_data": {
                "projectTitle": "Profile Data Project",
                "programOrProject": "Project",
                "mainPdpChapter": "Chapter 12 Expand and Upgrade Infrastructure",
                "mainPdpOutcome": "Sustainable, resilient, integrated, and modernized infrastructure facilities and services delivered",
                "projectCostRows": [
                    {
                        "source": "NG",
                        "y2022Prior": "0",
                        "y2023": "1000",
                        "y2024": "2000",
                        "y2025": "3000",
                        "y2026": "4000",
                        "y2027": "5000",
                        "y2028": "6000",
                        "y2029": "7000",
                        "continuingYears": "8000",
                        "overall": "36000",
                    }
                ],
                "pipBudgetRows": [{"year": "2025", "osbps": "100", "nep": "90", "gaa": "80"}],
                "provincialRows": [{"province": "NCR", "y2025": "5000", "overall": "5000"}],
                "projectReadinessItems": ["Feasibility Study"],
                "otherInfrastructureSectors": ["Transportation - Roads and Bridges"],
            },
        }
        create_res = self.client.post("/api/employee/projects/", payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        project_id = create_res.data["id"]
        project = Project.objects.get(id=project_id)
        self.assertIsInstance(project.profile_data, dict)
        self.assertEqual(project.profile_data.get("projectTitle"), "Profile Data Project")
        self.assertEqual(len(project.profile_data.get("projectCostRows", [])), 1)

    def test_employee_can_list_own_detailed_draft_when_office_differs_from_account_agency(self):
        self.employee.agency = "DENR"
        self.employee.save(update_fields=["agency"])
        self._as(self.employee)
        create_res = self.client.post(
            "/api/employee/projects/",
            {
                "title": "DENR Detailed Draft",
                "agency": "DENR-NCR Environmental Management and Solid Waste Management Unit",
                "budget": 480000000,
                "completion": 0,
                "status": "draft",
                "profile_data": {
                    "submission_type": "detailed",
                    "projectTitle": "DENR Detailed Draft",
                    "officeUnit": "DENR-NCR Environmental Management and Solid Waste Management Unit",
                },
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)

        project_id = create_res.data["id"]
        list_res = self.client.get("/api/employee/projects/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertIn(project_id, [project["id"] for project in list_res.data])
        self.assertEqual(
            self.client.get(f"/api/employee/projects/{project_id}/").status_code,
            status.HTTP_200_OK,
        )

    def test_employee_profile_data_must_be_json_object(self):
        self._as(self.employee)
        payload = {
            "title": "Invalid Profile Data",
            "agency": "MMDA",
            "budget": 1000,
            "status": "draft",
            "profile_data": ["invalid", "shape"],
        }
        create_res = self.client.post("/api/employee/projects/", payload, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profile_data", create_res.data)


class PerformanceApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="performance-admin", password="password", role="admin", email="performance@example.com"
        )

    def _project(self, index=1, validated=False):
        return Project.objects.create(
            name=f"Performance Project {index}",
            description="A complete narrative that belongs only in detail responses.",
            implementing_agency="MMDA",
            municipality="NCR",
            status="completed" if validated else "planning",
            cost=1000,
            latitude=14.5,
            longitude=121.0,
            agency="MMDA",
            budget=1000,
            validated=validated,
            created_by=self.admin,
            profile_data={
                "submission_type": "simplified",
                "simplified_form": {"status": "Ongoing", "location": "Manila"},
                "validator_review": {"review_status": "endorsed", "reviewed_by_username": "validator"},
            },
        )

    def test_project_and_revision_summary_views_omit_large_snapshots(self):
        project = self._project()
        revision = ProjectRevision.objects.create(
            project=project,
            revision_number=1,
            revision_type="progress_update",
            state="draft",
            created_by=self.admin,
            profile_data_snapshot={"submission_type": "simplified", "large": "x" * 5000},
        )
        self.client.force_authenticate(user=self.admin)

        summary = self.client.get("/api/admin/projects/?view=summary")
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertNotIn("profile_data", summary.data[0])
        self.assertEqual(summary.data[0]["submission_type"], "simplified")
        self.assertLess(len(json.dumps(summary.data[0], default=str).encode("utf-8")), 2048)
        detail = self.client.get(f"/api/admin/projects/{project.pk}/")
        self.assertIn("profile_data", detail.data)

        revision_summary = self.client.get("/api/project-revisions/?view=summary")
        row = next(item for item in revision_summary.data if item["id"] == revision.pk)
        self.assertNotIn("profile_data_snapshot", row)
        revision_detail = self.client.get(f"/api/project-revisions/{revision.pk}/")
        self.assertIn("profile_data_snapshot", revision_detail.data)

    def test_project_summary_query_count_stays_bounded(self):
        self.client.force_authenticate(user=self.admin)
        for index in range(2):
            self._project(index)
        with CaptureQueriesContext(connection) as small_context:
            response = self.client.get("/api/admin/projects/?view=summary")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        for index in range(2, 12):
            self._project(index)
        with CaptureQueriesContext(connection) as large_context:
            response = self.client.get("/api/admin/projects/?view=summary")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertLessEqual(len(large_context), len(small_context) + 1)

    def test_public_summary_is_lightweight_and_etag_changes_after_update(self):
        project = self._project(validated=True)
        first = self.client.get("/api/public/projects/?view=summary")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertNotIn("description", first.data[0])
        self.assertNotIn("public_update_timeline", first.data[0])
        self.assertLess(len(json.dumps(first.data[0], default=str).encode("utf-8")), 2048)
        etag = first["ETag"]

        unchanged = self.client.get("/api/public/projects/?view=summary", HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(unchanged.status_code, status.HTTP_304_NOT_MODIFIED)

        project.budget = 2000
        project.save(update_fields=["budget", "updated_at"])
        changed = self.client.get("/api/public/projects/?view=summary", HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.assertNotEqual(changed["ETag"], etag)
        detail = self.client.get(f"/api/public/projects/{project.pk}/")
        self.assertIn("description", detail.data)
        self.assertIn("public_update_timeline", detail.data)
