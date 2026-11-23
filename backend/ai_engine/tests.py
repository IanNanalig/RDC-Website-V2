import json
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import (
    Project,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    ProjectRevision,
    User,
)
from projects.priority_scoring import confirm_analysis, get_active_priority_rule_set

from .groq_client import GroqCompletion
from .groq_priority import _historical_context, analyze_priority_with_groq
from .historical_index import find_historical_matches, queue_historical_reference
from .models import AIModelVersion, AIProjectAnalysis, AITrainingRecord, HistoricalProjectReference
from .services import ensure_learning_assessment


class ControlledLearningTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="learning-admin",
            email="learning-admin@example.com",
            password="StrongTestPassword123!",
            role="admin",
        )
        self.validator = User.objects.create_user(
            username="learning-validator",
            email="learning-validator@example.com",
            password="StrongTestPassword123!",
            role="validator",
        )
        self.rule_set = get_active_priority_rule_set()

    def _analysis(self, index, suggested, score, sector, words):
        project = Project.objects.create(
            name=f"Historical Project {index}",
            implementing_agency="DPWH",
            agency="DPWH",
            municipality="NCR",
            status="proposed",
            cost=100_000_000 + index,
            budget=100_000_000 + index,
            latitude=14.5,
            created_by=self.admin,
            profile_data={},
        )
        snapshot = {
            "simplified_form": {
                "projectActivity": f"Historical Project {index}",
                "description": words,
                "agencyName": "DPWH",
                "developmentSector": sector,
                "location": "Region-wide",
                "status": "New",
                "fundingRequirementByYear": {"2026": 100_000_000 + index},
            }
        }
        return ProjectPriorityAnalysis.objects.create(
            project=project,
            validator=self.validator,
            rule_set=self.rule_set,
            source_hash=f"{index:064d}",
            input_snapshot=snapshot,
            supplements={},
            suggested_scores={
                "missing_facts": [],
                "pap_total": score * 0.5,
                "rdp_total": score * 0.5,
                "rdp_track": sector.lower(),
                "pap": [
                    {"key": "readiness", "raw": max(0, min(10, score / 10))},
                    {"key": "gad_responsiveness", "raw": 5},
                    {"key": "spatial_coverage", "raw": 10},
                ],
                "rdp_outcomes": [{"key": "outcome", "raw": max(0, min(10, score / 10))}],
            },
            regional_scorecard={"applicable": False, "total": 0},
            flags={"negative_matches": [], "risks": []},
            suggested_priority=suggested,
            base_score=score,
        )

    def _confirmed(self, index, priority, score, sector="infrastructure", words="road drainage regional connectivity"):
        analysis = self._analysis(index, priority, score, sector, words)
        confirmation = ProjectPriorityConfirmation.objects.create(
            analysis=analysis,
            validator=self.validator,
            final_priority=priority,
        )
        return analysis, confirmation

    def test_predictions_do_not_become_training_data(self):
        analysis = self._analysis(1, "low", 60, "infrastructure", "road bridge transport")

        assessment = ensure_learning_assessment(analysis)

        self.assertEqual(assessment.status, "untrained")
        self.assertEqual(AITrainingRecord.objects.count(), 0)
        self.assertIn("No trained historical model", assessment.explanation["summary"])

    def test_confirmation_becomes_training_candidate(self):
        analysis = self._analysis(2, "low", 60, "infrastructure", "road bridge transport")

        confirmation = confirm_analysis(analysis, self.validator, {}, "low", "", [])

        record = AITrainingRecord.objects.get(confirmation=confirmation)
        self.assertEqual(record.target_priority, "low")
        self.assertTrue(record.is_eligible)
        self.assertEqual(record.project_id, analysis.project_id)

    def test_training_requires_each_priority_label(self):
        self._confirmed(3, "low", 60)
        self._confirmed(4, "low", 62)
        self.client.force_authenticate(self.admin)

        response = self.client.post("/api/admin/ai/models/train/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("low and high", response.data["detail"])
        self.assertEqual(AIModelVersion.objects.count(), 0)

    def test_admin_trains_versioned_model_and_analysis_uses_it(self):
        self._confirmed(10, "low", 25, "social", "local office support")
        candidate, confirmation = self._confirmed(12, "high", 90, "environment", "regional flood climate resilience")
        self._index(candidate, confirmation)
        self.client.force_authenticate(self.admin)

        response = self.client.post("/api/admin/ai/models/train/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        model = AIModelVersion.objects.get(status="active")
        self.assertEqual(model.sample_count, 2)
        self.assertEqual(model.metrics["evaluation_scope"], "training_only_insufficient_data_for_holdout")
        self.assertEqual(model.dataset_memberships.count(), 2)
        duplicate = self.client.post("/api/admin/ai/models/train/", {}, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already trained", duplicate.data["detail"])
        self.assertEqual(AIModelVersion.objects.count(), 1)

        new_analysis = self._analysis(
            13,
            "high",
            88,
            "environment",
            "regional flood climate resilience drainage",
        )
        assessment = ensure_learning_assessment(new_analysis)
        self.assertEqual(assessment.status, "ready")
        self.assertEqual(assessment.model_version_id, model.pk)
        self.assertIn(assessment.predicted_priority, {"low", "high"})
        self.assertAlmostEqual(sum(assessment.class_probabilities.values()), 1.0, places=4)
        self.assertGreaterEqual(assessment.similar_projects.count(), 1)

        incomplete = self._analysis(14, "incomplete", 0, "infrastructure", "road proposal")
        incomplete.suggested_scores = {**incomplete.suggested_scores, "missing_facts": ["Readiness level"]}
        incomplete.save(update_fields=["suggested_scores"])
        incomplete_assessment = ensure_learning_assessment(incomplete)
        self.assertEqual(incomplete_assessment.status, "insufficient_evidence")
        self.assertEqual(incomplete_assessment.predicted_priority, "")

    def test_validator_cannot_train_or_manage_dataset(self):
        _, confirmation = self._confirmed(20, "low", 60)
        self.client.force_authenticate(self.validator)

        train_response = self.client.post("/api/admin/ai/models/train/", {}, format="json")
        data_response = self.client.get("/api/admin/ai/training-data/")

        self.assertEqual(train_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(data_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(hasattr(confirmation, "unexpected_training_mutation"))

    def test_excluding_training_record_requires_reason(self):
        _, confirmation = self._confirmed(30, "low", 60)
        self.client.force_authenticate(self.admin)
        self.client.get("/api/admin/ai/training-data/")
        record = AITrainingRecord.objects.get(confirmation=confirmation)

        rejected = self.client.patch(
            f"/api/admin/ai/training-data/{record.id}/",
            {"is_eligible": False, "exclusion_reason": ""},
            format="json",
        )
        accepted = self.client.patch(
            f"/api/admin/ai/training-data/{record.id}/",
            {"is_eligible": False, "exclusion_reason": "Duplicate or unreliable historical record."},
            format="json",
        )

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertFalse(record.is_eligible)
        self.assertEqual(record.exclusion_reason, "Duplicate or unreliable historical record.")

    def test_dataset_sync_does_not_change_unchanged_record_version(self):
        _, confirmation = self._confirmed(35, "low", 60)
        self.client.force_authenticate(self.admin)

        self.client.get("/api/admin/ai/training-data/")
        record = AITrainingRecord.objects.get(confirmation=confirmation)
        original_updated_at = record.updated_at
        self.client.get("/api/admin/ai/training-data/")
        record.refresh_from_db()

        self.assertEqual(record.updated_at, original_updated_at)

    def test_retraining_preserves_old_model_and_assessment(self):
        self._confirmed(40, "low", 20)
        self._confirmed(42, "high", 90)
        self.client.force_authenticate(self.admin)
        first = self.client.post("/api/admin/ai/models/train/", {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        analysis = self._analysis(43, "low", 65, "infrastructure", "regional road connectivity")
        original_assessment = ensure_learning_assessment(analysis)

        self._confirmed(44, "high", 95)
        second = self.client.post("/api/admin/ai/models/train/", {}, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        refreshed_assessment = ensure_learning_assessment(analysis)

        self.assertNotEqual(original_assessment.model_version_id, refreshed_assessment.model_version_id)
        self.assertTrue(AIModelVersion.objects.filter(pk=original_assessment.model_version_id, status="retired").exists())
        self.assertEqual(AIProjectAnalysis.objects.filter(priority_analysis=analysis).count(), 2)

    def _index(self, analysis, confirmation):
        Project.objects.filter(pk=analysis.project_id).update(validated=True, workflow_status=Project.WORKFLOW_VALIDATED)
        with self.captureOnCommitCallbacks(execute=True):
            queue_historical_reference(analysis.project_id, confirmation.pk)
        return HistoricalProjectReference.objects.get(project_id=analysis.project_id)

    @patch("ai_engine.groq_priority.is_groq_enabled", return_value=True)
    @patch("ai_engine.groq_priority.complete_json")
    def test_validated_reference_is_retrieved_traced_and_sent_to_groq(self, completion, _enabled):
        analysis, confirmation = self._confirmed(
            50, "low", 45, words="Rehabilitate the tide gate and restore drainage through the Malabon outlet. Contact: private@mail.test.",
        )
        reference = self._index(analysis, confirmation)
        self.assertEqual(reference.state, "ready")
        self.assertNotIn("private@mail.test", reference.normalized_text)
        self.assertEqual(queue_historical_reference(analysis.project_id, confirmation.pk).pk, reference.pk)
        pending, pending_confirmation = self._confirmed(51, "high", 91, words="Rehabilitate the tide gate and restore drainage through the Malabon outlet.")
        with self.captureOnCommitCallbacks(execute=True):
            queue_historical_reference(pending.project_id, pending_confirmation.pk)
        self.assertEqual(HistoricalProjectReference.objects.get(project_id=pending.project_id).state, "ineligible")

        snapshot = {"simplified_form": {
            "projectActivity": "Malabon tide gate work",
            "description": "Rehabilitate the tide gate and restore drainage through the Malabon outlet.",
            "location": "Region-wide", "agencyName": "DPWH",
        }}
        examples, _, _, info = _historical_context(snapshot, "infrastructure")
        self.assertEqual(info["status"], "ready")
        self.assertEqual([row["confirmation_id"] for row in examples], [confirmation.pk])
        self.assertEqual(examples[0]["rule_base_score"], 45)
        self.assertEqual(examples[0]["validator_final_priority"], "low")
        self.assertEqual(find_historical_matches({"description": "vaccination and prenatal nutrition"}), [])

        completion.return_value = GroqCompletion({
            "outcome_assessments": [{"key": "utility", "raw_score": 8, "explanation": "A gated outlet.", "evidence": []}],
        }, "test-model", False, ("test-model",))
        result = analyze_priority_with_groq(
            pending.project, snapshot, {}, [{"key": "utility", "label": "Utility", "weight": 10}], "infrastructure", [],
        )
        prompt = json.loads(completion.call_args.args[0][-1]["content"])
        sent = prompt["validator_confirmed_historical_examples"]
        self.assertEqual([row["confirmation_id"] for row in sent], [confirmation.pk])
        self.assertEqual(result["provider"]["historical_reference_ids"], [confirmation.pk])
        self.assertIn("tide gate", sent[0]["project_text"])
        self.assertNotIn("private@mail.test", json.dumps(sent))

    def test_admin_rebuild_backfills_matching_legacy_endorsement(self):
        analysis, confirmation = self._confirmed(53, "high", 91)
        Project.objects.filter(pk=analysis.project_id).update(validated=True, workflow_status=Project.WORKFLOW_VALIDATED)
        ProjectRevision.objects.create(
            project=analysis.project, revision_number=1, revision_type="initial_submission",
            state="endorsed", is_public_current=True, endorsed_at=timezone.now(),
            profile_data_snapshot=analysis.input_snapshot,
        )
        endpoint = "/api/admin/cms/ai-scoring/historical-references/rebuild/"
        self.client.force_authenticate(self.validator)
        self.assertEqual(self.client.post(endpoint, {}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(endpoint, {"after": 0}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["scheduled"], 1)
        reference = HistoricalProjectReference.objects.get(project_id=analysis.project_id)
        self.assertEqual(reference.state, "ready")
        self.assertEqual(reference.indexed_record.confirmation_id, confirmation.pk)

    def test_duplicate_detection_requires_matching_metadata(self):
        form = {
            "projectActivity": "Tide Gate Rehabilitation Phase I",
            "agencyName": "DPWH", "location": ["Malabon"],
            "description": "Rehabilitate the tide gate, replace three intake screens and restore drainage capacity.",
            "scope": "Tide gate and intake screens", "startYear": "2026", "endYear": "2027",
        }
        analysis, confirmation = self._confirmed(52, "high", 92)
        analysis.input_snapshot = {"simplified_form": form}
        analysis.save(update_fields=["input_snapshot"])
        self._index(analysis, confirmation)
        for changes, expected in (
            ({}, "potential_duplicate"),
            ({"description": "Restore drainage capacity and rehabilitate the tide gate, replacing three intake screens."}, "potential_duplicate"),
            ({"location": ["Navotas"]}, "similar_project"),
            ({"scope": "downstream pumping station construction"}, "similar_project"),
            ({"projectActivity": "Tide Gate Rehabilitation Phase II"}, "possible_continuation"),
        ):
            with self.subTest(changes=changes):
                matches = find_historical_matches({"simplified_form": {**form, **changes}}, "infrastructure")
                self.assertEqual(matches[0]["category"], expected)
