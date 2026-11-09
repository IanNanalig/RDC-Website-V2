from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from .models import Project, ProjectPriorityAnalysis, PriorityRuleSet, User

from .priority_evaluation import calculate_evaluation


class PriorityEvaluationCalculationTests(SimpleTestCase):
    def setUp(self):
        self.analysis = SimpleNamespace(
            suggested_scores={
                "pap": [{"key": "readiness", "criterion": "Readiness", "raw": 5, "weight": 40}],
                "rdp_outcomes": [{"key": "outcome", "criterion": "Outcome", "raw": 5, "weight": 60}],
                "missing_facts": [],
            },
            regional_scorecard={"applicable": True, "criteria": [{"key": "cost", "criterion": "Cost", "raw": 8, "weight": 20}]},
            suggested_priority="low",
            input_snapshot={"simplified_form": {"fundingRequirementByYear": {"2027": "1000000000"}}},
            rule_set=SimpleNamespace(),
        )

    @patch("projects.priority_evaluation.priority_rule_config", return_value={"thresholds": {"high": 70, "regional_project_cost": 500000000}})
    def test_validator_scores_recalculate_priority_and_regional_total(self, _config):
        scores, remarks, total, regional, priority = calculate_evaluation(
            self.analysis, {"pap:readiness": 9, "rdp:outcome": 8, "regional:cost": 10},
            {"pap:readiness": "Verified supporting evidence."},
        )
        self.assertEqual(scores["pap:readiness"], 9)
        self.assertEqual(remarks["pap:readiness"], "Verified supporting evidence.")
        self.assertEqual(total, 84)
        self.assertEqual(regional, 20)
        self.assertEqual(priority, "high")

    @patch("projects.priority_evaluation.priority_rule_config", return_value={"thresholds": {"high": 70, "regional_project_cost": 2000000000}})
    def test_regional_cost_cutoff_forces_low(self, _config):
        result = calculate_evaluation(self.analysis, {"pap:readiness": 10, "rdp:outcome": 10}, {})
        self.assertEqual(result[-1], "low")

    @patch("projects.priority_evaluation.priority_rule_config", return_value={"thresholds": {"high": 70, "regional_project_cost": 0}})
    def test_invalid_or_unknown_scores_are_rejected(self, _config):
        for scores in ({"pap:readiness": 11}, {"pap:readiness": 3.5}, {"unknown": 5}):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                calculate_evaluation(self.analysis, scores, {})


class PriorityEvaluationApiTests(APITestCase):
    def setUp(self):
        self.validator = User.objects.create_user(username="score_validator", email="score_validator@example.com", password="password", role="validator")
        self.admin = User.objects.create_user(username="score_admin", email="score_admin@example.com", password="password", role="admin")
        self.project = Project.objects.create(
            name="Scoring draft", implementing_agency="DPWH", municipality="NCR",
            status="proposed", cost=1, latitude=14.5, agency="DPWH", budget=1,
            profile_data={"form_schema": {"key": "simplified-rdip", "version": 1, "legacy": True}, "simplified_form": {"startYear": "2026", "endYear": "2026"}},
        )
        self.rules = PriorityRuleSet.objects.create(version="evaluation-api-rules", is_active=True)
        self.analysis = ProjectPriorityAnalysis.objects.create(
            project=self.project, validator=self.validator, rule_set=self.rules,
            source_hash="evaluation-api", input_snapshot=self.project.profile_data,
            suggested_scores={"pap": [{"key": "readiness", "criterion": "Readiness", "raw": 5, "weight": 40}], "rdp_outcomes": [], "missing_facts": []},
            suggested_priority="low", base_score=20,
        )
        self.url = f"/api/validator/projects/{self.project.id}/priority-analysis/{self.analysis.id}/evaluation/"

    def test_validator_saves_and_reopens_evaluation(self):
        self.client.force_authenticate(self.validator)
        response = self.client.post(self.url, {"adjusted_scores": {"pap:readiness": 8}, "validator_remarks": {"pap:readiness": "Checked."}}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["evaluation"]["adjusted_scores"]["pap:readiness"], 8)
        loaded = self.client.get(f"/api/validator/projects/{self.project.id}/priority-analysis/")
        self.assertEqual(loaded.data["analyses"][0]["evaluation"]["validator_remarks"]["pap:readiness"], "Checked.")

    def test_rejects_out_of_range_and_non_validator(self):
        self.client.force_authenticate(self.validator)
        invalid = self.client.post(self.url, {"adjusted_scores": {"pap:readiness": 11}}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.client.force_authenticate(self.admin)
        denied = self.client.post(self.url, {"adjusted_scores": {}}, format="json")
        self.assertEqual(denied.status_code, 403)
