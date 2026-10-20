from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ai_engine.models import (
    AIModelTrainingRecord,
    AIModelVersion,
    AIProjectAnalysis,
    AISimilarProject,
    AITrainingRecord,
)
from projects.management.commands.cleanup_detailed_projects import classify_profile
from projects.models import (
    AuditTrail,
    Notification,
    PriorityRuleSet,
    Project,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    ProjectRevision,
    User,
    UserActivity,
)


class DetailedProjectCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cleanup-user", email="cleanup@example.test", password="test-password", role="staff"
        )

    def _project(self, title, profile):
        return Project.objects.create(
            name=title,
            implementing_agency="DENR",
            municipality="NCR",
            status="proposed",
            cost=100,
            latitude=14.5,
            agency="DENR",
            created_by=self.user,
            profile_data=profile,
        )

    def _plan(self):
        output = StringIO()
        call_command("cleanup_detailed_projects", stdout=output)
        return output.getvalue()

    def test_classifier_fails_closed_for_unknown_or_contradictory_profiles(self):
        self.assertEqual(classify_profile({"submission_type": "detailed", "projectTitle": "Old"}), "detailed")
        self.assertEqual(classify_profile({"simplified_form": {"projectActivity": "New"}}), "simplified")
        self.assertEqual(classify_profile({"submission_type": "simplified", "projectActivity": "Legacy simple"}), "simplified")
        self.assertEqual(classify_profile({}), "ambiguous")
        self.assertEqual(
            classify_profile({"submission_type": "detailed", "simplified_form": {"projectActivity": "Conflict"}}),
            "ambiguous",
        )

    def test_dry_run_reports_candidates_and_never_deletes(self):
        legacy = self._project("Legacy detailed", {"submission_type": "detailed", "projectTitle": "Legacy detailed"})
        self._project("Current simplified", {"submission_type": "simplified", "simplified_form": {"projectActivity": "Current"}})
        output = self._plan()
        self.assertIn(f"project {legacy.id}: Legacy detailed", output)
        self.assertIn("DRY RUN ONLY", output)
        self.assertEqual(Project.objects.count(), 2)

    def test_ambiguous_records_abort_execution_without_deleting_anything(self):
        legacy = self._project("Legacy detailed", {"submission_type": "detailed", "projectTitle": "Legacy detailed"})
        ambiguous = self._project("Unknown old record", {})
        output = self._plan()
        fingerprint = output.split("Review fingerprint: ", 1)[1].strip()
        with self.assertRaises(CommandError):
            call_command(
                "cleanup_detailed_projects",
                execute=True,
                backup_confirmed=True,
                confirm_plan=fingerprint,
                stdout=StringIO(),
            )
        self.assertTrue(Project.objects.filter(pk=legacy.pk).exists())
        self.assertTrue(Project.objects.filter(pk=ambiguous.pk).exists())

    def test_execute_removes_related_records_and_preserves_audit_history(self):
        project = self._project("Legacy detailed", {"submission_type": "detailed", "projectTitle": "Legacy detailed"})
        simplified_project = self._project(
            "Keep simplified",
            {"submission_type": "simplified", "simplified_form": {"projectActivity": "Keep simplified"}},
        )
        ProjectRevision.objects.create(
            project=project,
            revision_number=1,
            revision_type="initial_submission",
            profile_data_snapshot={"submission_type": "detailed", "projectTitle": "Legacy detailed"},
        )
        activity = UserActivity.objects.create(
            user=self.user,
            actor_username=self.user.username,
            role="staff",
            event="project_update",
            project=project,
        )
        audit = AuditTrail.objects.create(actor=self.user, project=project, action="update", detail="Updated legacy project")
        notification = Notification.objects.create(
            recipient=self.user,
            project=project,
            event_type="project_updated",
            title="Project updated",
        )
        rules = PriorityRuleSet.objects.create(version="cleanup-test", is_active=False)
        analysis = ProjectPriorityAnalysis.objects.create(
            project=project,
            validator=self.user,
            rule_set=rules,
            source_hash="a" * 64,
            input_snapshot={"submission_type": "detailed", "projectTitle": "Legacy detailed"},
            suggested_priority="low",
        )
        confirmation = ProjectPriorityConfirmation.objects.create(
            analysis=analysis,
            validator=self.user,
            final_priority="low",
        )
        training = AITrainingRecord.objects.create(
            confirmation=confirmation,
            project=project,
            rule_set=rules,
            feature_schema_version="old",
            target_priority="low",
            source_hash="b" * 64,
        )
        model = AIModelVersion.objects.create(
            version="cleanup-model",
            feature_schema_version="old",
            dataset_version="c" * 64,
            sample_count=1,
            class_labels=["low", "high"],
            feature_names=[],
            parameters={},
        )
        AIModelTrainingRecord.objects.create(model_version=model, training_record=training)
        inference = AIProjectAnalysis.objects.create(
            priority_analysis=analysis,
            guideline_rule_set=rules,
            model_version=model,
            inference_version="old-inference",
            feature_schema_version="old",
            status="ready",
        )
        AISimilarProject.objects.create(analysis=inference, training_record=training, rank=1)

        output = self._plan()
        fingerprint = output.split("Review fingerprint: ", 1)[1].strip()
        call_command(
            "cleanup_detailed_projects",
            execute=True,
            backup_confirmed=True,
            confirm_plan=fingerprint,
            stdout=StringIO(),
        )

        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
        self.assertTrue(Project.objects.filter(pk=simplified_project.pk).exists())
        self.assertFalse(ProjectRevision.objects.filter(project_id=project.pk).exists())
        self.assertFalse(ProjectPriorityAnalysis.objects.filter(pk=analysis.pk).exists())
        self.assertFalse(AITrainingRecord.objects.filter(pk=training.pk).exists())
        self.assertFalse(AIModelVersion.objects.filter(pk=model.pk).exists())
        self.assertFalse(AIProjectAnalysis.objects.filter(pk=inference.pk).exists())
        self.assertEqual(AISimilarProject.objects.count(), 0)
        activity.refresh_from_db()
        audit.refresh_from_db()
        self.assertIsNone(activity.project_id)
        self.assertEqual(activity.project_title_snapshot, "Legacy detailed")
        self.assertIsNone(audit.project_id)
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())
        self.assertTrue(UserActivity.objects.filter(pk=activity.pk).exists())
        self.assertTrue(AuditTrail.objects.filter(pk=audit.pk).exists())

        second_dry_run = self._plan()
        self.assertIn("projects: 0", second_dry_run)
        self.assertTrue(Project.objects.filter(pk=simplified_project.pk).exists())

