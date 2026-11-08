from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from ai_engine.models import AITrainingRecord
from ai_engine.services import sync_all_training_records
from .priority_scoring import confirm_analysis, default_priority_rule_config, validate_priority_rule_config, _sector_track


class PriorityConfigurationTests(SimpleTestCase):
    def test_configured_high_threshold_and_regional_cost_floor(self):
        config = default_priority_rule_config()
        config["thresholds"]["high"] = 82
        self.assertEqual(validate_priority_rule_config(config, enforce_current_high=True)["thresholds"]["high"], 82)
        config["thresholds"]["regional_criteria"]["cost"]["thresholds"]["over_500m"] = 1
        with self.assertRaisesRegex(ValueError, "eligibility cutoff"):
            validate_priority_rule_config(config)

    def test_stale_sceeed_track_does_not_override_other_sector(self):
        self.assertEqual(_sector_track({"developmentSector": "Infrastructure"}, {"sceeedTrack": "economic"}, ""), "infrastructure")
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

    def test_incomplete_analysis_cannot_be_overridden_or_confirmed(self):
        project, analysis, _ = self.make_analysis()
        url = self.confirm_url(project, analysis)
        without_reason = self.client.post(url, {"final_priority": "high"}, format="json")
        self.assertEqual(without_reason.status_code, 400)
        self.assertIn("cannot be confirmed", without_reason.data["detail"].lower())
        invalid_label = self.client.post(url, {
            "final_priority": "incomplete", "override_rationale": "Validator decision",
        }, format="json")
        self.assertEqual(invalid_label.status_code, 400)

        response = self.client.post(url, {
            "final_priority": "high", "override_rationale": "Regional impact merits high priority.",
        }, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(ProjectPriorityConfirmation.objects.filter(analysis=analysis).count(), 0)

    def test_incomplete_low_override_is_blocked(self):
        project, analysis, profile = self.make_analysis()
        confirmed = self.client.post(self.confirm_url(project, analysis), {
            "final_priority": "low", "override_rationale": "Evidence supports a local-scale priority.",
        }, format="json")
        self.assertEqual(confirmed.status_code, 400, confirmed.data)
        self.assertIn("cannot be confirmed", confirmed.data["detail"].lower())
        self.assertEqual(ProjectPriorityConfirmation.objects.filter(analysis=analysis).count(), 0)

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
