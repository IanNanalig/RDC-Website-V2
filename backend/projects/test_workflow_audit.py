import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from projects.models import Project, ProjectRevision


class WorkflowAuditTests(TestCase):
    def test_dry_run_preserves_rows_and_apply_repairs_only_active_revision_status(self):
        project = Project.objects.create(
            name="Audit fixture", implementing_agency="DPWH", municipality="NCR",
            status="ongoing", validated=True, cost=1, latitude=14.5,
            agency="DPWH", budget=1,
        )
        revision = ProjectRevision.objects.create(
            project=project, revision_number=1, revision_type="progress_update",
            state="submitted", submitted_at=timezone.now(),
            profile_data_snapshot={"form_schema": {"key": "simplified-rdip", "version": 1}},
        )
        ProjectRevision.objects.filter(pk=revision.pk).update(workflow_status=Project.WORKFLOW_DRAFT)
        output = StringIO()
        call_command("audit_project_workflows", stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["repaired"], 0)
        self.assertEqual(report["findings"][0]["kind"], "active_revision_status")
        revision.refresh_from_db()
        self.assertEqual(revision.workflow_status, Project.WORKFLOW_DRAFT)

        output = StringIO()
        call_command("audit_project_workflows", "--apply", stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["repaired"], 1)
        revision.refresh_from_db()
        self.assertEqual(revision.workflow_status, Project.WORKFLOW_PENDING)
        output = StringIO()
        call_command("audit_project_workflows", "--apply", stdout=output)
        self.assertEqual(json.loads(output.getvalue())["repaired"], 0)
