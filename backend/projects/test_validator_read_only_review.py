from copy import deepcopy

from django.test import override_settings
from rest_framework.test import APITestCase

from .models import PriorityRuleSet, Project, ProjectPriorityAnalysis, ProjectPriorityConfirmation, ProjectRevision, ProjectSupportingDocument, User
from .priority_scoring import confirmation_eligibility, get_active_priority_rule_set


class ValidatorReadOnlyReviewTests(APITestCase):
    def setUp(self):
        self.validator = User.objects.create_user(
            username="read-only-validator", password="TestPassword123!", role="validator",
            email="read-only-validator@example.com",
        )
        self.contributor = User.objects.create_user(
            username="read-only-contributor", password="TestPassword123!", role="staff",
            email="read-only-contributor@example.com", agency="DENR",
        )
        self.profile = {
            "submission_type": "simplified",
            "form_schema": {"key": "simplified-rdip", "version": 1, "legacy": True},
            "simplified_form": {
                "agencyName": "DENR", "projectActivity": "Estero cleanup",
                "description": "Contributor's original description",
                "startYear": "2026", "endYear": "2026",
                "fundingRequirementByYear": {"2026": "100"},
            },
        }
        self.project = Project.objects.create(
            name="Estero cleanup", implementing_agency="DENR", municipality="NCR",
            status="proposed", cost=100, latitude=14.5, agency="DENR", budget=100,
            created_by=self.contributor, profile_data=deepcopy(self.profile),
        )
        self.client.force_authenticate(user=self.validator)

    def modified_profile(self):
        profile = deepcopy(self.profile)
        profile["simplified_form"]["description"] = "Validator changed this answer"
        return profile

    def test_admin_validator_tracker_uses_current_reviewer_name(self):
        self.validator.first_name = "Ray Gabriel"
        self.validator.last_name = "Paras"
        self.validator.save(update_fields=["first_name", "last_name"])
        self.project.profile_data = {
            **self.profile,
            "validator_review": {
                "review_status": "validated",
                "reviewed_by_id": self.validator.id,
                "reviewed_by_username": "old.email.name",
            },
        }
        self.project.save(update_fields=["profile_data"])
        admin = User.objects.create_user(
            username="tracker-admin", password="TestPassword123!", role="admin",
            email="tracker-admin@example.com",
        )
        self.client.force_authenticate(user=admin)
        response = self.client.get("/api/admin/projects/")
        self.assertEqual(response.status_code, 200, response.data)
        item = next(row for row in response.data if row["id"] == self.project.id)
        self.assertEqual(item["reviewed_by_name"], "Ray Gabriel Paras")
        self.assertEqual(item["profile_data"]["validator_review"]["reviewed_by_username"], "old.email.name")

    def test_confirmation_eligibility_reports_missing_stale_and_ready_states(self):
        rules = get_active_priority_rule_set()
        snapshot = deepcopy(self.profile)
        self.assertEqual(confirmation_eligibility(self.project, snapshot)["code"], "analysis_missing")
        analysis = ProjectPriorityAnalysis.objects.create(
            project=self.project, validator=self.validator, rule_set=rules,
            source_hash="a" * 64, input_snapshot=snapshot,
            suggested_scores={"missing_facts": []}, suggested_priority="low", base_score=30,
        )
        self.assertEqual(confirmation_eligibility(self.project, snapshot)["code"], "priority_unconfirmed")
        ProjectPriorityConfirmation.objects.create(analysis=analysis, validator=self.validator, final_priority="low")
        ready = confirmation_eligibility(self.project, snapshot)
        self.assertTrue(ready["eligible"])
        self.assertEqual(ready["analysis_id"], analysis.id)
        self.assertEqual(confirmation_eligibility(self.project, self.modified_profile())["code"], "analysis_project_outdated")
        rules.is_active = False
        rules.save(update_fields=["is_active"])
        PriorityRuleSet.objects.create(version="next-rule-version", is_active=True)
        self.assertEqual(confirmation_eligibility(self.project, snapshot)["code"], "analysis_rule_outdated")

    def test_reviewed_project_documents_remain_readable_to_its_validator(self):
        document = ProjectSupportingDocument.objects.create(
            project=self.project, original_filename="evidence.pdf", content_type="application/pdf",
            extension="pdf", size_bytes=8, checksum_sha256="a" * 64,
            content=b"%PDF-1.4", uploaded_by=self.contributor,
        )
        self.project.status = "completed"
        self.project.validated = True
        self.project.workflow_status = "validated"
        self.project.profile_data = {
            **self.profile,
            "validator_review": {"review_status": "validated", "reviewed_by_id": self.validator.id},
        }
        self.project.save(update_fields=["status", "validated", "workflow_status", "profile_data"])

        listing = self.client.get(f"/api/project-supporting-documents/?project={self.project.id}")
        self.assertEqual(listing.status_code, 200, listing.data)
        self.assertEqual([row["id"] for row in listing.data], [document.id])
        download = self.client.get(f"/api/project-supporting-documents/{document.id}/download/")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, b"%PDF-1.4")
        assessment = self.client.get(f"/api/project-supporting-documents/assessment-status/?project={self.project.id}")
        self.assertEqual(assessment.status_code, 200, assessment.data)
        self.assertEqual(self.client.delete(f"/api/project-supporting-documents/{document.id}/").status_code, 403)

        other_validator = User.objects.create_user(
            username="other-history-validator", password="TestPassword123!", role="validator",
            email="other-history-validator@example.com",
        )
        self.client.force_authenticate(user=other_validator)
        self.assertEqual(self.client.get(f"/api/project-supporting-documents/?project={self.project.id}").data, [])
        self.assertEqual(self.client.get(f"/api/project-supporting-documents/{document.id}/download/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/project-supporting-documents/assessment-status/?project={self.project.id}").status_code, 403)

    def test_contributor_drafts_are_hidden_from_all_validator_project_scopes(self):
        draft = Project.objects.create(
            name="Private contributor draft",
            implementing_agency="DENR",
            municipality="NCR",
            status="planning",
            cost=100,
            latitude=14.5,
            agency="DENR",
            budget=100,
            created_by=self.contributor,
            profile_data={
                **deepcopy(self.profile),
                # Stale review metadata must not make the contributor's draft visible.
                "validator_review": {
                    "review_status": "reviewed",
                    "reviewed_by_id": self.validator.id,
                },
            },
        )
        contributor_revision_draft = ProjectRevision.objects.create(
            project=self.project,
            revision_number=2,
            revision_type="progress_update",
            state="draft",
            profile_data_snapshot=deepcopy(self.profile),
            created_by=self.contributor,
        )

        for query in (
            "",
            "?scope=history",
        ):
            response = self.client.get(f"/api/validator/projects/{query}")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertNotIn(draft.id, {row["id"] for row in response.data})

        self.assertEqual(
            self.client.get("/api/validator/projects/?scope=update_forms").status_code,
            403,
        )

        self.assertEqual(
            self.client.get(f"/api/validator/projects/{draft.id}/").status_code,
            404,
        )
        self.assertEqual(
            self.client.post(f"/api/validator/projects/{draft.id}/update-form/").status_code,
            403,
        )
        revision_queue = self.client.get("/api/project-revisions/")
        self.assertEqual(revision_queue.status_code, 200, revision_queue.data)
        self.assertNotIn(contributor_revision_draft.id, {row["id"] for row in revision_queue.data})
        self.assertEqual(
            self.client.get(f"/api/project-revisions/{contributor_revision_draft.id}/").status_code,
            404,
        )

    def test_validator_queue_and_history_filter_review_metadata_in_database(self):
        legacy_review = Project.objects.create(
            name="Legacy string reviewer ID",
            implementing_agency="DENR",
            municipality="NCR",
            status="ongoing",
            workflow_status="needs_revision",
            cost=100,
            latitude=14.5,
            agency="DENR",
            budget=100,
            created_by=self.contributor,
            profile_data={
                **deepcopy(self.profile),
                "validator_review": {
                    "review_status": "reviewed",
                    "reviewed_by_id": str(self.validator.id),
                },
            },
        )
        other_validator_review = Project.objects.create(
            name="Different validator review",
            implementing_agency="DENR",
            municipality="NCR",
            status="ongoing",
            workflow_status="needs_revision",
            cost=100,
            latitude=14.5,
            agency="DENR",
            budget=100,
            created_by=self.contributor,
            profile_data={
                **deepcopy(self.profile),
                "validator_review": {
                    "review_status": "reviewed",
                    "reviewed_by_id": self.validator.id + 100,
                },
            },
        )

        queue = self.client.get("/api/validator/projects/?view=summary&scope=queue")
        history = self.client.get("/api/validator/projects/?view=summary&scope=history")
        self.assertEqual(queue.status_code, 200, queue.data)
        self.assertEqual(history.status_code, 200, history.data)
        self.assertIn(legacy_review.id, {row["id"] for row in queue.data})
        self.assertIn(legacy_review.id, {row["id"] for row in history.data})
        self.assertNotIn(other_validator_review.id, {row["id"] for row in queue.data})
        self.assertNotIn(other_validator_review.id, {row["id"] for row in history.data})

    def test_review_rejects_form_edits_but_allows_notes_and_revision_selection(self):
        url = f"/api/validator/projects/{self.project.id}/validate/"
        blocked = self.client.post(url, {
            "action": "save_reviewed", "notes": "Please revise the description.",
            "editable_fields": ["description"], "edited_profile_data": self.modified_profile(),
        }, format="json")
        self.assertEqual(blocked.status_code, 403, blocked.data)
        self.assertIn("read-only", blocked.data["detail"])

        accepted = self.client.post(url, {
            "action": "save_reviewed", "notes": "Please revise the description.",
            "editable_fields": ["description"],
        }, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.project.refresh_from_db()
        self.assertEqual(self.project.profile_data["simplified_form"]["description"], "Contributor's original description")
        self.assertEqual(self.project.profile_data["validator_review"]["editable_fields"], ["description"])
        self.assertEqual(
            self.project.profile_data["validator_review"]["working_copy"]["simplified_form"]["description"],
            "Contributor's original description",
        )

    def test_direct_project_update_and_ai_run_cannot_change_answers(self):
        changed = self.modified_profile()
        direct = self.client.patch(f"/api/projects/{self.project.id}/", {
            "profile_data": changed,
        }, format="json")
        self.assertEqual(direct.status_code, 403, direct.data)

        analysis = self.client.post(f"/api/validator/projects/{self.project.id}/priority-analysis/run/", {
            "edited_profile_data": changed, "supplements": {"readinessLevel": "completed_documents"},
        }, format="json")
        self.assertEqual(analysis.status_code, 403, analysis.data)
        self.assertIn("read-only", analysis.data["detail"])
        self.project.refresh_from_db()
        self.assertEqual(self.project.profile_data, self.profile)

        created = self.client.post("/api/validator/projects/", {
            "name": "Unauthorized project", "profile_data": self.modified_profile(),
        }, format="json")
        self.assertEqual(created.status_code, 403, created.data)
        generic_created = self.client.post("/api/projects/", {
            "name": "Unauthorized project", "profile_data": self.modified_profile(),
        }, format="json")
        self.assertEqual(generic_created.status_code, 403, generic_created.data)

        unchanged = self.client.post(f"/api/validator/projects/{self.project.id}/validate/", {
            "action": "save_draft", "edited_profile_data": deepcopy(self.profile),
        }, format="json")
        self.assertEqual(unchanged.status_code, 403, unchanged.data)

    @override_settings(GROQ_ENABLED=False)
    def test_ai_scoring_still_accepts_validator_facts_without_form_edits(self):
        response = self.client.post(f"/api/validator/projects/{self.project.id}/priority-analysis/run/", {
            "supplements": {
                "readinessLevel": "completed_documents",
                "gadResponsiveness": "gender_responsive",
                "spatialCoverageScope": "region_wide",
            },
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        analysis = self.project.priority_analyses.get()
        self.assertEqual(analysis.input_snapshot["simplified_form"]["description"], "Contributor's original description")

    def test_progress_review_cannot_change_contributor_snapshot(self):
        revision = ProjectRevision.objects.create(
            project=self.project, revision_number=2, revision_type="progress_update",
            state="submitted", profile_data_snapshot=deepcopy(self.profile),
            created_by=self.contributor, submitted_by=self.contributor,
        )
        blocked = self.client.post(f"/api/project-revisions/{revision.id}/review/", {
            "action": "save_draft", "edited_profile_data": self.modified_profile(),
        }, format="json")
        self.assertEqual(blocked.status_code, 403, blocked.data)
        revision.refresh_from_db()
        self.assertEqual(revision.state, "submitted")
        self.assertEqual(revision.profile_data_snapshot, self.profile)

        accepted = self.client.post(f"/api/project-revisions/{revision.id}/review/", {
            "action": "save_draft", "notes": "Review in progress.",
        }, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        revision.refresh_from_db()
        self.assertEqual(revision.state, "validator_draft")
        self.assertEqual(
            revision.profile_data_snapshot["simplified_form"]["description"],
            "Contributor's original description",
        )

    def test_resubmitted_answers_supersede_old_validator_copy(self):
        revised = deepcopy(self.profile)
        revised["simplified_form"]["description"] = "Contributor's revised description"
        self.project.profile_data = {
            **revised,
            "contributor_snapshot": deepcopy(revised),
            "validator_review": {
                "review_status": "draft", "resubmitted_at": "2026-10-08T00:00:00Z",
                "working_copy": self.modified_profile(),
            },
        }
        self.project.save(update_fields=["profile_data"])
        response = self.client.post(f"/api/validator/projects/{self.project.id}/validate/", {
            "action": "save_draft",
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.project.refresh_from_db()
        self.assertEqual(
            self.project.profile_data["validator_review"]["working_copy"]["simplified_form"]["description"],
            "Contributor's revised description",
        )
