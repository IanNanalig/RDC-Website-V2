from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import F
from django.utils import timezone

from .models import ProjectConcernReport


logger = logging.getLogger(__name__)


def _safe_delivery_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: email delivery was unsuccessful"[:300]


def _evidence_filename(index: int, extension: str) -> str:
    suffix = str(extension or "bin").lower().lstrip(".")
    return f"Evidence-{index:02d}.{suffix}"


def _header_text(value: str) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def _receiver_message(report: ProjectConcernReport) -> EmailMessage:
    receiver = str(getattr(settings, "PROJECT_CONCERN_RECEIVER_EMAIL", "") or "").strip()
    if not receiver:
        raise RuntimeError("Project concern receiver is not configured")

    evidence = list(report.evidence_files.all().order_by("id"))
    attachment_lines = [
        f"- {_evidence_filename(index, item.extension)} (submitted as {item.original_filename}, {item.size_bytes} bytes)"
        for index, item in enumerate(evidence, start=1)
    ]
    body = [
        "A public project concern was accepted by the RDC-NCR website.",
        "",
        f"Report reference: {report.reference_code}",
        f"Project ID: {report.project_id_snapshot}",
        f"Project: {report.project_title_snapshot}",
        f"Primary agency: {report.project_agency_snapshot or '-'}",
        f"Concern category: {report.category_label_snapshot}",
        f"Reporting mode: {report.get_reporting_mode_display()}",
        f"Reporter email: {report.reporter_email or 'Not supplied (anonymous report)'}",
        "",
        "Description:",
        report.description,
        "",
        "Supporting evidence:",
        *(attachment_lines or ["- None"]),
        "",
        "Security notice: attachments were checked for allowed format and bounded archive content, but were not malware-scanned.",
        "Treat the submission as a concern requiring review; it is not a finding of wrongdoing.",
    ]
    admin_url = str(getattr(settings, "FRONTEND_BASE_URL", "") or "").rstrip("/")
    if admin_url:
        body.extend(["", f"Administrator delivery record: {admin_url}/admin/project-concerns?reference={report.reference_code}"])

    reply_to = [report.reporter_email] if report.reporting_mode == report.MODE_EMAIL and report.reporter_email else None
    message = EmailMessage(
        subject=f"[RDC-NCR Project Concern] {report.reference_code} - {_header_text(report.project_title_snapshot)}"[:998],
        body="\n".join(body),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[receiver],
        reply_to=reply_to,
        headers={"X-RDC-Concern-Reference": report.reference_code},
    )
    for index, item in enumerate(evidence, start=1):
        message.attach(
            _evidence_filename(index, item.extension),
            bytes(item.content),
            item.content_type,
        )
    return message


def _acknowledgement_message(report: ProjectConcernReport) -> EmailMessage:
    if report.reporting_mode != report.MODE_EMAIL or not report.reporter_email:
        raise RuntimeError("Acknowledgment is not applicable")
    body = (
        "Your project concern has been accepted by the RDC-NCR website.\n\n"
        f"Report reference: {report.reference_code}\n"
        f"Project ID: {report.project_id_snapshot}\n"
        f"Project: {report.project_title_snapshot}\n"
        f"Concern category: {report.category_label_snapshot}\n\n"
        "Keep this reference for any email correspondence. Providing an email enables follow-up, "
        "but does not guarantee a particular response time or outcome.\n\n"
        "This acknowledgment does not confirm that the reported concern is true or that wrongdoing occurred."
    )
    return EmailMessage(
        subject=f"RDC-NCR project concern received - {report.reference_code}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[report.reporter_email],
        headers={"X-RDC-Concern-Reference": report.reference_code},
    )


def _claim_delivery(report_id: int, field: str, attempts_field: str) -> bool:
    eligible = [ProjectConcernReport.DELIVERY_PENDING, ProjectConcernReport.DELIVERY_FAILED]
    return bool(
        ProjectConcernReport.objects.filter(pk=report_id, **{f"{field}__in": eligible}).update(
            **{
                field: ProjectConcernReport.DELIVERY_SENDING,
                attempts_field: F(attempts_field) + 1,
                "updated_at": timezone.now(),
            }
        )
    )


def deliver_project_concern(report_id: int) -> dict:
    """Deliver pending/failed receiver and acknowledgment messages idempotently."""
    stale_before = timezone.now() - timedelta(minutes=5)
    ProjectConcernReport.objects.filter(
        pk=report_id,
        receiver_delivery_status=ProjectConcernReport.DELIVERY_SENDING,
        updated_at__lt=stale_before,
    ).update(receiver_delivery_status=ProjectConcernReport.DELIVERY_FAILED)
    ProjectConcernReport.objects.filter(
        pk=report_id,
        acknowledgement_delivery_status=ProjectConcernReport.DELIVERY_SENDING,
        updated_at__lt=stale_before,
    ).update(acknowledgement_delivery_status=ProjectConcernReport.DELIVERY_FAILED)
    report = ProjectConcernReport.objects.prefetch_related("evidence_files").filter(pk=report_id).first()
    if not report:
        return {"status": "missing"}

    if _claim_delivery(report.id, "receiver_delivery_status", "receiver_delivery_attempts"):
        report.refresh_from_db()
        try:
            message = _receiver_message(report)
            message.send(fail_silently=False)
        except Exception as exc:
            ProjectConcernReport.objects.filter(pk=report.id).update(
                receiver_delivery_status=ProjectConcernReport.DELIVERY_FAILED,
                receiver_last_error=_safe_delivery_error(exc),
            )
        else:
            ProjectConcernReport.objects.filter(pk=report.id).update(
                receiver_delivery_status=ProjectConcernReport.DELIVERY_SENT,
                receiver_sent_at=timezone.now(),
                receiver_last_error="",
            )

    report.refresh_from_db()
    if report.reporting_mode == report.MODE_EMAIL and report.reporter_email:
        if _claim_delivery(report.id, "acknowledgement_delivery_status", "acknowledgement_delivery_attempts"):
            report.refresh_from_db()
            try:
                _acknowledgement_message(report).send(fail_silently=False)
            except Exception as exc:
                ProjectConcernReport.objects.filter(pk=report.id).update(
                    acknowledgement_delivery_status=ProjectConcernReport.DELIVERY_FAILED,
                    acknowledgement_last_error=_safe_delivery_error(exc),
                )
            else:
                ProjectConcernReport.objects.filter(pk=report.id).update(
                    acknowledgement_delivery_status=ProjectConcernReport.DELIVERY_SENT,
                    acknowledgement_sent_at=timezone.now(),
                    acknowledgement_last_error="",
                )

    report.refresh_from_db()
    return {
        "status": "complete" if report.receiver_delivery_status == report.DELIVERY_SENT else "pending_retry",
        "receiver": report.receiver_delivery_status,
        "acknowledgement": report.acknowledgement_delivery_status,
    }


def dispatch_project_concern_delivery(report_id: int) -> bool:
    try:
        from .tasks import retry_project_concern_delivery

        if settings.CELERY_TASK_ALWAYS_EAGER:
            retry_project_concern_delivery.run(report_id)
        else:
            retry_project_concern_delivery.delay(report_id)
        return True
    except Exception:
        logger.exception("Could not queue project concern delivery retry for report %s", report_id)
        return False
