from copy import deepcopy

from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Project, ProjectRevision, User


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
        self.assertEqual(blocked.status_code, 400, blocked.data)
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
        self.assertEqual(analysis.status_code, 400, analysis.data)
        self.assertIn("read-only", analysis.data["detail"])
        self.project.refresh_from_db()
        self.assertEqual(self.project.profile_data, self.profile)

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
        self.assertEqual(blocked.status_code, 400, blocked.data)
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
