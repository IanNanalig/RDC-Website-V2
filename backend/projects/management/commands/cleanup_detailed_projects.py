"""Safely remove legacy projects that were saved only in the retired detailed form."""

import hashlib
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.db.models import Q


SIMPLIFIED_MARKERS = {"", "simplified"}
DETAILED_FIELDS = {
    "projectTitle", "programOrProject", "projectCostRows", "totalProjectCost",
    "mainPdpChapter", "mainInfrastructureSector", "physicalFinancialStatus",
    "pipBudgetRows", "provincialRows", "expectedOutputIndicator",
}


def classify_profile(profile):
    """Classify only unmistakable formats; uncertainty must never trigger deletion."""
    if not isinstance(profile, dict) or not profile:
        return "ambiguous"
    marker = str(profile.get("submission_type") or "").strip().lower()
    has_simplified = isinstance(profile.get("simplified_form"), dict)
    if has_simplified:
        return "simplified" if marker in SIMPLIFIED_MARKERS else "ambiguous"
    if marker == "detailed":
        return "detailed"
    if marker == "simplified":
        return "ambiguous" if DETAILED_FIELDS.intersection(profile) else "simplified"
    if DETAILED_FIELDS.intersection(profile):
        return "detailed"
    return "ambiguous"


class Command(BaseCommand):
    help = "Dry-run by default; explicitly purge only unambiguous detailed-form projects and related AI data."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default", help="Django database alias (default: default)")
        parser.add_argument("--execute", action="store_true", help="Execute the deletion; dry-run is the default")
        parser.add_argument("--backup-confirmed", action="store_true", help="Confirm a current database backup exists")
        parser.add_argument("--confirm-plan", help="Fingerprint printed by the reviewed dry-run")

    def handle(self, *args, **options):
        alias = options["database"]
        if alias not in connections:
            raise CommandError(f"Unknown database alias: {alias}")
        plan = self._build_plan(alias)
        connection = connections[alias]
        config = connection.settings_dict
        self.stdout.write(f"Database: vendor={connection.vendor}; name={config.get('NAME')}")
        self._report(plan)
        if not options["execute"]:
            self.stdout.write(self.style.WARNING("DRY RUN ONLY. No records were changed."))
            self.stdout.write(f"Review fingerprint: {plan['fingerprint']}")
            return
        if not options["backup_confirmed"]:
            raise CommandError("Execution requires --backup-confirmed after taking a current database backup.")
        if not options.get("confirm_plan"):
            raise CommandError("Execution requires --confirm-plan with the reviewed dry-run fingerprint.")
        if plan["ambiguous"]:
            raise CommandError("Ambiguous project/revision/analysis records exist. No records were deleted; review them first.")
        if options["confirm_plan"] != plan["fingerprint"]:
            raise CommandError("The reviewed plan fingerprint no longer matches the database. Re-run and review the dry-run.")
        self._execute(alias, plan, options["confirm_plan"])
        self.stdout.write(self.style.SUCCESS("Detailed-form cleanup completed."))

    def _build_plan(self, alias):
        from ai_engine.models import AIModelTrainingRecord, AIProjectAnalysis, AITrainingRecord
        from projects.models import Project, ProjectPriorityAnalysis, ProjectRevision

        db = lambda model: model.objects.using(alias)
        target_projects, ambiguous = [], []
        for project in db(Project).all().only("id", "name", "profile_data").order_by("id"):
            kind = classify_profile(project.profile_data)
            if kind == "detailed":
                target_projects.append({"id": project.id, "title": project.name})
            elif kind == "ambiguous":
                ambiguous.append(f"project:{project.id}")
        project_ids = [item["id"] for item in target_projects]

        target_revisions = []
        for revision in db(ProjectRevision).exclude(project_id__in=project_ids).only(
            "id", "project_id", "profile_data_snapshot"
        ).order_by("id"):
            kind = classify_profile(revision.profile_data_snapshot)
            if kind == "detailed":
                target_revisions.append(revision.id)
            elif kind == "ambiguous":
                ambiguous.append(f"revision:{revision.id}")

        target_analyses = []
        for analysis in db(ProjectPriorityAnalysis).exclude(project_id__in=project_ids).only(
            "id", "project_id", "input_snapshot"
        ).order_by("id"):
            kind = classify_profile(analysis.input_snapshot)
            if kind == "detailed":
                target_analyses.append(analysis.id)
            elif kind == "ambiguous":
                ambiguous.append(f"priority_analysis:{analysis.id}")

        # All revisions/priority analyses attached to deleted projects are included.
        target_revision_ids = sorted(set(target_revisions) | set(
            db(ProjectRevision).filter(project_id__in=project_ids).values_list("id", flat=True)
        ))
        target_analysis_ids = sorted(set(target_analyses) | set(
            db(ProjectPriorityAnalysis).filter(project_id__in=project_ids).values_list("id", flat=True)
        ))
        training_ids = sorted(db(AITrainingRecord).filter(
            Q(project_id__in=project_ids) | Q(confirmation__analysis_id__in=target_analysis_ids)
        ).values_list("id", flat=True))
        contaminated_model_ids = sorted(set(db(AIModelTrainingRecord).filter(
            training_record_id__in=training_ids
        ).values_list("model_version_id", flat=True)))
        inference_ids = sorted(db(AIProjectAnalysis).filter(
            Q(priority_analysis_id__in=target_analysis_ids) | Q(model_version_id__in=contaminated_model_ids)
        ).values_list("id", flat=True))
        payload = {
            "projects": target_projects,
            "revisions": target_revision_ids,
            "priority_analyses": target_analysis_ids,
            "training_records": training_ids,
            "model_versions": contaminated_model_ids,
            "inferences": inference_ids,
            "ambiguous": sorted(ambiguous),
        }
        payload["fingerprint"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        return payload

    def _report(self, plan):
        self.stdout.write("Candidate records (no changes made):")
        for key in ("projects", "revisions", "priority_analyses", "training_records", "model_versions", "inferences"):
            value = plan[key]
            self.stdout.write(f"  {key}: {len(value)}")
            if key == "projects":
                for item in value:
                    self.stdout.write(f"    project {item['id']}: {item['title']}")
        self.stdout.write(f"  ambiguous: {len(plan['ambiguous'])}")
        for item in plan["ambiguous"]:
            self.stdout.write(f"    {item}")

    def _execute(self, alias, reviewed_plan, fingerprint):
        from ai_engine.models import (
            AIModelTrainingRecord, AIModelVersion, AIProjectAnalysis, AISimilarProject, AITrainingRecord,
        )
        from projects.models import (
            AuditTrail, Notification, Project, ProjectPriorityAnalysis, ProjectRevision, UserActivity,
        )

        db = lambda model: model.objects.using(alias)
        with transaction.atomic(using=alias):
            # Lock source and dependent rows while the target set is recalculated and removed.
            for model in (Project, ProjectRevision, ProjectPriorityAnalysis, AITrainingRecord, AIModelVersion):
                list(db(model).select_for_update().values_list("pk", flat=True))
            # Recompute while holding the write transaction and refuse changed targets.
            current = self._build_plan(alias)
            if current["fingerprint"] != fingerprint or current["ambiguous"]:
                raise CommandError("Database targets changed or are ambiguous; transaction cancelled without deletion.")
            project_ids = [row["id"] for row in current["projects"]]
            analysis_ids = current["priority_analyses"]
            training_ids = current["training_records"]
            inference_ids = current["inferences"]
            model_ids = current["model_versions"]

            # Preserve independent activity records and detach them before project deletion.
            activities = db(UserActivity).filter(project_id__in=project_ids)
            for activity in activities.only("id", "project_id", "project_title_snapshot"):
                title = next((row["title"] for row in current["projects"] if row["id"] == activity.project_id), "")
                activity.project_title_snapshot = activity.project_title_snapshot or title
                activity.project = None
                activity.save(update_fields=["project", "project_title_snapshot"], using=alias)
            for entry in db(AuditTrail).filter(project_id__in=project_ids).only("id", "project_id", "detail"):
                title = next((row["title"] for row in current["projects"] if row["id"] == entry.project_id), "")
                if title and title not in (entry.detail or ""):
                    entry.detail = f"{entry.detail}\nProject title at cleanup: {title}".strip()
                    entry.save(update_fields=["detail"], using=alias)
                entry.project = None
                entry.save(update_fields=["project"], using=alias)
            db(Notification).filter(project_id__in=project_ids).delete()

            db(AISimilarProject).filter(
                Q(analysis_id__in=inference_ids) | Q(training_record_id__in=training_ids)
            ).delete()
            db(AIModelTrainingRecord).filter(
                Q(training_record_id__in=training_ids) | Q(model_version_id__in=model_ids)
            ).delete()
            db(AIProjectAnalysis).filter(pk__in=inference_ids).delete()
            db(AIModelVersion).filter(pk__in=model_ids).delete()
            db(AITrainingRecord).filter(pk__in=training_ids).delete()
            db(ProjectPriorityAnalysis).filter(pk__in=analysis_ids).delete()
            db(ProjectRevision).filter(pk__in=current["revisions"]).delete()
            db(Project).filter(pk__in=project_ids).delete()

