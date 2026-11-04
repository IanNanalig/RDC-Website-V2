"""Safely recover uploaded documents stranded before AI processing completed."""

from datetime import timedelta
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from projects.models import ProjectAIProcessingEvent, ProjectAIProcessingJob, ProjectSupportingDocument


class Command(BaseCommand):
    help = (
        "Report, or explicitly reset, uploaded supporting documents with stale "
        "processing AI states. The command is dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--stale-after-minutes",
            type=int,
            default=30,
            help="Only consider documents untouched for this many minutes (default: 30).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Reset the listed documents to not_processed after review.",
        )
        parser.add_argument(
            "--include-queued",
            action="store_true",
            help="Include stale queued records only after confirming no worker can still consume them.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit the report as JSON.",
        )

    def handle(self, *args, **options):
        stale_after_minutes = options["stale_after_minutes"]
        if stale_after_minutes < 1:
            raise CommandError("--stale-after-minutes must be at least 1.")

        cutoff = timezone.now() - timedelta(minutes=stale_after_minutes)
        candidates = []
        unavailable = []
        statuses = [ProjectSupportingDocument.EXTRACTION_PROCESSING]
        if options["include_queued"]:
            statuses.append(ProjectSupportingDocument.EXTRACTION_QUEUED)
        queryset = ProjectSupportingDocument.objects.select_related("processing_job").filter(
            removed_at__isnull=True,
            extraction_status__in=statuses,
            updated_at__lte=cutoff,
        ).order_by("id")
        for document in queryset.iterator():
            job = document.processing_job
            if job and job.status in {
                ProjectAIProcessingJob.STATUS_COMPLETED,
                ProjectAIProcessingJob.STATUS_FAILED,
                ProjectAIProcessingJob.STATUS_STALLED,
            }:
                continue
            if job and job.heartbeat_at and job.heartbeat_at > cutoff:
                continue
            if (
                document.upload_status == ProjectSupportingDocument.UPLOAD_UPLOADED
                and bool(document.content)
            ):
                candidates.append(document)
            else:
                unavailable.append(document)

        report = {
            "mode": "apply" if options["apply"] else "dry_run",
            "stale_after_minutes": stale_after_minutes,
            "include_queued": bool(options["include_queued"]),
            "cutoff": cutoff.isoformat(),
            "candidate_count": len(candidates),
            "unavailable_count": len(unavailable),
            "candidates": [
                {
                    "id": item.id,
                    "project_id": item.project_id,
                    "filename": item.original_filename,
                    "ai_processing_status": item.extraction_status,
                    "job_id": item.processing_job_id,
                    "correlation_id": str(item.processing_job.correlation_id) if item.processing_job_id else "",
                    "job_stage": item.processing_job.stage if item.processing_job_id else "legacy",
                    "heartbeat_at": item.processing_job.heartbeat_at.isoformat() if item.processing_job_id and item.processing_job.heartbeat_at else None,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in candidates
            ],
            "unavailable": [
                {"id": item.id, "project_id": item.project_id, "filename": item.original_filename}
                for item in unavailable
            ],
        }

        if options["apply"] and candidates:
            candidate_ids = [item.id for item in candidates]
            with transaction.atomic():
                updated = ProjectSupportingDocument.objects.filter(
                    id__in=candidate_ids,
                    removed_at__isnull=True,
                    upload_status=ProjectSupportingDocument.UPLOAD_UPLOADED,
                    extraction_status__in=statuses,
                    updated_at__lte=cutoff,
                ).update(
                    extraction_status=ProjectSupportingDocument.EXTRACTION_NOT_PROCESSED,
                    processing_error="",
                )
                job_ids = {item.processing_job_id for item in candidates if item.processing_job_id}
                stale_jobs = ProjectAIProcessingJob.objects.select_for_update().filter(
                    id__in=job_ids,
                    status__in=[ProjectAIProcessingJob.STATUS_QUEUED, ProjectAIProcessingJob.STATUS_PROCESSING],
                )
                now = timezone.now()
                for job in stale_jobs:
                    job.status = ProjectAIProcessingJob.STATUS_STALLED
                    job.stage = ProjectAIProcessingJob.STAGE_STALLED
                    job.safe_error_code = "stale_processing"
                    job.safe_error_message = "AI processing exceeded the stale-work threshold and was safely reset for retry."
                    job.completed_at = now
                    job.heartbeat_at = now
                    job.save(update_fields=[
                        "status", "stage", "safe_error_code", "safe_error_message", "completed_at", "heartbeat_at",
                    ])
                    ProjectAIProcessingEvent.objects.create(
                        job=job,
                        event="stalled_recovered",
                        stage=ProjectAIProcessingJob.STAGE_STALLED,
                        details={"error_code": "stale_processing"},
                    )
            report["recovered_count"] = updated
        else:
            report["recovered_count"] = 0

        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
            return

        self.stdout.write(
            f"{report['mode']}: {report['candidate_count']} recoverable, "
            f"{report['unavailable_count']} skipped, {report['recovered_count']} recovered."
        )
        for item in report["candidates"]:
            self.stdout.write(
                f"  #{item['id']} project #{item['project_id']}: {item['filename']} "
                f"({item['ai_processing_status']})"
            )
