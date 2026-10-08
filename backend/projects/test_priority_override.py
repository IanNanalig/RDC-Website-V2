from django.test import override_settings
from rest_framework.test import APITestCase

from ai_engine.models import AITrainingRecord
from ai_engine.services import sync_all_training_records
from .priority_scoring import confirm_analysis
from .models import (
    Notification, PriorityRuleSet, Project, ProjectPriorityAnalysis,
    ProjectPriorityConfirmation, User, UserActivity,
)


@override_settings(GROQ_ENABLED=False)
class ValidatorPriorityOverrideTests(APITestCase):
    def setUp(self):
        self.validator = User.objects.create_user(
            username="priority-validator", password="TestPassword123!", role="validator",
            email="priority-validator@example.com",
        )
        self.contributor = User.objects.create_user(
            username="priority-contributor", password="TestPassword123!", role="staff",
            email="priority-contributor@example.com", agency="DENR",
        )
        self.admin = User.objects.create_user(
            username="priority-admin", password="TestPassword123!", role="admin",
            email="priority-admin@example.com",
        )
        self.rules = PriorityRuleSet.objects.create(version="priority-override-test", is_active=True)
        self.client.force_authenticate(user=self.validator)

    def make_analysis(self, suggested="incomplete", missing=None):
        profile = {
            "submission_type": "simplified",
            "form_schema": {"key": "simplified-rdip", "version": 1, "legacy": True},
            "simplified_form": {
                "agencyName": "DENR", "projectActivity": "NCR environment project",
                "startYear": "2026", "endYear": "2026",
                "fundingRequirementByYear": {"2026": "100"},
            },
        }
        project = Project.objects.create(
            name="NCR environment project", implementing_agency="DENR", municipality="NCR",
            status="proposed", cost=100, latitude=14.5, agency="DENR", budget=100,
            created_by=self.contributor, profile_data=profile,
        )
        analysis = ProjectPriorityAnalysis.objects.create(
            project=project, validator=self.validator, rule_set=self.rules,
            source_hash=f"{project.id:064d}", input_snapshot=profile,
            suggested_scores={"missing_facts": missing if missing is not None else ["Readiness Level"]},
            suggested_priority=suggested, base_score="58.50",
        )
        return project, analysis, profile

    def confirm_url(self, project, analysis):
        return f"/api/validator/projects/{project.id}/priority-analysis/{analysis.id}/confirm/"

    def test_incomplete_override_requires_rationale_and_preserves_ai_result(self):
        project, analysis, _ = self.make_analysis()
        url = self.confirm_url(project, analysis)
        without_reason = self.client.post(url, {"final_priority": "high"}, format="json")
        self.assertEqual(without_reason.status_code, 400)
        self.assertIn("override rationale", without_reason.data["detail"].lower())
        invalid_label = self.client.post(url, {
            "final_priority": "incomplete", "override_rationale": "Validator decision",
        }, format="json")
        self.assertEqual(invalid_label.status_code, 400)

        response = self.client.post(url, {
            "final_priority": "high", "override_rationale": "Regional impact merits high priority.",
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["suggested_priority"], "incomplete")
        self.assertEqual(response.data["base_score"], "58.50")
        self.assertEqual(response.data["suggested_scores"]["missing_facts"], ["Readiness Level"])
        self.assertEqual(response.data["latest_confirmation"]["final_priority"], "high")
        self.assertEqual(response.data["latest_confirmation"]["override_rationale"], "Regional impact merits high priority.")
        self.assertEqual(ProjectPriorityConfirmation.objects.filter(analysis=analysis).count(), 1)
        record = AITrainingRecord.objects.get(confirmation__analysis=analysis)
        self.assertFalse(record.is_eligible)
        self.assertIn("incomplete AI result", record.exclusion_reason)
        self.assertTrue(UserActivity.objects.filter(project=project, event="priority_analysis_overridden").exists())
        self.assertTrue(Notification.objects.filter(project=project, recipient=self.contributor, event_type="classification_priority").exists())

        self.client.force_authenticate(user=self.admin)
        history = self.client.get("/api/admin/ai/training-data/")
        self.assertEqual(history.status_code, 200)
        row = next(item for item in history.data["results"] if item["id"] == record.id)
        self.assertFalse(row["is_eligible"])
        self.assertEqual(row["target_priority"], "high")
        included = self.client.patch(f"/api/admin/ai/training-data/{record.id}/", {
            "is_eligible": True,
        }, format="json")
        self.assertEqual(included.status_code, 200, included.data)
        sync_all_training_records()
        record.refresh_from_db()
        self.assertTrue(record.is_eligible, "Background resync must preserve the administrator's approval")

    def test_incomplete_low_override_allows_endorsement_but_locks_later_changes(self):
        project, analysis, profile = self.make_analysis()
        confirmed = self.client.post(self.confirm_url(project, analysis), {
            "final_priority": "low", "override_rationale": "Evidence supports a local-scale priority.",
        }, format="json")
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        stale_analysis = ProjectPriorityAnalysis.objects.select_related("project").get(pk=analysis.pk)
        endorsed = self.client.post(f"/api/validator/projects/{project.id}/validate/", {
            "action": "endorse", "edited_profile_data": profile, "editable_fields": [],
        }, format="json")
        self.assertEqual(endorsed.status_code, 200, endorsed.data)
        project.refresh_from_db()
        self.assertEqual(project.status, "completed")
        self.assertEqual(project.priority_analyses.first().confirmations.first().final_priority, "low")

        changed = self.client.post(self.confirm_url(project, analysis), {
            "final_priority": "high", "override_rationale": "Attempted later change.",
        }, format="json")
        self.assertEqual(changed.status_code, 400)
        self.assertIn("locked after endorsement", changed.data["detail"])
        self.assertEqual(ProjectPriorityConfirmation.objects.filter(analysis=analysis).count(), 1)
        with self.assertRaisesRegex(ValueError, "locked after endorsement"):
            confirm_analysis(stale_analysis, self.validator, {}, "high", "Attempted direct change.", [])

    def test_completed_result_overrides_still_require_rationale(self):
        for suggested, final in (("low", "high"), ("high", "low")):
            with self.subTest(suggested=suggested):
                project, analysis, _ = self.make_analysis(suggested=suggested, missing=[])
                url = self.confirm_url(project, analysis)
                rejected = self.client.post(url, {"final_priority": final}, format="json")
                self.assertEqual(rejected.status_code, 400)
                confirmed = self.client.post(url, {
                    "final_priority": final, "override_rationale": "Validator-reviewed evidence.",
                }, format="json")
                self.assertEqual(confirmed.status_code, 200, confirmed.data)
                self.assertEqual(confirmed.data["suggested_priority"], suggested)
                self.assertEqual(confirmed.data["latest_confirmation"]["final_priority"], final)
                self.assertTrue(AITrainingRecord.objects.get(confirmation__analysis=analysis).is_eligible)

        project, analysis, _ = self.make_analysis(suggested="low", missing=[])
        same = self.client.post(self.confirm_url(project, analysis), {"final_priority": "low"}, format="json")
        self.assertEqual(same.status_code, 200, same.data)
