from copy import deepcopy

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import (
    PriorityRuleSet,
    Project,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    User,
    UserActivity,
)
from projects.priority_scoring import (
    analyze_project,
    default_priority_rule_config,
    get_active_priority_rule_set,
    has_matching_confirmation,
    source_hash,
)


class AIPriorityCMSTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ai-cms-admin",
            email="ai-cms-admin@example.com",
            password="StrongTestPassword123!",
            role="admin",
        )
        self.editor = User.objects.create_user(
            username="ai-cms-editor",
            email="ai-cms-editor@example.com",
            password="StrongTestPassword123!",
            role="content_editor",
        )
        self.validator = User.objects.create_user(
            username="ai-cms-validator",
            email="ai-cms-validator@example.com",
            password="StrongTestPassword123!",
            role="validator",
        )
        self.rule_set = get_active_priority_rule_set()
        self.project = Project.objects.create(
            name="Historical flood-control project",
            implementing_agency="DPWH",
            agency="DPWH",
            municipality="NCR",
            status="proposed",
            cost=100_000_000,
            budget=100_000_000,
            latitude=14.5,
            created_by=self.admin,
            profile_data={},
        )
        self.snapshot = {
            "simplified_form": {
                "projectActivity": "Regional flood-control drainage",
                "developmentSector": "Infrastructure",
                "description": "Flood resilient drainage and road connectivity.",
                "rdpMainChapter": "Connectivity and climate resilience",
                "location": "Region-wide",
                "status": "New",
                "fundingRequirementByYear": {"2026": 100_000_000},
            }
        }
        self.analysis = ProjectPriorityAnalysis.objects.create(
            project=self.project,
            validator=self.validator,
            rule_set=self.rule_set,
            source_hash=source_hash(self.snapshot, {}, self.rule_set),
            input_snapshot=self.snapshot,
            suggested_scores={"missing_facts": []},
            suggested_priority="low",
            base_score=65,
        )
        self.confirmation = ProjectPriorityConfirmation.objects.create(
            analysis=self.analysis,
            validator=self.validator,
            final_priority="low",
        )

    def test_cms_explains_controlled_learning_and_lists_training_projects(self):
        self.client.force_authenticate(self.editor)
        response = self.client.get("/api/admin/cms/ai-scoring/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["system_type"], "hybrid_rules_similarity_ml")
        self.assertTrue(response.data["learns_from_historical_projects"])
        self.assertIn("validator-confirmed", response.data["learning_explanation"])
        self.assertEqual(response.data["active_rule_set"]["version"], self.rule_set.version)
        history = response.data["historical_projects"]
        self.assertEqual(history[0]["project_title"], self.project.name)
        self.assertEqual(history[0]["final_priority"], "low")
        self.assertTrue(history[0]["training_eligible"])
        self.assertIsNotNone(history[0]["training_record_id"])
        self.assertNotIn("input_snapshot", history[0])

    def test_content_editor_cannot_activate_rules(self):
        self.client.force_authenticate(self.editor)
        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": default_priority_rule_config()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_activates_immutable_rule_version_and_invalidates_old_confirmation(self):
        config = deepcopy(default_priority_rule_config())
        config["thresholds"]["regional_project_cost"] = 300_000_000
        config["keyword_dictionaries"]["guidelines"].append("Use the current RDC-approved scoring memorandum.")
        self.assertTrue(has_matching_confirmation(self.project, self.snapshot))

        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": config, "change_note": "Updated approved priority thresholds."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        active = PriorityRuleSet.objects.get(is_active=True)
        self.assertNotEqual(active.pk, self.rule_set.pk)
        self.rule_set.refresh_from_db()
        self.assertFalse(self.rule_set.is_active)
        self.assertEqual(active.thresholds["high"], 81)
        self.assertEqual(active.thresholds["regional_project_cost"], 300_000_000)
        self.assertEqual(self.analysis.rule_set_id, self.rule_set.pk)
        self.assertFalse(has_matching_confirmation(self.project, self.snapshot))
        new_analysis, reused = analyze_project(
            self.project,
            self.validator,
            self.snapshot,
            {
                "readinessLevel": "completed_documents",
                "gadResponsiveness": "gender_responsive",
                "spatialCoverageScope": "region_wide",
            },
        )
        self.assertFalse(reused)
        self.assertEqual(new_analysis.rule_set_id, active.pk)
        self.assertEqual(new_analysis.suggested_priority, "low")
        self.assertTrue(
            UserActivity.objects.filter(
                user=self.admin,
                event="cms_content_updated",
                details__content_type="ai_priority_rules",
                details__rule_set_id=active.pk,
            ).exists()
        )

    def test_invalid_weight_total_does_not_create_rule_version(self):
        config = deepcopy(default_priority_rule_config())
        config["thresholds"]["pap_weights"]["readiness"] = 19
        before = PriorityRuleSet.objects.count()
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": config},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must total 100", response.data["detail"])
        self.assertEqual(PriorityRuleSet.objects.count(), before)

    def test_binary_priority_boundary_cannot_be_changed(self):
        config = deepcopy(default_priority_rule_config())
        config["thresholds"]["high"] = 80
        before = PriorityRuleSet.objects.count()
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": config, "change_note": "Attempted threshold change."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be 81", response.data["detail"])
        self.assertEqual(PriorityRuleSet.objects.count(), before)
