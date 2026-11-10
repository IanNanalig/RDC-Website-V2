"""Review status, form, and scoring links without changing project data by default."""

import json

from django.core.management.base import BaseCommand
from django.db import transaction

from projects.models import Project, ProjectPriorityAnalysis, ProjectRevision


ACTIVE_STATES = {
    "draft": Project.WORKFLOW_DRAFT,
    "submitted": Project.WORKFLOW_PENDING,
    "validator_draft": Project.WORKFLOW_PENDING,
    "reviewed": Project.WORKFLOW_NEEDS_REVISION,
}


class Command(BaseCommand):
    help = "Audit project workflow, form-version, and priority-analysis associations. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Repair only unambiguous active revision statuses.")

    def handle(self, *args, **options):
        findings = []
        repaired = 0
        with transaction.atomic():
            revisions = ProjectRevision.objects.select_related("project").order_by("project_id", "id")
            if options["apply"]:
                revisions = revisions.select_for_update(of=("self",))
            for revision in revisions.iterator():
                expected = ACTIVE_STATES.get(revision.state) if revision.revision_type == "progress_update" else None
                if expected and revision.workflow_status != expected:
                    evidence_present = (
                        revision.state == "draft"
                        or revision.state in {"submitted", "validator_draft"} and bool(revision.submitted_at)
                        or revision.state == "reviewed" and bool(revision.reviewed_at)
                    )
                    findings.append({
                        "kind": "active_revision_status", "project_id": revision.project_id,
                        "revision_id": revision.id, "stored": revision.workflow_status, "expected": expected,
                        "repairable": evidence_present,
                    })
                    if options["apply"] and evidence_present:
                        ProjectRevision.objects.filter(pk=revision.pk, workflow_status=revision.workflow_status).update(workflow_status=expected)
                        repaired += 1
                if revision.revision_type == "progress_update" and revision.state in ACTIVE_STATES:
                    profile = revision.profile_data_snapshot if isinstance(revision.profile_data_snapshot, dict) else {}
                    marker = profile.get("form_schema")
                    if not isinstance(marker, dict) or not marker.get("version"):
                        findings.append({
                            "kind": "active_revision_form_marker", "project_id": revision.project_id,
                            "revision_id": revision.id, "repairable": False,
                        })
            for project in Project.objects.only("id", "validated", "workflow_status").iterator():
                if project.validated and project.workflow_status != Project.WORKFLOW_VALIDATED:
                    findings.append({
                        "kind": "project_status_conflict", "project_id": project.id,
                        "stored": project.workflow_status, "validated": True, "repairable": False,
                    })
            for analysis in ProjectPriorityAnalysis.objects.filter(revision__isnull=False).select_related("revision").iterator():
                if analysis.project_id != analysis.revision.project_id:
                    findings.append({
                        "kind": "analysis_project_mismatch", "project_id": analysis.project_id,
                        "revision_id": analysis.revision_id, "analysis_id": analysis.id,
                        "repairable": False,
                    })
        self.stdout.write(json.dumps({
            "mode": "apply" if options["apply"] else "dry_run",
            "findings": findings, "repaired": repaired,
        }, sort_keys=True))
