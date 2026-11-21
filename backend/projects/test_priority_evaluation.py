import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from .models import Project, ProjectPriorityAnalysis, ProjectRevision, PriorityRuleSet, User
from .priority_scoring import SCORE_TOTAL_VERSION, default_priority_rule_config, analyze_project
from ai_engine.groq_client import GroqCompletion

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

    @patch("projects.priority_evaluation.priority_rule_config", return_value={"thresholds": {"high": 100, "regional_project_cost": 0}})
    def test_final_scores_are_bounded_independently(self, _config):
        self.analysis.suggested_scores["pap"][0]["weight"] = 40.009
        self.analysis.regional_scorecard["criteria"][0].update(raw=10, weight=100)
        result = calculate_evaluation(self.analysis, {"pap:readiness": 10, "rdp:outcome": 10}, {})
        self.assertEqual(result[2:], (100, 100, "high"))

    @patch("projects.priority_evaluation.priority_rule_config", return_value={"thresholds": {"high": 81, "regional_project_cost": 200000000}})
    def test_new_formula_reacts_to_regional_edits(self, _config):
        self.analysis.suggested_scores["score_total_version"] = SCORE_TOTAL_VERSION
        self.analysis.regional_scorecard["criteria"][0]["weight"] = 100
        low_regional = calculate_evaluation(self.analysis, {"regional:cost": 0}, {})
        high_regional = calculate_evaluation(self.analysis, {"regional:cost": 10}, {})
        maximum = calculate_evaluation(self.analysis, {"pap:readiness": 10, "rdp:outcome": 10, "regional:cost": 10}, {})
        self.assertEqual(low_regional[2], 25)
        self.assertEqual(high_regional[2], 75)
        self.assertEqual(maximum[2:], (100, 100, "high"))


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

    def test_confirm_accepts_the_same_partial_payload_used_to_save(self):
        self.client.force_authenticate(self.validator)
        scores = {"pap:readiness": 8}
        remarks = {"pap:readiness": " Checked. "}
        saved = self.client.post(self.url, {
            "adjusted_scores": scores, "validator_remarks": remarks,
        }, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["evaluation"]["validator_remarks"]["pap:readiness"], "Checked.")
        confirmed = self.client.post(
            f"/api/validator/projects/{self.project.id}/priority-analysis/{self.analysis.id}/confirm/",
            {"adjusted_scores": scores, "validator_remarks": remarks, "final_priority": "low"},
            format="json",
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(confirmed.data["latest_confirmation"]["final_priority"], "low")

    def test_rejects_out_of_range_and_non_validator(self):
        self.client.force_authenticate(self.validator)
        invalid = self.client.post(self.url, {"adjusted_scores": {"pap:readiness": 11}}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.client.force_authenticate(self.admin)
        denied = self.client.post(self.url, {"adjusted_scores": {}}, format="json")
        self.assertEqual(denied.status_code, 403)


@override_settings(GROQ_ENABLED=False)
class ValidatorFactsApiTests(APITestCase):
    def setUp(self):
        self.validator = User.objects.create_user(username="facts_validator", role="validator")
        self.client.force_authenticate(self.validator)
        self.project = Project.objects.create(
            name="Facts test", implementing_agency="DPWH", municipality="NCR",
            status="proposed", cost=1, latitude=14.5, agency="DPWH", budget=1,
            profile_data={
                "form_schema": {"key": "simplified-rdip", "version": 1, "legacy": True},
                "simplified_form": {"location": ["Quezon City"], "fundingRequirementByYear": {"2026": "199,999,999.99"}},
            },
        )
        self.url = f"/api/validator/projects/{self.project.id}/priority-analysis/"

    def save_facts(self, version, **values):
        return self.client.put(self.url + "facts/", {"facts_version": version, "supplements": values}, format="json")

    def budget(self, amount):
        self.project.profile_data["simplified_form"]["fundingRequirementByYear"]["2026"] = amount
        self.project.save(update_fields=["profile_data"])

    @patch("projects.views.serialize_document_assessment", return_value={"status": "not_required"})
    def test_restore_fact_selects_a_new_analysis_and_preserves_confirmation(self, _documents):
        first = self.save_facts(0, readinessLevel="concept_only", gadResponsiveness="invisible", spatialCoverageScope="specific_lgus")
        self.assertEqual(first.status_code, 200, first.data)
        runs = []
        for version, scope in enumerate(["specific_lgus", "region_wide", "specific_lgus"], 1):
            if version > 1:
                saved = self.save_facts(version - 1, spatialCoverageScope=scope)
                self.assertEqual(saved.status_code, 200, saved.data)
                self.assertEqual(saved.data["facts_version"], version)
                stale = self.save_facts(version - 1, spatialCoverageScope="none")
                self.assertEqual(stale.status_code, 409, stale.data)
                stale_run = self.client.post(self.url + "run/", {"facts_version": version - 1}, format="json")
                self.assertEqual(stale_run.status_code, 409, stale_run.data)
            run = self.client.post(self.url + "run/", {"facts_version": version}, format="json")
            self.assertEqual(run.status_code, 200, run.data)
            self.assertFalse(run.data["reused"])
            runs.append(run.data["analysis"]["id"])
            loaded = self.client.get(self.url)
            self.assertEqual(loaded.data["current_analysis_id"], runs[-1])
            self.assertEqual(loaded.data["validator_facts"]["spatialCoverageScope"], scope)
            if version == 1:
                confirmed = self.client.post(self.url + f"{runs[0]}/confirm/", {"final_priority": "low"}, format="json")
                self.assertEqual(confirmed.status_code, 200, confirmed.data)
        self.assertEqual(len(set(runs)), 3)
        self.assertEqual(ProjectPriorityAnalysis.objects.get(pk=runs[0]).confirmations.get().final_priority, "low")
        self.assertFalse(self.client.get(self.url).data["validation_eligibility"]["eligible"])
        self.project.workflow_status = Project.WORKFLOW_VALIDATED
        self.project.save(update_fields=["workflow_status"])
        self.assertEqual(self.save_facts(3, spatialCoverageScope="none").status_code, 404)

    def test_regional_boundary_hidden_facts_and_revision_isolation(self):
        for amount, applicable in (("199,999,999.99", False), ("200,000,000.00", True), ("200,000,000.01", True)):
            self.budget(amount)
            self.assertEqual(self.client.get(self.url).data["regional_eligibility"]["applicable"], applicable)
        saved = self.save_facts(0, beneficiaryCount="123", contributedOutcomeCount=0, regionalSpatialCategory="single_city")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["validator_facts"]["contributedOutcomeCount"], "0")
        self.assertEqual(self.save_facts(1, beneficiaryCount="-1").status_code, 400)
        revision = ProjectRevision.objects.create(
            project=self.project, revision_number=1, revision_type="progress_update", state="submitted",
            profile_data_snapshot=self.project.profile_data,
        )
        revised = self.client.put(self.url + "facts/", {
            "revision": revision.pk, "facts_version": 0, "supplements": {"beneficiaryCount": "42"},
        }, format="json")
        self.assertEqual(revised.status_code, 200, revised.data)
        self.budget("199999999.99")
        hidden = self.save_facts(1, beneficiaryCount="")
        self.assertEqual(hidden.data["facts_version"], 1)
        self.budget("200000000")
        self.assertEqual(self.client.get(self.url).data["validator_facts"]["beneficiaryCount"], "123")
        self.assertEqual(self.client.get(self.url + f"?revision={revision.pk}").data["validator_facts"]["beneficiaryCount"], "42")

    @override_settings(GROQ_ENABLED=True, GROQ_API_KEY="test-key")
    @patch("ai_engine.groq_priority._historical_context", return_value=([], [], "test", {}))
    @patch("ai_engine.groq_priority.complete_json")
    @patch("projects.views.serialize_document_assessment", return_value={"status": "not_required"})
    def test_rule_updates_use_current_outcomes_and_bad_responses_do_not_replace_history(self, _documents, completion, _history):
        captured = []
        broken = False

        def outcome_response(messages, **options):
            payload = json.loads(messages[-1]["content"])
            captured.append(payload)
            facts = payload["validator_facts"]
            self.assertNotIn("beneficiaryCount", facts)
            self.assertNotIn("regional_scorecard_context", payload)
            rows = [
                {"key": item["key"], "raw_score": 0 if index == 1 else 8,
                 "explanation": "Explicit test evidence.", "evidence": []}
                for index, item in enumerate(payload["criteria"])
            ]
            data = {
                "outcome_assessments": rows[:-1] if broken else rows,
                "historical_prediction": {"priority": "low", "confidence": 0.7, "explanation": "Example."},
            }
            return GroqCompletion(data, "test-model", False, ("test-model",))

        completion.side_effect = outcome_response
        snapshot = self.project.profile_data
        facts = {"readinessLevel": "concept_only", "gadResponsiveness": "invisible", "spatialCoverageScope": "specific_lgus"}
        config = default_priority_rule_config()
        first_rules = PriorityRuleSet.objects.create(version="test-outcomes-v1", is_active=True, **config)
        first, _ = analyze_project(self.project, self.validator, snapshot, facts, rule_set=first_rules)
        original_outcomes = first.suggested_scores["rdp_outcomes"]
        first_rules.is_active = False
        first_rules.save(update_fields=["is_active"])
        config["keyword_dictionaries"]["common_outcomes"][0]["label"] = "Updated criterion description"
        config["thresholds"]["pap_spatial_scores"]["one_to_five_lgus"] = 4
        recent_rules = PriorityRuleSet.objects.create(version="test-outcomes-v2", is_active=True, **config)
        saved = self.save_facts(0, readinessNotes="Current facts", **facts)
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["facts_version"], 1)
        broken = True
        failed = self.client.post(self.url + "run/", {"facts_version": 1}, format="json")
        self.assertEqual(failed.status_code, 502, failed.data)
        self.assertEqual(failed.data["reason"], "invalid_response")
        self.assertEqual(ProjectPriorityAnalysis.objects.filter(project=self.project).count(), 1)
        broken = False
        successful = self.client.post(self.url + "run/", {"facts_version": 1}, format="json")
        self.assertEqual(successful.status_code, 200, successful.data)
        result = ProjectPriorityAnalysis.objects.get(pk=successful.data["analysis"]["id"])
        self.assertEqual(result.rule_set, recent_rules)
        self.assertEqual([captured[-1]["criteria"][i]["key"] for i in (0, 1)], [row["key"] for row in original_outcomes[:2]])
        self.assertEqual(captured[-1]["criteria"][0]["label"], "Updated criterion description")
        self.assertEqual([row["raw"] for row in result.suggested_scores["rdp_outcomes"][:2]], [8, 0])
        self.assertEqual(result.suggested_scores["pap"][2]["raw"], 4)
        first.refresh_from_db()
        self.assertEqual(first.suggested_scores["rdp_outcomes"], original_outcomes)
