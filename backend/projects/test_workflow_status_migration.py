from importlib import import_module

from django.apps import apps
from django.db import transaction
from django.test import TestCase

from .models import Project, ProjectRevision

backfill_workflow = import_module("projects.migrations.0057_project_workflow_status").backfill_workflow


class WorkflowStatusBackfillTests(TestCase):
    def project(self, name, *, status="planning", validated=False, review=None):
        profile = {"validator_review": review} if review else {}
        return Project.objects.create(
            name=name, implementing_agency="DPWH", municipality="NCR",
            status=status, validated=validated, cost=0, latitude=14.5,
            agency="DPWH", profile_data=profile,
        )

    def test_legacy_project_and_revision_states_are_mapped_without_rewriting_history(self):
        draft = self.project("Draft")
        pending = self.project("Pending", status="proposed")
        returned = self.project("Returned", status="proposed", review={"review_status": "reviewed", "review_notes": "Fix the location"})
        validated = self.project("Validated", status="ongoing", validated=True)
        revision = ProjectRevision.objects.create(project=validated, revision_number=1, revision_type="progress_update", state="reviewed")

        backfill_workflow(apps, None)

        for project, expected in ((draft, "draft"), (pending, "pending_validation"), (returned, "needs_revision"), (validated, "validated")):
            project.refresh_from_db()
            self.assertEqual(project.workflow_status, expected)
        revision.refresh_from_db()
        self.assertEqual(revision.workflow_status, "needs_revision")
        self.assertEqual(returned.profile_data["validator_review"]["review_notes"], "Fix the location")

    def test_ambiguous_legacy_project_aborts_atomic_backfill(self):
        clear = self.project("Clear")
        ambiguous = self.project("Ambiguous", status="completed")
        clear.workflow_status = "needs_revision"
        clear.save(update_fields=["workflow_status"])
        with self.assertRaisesMessage(RuntimeError, str(ambiguous.pk)):
            with transaction.atomic():
                backfill_workflow(apps, None)
        clear.refresh_from_db()
        self.assertEqual(clear.workflow_status, "needs_revision")
