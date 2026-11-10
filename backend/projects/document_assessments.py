import hashlib
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .document_policy import active_project_documents, documents_for_revision, resolve_project_document_policy, revision_document_policy
from .models import (
    Project,
    ProjectAIProcessingEvent,
    ProjectAIProcessingJob,
    ProjectDocumentAssessment,
    ProjectSupportingDocument,
)


logger = logging.getLogger(__name__)


ACTIVE_JOB_STATUSES = {
    ProjectAIProcessingJob.STATUS_QUEUED,
    ProjectAIProcessingJob.STATUS_PROCESSING,
}


def document_processing_runs_inline():
    """Whether Validator-initiated document AI is executed by this API request.

    The default is intentionally inline: a deployment without a permanent
    Celery worker must never leave a Validator waiting on a queue that nobody
    consumes.  Celery remains available for installations which explicitly
    choose the worker mode and for non-document delivery retries.
    """
    return getattr(settings, "DOCUMENT_AI_PROCESSING_MODE", "inline") != "worker"


def record_processing_event(job, event, *, stage="", document=None, assessment=None, task_id="", duration_ms=None, details=None):
    """Persist safe operational facts only; never store extracted content or credentials."""
    if not job:
        return None
    allowed_details = {
        key: value
        for key, value in (details or {}).items()
        if key in {"error_code", "retry", "attempt", "document_id", "assessment_id", "character_count"}
    }
    return ProjectAIProcessingEvent.objects.create(
        job=job,
        document=document,
        assessment=assessment,
        event=event[:64],
        stage=stage[:20],
        celery_task_id=str(task_id or "")[:255],
        duration_ms=duration_ms,
        details=allowed_details,
    )


def update_processing_job(job, *, status=None, stage=None, task_id=None, error_code=None, error_message=None, started=False, complete=False):
    if not job:
        return None
    # Another document task may have already made this shared job terminal.
    # Never let a late sibling task reopen it.
    job.refresh_from_db()
    if job.status in {
        ProjectAIProcessingJob.STATUS_COMPLETED,
        ProjectAIProcessingJob.STATUS_FAILED,
        ProjectAIProcessingJob.STATUS_STALLED,
    } and status in ACTIVE_JOB_STATUSES:
        return job
    now = timezone.now()
    fields = ["heartbeat_at"]
    job.heartbeat_at = now
    if status is not None:
        job.status = status
        fields.append("status")
    if stage is not None:
        job.stage = stage
        fields.append("stage")
    if task_id is not None:
        job.celery_task_id = str(task_id)[:255]
        fields.append("celery_task_id")
    if error_code is not None:
        job.safe_error_code = str(error_code)[:80]
        fields.append("safe_error_code")
    if error_message is not None:
        job.safe_error_message = str(error_message)[:2000]
        fields.append("safe_error_message")
    if started and not job.started_at:
        job.started_at = now
        fields.append("started_at")
    if complete:
        job.completed_at = now
        fields.append("completed_at")
    job.save(update_fields=[*dict.fromkeys(fields)])
    return job


def fail_processing_job(job, *, error_code, error_message, document=None, assessment=None, task_id=""):
    if not job:
        return None
    update_processing_job(
        job,
        status=ProjectAIProcessingJob.STATUS_FAILED,
        stage=ProjectAIProcessingJob.STAGE_FAILED,
        task_id=task_id or None,
        error_code=error_code,
        error_message=error_message,
        complete=True,
    )
    record_processing_event(
        job,
        "failed",
        stage=ProjectAIProcessingJob.STAGE_FAILED,
        document=document,
        assessment=assessment,
        task_id=task_id,
        details={"error_code": error_code},
    )
    logger.warning(
        "AI processing failed correlation_id=%s project_id=%s stage=%s code=%s",
        job.correlation_id,
        job.project_id,
        job.stage,
        error_code,
    )
    return job


def active_processing_job(project, revision=None):
    job = project.ai_processing_jobs.filter(revision=revision, status__in=ACTIVE_JOB_STATUSES).order_by("-requested_at", "-id").first()
    job = mark_stale_processing_job(job)
    return job if job and job.status in ACTIVE_JOB_STATUSES else None


def mark_stale_processing_job(job):
    """Terminally fail abandoned work after the configured worker-time budget.

    This is deliberately bounded above the Celery hard limit. It never changes
    upload availability and it does not reset a job merely because a page was
    refreshed; only an expired heartbeat changes state.
    """
    if not job or job.status not in ACTIVE_JOB_STATUSES:
        return job
    threshold = max(
        int(getattr(settings, "AI_PROCESSING_STALE_AFTER_SECONDS", 900)),
        int(getattr(settings, "CELERY_TASK_TIME_LIMIT", 600)) + 120,
    )
    last_seen = job.heartbeat_at or job.started_at or job.requested_at
    if not last_seen or last_seen > timezone.now() - timedelta(seconds=threshold):
        return job
    with transaction.atomic():
        locked = ProjectAIProcessingJob.objects.select_for_update().get(pk=job.pk)
        last_seen = locked.heartbeat_at or locked.started_at or locked.requested_at
        if locked.status not in ACTIVE_JOB_STATUSES or not last_seen or last_seen > timezone.now() - timedelta(seconds=threshold):
            return locked
        now = timezone.now()
        ProjectSupportingDocument.objects.filter(
            processing_job=locked,
            extraction_status__in=[
                ProjectSupportingDocument.EXTRACTION_QUEUED,
                ProjectSupportingDocument.EXTRACTION_PROCESSING,
            ],
        ).update(
            extraction_status=ProjectSupportingDocument.EXTRACTION_FAILED,
            processing_error="AI processing did not receive a worker update in time. A Validator can retry it.",
        )
        locked.status = ProjectAIProcessingJob.STATUS_STALLED
        locked.stage = ProjectAIProcessingJob.STAGE_STALLED
        locked.safe_error_code = "worker_heartbeat_stale"
        locked.safe_error_message = "AI processing did not receive a worker update in time. A Validator can retry it."
        locked.completed_at = now
        locked.heartbeat_at = now
        locked.save(update_fields=[
            "status", "stage", "safe_error_code", "safe_error_message", "completed_at", "heartbeat_at",
        ])
        record_processing_event(
            locked,
            "stalled",
            stage=ProjectAIProcessingJob.STAGE_STALLED,
            details={"error_code": "worker_heartbeat_stale"},
        )
        logger.warning("AI processing marked stale correlation_id=%s project_id=%s", locked.correlation_id, locked.project_id)
        return locked


def latest_processing_job(project, revision=None):
    active_processing_job(project, revision=revision)
    return project.ai_processing_jobs.filter(revision=revision).order_by("-requested_at", "-id").first()


def _serialize_job(job):
    if not job:
        return None
    now = timezone.now()
    started = job.started_at or job.requested_at
    return {
        "id": job.id,
        "correlation_id": str(job.correlation_id),
        "status": job.status,
        "stage": job.stage,
        "stage_label": dict(ProjectAIProcessingJob.STAGE_CHOICES).get(job.stage, job.stage.replace("_", " ").title()),
        "attempt_count": job.attempt_count,
        "elapsed_seconds": max(0, int((now - started).total_seconds())) if started else 0,
        "requested_at": job.requested_at,
        "started_at": job.started_at,
        "heartbeat_at": job.heartbeat_at,
        "completed_at": job.completed_at,
        "error_code": job.safe_error_code,
        "error_message": job.safe_error_message,
    }


def serialize_processing_job(job):
    """Public safe job summary; raw event details remain server-only."""
    return _serialize_job(job)


def current_document_source_hash(project, policy=None, documents=None, *, revision=None):
    policy = policy if isinstance(policy, dict) else (revision_document_policy(revision) if revision else resolve_project_document_policy(project))
    documents = list(documents) if documents is not None else list(documents_for_revision(revision) if revision else active_project_documents(project))
    profile = revision.profile_data_snapshot if revision else project.profile_data
    profile = profile if isinstance(profile, dict) else {}
    form = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
    project_context = {
        key: form.get(key)
        for key in (
            "agencyName", "projectActivity", "projectTitle", "description", "objective",
            "developmentSector", "mainInfrastructureSector", "fundingRequirementByYear",
            "targetBeneficiaries", "beneficiaries", "expectedOutputIndicator",
        )
    }
    if revision is None:
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
    if revision is not None:
        payload["revision_id"] = revision.pk
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    ).hexdigest()


def current_document_assessment(project, *, revision=None):
    documents = list(documents_for_revision(revision) if revision else active_project_documents(project))
    policy = revision_document_policy(revision) if revision else resolve_project_document_policy(project)
    if not policy:
        return None
    source_hash = current_document_source_hash(project, policy, documents, revision=revision)
    return project.document_assessments.filter(revision=revision, source_hash=source_hash).order_by("-created_at").first()


def ensure_queued_assessment(project, *, processing_job=None, requested_by=None, revision=None):
    policy = revision_document_policy(revision) if revision else resolve_project_document_policy(project, persist=True)
    documents = list(documents_for_revision(revision) if revision else active_project_documents(project))
    if not policy or not documents:
        return None, False
    processing_job = processing_job or active_processing_job(project, revision=revision)
    if processing_job is None:
        processing_job = ProjectAIProcessingJob.objects.create(
            project=project,
            revision=revision,
            requested_by=requested_by,
            source_hash=current_document_source_hash(project, policy, documents, revision=revision),
            status=ProjectAIProcessingJob.STATUS_QUEUED,
            stage=ProjectAIProcessingJob.STAGE_ASSESSMENT,
            heartbeat_at=timezone.now(),
        )
        record_processing_event(processing_job, "requested", stage=ProjectAIProcessingJob.STAGE_ASSESSMENT)
    source_hash = current_document_source_hash(project, policy, documents, revision=revision)
    try:
        assessment, created = ProjectDocumentAssessment.objects.get_or_create(
            project=project,
            revision=revision,
            source_hash=source_hash,
            defaults={
                "status": ProjectDocumentAssessment.STATUS_QUEUED,
                "policy_snapshot": policy,
                "processing_job": processing_job,
            },
        )
    except IntegrityError:
        assessment = ProjectDocumentAssessment.objects.get(project=project, revision=revision, source_hash=source_hash)
        created = False
    if processing_job and assessment.processing_job_id != processing_job.id:
        assessment.processing_job = processing_job
        assessment.save(update_fields=["processing_job", "updated_at"])
    return assessment, created


def serialize_document_assessment(project, *, revision=None):
    policy = revision_document_policy(revision) if revision else resolve_project_document_policy(project)
    documents = list(documents_for_revision(revision) if revision else active_project_documents(project))
    if not policy:
        return {"status": "not_required", "required": False, "document_results": []}
    if not documents:
        return {
            "status": "missing" if policy.get("required") else "not_required",
            "required": bool(policy.get("required")),
            "document_results": [],
            "summary": "Supporting documents have not been uploaded.",
        }
    assessment = current_document_assessment(project, revision=revision)
    job = latest_processing_job(project, revision=revision)
    if not assessment:
        upload_failed = any(
            item.upload_status != ProjectSupportingDocument.UPLOAD_UPLOADED or not item.content
            for item in documents
        )
        not_processed = any(
            item.extraction_status == ProjectSupportingDocument.EXTRACTION_NOT_PROCESSED
            for item in documents
        )
        queued = any(
            item.extraction_status == ProjectSupportingDocument.EXTRACTION_QUEUED
            and not str(item.processing_error or "").strip()
            for item in documents
        )
        processing = any(
            item.extraction_status == ProjectSupportingDocument.EXTRACTION_PROCESSING
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
        elif queued:
            summary = (
                "AI processing is awaiting an authorized Validator request."
                if document_processing_runs_inline()
                else "AI processing is queued and waiting for the document worker."
            )
        elif processing:
            summary = "AI processing is reading the supporting documents."
        elif failed:
            summary = "AI processing could not read one or more supporting documents. The uploaded files remain available; a Validator can retry processing."
        else:
            summary = "Supporting documents are ready. The files will be read when the Validator runs the AI Assistant analysis."
        return {
            "status": (
                "stalled" if job and job.status == ProjectAIProcessingJob.STATUS_STALLED
                else "failed" if job and job.status == ProjectAIProcessingJob.STATUS_FAILED
                else "unavailable" if upload_failed or failed
                else "queued" if queued
                else "processing" if processing
                else "not_processed" if not_processed
                else "pending"
            ),
            "required": bool(policy.get("required")),
            "document_results": [],
            "summary": summary,
            "job": _serialize_job(job),
            "retry_available": bool(failed or (job and job.status in {ProjectAIProcessingJob.STATUS_FAILED, ProjectAIProcessingJob.STATUS_STALLED})),
        }
    job = job or assessment.processing_job
    payload = {
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
        "job": _serialize_job(job),
        "retry_available": assessment.status == ProjectDocumentAssessment.STATUS_UNAVAILABLE or bool(
            job and job.status in {ProjectAIProcessingJob.STATUS_FAILED, ProjectAIProcessingJob.STATUS_STALLED}
        ),
    }
    if job and job.status == ProjectAIProcessingJob.STATUS_QUEUED:
        payload["status"] = "queued"
        payload["summary"] = (
            "AI processing is awaiting an authorized Validator request."
            if document_processing_runs_inline()
            else "AI processing is queued and waiting for the document worker."
        )
    elif job and job.status == ProjectAIProcessingJob.STATUS_PROCESSING and assessment.status == ProjectDocumentAssessment.STATUS_QUEUED:
        payload["status"] = "processing"
        payload["summary"] = "AI processing is reading the supporting documents."
    elif job and job.status == ProjectAIProcessingJob.STATUS_STALLED:
        payload["status"] = "stalled"
        payload["summary"] = job.safe_error_message or "AI processing appears stalled. A Validator can retry it."
    elif job and job.status == ProjectAIProcessingJob.STATUS_FAILED:
        payload["status"] = "failed"
        payload["summary"] = job.safe_error_message or "AI processing failed. A Validator can retry it."
    return payload


def dispatch_document_processing(document_id, *, processing_job=None):
    try:
        from .tasks import process_supporting_document

        if processing_job is None:
            processing_job = ProjectSupportingDocument.objects.select_related("processing_job").filter(pk=document_id).first()
            processing_job = getattr(processing_job, "processing_job", None)

        if document_processing_runs_inline() or settings.CELERY_TASK_ALWAYS_EAGER:
            # Inline mode is deliberately invoked only after a Validator starts
            # the scorer. It has no broker/worker dependency and never runs on
            # contributor upload. Eager mode remains useful for worker-mode
            # local tests.
            process_supporting_document.run(document_id)
            return {"ok": True, "task_id": ""}
        # The task resolves the job through the locked document row. Keeping
        # the task argument stable also makes delayed legacy messages safe.
        result = process_supporting_document.delay(document_id)
        task_id = str(getattr(result, "id", "") or "")
        if processing_job:
            update_processing_job(processing_job, stage=ProjectAIProcessingJob.STAGE_QUEUED, task_id=task_id)
            record_processing_event(
                processing_job,
                "task_published",
                stage=ProjectAIProcessingJob.STAGE_QUEUED,
                document=ProjectSupportingDocument.objects.filter(pk=document_id).first(),
                task_id=task_id,
            )
        logger.info(
            "AI document task published correlation_id=%s document_id=%s task_id=%s",
            getattr(processing_job, "correlation_id", ""), document_id, task_id,
        )
        return {"ok": True, "task_id": task_id}
    except Exception:
        logger.exception("Could not dispatch supporting document %s for processing", document_id)
        return {"ok": False, "task_id": ""}


def dispatch_project_document_processing(project, *, retry_failed=False, requested_by=None, revision=None):
    """Claim eligible documents and start extraction after Validator action.

    Contributors never call this helper. The project and document locks make
    repeated Validator clicks idempotent. Inline mode also reclaims a legacy
    queued/processing row because there is no worker executing it in that mode.
    """
    with transaction.atomic():
        locked_project = Project.objects.select_for_update().get(pk=project.pk)
        existing_job = active_processing_job(locked_project, revision=revision)
        source_hash = current_document_source_hash(locked_project, revision=revision)
        processing_job = existing_job or ProjectAIProcessingJob.objects.create(
            project=locked_project,
            revision=revision,
            requested_by=requested_by,
            source_hash=source_hash,
            status=ProjectAIProcessingJob.STATUS_QUEUED,
            stage=ProjectAIProcessingJob.STAGE_DISPATCH,
            heartbeat_at=timezone.now(),
        )
        if not existing_job:
            record_processing_event(processing_job, "requested", stage=ProjectAIProcessingJob.STAGE_DISPATCH)
        documents = list(
            (documents_for_revision(revision) if revision else active_project_documents(locked_project))
            # The active-document filter joins the nullable revision FK.
            # PostgreSQL cannot lock the nullable side of that outer join.
            .select_for_update(of=("self",))
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
                or (
                    document_processing_runs_inline()
                    and document.extraction_status in {
                        ProjectSupportingDocument.EXTRACTION_QUEUED,
                        ProjectSupportingDocument.EXTRACTION_PROCESSING,
                    }
                )
            )
        ]
        for document in candidates:
            document.extraction_status = ProjectSupportingDocument.EXTRACTION_QUEUED
            document.processing_error = ""
            document.processing_job = processing_job
            document.save(update_fields=["extraction_status", "processing_error", "processing_job", "updated_at"])

    queued_ids = []
    unavailable_ids = []
    for document in candidates:
        result = dispatch_document_processing(document.id)
        dispatched = result.get("ok", False) if isinstance(result, dict) else bool(result)
        if dispatched:
            queued_ids.append(document.id)
            continue
        ProjectSupportingDocument.objects.filter(pk=document.id).update(
            extraction_status=ProjectSupportingDocument.EXTRACTION_FAILED,
            processing_error="The document could not be prepared for AI analysis. A Validator can retry AI processing.",
        )
        fail_processing_job(
            processing_job,
            error_code="broker_publish_failed",
            error_message="The document could not be prepared for AI analysis. Retry AI processing.",
            document=document,
        )
        unavailable_ids.append(document.id)
    if queued_ids:
        # A direct task sets this to processing/completed itself. Preserve that
        # truthful terminal state instead of re-labelling it as queued.
        if not document_processing_runs_inline():
            update_processing_job(processing_job, status=ProjectAIProcessingJob.STATUS_QUEUED, stage=ProjectAIProcessingJob.STAGE_QUEUED)
    return {"queued_ids": queued_ids, "unavailable_ids": unavailable_ids, "job": processing_job}


def dispatch_document_assessment(assessment_id, *, processing_job=None):
    try:
        from .tasks import assess_supporting_documents

        if processing_job is None:
            assessment = ProjectDocumentAssessment.objects.select_related("processing_job").filter(pk=assessment_id).first()
            processing_job = getattr(assessment, "processing_job", None)

        if document_processing_runs_inline() or settings.CELERY_TASK_ALWAYS_EAGER:
            # Match document extraction: Validator action stays in the current
            # request when inline mode is selected, so no document worker or
            # Redis broker is required to reach a terminal result.
            assess_supporting_documents.run(assessment_id)
            return {"ok": True, "task_id": ""}
        result = assess_supporting_documents.delay(assessment_id)
        task_id = str(getattr(result, "id", "") or "")
        if processing_job:
            update_processing_job(processing_job, stage=ProjectAIProcessingJob.STAGE_ASSESSMENT, task_id=task_id)
            record_processing_event(
                processing_job,
                "assessment_task_published",
                stage=ProjectAIProcessingJob.STAGE_ASSESSMENT,
                assessment=ProjectDocumentAssessment.objects.filter(pk=assessment_id).first(),
                task_id=task_id,
            )
        return {"ok": True, "task_id": task_id}
    except Exception:
        logger.exception("Could not dispatch supporting document assessment %s", assessment_id)
        return {"ok": False, "task_id": ""}
