from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import (
    Project,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    User,
)
from projects.priority_scoring import confirm_analysis, get_active_priority_rule_set

from .models import AIModelVersion, AIProjectAnalysis, AITrainingRecord
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
        self._confirmed(12, "high", 90, "environment", "regional flood climate resilience")
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
