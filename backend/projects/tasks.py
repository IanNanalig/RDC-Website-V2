from celery import shared_task
from django.utils import timezone

from ai_engine.document_assessment import GroqUnavailable, assess_project_documents
from .document_assessments import ensure_queued_assessment
from .document_processing import DocumentProcessingError, extract_document_text
from .models import ProjectDocumentAssessment, ProjectSupportingDocument, UserActivity


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def process_supporting_document(self, document_id):
    document = ProjectSupportingDocument.objects.filter(pk=document_id, removed_at__isnull=True).first()
    if not document:
        return {"status": "missing"}
    document.extraction_status = ProjectSupportingDocument.EXTRACTION_PROCESSING
    document.processing_error = ""
    document.save(update_fields=["extraction_status", "processing_error", "updated_at"])
    try:
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
        return {"status": "failed", "detail": str(exc)}
    document.extraction_status = ProjectSupportingDocument.EXTRACTION_READY
    document.extracted_text = text
    document.extraction_metadata = metadata
    document.processing_error = ""
    document.save(update_fields=[
        "extraction_status", "extracted_text", "extraction_metadata", "processing_error", "updated_at",
    ])
    return {"status": "ready", "characters": len(text)}


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def assess_supporting_documents(self, assessment_id):
    assessment = ProjectDocumentAssessment.objects.select_related("project").filter(pk=assessment_id).first()
    if not assessment:
        return {"status": "missing"}
    documents = list(assessment.project.supporting_documents.filter(removed_at__isnull=True).order_by("id"))
    if not documents or any(item.extraction_status != ProjectSupportingDocument.EXTRACTION_READY for item in documents):
        assessment.status = ProjectDocumentAssessment.STATUS_UNAVAILABLE
        assessment.error_message = "Every active document must finish processing before assessment."
        assessment.save(update_fields=["status", "error_message", "updated_at"])
        return {"status": "unavailable"}
    assessment.status = ProjectDocumentAssessment.STATUS_PROCESSING
    assessment.error_message = ""
    assessment.save(update_fields=["status", "error_message", "updated_at"])
    try:
        result = assess_project_documents(assessment.project, documents, assessment.policy_snapshot)
    except GroqUnavailable as exc:
        assessment.status = ProjectDocumentAssessment.STATUS_UNAVAILABLE
        assessment.error_message = str(exc)[:2000]
        assessment.save(update_fields=["status", "error_message", "updated_at"])
        return {"status": "unavailable"}
    except Exception:
        assessment.status = ProjectDocumentAssessment.STATUS_UNAVAILABLE
        assessment.error_message = "The document assessment service could not complete this request."
        assessment.save(update_fields=["status", "error_message", "updated_at"])
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
    UserActivity.objects.create(
        event="document_assessment_completed",
        project=assessment.project,
        project_id_snapshot=assessment.project_id,
        project_title_snapshot=assessment.project.name,
        details={"assessment_id": assessment.id, "status": assessment.status},
        created_at=timezone.now(),
    )
    return {"status": assessment.status}
