import hashlib
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction

from .document_policy import active_project_documents, resolve_project_document_policy
from .models import Project, ProjectDocumentAssessment, ProjectSupportingDocument


logger = logging.getLogger(__name__)


def current_document_source_hash(project, policy=None, documents=None):
    policy = policy if isinstance(policy, dict) else resolve_project_document_policy(project)
    documents = list(documents) if documents is not None else list(active_project_documents(project))
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    form = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
    project_context = {
        key: form.get(key)
        for key in (
            "agencyName", "projectActivity", "projectTitle", "description", "objective",
            "developmentSector", "mainInfrastructureSector", "fundingRequirementByYear",
            "targetBeneficiaries", "beneficiaries", "expectedOutputIndicator",
        )
    }
    project_context.update({
        "stored_name": project.name,
        "stored_description": project.description,
        "stored_agency": project.agency,
        "stored_implementing_agency": project.implementing_agency,
        "stored_budget": project.budget,
    })
    payload = {
        "project": project_context,
        "policy": policy or {},
        "documents": [
            [item.id, item.checksum_sha256, item.upload_status, item.extraction_status]
            for item in sorted(documents, key=lambda value: value.id)
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    ).hexdigest()


def current_document_assessment(project):
    documents = list(active_project_documents(project))
    policy = resolve_project_document_policy(project)
    if not policy:
        return None
    source_hash = current_document_source_hash(project, policy, documents)
    return project.document_assessments.filter(source_hash=source_hash).order_by("-created_at").first()


def ensure_queued_assessment(project):
    policy = resolve_project_document_policy(project, persist=True)
    documents = list(active_project_documents(project))
    if not policy or not documents:
        return None, False
    source_hash = current_document_source_hash(project, policy, documents)
    try:
        assessment, created = ProjectDocumentAssessment.objects.get_or_create(
            project=project,
            source_hash=source_hash,
            defaults={"status": ProjectDocumentAssessment.STATUS_QUEUED, "policy_snapshot": policy},
        )
    except IntegrityError:
        assessment = ProjectDocumentAssessment.objects.get(project=project, source_hash=source_hash)
        created = False
    return assessment, created


def serialize_document_assessment(project):
    policy = resolve_project_document_policy(project)
    documents = list(active_project_documents(project))
    if not policy:
        return {"status": "not_required", "required": False, "document_results": []}
    if not documents:
        return {
            "status": "missing" if policy.get("required") else "not_required",
            "required": bool(policy.get("required")),
            "document_results": [],
            "summary": "Supporting documents have not been uploaded.",
        }
    assessment = current_document_assessment(project)
    if not assessment:
        upload_failed = any(
            item.upload_status != ProjectSupportingDocument.UPLOAD_UPLOADED or not item.content
            for item in documents
        )
        not_processed = any(
            item.extraction_status == ProjectSupportingDocument.EXTRACTION_NOT_PROCESSED
            for item in documents
        )
        processing = any(
            item.extraction_status in {
                ProjectSupportingDocument.EXTRACTION_QUEUED,
                ProjectSupportingDocument.EXTRACTION_PROCESSING,
            }
            and not str(item.processing_error or "").strip()
            for item in documents
        )
        failed = any(
            item.extraction_status == ProjectSupportingDocument.EXTRACTION_FAILED
            or bool(str(item.processing_error or "").strip())
            for item in documents
        )
        if upload_failed:
            summary = "One or more supporting files are unavailable. Upload a replacement before submitting or running analysis."
        elif not_processed:
            summary = "Supporting documents are uploaded."
        elif processing:
            summary = "The AI Assistant is preparing the supporting documents."
        elif failed:
            summary = "AI processing could not read one or more supporting documents. The uploaded files remain available; a Validator can retry processing."
        else:
            summary = "Supporting documents are ready. The files will be read when the Validator runs the AI Assistant analysis."
        return {
            "status": (
                "unavailable" if upload_failed or failed
                else "processing" if processing
                else "not_processed" if not_processed
                else "pending"
            ),
            "required": bool(policy.get("required")),
            "document_results": [],
            "summary": summary,
        }
    return {
        "id": assessment.id,
        "status": assessment.status,
        "required": bool(policy.get("required")),
        "document_results": assessment.document_results,
        "collective_sufficient": assessment.collective_sufficient,
        "summary": assessment.summary,
        "provider": assessment.provider,
        "model": assessment.model,
        "used_backup_model": assessment.used_backup_model,
        "error_message": assessment.error_message,
        "source_hash": assessment.source_hash,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
    }


def dispatch_document_processing(document_id):
    try:
        from .tasks import process_supporting_document

        if settings.CELERY_TASK_ALWAYS_EAGER:
            # Local/eager environments do not need Redis. Calling the task
            # directly also avoids a queue connection delaying the upload.
            process_supporting_document.run(document_id)
            return True
        process_supporting_document.delay(document_id)
        return True
    except Exception:
        logger.exception("Could not dispatch supporting document %s for processing", document_id)
        return False


def dispatch_project_document_processing(project, *, retry_failed=False):
    """Claim eligible documents and enqueue extraction after Validator action.

    Contributors never call this helper. The project and document locks make
    repeated Validator clicks idempotent: only ``not_processed`` documents,
    or explicitly retried failed documents, are queued once.
    """
    with transaction.atomic():
        locked_project = Project.objects.select_for_update().get(pk=project.pk)
        documents = list(
            active_project_documents(locked_project)
            .select_for_update()
            .order_by("id")
        )
        candidates = [
            document
            for document in documents
            if document.upload_status == ProjectSupportingDocument.UPLOAD_UPLOADED
            and bool(document.content)
            and (
                document.extraction_status == ProjectSupportingDocument.EXTRACTION_NOT_PROCESSED
                or (
                    retry_failed
                    and document.extraction_status == ProjectSupportingDocument.EXTRACTION_FAILED
                )
            )
        ]
        for document in candidates:
            document.extraction_status = ProjectSupportingDocument.EXTRACTION_QUEUED
            document.processing_error = ""
            document.save(update_fields=["extraction_status", "processing_error", "updated_at"])

    queued_ids = []
    unavailable_ids = []
    for document in candidates:
        if dispatch_document_processing(document.id):
            queued_ids.append(document.id)
            continue
        ProjectSupportingDocument.objects.filter(pk=document.id).update(
            extraction_status=ProjectSupportingDocument.EXTRACTION_FAILED,
            processing_error="The document processing worker is unavailable. A Validator can retry AI processing when it is online.",
        )
        unavailable_ids.append(document.id)
    return {"queued_ids": queued_ids, "unavailable_ids": unavailable_ids}


def dispatch_document_assessment(assessment_id):
    try:
        from .tasks import assess_supporting_documents

        if settings.CELERY_TASK_ALWAYS_EAGER:
            # Match document extraction: complete the assessment immediately
            # when this installation explicitly opts into eager execution.
            assess_supporting_documents.run(assessment_id)
            return True
        assess_supporting_documents.delay(assessment_id)
        return True
    except Exception:
        logger.exception("Could not dispatch supporting document assessment %s", assessment_id)
        return False
