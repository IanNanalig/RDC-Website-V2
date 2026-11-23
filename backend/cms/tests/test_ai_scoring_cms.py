from copy import deepcopy
from unittest.mock import patch

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
                "program": "Metro Manila Flood Resilience Program",
                "objective": "Reduce flooding and protect regional mobility.",
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

    def test_historical_references_search_is_paginated_and_admin_only(self):
        url = "/api/admin/cms/ai-scoring/historical-references/"
        ProjectPriorityConfirmation.objects.bulk_create([
            ProjectPriorityConfirmation(analysis=self.analysis, validator=self.validator, final_priority="low")
            for _ in range(10)
        ])
        self.client.force_authenticate(self.admin)
        response = self.client.get(url, {"q": "Infrastructure"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 11)
        self.assertEqual(response.data["total_pages"], 2)
        self.assertEqual(len(response.data["results"]), 10)
        last_page = self.client.get(url, {"q": "Infrastructure", "page": 2})
        self.assertEqual(last_page.data["page"], 2)
        self.assertIsNone(last_page.data["next"])
        self.assertEqual([row["confirmation_id"] for row in last_page.data["results"]], [self.confirmation.pk])
        self.assertEqual(self.client.get(url, {"q": "nonmatching value"}).data["count"], 0)
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_rule_history_workspace_first_page_matches_paginated_endpoint(self):
        PriorityRuleSet.objects.bulk_create([
            PriorityRuleSet(version=f"paginated-version-{number}", status=PriorityRuleSet.STATUS_SUPERSEDED, is_active=False)
            for number in range(10)
        ])
        self.client.force_authenticate(self.admin)
        url = "/api/admin/cms/ai-scoring/versions/"
        workspace = self.client.get("/api/admin/cms/ai-scoring/", {"limit": 0})
        first = self.client.get(url)
        second = self.client.get(url, {"page": 2})
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["total_pages"], 2)
        self.assertEqual(workspace.data["rule_versions_total_pages"], first.data["total_pages"])
        self.assertEqual(workspace.data["rule_versions"], first.data["results"])
        self.assertEqual(len(first.data["results"]), 10)
        self.assertEqual(len(second.data["results"]), 1)
        self.assertNotIn(second.data["results"][0]["id"], {row["id"] for row in first.data["results"]})
        self.assertIsNone(second.data["next"])

    def test_invalid_scoring_limits_are_rejected_on_save_preview_and_activation(self):
        self.client.force_authenticate(self.admin)
        url = "/api/admin/cms/ai-scoring/drafts/"
        config = default_priority_rule_config()
        config["thresholds"]["high"] = 101
        self.assertEqual(self.client.post(url, {"config": config}, format="json").status_code, 400)
        config["thresholds"]["high"] = 100
        saved = self.client.post(url, {"config": config, "change_note": "Test a valid high threshold."}, format="json")
        self.assertEqual(saved.status_code, 201, saved.data)
        draft_id = saved.data["draft_rule_set"]["id"]
        config["thresholds"]["pap_weights"]["readiness"] = 101
        self.assertEqual(self.client.patch(f"{url}{draft_id}/", {"config": config}, format="json").status_code, 400)
        draft = PriorityRuleSet.objects.get(pk=draft_id)
        draft.thresholds["high"] = 101
        draft.save(update_fields=["thresholds"])
        for action in ("preview", "publish"):
            result = self.client.post(f"{url}{draft_id}/{action}/", {"project_id": self.project.pk}, format="json")
            self.assertEqual(result.status_code, 400, result.data)
            self.assertIn("High-priority threshold", result.data["detail"])
        self.rule_set.refresh_from_db()
        self.assertTrue(self.rule_set.is_active)

    def test_whole_number_weights_and_required_notes_are_enforced_on_api(self):
        self.client.force_authenticate(self.admin)
        path = "/api/admin/cms/ai-scoring/"
        config = default_priority_rule_config()
        self.assertEqual(self.client.post(path + "drafts/", {"config": config, "change_note": " "}, format="json").status_code, 400)
        for weight in (0, 0.5, 1.5, -1, 101):
            invalid = deepcopy(config)
            common = invalid["keyword_dictionaries"]["common_outcomes"]
            common[1]["weight"] += common[0]["weight"] - weight
            common[0]["weight"] = weight
            for endpoint in (path, path + "drafts/"):
                result = self.client.post(endpoint, {"config": invalid, "change_note": "Check weights."}, format="json")
                self.assertEqual(result.status_code, 400, result.data)
                self.assertIn("whole number from 1 to 100", result.data["detail"])
        common = config["keyword_dictionaries"]["common_outcomes"]
        common[1]["weight"] += common[0]["weight"] - 1
        common[0]["weight"] = 1
        saved = self.client.post(path + "drafts/", {"config": config, "change_note": "Set a whole-number weight."}, format="json")
        self.assertEqual(saved.status_code, 201, saved.data)
        draft_id = saved.data["draft_rule_set"]["id"]
        activation = self.client.post(path + f"drafts/{draft_id}/publish/", {}, format="json")
        self.assertEqual(activation.status_code, 200, activation.data)
        self.assertEqual(activation.data["rule_versions"][0]["change_note"], "Set a whole-number weight.")

    def test_history_compares_keyed_rules_and_restores_as_a_new_version(self):
        self.client.force_authenticate(self.admin)
        path = "/api/admin/cms/ai-scoring/"
        original = deepcopy(self.rule_set.keyword_dictionaries)
        config = default_priority_rule_config()
        config["thresholds"]["high"] = 82
        outcomes = config["keyword_dictionaries"]["common_outcomes"]
        outcomes[0]["matching_guidance"] = "Preserve this custom evaluation instruction."
        extra = deepcopy(outcomes[0])
        extra.update(key="custom_review", label="Additional review", weight=1)
        outcomes[0]["weight"] -= 1
        outcomes.append(extra)
        published = self.client.post(path, {"config": config, "change_note": "Changed the threshold and outcome guidance."}, format="json")
        self.assertEqual(published.status_code, 201, published.data)
        current = published.data["active_rule_set"]["id"]
        self.assertEqual(published.data["active_rule_set"]["draft_config"]["keyword_dictionaries"]["common_outcomes"][0]["matching_guidance"], outcomes[0]["matching_guidance"])
        versions = self.client.get(path + "versions/")
        self.assertEqual(versions.status_code, 200)
        self.assertEqual(versions.data["results"][0]["activated_by"], self.admin.username)
        self.assertEqual(versions.data["results"][0]["change_note"], "Changed the threshold and outcome guidance.")
        details = self.client.get(path + f"versions/{current}/")
        changes = {tuple(change["path"]): change for change in details.data["changes"]}
        self.assertEqual(changes["thresholds", "high"]["after"], 82)
        self.assertEqual(changes["keyword_dictionaries", "common_outcomes", "custom_review"]["kind"], "added")
        self.assertEqual(changes["keyword_dictionaries", "common_outcomes", outcomes[0]["key"], "matching_guidance"]["after"], outcomes[0]["matching_guidance"])
        old_draft = self.client.post(path + "drafts/", {"config": config, "change_note": "Keep this draft."}, format="json").data["draft_rule_set"]["id"]
        restore = path + f"versions/{self.rule_set.pk}/restore/"
        payload = {"expected_active_id": current, "change_note": "Restore the original scoring rules."}
        self.client.force_authenticate(self.editor)
        self.assertEqual(self.client.post(restore, payload, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        restored = self.client.post(restore, payload, format="json")
        self.assertEqual(restored.status_code, 201, restored.data)
        self.assertEqual(restored.data["result"], "restored")
        new = PriorityRuleSet.objects.get(pk=restored.data["rule_set"]["id"])
        self.assertEqual(new.restored_from_id, self.rule_set.pk)
        self.assertEqual(new.based_on_id, current)
        self.assertEqual(new.keyword_dictionaries, original)
        self.assertEqual(PriorityRuleSet.objects.get(pk=old_draft).status, "draft")
        self.assertEqual(self.client.post(path + f"drafts/{old_draft}/publish/", {}, format="json").status_code, 409)
        draft_path = path + f"drafts/{old_draft}/"
        self.assertEqual(self.client.patch(draft_path, {
            "config": config, "change_note": "Stale active version.", "expected_active_id": current,
        }, format="json").status_code, 409)
        rebased = self.client.patch(draft_path, {
            "config": config, "change_note": "Reviewed against the restored version.", "expected_active_id": new.pk,
        }, format="json")
        self.assertEqual(rebased.status_code, 200, rebased.data)
        self.assertEqual(rebased.data["draft_rule_set"]["based_on"], new.pk)
        self.assertEqual(self.client.post(restore, payload, format="json").status_code, 409)
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.rule_set_id, self.rule_set.id)
        self.assertEqual(self.confirmation.final_priority, "low")

    def test_zero_weight_history_opens_repair_draft_without_activating(self):
        self.client.force_authenticate(self.admin)
        path = "/api/admin/cms/ai-scoring/"
        config = default_priority_rule_config()
        common = config["keyword_dictionaries"]["common_outcomes"]
        common[1]["weight"] += common[0]["weight"]
        common[0]["weight"] = 0
        legacy = PriorityRuleSet.objects.create(version="legacy-zero", status="superseded", **config)
        response = self.client.post(path + f"versions/{legacy.pk}/restore/", {
            "expected_active_id": self.rule_set.pk, "change_note": "Review the old weighting.",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["result"], "repair_draft")
        self.assertIn("whole number from 1 to 100", response.data["issues"][0])
        draft = PriorityRuleSet.objects.get(pk=response.data["rule_set"]["id"])
        self.assertEqual(draft.restored_from, legacy)
        self.assertEqual(draft.keyword_dictionaries, legacy.keyword_dictionaries)
        self.assertEqual(get_active_priority_rule_set().pk, self.rule_set.pk)
        self.assertEqual(self.client.post(path + f"drafts/{draft.pk}/publish/", {}, format="json").status_code, 400)
        corrected = self.client.patch(path + f"drafts/{draft.pk}/", {
            "config": default_priority_rule_config(), "change_note": "Correct the legacy weight.",
        }, format="json")
        self.assertEqual(corrected.status_code, 200, corrected.data)
        self.assertEqual(self.client.post(path + f"drafts/{draft.pk}/publish/", {}, format="json").status_code, 200)
        legacy.refresh_from_db()
        self.assertEqual(legacy.keyword_dictionaries["common_outcomes"][0]["weight"], 0)

    @override_settings(GROQ_ENABLED=False)
    def test_maximum_ai_score_rounds_the_total_once(self):
        config = default_priority_rule_config()
        config["thresholds"]["high"] = 100
        config["thresholds"]["pap_weights"] = {
            "readiness": 33.335, "gad_responsiveness": 33.335, "spatial_coverage": 33.33,
        }
        for group in [config["keyword_dictionaries"]["common_outcomes"], *config["sector_criteria"].values()]:
            for criterion in group:
                criterion["weight"] = 0
        rules = PriorityRuleSet.objects.create(version="fractional-weights", **config)
        with (
            patch("projects.priority_scoring._scale_rating", return_value=(10, "Maximum rating")),
            patch("projects.priority_scoring._spatial_rating", return_value=(10, "Maximum rating")),
        ):
            result, _ = analyze_project(self.project, self.validator, self.snapshot, rule_set=rules, persist=False)
        self.assertGreater(sum(item["score"] for item in result["suggested_scores"]["pap"]), 100)
        self.assertEqual(result["base_score"], 100)
        self.assertEqual(result["suggested_scores"]["base_total"], 100)

    @override_settings(GROQ_ENABLED=False)
    def test_cms_explains_controlled_learning_and_lists_training_projects(self):
        self.client.force_authenticate(self.editor)
        denied = self.client.get("/api/admin/cms/ai-scoring/")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
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
                "program": "Metro Manila Flood Resilience Program",
                "objective": "Reduce flood exposure and improve drainage capacity.",
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

    def test_draft_preview_is_non_destructive_and_activation_versions_the_rules(self):
        self.client.force_authenticate(self.admin)
        before_analysis_count = ProjectPriorityAnalysis.objects.count()
        self.project.profile_data = self.snapshot
        self.project.save(update_fields=["profile_data"])

        created = self.client.post(
            "/api/admin/cms/ai-scoring/drafts/",
            {"config": default_priority_rule_config(), "change_note": "Review the current scorecard before activation."},
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        draft_id = created.data["draft_rule_set"]["id"]
        self.assertEqual(created.data["draft_rule_set"]["status"], "draft")

        preview = self.client.post(
            f"/api/admin/cms/ai-scoring/drafts/{draft_id}/preview/",
            {"project_id": self.project.pk},
            format="json",
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertEqual(preview.data["status"], "incomplete")
        self.assertFalse(preview.data["input_preflight"]["can_evaluate"])
        self.assertEqual(ProjectPriorityAnalysis.objects.count(), before_analysis_count)

        published = self.client.post(
            f"/api/admin/cms/ai-scoring/drafts/{draft_id}/publish/", {}, format="json",
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK, published.data)
        draft = PriorityRuleSet.objects.get(pk=draft_id)
        self.assertTrue(draft.is_active)
        self.assertEqual(draft.status, PriorityRuleSet.STATUS_ACTIVE)
        self.rule_set.refresh_from_db()
        self.assertEqual(self.rule_set.status, PriorityRuleSet.STATUS_SUPERSEDED)

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
        self.assertEqual(active.thresholds["high"], 70)
        self.assertEqual(active.thresholds["regional_project_cost"], 300_000_000)
        self.assertIn("cost", active.thresholds["regional_criteria"])
        self.assertEqual(active.algorithm_version, "expert-v4-regional-eligibility")
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

    @override_settings(GROQ_ENABLED=False)
    def test_regional_budget_rule_skips_scorecard_and_forces_low_below_cutoff(self):
        supplements = {
            "readinessLevel": "completed_documents",
            "gadResponsiveness": "gender_responsive",
            "spatialCoverageScope": "region_wide",
            "beneficiaryCount": "100",
            "regionalSpatialCategory": "region_wide",
            "contributedOutcomeCount": "2",
        }
        with patch("projects.priority_scoring._priority_for", return_value="high"):
            below = deepcopy(self.snapshot)
            below["simplified_form"]["fundingRequirementByYear"] = {"2026": 199_999_999}
            below_analysis, _ = analyze_project(self.project, self.validator, below, supplements)
            self.assertGreaterEqual(float(below_analysis.base_score), 0)
            self.assertEqual(below_analysis.suggested_priority, "low")
            self.assertFalse(below_analysis.regional_scorecard["applicable"])
            self.assertEqual(below_analysis.regional_scorecard["criteria"], [])
            self.assertTrue(below_analysis.suggested_scores["budget_priority_override"]["applied"])

            at_cutoff = deepcopy(self.snapshot)
            at_cutoff["simplified_form"]["fundingRequirementByYear"] = {"2026": 200_000_000}
            exact_analysis, _ = analyze_project(self.project, self.validator, at_cutoff, supplements)
            self.assertTrue(exact_analysis.regional_scorecard["applicable"])
            self.assertEqual(exact_analysis.suggested_priority, "high")
            self.assertFalse(exact_analysis.suggested_scores["budget_priority_override"]["applied"])

            above = deepcopy(self.snapshot)
            above["simplified_form"]["fundingRequirementByYear"] = {"2026": 200_000_001}
            above_analysis, _ = analyze_project(self.project, self.validator, above, supplements)
            self.assertTrue(above_analysis.regional_scorecard["applicable"])
            self.assertEqual(above_analysis.suggested_priority, "high")

    def test_draft_hierarchy_rejects_equal_and_reversed_adjacent_levels(self):
        self.client.force_authenticate(self.admin)
        url = "/api/admin/cms/ai-scoring/drafts/"
        config = default_priority_rule_config()
        regional = config["thresholds"]["regional_criteria"]
        spatial = regional["spatial_coverage"]["scores"]
        spatial["region_wide"] = 9
        config["keyword_dictionaries"]["readiness"].reverse()
        saved = self.client.post(url, {"config": config, "change_note": "Test valid rank ordering."}, format="json")
        self.assertEqual(saved.status_code, 201, saved.data)
        draft = PriorityRuleSet.objects.get(pk=saved.data["draft_rule_set"]["id"])
        self.assertEqual(draft.thresholds["regional_criteria"]["spatial_coverage"]["scores"]["region_wide"], 9)

        for values, key, invalid, expected in (
            (spatial, "eight_to_twelve_lgus", 10, "Region-wide (9)"),
            (spatial, "eight_to_twelve_lgus", 9, "8–12 LGUs (9)"),
            (regional["outcome_contribution"]["thresholds"], "at_least_3", 6, "Level 4 (5)"),
            (regional["outcome_contribution"]["thresholds"], "at_least_3", 5, "Level 3 (5)"),
            (regional["outcome_contribution"]["scores"], "at_least_5", 10, "RDP outcome scores"),
            (regional["cost"]["scores"], "over_3b", 10, "Regional cost scores"),
            (regional["beneficiaries"]["scores"], "over_1m", 10, "Beneficiary scores"),
            (config["keyword_dictionaries"]["readiness"][0], "raw", 3, "Readiness scores"),
            (config["keyword_dictionaries"]["gad"][1], "raw", 10, "GAD responsiveness scores"),
            (config["keyword_dictionaries"]["outcome_rating"], "chapter_or_three_keywords", 10, "Text-matching scores"),
        ):
            previous = values[key]
            with self.subTest(key=key, invalid=invalid):
                values[key] = invalid
                response = self.client.patch(f"{url}{draft.pk}/", {"config": config}, format="json")
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(expected, response.data["detail"])
                values[key] = previous

        # A legacy draft already in storage must pass the same checks before use.
        draft.thresholds["regional_criteria"]["spatial_coverage"]["scores"]["region_wide"] = 10
        draft.save(update_fields=["thresholds"])
        for action in ("preview", "publish"):
            result = self.client.post(f"{url}{draft.pk}/{action}/", {"project_id": self.project.pk}, format="json")
            self.assertEqual(result.status_code, 400, result.data)
            self.assertIn("Region-wide (10)", result.data["detail"])

    @override_settings(GROQ_ENABLED=False)
    def test_saved_outcome_threshold_drives_preview_and_new_analyses(self):
        self.client.force_authenticate(self.admin)
        self.snapshot["simplified_form"]["fundingRequirementByYear"] = {"2026": 500_000_000}
        self.project.profile_data = self.snapshot
        self.project.save(update_fields=["profile_data"])
        config = default_priority_rule_config()
        config["thresholds"]["regional_criteria"]["outcome_contribution"]["thresholds"]["at_least_7"] = 11
        url = "/api/admin/cms/ai-scoring/drafts/"
        saved = self.client.post(url, {"config": config, "change_note": "Test the updated outcome threshold."}, format="json")
        self.assertEqual(saved.status_code, 201, saved.data)
        draft_id = saved.data["draft_rule_set"]["id"]
        draft = self.client.get(f"{url}{draft_id}/")
        self.assertEqual(draft.data["config"]["thresholds"]["regional_criteria"]["outcome_contribution"]["thresholds"]["at_least_7"], 11)
        preview = self.client.post(f"{url}{draft_id}/preview/", {"project_id": self.project.pk}, format="json")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["regional_outcome_bands"][0]["label"], "At least 11 outcomes")
        published = self.client.post(f"{url}{draft_id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)

        with patch("ai_engine.groq_priority.analyze_priority_with_groq", return_value=None) as groq:
            for count, expected_score, expected_label in ((10, 8, "At least 5 outcomes"), (11, 10, "At least 11 outcomes")):
                supplements = {
                    "readinessLevel": "completed_documents", "gadResponsiveness": "gender_responsive",
                    "spatialCoverageScope": "region_wide", "beneficiaryCount": "100",
                    "regionalSpatialCategory": "region_wide", "contributedOutcomeCount": str(count),
                }
                analysis, _ = analyze_project(self.project, self.validator, self.snapshot, supplements)
                row = next(row for row in analysis.regional_scorecard["criteria"] if row["key"] == "regional_outcomes")
                self.assertEqual(row["raw"], expected_score)
                self.assertIn(expected_label, row["remarks"])
                self.assertEqual(analysis.rule_set_id, draft_id)
                self.assertLessEqual(analysis.base_score, 100)
            context = groq.call_args.kwargs["regional_context"]
            self.assertEqual(context["bands"]["outcome_contribution"][0]["minimum"], 11)
        self.analysis.refresh_from_db()
        self.confirmation.refresh_from_db()
        self.assertEqual(self.analysis.base_score, 65)
        self.assertEqual(self.analysis.rule_set_id, self.rule_set.pk)
        self.assertEqual(self.confirmation.final_priority, "low")

    def test_admin_can_version_regional_criteria_bands_and_invalid_order_is_rejected(self):
        config = deepcopy(default_priority_rule_config())
        config["thresholds"]["regional_criteria"]["cost"]["thresholds"]["at_least_5b"] = 6_000_000_000
        config["thresholds"]["regional_criteria"]["spatial_coverage"]["scores"]["region_wide"] = 9
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": config, "change_note": "Update regional scorecard bands."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        active = PriorityRuleSet.objects.get(is_active=True)
        self.assertEqual(active.thresholds["high"], 70)
        self.assertEqual(active.thresholds["regional_criteria"]["cost"]["thresholds"]["at_least_5b"], 6_000_000_000)
        self.assertEqual(active.thresholds["regional_criteria"]["spatial_coverage"]["scores"]["region_wide"], 9)

        invalid = deepcopy(response.data["active_rule_set"]["config"])
        invalid["thresholds"]["regional_criteria"]["cost"]["thresholds"]["at_least_5b"] = 100
        before = PriorityRuleSet.objects.count()
        rejected = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": invalid, "change_note": "Invalid threshold order."},
            format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("thresholds must decrease", rejected.data["detail"])
        self.assertEqual(PriorityRuleSet.objects.count(), before)

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

    def test_binary_priority_boundary_can_be_changed(self):
        config = deepcopy(default_priority_rule_config())
        config["thresholds"]["high"] = 80
        before = PriorityRuleSet.objects.count()
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/admin/cms/ai-scoring/",
            {"config": config, "change_note": "Attempted threshold change."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(PriorityRuleSet.objects.count(), before + 1)
