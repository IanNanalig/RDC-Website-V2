"""Safely recover uploaded documents stranded before AI processing completed."""

from datetime import timedelta
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from projects.models import ProjectSupportingDocument


class Command(BaseCommand):
    help = (
        "Report, or explicitly reset, uploaded supporting documents with stale "
        "queued/processing AI states. The command is dry-run by default."
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
        queryset = ProjectSupportingDocument.objects.filter(
            removed_at__isnull=True,
            extraction_status__in=[
                ProjectSupportingDocument.EXTRACTION_QUEUED,
                ProjectSupportingDocument.EXTRACTION_PROCESSING,
            ],
            updated_at__lte=cutoff,
        ).order_by("id")
        for document in queryset.iterator():
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
            "cutoff": cutoff.isoformat(),
            "candidate_count": len(candidates),
            "unavailable_count": len(unavailable),
            "candidates": [
                {
                    "id": item.id,
                    "project_id": item.project_id,
                    "filename": item.original_filename,
                    "ai_processing_status": item.extraction_status,
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
                    extraction_status__in=[
                        ProjectSupportingDocument.EXTRACTION_QUEUED,
                        ProjectSupportingDocument.EXTRACTION_PROCESSING,
                    ],
                    updated_at__lte=cutoff,
                ).update(
                    extraction_status=ProjectSupportingDocument.EXTRACTION_NOT_PROCESSED,
                    processing_error="",
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
