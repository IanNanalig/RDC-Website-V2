import logging
import time

from billiard.exceptions import SoftTimeLimitExceeded
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ai_engine.document_assessment import GroqUnavailable, assess_project_documents
from .document_assessments import (
    fail_processing_job,
    record_processing_event,
    update_processing_job,
)
from .document_processing import DocumentProcessingError, extract_document_text
from .models import (
    ProjectAIProcessingJob,
    ProjectDocumentAssessment,
    ProjectSupportingDocument,
    UserActivity,
)
from .contact_delivery import deliver_public_contact_message
from .concern_delivery import deliver_project_concern


logger = logging.getLogger(__name__)


def _processing_job(job_id):
    if not job_id:
        return None
    return ProjectAIProcessingJob.objects.filter(pk=job_id).first()


def _task_started(job, *, task_id, stage, document=None, assessment=None):
    if not job:
        return
    job.attempt_count += 1
    job.save(update_fields=["attempt_count"])
    update_processing_job(
        job,
        status=ProjectAIProcessingJob.STATUS_PROCESSING,
        stage=stage,
        task_id=task_id,
        started=True,
    )
    record_processing_event(job, "worker_received", stage=stage, document=document, assessment=assessment, task_id=task_id)
    logger.info(
        "AI processing worker received correlation_id=%s task_id=%s stage=%s",
        job.correlation_id, task_id, stage,
    )


@shared_task(bind=True, autoretry_for=(), max_retries=3)
def retry_project_concern_delivery(self, report_id):
    result = deliver_project_concern(report_id)
    if result.get("status") == "pending_retry" and self.request.retries < self.max_retries:
        delays = [60, 300, 900]
        raise self.retry(countdown=delays[min(self.request.retries, len(delays) - 1)])
    return result


@shared_task(bind=True, autoretry_for=(), max_retries=3)
def retry_public_contact_delivery(self, message_id):
    result = deliver_public_contact_message(message_id)
    if result.get("status") == "pending_retry" and self.request.retries < self.max_retries:
        delays = [60, 300, 900]
        raise self.retry(countdown=delays[min(self.request.retries, len(delays) - 1)])
    return result


@shared_task(bind=True, autoretry_for=(), max_retries=2)
def process_supporting_document(self, document_id, job_id=None):
    document = ProjectSupportingDocument.objects.select_related("project").filter(pk=document_id, removed_at__isnull=True).first()
    job = _processing_job(job_id) or getattr(document, "processing_job", None)
    task_id = str(getattr(self.request, "id", "") or "")
    if not document:
        return {"status": "missing"}
    _task_started(
        job,
        task_id=task_id,
        stage=ProjectAIProcessingJob.STAGE_EXTRACTION,
        document=document,
    )
    if document.upload_status != ProjectSupportingDocument.UPLOAD_UPLOADED or not document.content:
        document.extraction_status = ProjectSupportingDocument.EXTRACTION_FAILED
        document.processing_error = "The uploaded file is unavailable for AI processing."
        document.save(update_fields=["extraction_status", "processing_error", "updated_at"])
        fail_processing_job(
            job,
            error_code="document_unavailable",
            error_message=document.processing_error,
            document=document,
            task_id=task_id,
        )
        return {"status": "unavailable"}
    with transaction.atomic():
        locked = ProjectSupportingDocument.objects.select_for_update().get(pk=document.pk)
        if locked.extraction_status == ProjectSupportingDocument.EXTRACTION_READY:
            return {"status": "ready", "reused": True}
        locked.extraction_status = ProjectSupportingDocument.EXTRACTION_PROCESSING
        locked.processing_error = ""
        locked.save(update_fields=["extraction_status", "processing_error", "updated_at"])
        document = locked
    started = time.monotonic()
    try:
        record_processing_event(job, "extraction_started", stage=ProjectAIProcessingJob.STAGE_EXTRACTION, document=document, task_id=task_id)
        text, metadata = extract_document_text(document)
    except DocumentProcessingError as exc:
        document.extraction_status = ProjectSupportingDocument.EXTRACTION_FAILED
        document.extracted_text = ""
        document.processing_error = str(exc)[:2000]
        document.save(update_fields=["extraction_status", "extracted_text", "processing_error", "updated_at"])
        UserActivity.objects.create(
            user=document.uploaded_by,
            actor_username=getattr(document.uploaded_by, "username", "") or "",
            actor_full_name=document.uploaded_by.get_full_name() if document.uploaded_by else "",
            role=getattr(document.uploaded_by, "role", "") or "",
            event="supporting_document_extraction_failed",
            project=document.project,
            project_id_snapshot=document.project_id,
            project_title_snapshot=document.project.name,
            details={"document_id": document.id, "filename": document.original_filename, "error": str(exc)[:500]},
        )
        fail_processing_job(
            job,
            error_code="extraction_failed",
            error_message="The document could not be read for AI analysis.",
            document=document,
            task_id=task_id,
        )
        return {"status": "failed", "detail": str(exc)}
    except SoftTimeLimitExceeded:
        document.extraction_status = ProjectSupportingDocument.EXTRACTION_FAILED
        document.processing_error = "Document extraction exceeded the processing time limit."
        document.save(update_fields=["extraction_status", "processing_error", "updated_at"])
        fail_processing_job(
            job,
            error_code="extraction_timeout",
            error_message="Document extraction exceeded the processing time limit. Retry AI processing.",
            document=document,
            task_id=task_id,
        )
        return {"status": "failed", "detail": "timeout"}
    except Exception:
        logger.exception("AI document extraction crashed document_id=%s task_id=%s", document.id, task_id)
        document.extraction_status = ProjectSupportingDocument.EXTRACTION_FAILED
        document.processing_error = "The document processing worker could not complete extraction."
        document.save(update_fields=["extraction_status", "processing_error", "updated_at"])
        fail_processing_job(
            job,
            error_code="extraction_worker_error",
            error_message="The document processing worker could not complete extraction. Retry AI processing.",
            document=document,
            task_id=task_id,
        )
        return {"status": "failed", "detail": "worker_error"}
    document.extraction_status = ProjectSupportingDocument.EXTRACTION_READY
    document.extracted_text = text
    document.extraction_metadata = metadata
    document.processing_error = ""
    document.save(update_fields=[
        "extraction_status", "extracted_text", "extraction_metadata", "processing_error", "updated_at",
    ])
    update_processing_job(job, status=ProjectAIProcessingJob.STATUS_PROCESSING, stage=ProjectAIProcessingJob.STAGE_EXTRACTION)
    record_processing_event(
        job,
        "extraction_completed",
        stage=ProjectAIProcessingJob.STAGE_EXTRACTION,
        document=document,
        task_id=task_id,
        duration_ms=int((time.monotonic() - started) * 1000),
        details={"character_count": len(text)},
    )
    return {"status": "ready", "characters": len(text)}


@shared_task(bind=True, autoretry_for=(), max_retries=2)
def assess_supporting_documents(self, assessment_id, job_id=None):
    assessment = ProjectDocumentAssessment.objects.select_related("project").filter(pk=assessment_id).first()
    job = _processing_job(job_id) or getattr(assessment, "processing_job", None)
    task_id = str(getattr(self.request, "id", "") or "")
    if not assessment:
        return {"status": "missing"}
    _task_started(
        job,
        task_id=task_id,
        stage=ProjectAIProcessingJob.STAGE_ASSESSMENT,
        assessment=assessment,
    )
    documents = list(assessment.project.supporting_documents.filter(removed_at__isnull=True).order_by("id"))
    if not documents or any(item.extraction_status != ProjectSupportingDocument.EXTRACTION_READY for item in documents):
        assessment.status = ProjectDocumentAssessment.STATUS_UNAVAILABLE
        assessment.error_message = "Every active document must finish processing before assessment."
        assessment.save(update_fields=["status", "error_message", "updated_at"])
        fail_processing_job(
            job,
            error_code="documents_not_ready",
            error_message="Every active document must finish processing before assessment.",
            assessment=assessment,
            task_id=task_id,
        )
        return {"status": "unavailable"}
    assessment.status = ProjectDocumentAssessment.STATUS_PROCESSING
    assessment.error_message = ""
    assessment.save(update_fields=["status", "error_message", "updated_at"])
    update_processing_job(job, stage=ProjectAIProcessingJob.STAGE_SCORING)
    record_processing_event(job, "assessment_started", stage=ProjectAIProcessingJob.STAGE_SCORING, assessment=assessment, task_id=task_id)
    started = time.monotonic()
    try:
        result = assess_project_documents(assessment.project, documents, assessment.policy_snapshot)
    except GroqUnavailable as exc:
        if not settings.CELERY_TASK_ALWAYS_EAGER and self.request.retries < self.max_retries:
            delay = [30, 120, 300][min(self.request.retries, 2)]
            record_processing_event(job, "provider_retry_scheduled", stage=ProjectAIProcessingJob.STAGE_SCORING, assessment=assessment, task_id=task_id, details={"retry": self.request.retries + 1})
            update_processing_job(job, status=ProjectAIProcessingJob.STATUS_QUEUED, stage=ProjectAIProcessingJob.STAGE_ASSESSMENT)
            raise self.retry(exc=exc, countdown=delay)
        assessment.status = ProjectDocumentAssessment.STATUS_UNAVAILABLE
        assessment.error_message = (
            "The AI assessment service is currently unavailable. Retry when it is online. "
            + str(exc)[:500]
        )
        assessment.save(update_fields=["status", "error_message", "updated_at"])
        fail_processing_job(job, error_code="provider_unavailable", error_message=assessment.error_message, assessment=assessment, task_id=task_id)
        return {"status": "unavailable"}
    except SoftTimeLimitExceeded:
        assessment.status = ProjectDocumentAssessment.STATUS_UNAVAILABLE
        assessment.error_message = "AI assessment exceeded the processing time limit. Retry when the service is available."
        assessment.save(update_fields=["status", "error_message", "updated_at"])
        fail_processing_job(job, error_code="assessment_timeout", error_message=assessment.error_message, assessment=assessment, task_id=task_id)
        return {"status": "unavailable"}
    except Exception:
        logger.exception("AI document assessment crashed assessment_id=%s task_id=%s", assessment.id, task_id)
        assessment.status = ProjectDocumentAssessment.STATUS_UNAVAILABLE
        assessment.error_message = "The document assessment service could not complete this request."
        assessment.save(update_fields=["status", "error_message", "updated_at"])
        fail_processing_job(job, error_code="assessment_worker_error", error_message=assessment.error_message, assessment=assessment, task_id=task_id)
        return {"status": "unavailable"}
    assessment.status = result["status"]
    assessment.document_results = result["document_results"]
    assessment.collective_sufficient = result["collective_sufficient"]
    assessment.summary = result["summary"]
    assessment.provider = result["provider"]
    assessment.model = result["model"]
    assessment.used_backup_model = result["used_backup_model"]
    assessment.error_message = ""
    assessment.save(update_fields=[
        "status", "document_results", "collective_sufficient", "summary", "provider", "model",
        "used_backup_model", "error_message", "updated_at",
    ])
    update_processing_job(
        job,
        status=ProjectAIProcessingJob.STATUS_COMPLETED,
        stage=ProjectAIProcessingJob.STAGE_COMPLETED,
        error_code="",
        error_message="",
        complete=True,
    )
    record_processing_event(
        job,
        "assessment_completed",
        stage=ProjectAIProcessingJob.STAGE_COMPLETED,
        assessment=assessment,
        task_id=task_id,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    UserActivity.objects.create(
        event="document_assessment_completed",
        project=assessment.project,
        project_id_snapshot=assessment.project_id,
        project_title_snapshot=assessment.project.name,
        details={"assessment_id": assessment.id, "status": assessment.status},
        created_at=timezone.now(),
    )
    return {"status": assessment.status}
