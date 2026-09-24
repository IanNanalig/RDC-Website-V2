from copy import deepcopy

from django.test import override_settings
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
    confirm_analysis,
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

    @override_settings(GROQ_ENABLED=False)
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

        draft = response.data["active_rule_set"]["draft_config"]
        capabilities = draft["keyword_dictionaries"]["common_outcomes"][0]
        connectivity = draft["sector_criteria"]["infrastructure"][0]
        climate = draft["sector_criteria"]["environment"][1]
        self.assertEqual(capabilities["match_mode"], "contextual")
        self.assertIn("individuals, families, or communities", capabilities["matching_guidance"])
        self.assertIn("improve health", capabilities["context_phrases"])
        self.assertIn("reduce travel time", connectivity["context_phrases"])
        self.assertIn("mitigate emissions", climate["context_phrases"])
        self.assertNotEqual(capabilities["context_phrases"], connectivity["context_phrases"])

    @override_settings(GROQ_ENABLED=True, GROQ_API_KEY="")
    def test_new_confirmation_does_not_invalidate_its_own_validator_copy(self):
        project = Project.objects.create(
            name="Self-stable priority confirmation",
            implementing_agency="DPWH",
            agency="DPWH",
            municipality="NCR",
            status="proposed",
            cost=150_000_000,
            budget=150_000_000,
            latitude=14.6,
            created_by=self.admin,
            profile_data={},
        )
        snapshot = {
            "simplified_form": {
                "projectActivity": "Regional drainage improvement",
                "developmentSector": "Infrastructure",
                "description": "Improve drainage capacity and reduce flood exposure for communities.",
                "rdpMainChapter": "Connectivity and climate resilience",
                "location": "NCR",
                "status": "New",
                "fundingRequirementByYear": {"2026": 150_000_000},
            }
        }
        supplements = {
            "readinessLevel": "completed_documents",
            "gadResponsiveness": "gender_responsive",
            "spatialCoverageScope": "region_wide",
        }

        analysis, _reused = analyze_project(
            project,
            self.validator,
            snapshot,
            supplements,
        )
        # Simulate a confirmation created with an older AI/environment hash.
        analysis.source_hash = "legacy-confirmed-analysis".ljust(64, "0")
        analysis.save(update_fields=["source_hash"])
        confirm_analysis(
            analysis,
            self.validator,
            {},
            analysis.suggested_priority,
            "",
            [],
        )

        self.assertTrue(has_matching_confirmation(project, snapshot))
        changed_snapshot = deepcopy(snapshot)
        changed_snapshot["simplified_form"]["description"] = "The validator changed this project description."
        self.assertFalse(has_matching_confirmation(project, changed_snapshot))

    def test_content_editor_cannot_activate_rules(self):
        self.client.force_authenticate(self.editor)
        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": default_priority_rule_config()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(
        GROQ_ENABLED=True,
        GROQ_API_KEY="test-key",
        GROQ_PRIMARY_MODEL="llama-3.1-8b-instant",
        GROQ_BACKUP_MODEL="llama-3.3-70b-versatile",
    )
    def test_cms_reports_groq_provider_and_rebuilds_versioned_rag_context(self):
        high_project = Project.objects.create(
            name="Regional climate adaptation network",
            implementing_agency="DENR",
            agency="DENR",
            municipality="NCR",
            status="proposed",
            cost=500_000_000,
            budget=500_000_000,
            latitude=14.6,
            created_by=self.admin,
            profile_data={},
        )
        high_snapshot = {
            "simplified_form": {
                "projectActivity": "Regional climate adaptation network",
                "developmentSector": "Environment",
                "description": "Region-wide flood resilience and ecosystem restoration.",
                "location": "NCR",
                "status": "New",
            }
        }
        high_analysis = ProjectPriorityAnalysis.objects.create(
            project=high_project,
            validator=self.validator,
            rule_set=self.rule_set,
            source_hash=source_hash(high_snapshot, {}, self.rule_set),
            input_snapshot=high_snapshot,
            suggested_scores={"missing_facts": []},
            suggested_priority="high",
            base_score=91,
        )
        ProjectPriorityConfirmation.objects.create(
            analysis=high_analysis,
            validator=self.validator,
            final_priority="high",
        )
        self.client.force_authenticate(self.admin)

        workspace = self.client.get("/api/admin/cms/ai-scoring/")
        training = self.client.post("/api/admin/ai/models/train/", {}, format="json")
        rebuilt_workspace = self.client.get("/api/admin/cms/ai-scoring/")

        self.assertEqual(workspace.status_code, status.HTTP_200_OK)
        self.assertEqual(workspace.data["system_type"], "groq_rag_rules")
        self.assertEqual(workspace.data["ai_provider"]["name"], "groq")
        self.assertEqual(workspace.data["ai_provider"]["primary_model"], "llama-3.1-8b-instant")
        self.assertEqual(workspace.data["ai_provider"]["backup_model"], "llama-3.3-70b-versatile")
        self.assertEqual(workspace.data["ai_provider"]["historical_mode"], "versioned_rag_calibration")
        self.assertTrue(workspace.data["rag_pipeline"]["rules_primary"])
        self.assertFalse(workspace.data["rag_pipeline"]["hosted_model_fine_tuned"])
        self.assertTrue(
            workspace.data["training_dataset"]["requires_retraining"],
            workspace.data["training_dataset"],
        )
        self.assertEqual(training.status_code, status.HTTP_201_CREATED, training.data)
        self.assertIn("hosted Groq model was not fine-tuned", training.data["detail"])
        self.assertTrue(rebuilt_workspace.data["training_dataset"]["is_current"])
        self.assertFalse(rebuilt_workspace.data["training_dataset"]["requires_retraining"])
        self.assertEqual(
            rebuilt_workspace.data["rag_pipeline"]["reference_model_version"],
            training.data["model"]["version"],
        )

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
        self.assertEqual(active.algorithm_version, "expert-v3-contextual")
        stored_common = active.keyword_dictionaries["common_outcomes"][0]
        self.assertEqual(stored_common["match_mode"], "contextual")
        self.assertTrue(stored_common["description"])
        self.assertTrue(stored_common["matching_guidance"])
        self.assertTrue(stored_common["context_phrases"])
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

    def test_contextual_rules_do_not_score_an_incidental_keyword_without_sentence_support(self):
        self.client.force_authenticate(self.admin)
        activated = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {
                "config": default_priority_rule_config(),
                "change_note": "Require sentence-level context for outcome evidence.",
            },
            format="json",
        )
        self.assertEqual(activated.status_code, status.HTTP_201_CREATED, activated.data)

        common_rule = activated.data["active_rule_set"]["config"]["keyword_dictionaries"]["common_outcomes"][0]
        self.assertEqual(common_rule["match_mode"], "contextual")

        supplements = {
            "readinessLevel": "completed_documents",
            "gadResponsiveness": "gender_responsive",
            "spatialCoverageScope": "region_wide",
        }
        weak_snapshot = {
            "simplified_form": {
                "projectActivity": "Background reference",
                "developmentSector": "Social",
                "description": "Health appears in the background information.",
                "rdpMainChapter": "Unrelated planning chapter",
                "location": "NCR",
                "status": "New",
                "fundingRequirementByYear": {"2026": 100_000_000},
            }
        }
        strong_snapshot = deepcopy(weak_snapshot)
        strong_snapshot["simplified_form"]["description"] = (
            "The project will improve health access for families through new community clinics."
        )

        weak_analysis, _ = analyze_project(self.project, self.validator, weak_snapshot, supplements)
        strong_analysis, _ = analyze_project(self.project, self.validator, strong_snapshot, supplements)
        weak_criterion = next(
            item for item in weak_analysis.suggested_scores["rdp_outcomes"] if item["key"] == "capabilities"
        )
        strong_criterion = next(
            item for item in strong_analysis.suggested_scores["rdp_outcomes"] if item["key"] == "capabilities"
        )

        self.assertEqual(weak_criterion["raw"], 0)
        self.assertGreater(strong_criterion["raw"], weak_criterion["raw"])
        strong_reason = next(
            item for item in strong_analysis.suggested_scores["reasoning"]["criteria"]
            if item["key"] == "capabilities"
        )
        self.assertEqual(strong_reason["match_mode"], "contextual")
        self.assertIn("criterion intent", strong_reason["explanation"].lower())
        self.assertIn("cms matching guidance", strong_reason["explanation"].lower())
        self.assertTrue(strong_reason["evidence_sources"])

    def test_contextual_rule_requires_supporting_phrases(self):
        config = deepcopy(default_priority_rule_config())
        config["keyword_dictionaries"]["common_outcomes"][0]["context_phrases"] = []
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": config, "change_note": "Invalid contextual rule."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("supporting context phrase", response.data["detail"])

    def test_admin_cannot_activate_keyword_only_outcome_matching(self):
        config = deepcopy(default_priority_rule_config())
        config["sector_criteria"]["infrastructure"][0]["match_mode"] = "keyword"
        before = PriorityRuleSet.objects.count()
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": config, "change_note": "Attempt keyword-only matching."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must use contextual sentence matching", response.data["detail"])
        self.assertEqual(PriorityRuleSet.objects.count(), before)

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
