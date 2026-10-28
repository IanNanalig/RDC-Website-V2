from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .concern_categories import configured_categories
from .concern_delivery import deliver_project_concern, dispatch_project_concern_delivery
from .file_validation import ALLOWED_EVIDENCE_EXTENSIONS, validate_uploaded_document
from .models import Project, ProjectConcernEvidence, ProjectConcernReport
from .permissions import IsAdmin
from .views import _client_ip, _log_activity, _verify_turnstile


MAX_DESCRIPTION_LENGTH = 10_000
MIN_DESCRIPTION_LENGTH = 10
REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _public_project_queryset():
    return Project.objects.filter(validated=True, archived=False, is_active=True).select_related("primary_agency")


def _project_agency(project):
    if project.primary_agency_id:
        return project.primary_agency.code
    return str(project.agency or project.implementing_agency or "").strip()


def _ip_fingerprint(request):
    raw = _client_ip(request).strip() or "unknown"
    secret = str(settings.SECRET_KEY).encode("utf-8")
    return hmac.new(secret, f"project-concern:{raw}".encode("utf-8"), hashlib.sha256).hexdigest()


def _new_reference():
    stamp = timezone.localtime(timezone.now()).strftime("%Y%m%d")
    for _ in range(10):
        suffix = "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(10))
        reference = f"PCR-{stamp}-{suffix}"
        if not ProjectConcernReport.objects.filter(reference_code=reference).exists():
            return reference
    raise RuntimeError("Could not create a unique report reference")


def _delivery_payload(report):
    receiver_sent = report.receiver_delivery_status == ProjectConcernReport.DELIVERY_SENT
    if not receiver_sent:
        message = "Your report was accepted. Email notification delivery is pending retry."
    elif report.reporting_mode == report.MODE_EMAIL and report.acknowledgement_delivery_status != report.DELIVERY_SENT:
        message = "Your report was accepted and sent to the receiving office. Your acknowledgment email is pending retry."
    else:
        message = "Your report was accepted and sent to the receiving office."
    return {
        "accepted": True,
        "reference": report.reference_code,
        "notification_status": report.receiver_delivery_status,
        "acknowledgement_status": report.acknowledgement_delivery_status,
        "message": message,
    }


def _serialize_evidence(item):
    return {
        "id": item.id,
        "filename": item.original_filename,
        "content_type": item.content_type,
        "extension": item.extension,
        "size_bytes": item.size_bytes,
        "checksum_sha256": item.checksum_sha256,
    }


def _serialize_admin_report(report, *, detail=False):
    payload = {
        "reference": report.reference_code,
        "project_id": report.project_id_snapshot,
        "project_title": report.project_title_snapshot,
        "project_agency": report.project_agency_snapshot,
        "reporting_mode": report.reporting_mode,
        "category_code": report.category_code,
        "category_label": report.category_label_snapshot,
        "receiver_delivery_status": report.receiver_delivery_status,
        "acknowledgement_delivery_status": report.acknowledgement_delivery_status,
        "receiver_delivery_attempts": report.receiver_delivery_attempts,
        "acknowledgement_delivery_attempts": report.acknowledgement_delivery_attempts,
        "receiver_sent_at": report.receiver_sent_at,
        "acknowledgement_sent_at": report.acknowledgement_sent_at,
        "created_at": report.created_at,
        "evidence_count": getattr(report, "evidence_count", report.evidence_files.count()),
    }
    if detail:
        payload.update(
            {
                "reporter_email": report.reporter_email,
                "description": report.description,
                "receiver_last_error": report.receiver_last_error,
                "acknowledgement_last_error": report.acknowledgement_last_error,
                "evidence": [_serialize_evidence(item) for item in report.evidence_files.all()],
            }
        )
    return payload


class PublicProjectConcernOptionsView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "categories": [
                    {"code": item["code"], "label": item["label"]}
                    for item in configured_categories(active_only=True)
                ],
                "upload_policy": {
                    "allowed_extensions": sorted(ALLOWED_EVIDENCE_EXTENSIONS),
                    "max_files": settings.PROJECT_CONCERN_MAX_FILES,
                    "max_file_bytes": settings.PROJECT_CONCERN_MAX_FILE_BYTES,
                    "max_total_bytes": settings.PROJECT_CONCERN_MAX_TOTAL_BYTES,
                    "malware_scanned": False,
                },
                "turnstile_required": bool(getattr(settings, "TURNSTILE_REQUIRED", False)),
            }
        )


class PublicProjectConcernSubmitView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        submission_raw = str(request.data.get("submission_id") or "").strip()
        try:
            submission_id = uuid.UUID(submission_raw)
        except (ValueError, AttributeError):
            return Response({"detail": "A valid submission identifier is required."}, status=400)

        existing = ProjectConcernReport.objects.filter(client_submission_id=submission_id).first()
        if existing:
            existing.refresh_from_db()
            return Response(
                _delivery_payload(existing),
                status=201 if existing.receiver_delivery_status == existing.DELIVERY_SENT else 202,
            )

        captcha_token = str(request.data.get("captcha_token") or "").strip()
        if getattr(settings, "TURNSTILE_REQUIRED", False) and not _verify_turnstile(captcha_token, _client_ip(request)):
            return Response({"detail": "Captcha verification failed."}, status=400)

        fingerprint = _ip_fingerprint(request)
        now = timezone.now()
        hourly = ProjectConcernReport.objects.filter(
            abuse_fingerprint=fingerprint,
            created_at__gte=now - timedelta(hours=1),
        ).count()
        daily = ProjectConcernReport.objects.filter(
            abuse_fingerprint=fingerprint,
            created_at__gte=now - timedelta(days=1),
        ).count()
        if hourly >= settings.PROJECT_CONCERN_RATE_LIMIT_HOURLY or daily >= settings.PROJECT_CONCERN_RATE_LIMIT_DAILY:
            response = Response(
                {"detail": "Too many reports were submitted from this network. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = "3600"
            return response

        try:
            project_id = int(str(request.data.get("project_id") or "").strip())
        except (TypeError, ValueError):
            return Response({"detail": "Choose a valid public project."}, status=400)
        project = _public_project_queryset().filter(pk=project_id).first()
        if not project:
            return Response({"detail": "The selected project is not available for public reporting."}, status=400)

        mode = str(request.data.get("reporting_mode") or "").strip().lower()
        if mode not in {ProjectConcernReport.MODE_ANONYMOUS, ProjectConcernReport.MODE_EMAIL}:
            return Response({"detail": "Choose anonymous or email-enabled reporting."}, status=400)

        reporter_email = str(request.data.get("email") or "").strip().lower()
        if mode == ProjectConcernReport.MODE_ANONYMOUS:
            reporter_email = ""
        else:
            if not reporter_email:
                return Response({"detail": "Email is required for email-enabled reporting."}, status=400)
            try:
                validate_email(reporter_email)
            except ValidationError:
                return Response({"detail": "Enter a valid email address."}, status=400)

        category_code = str(request.data.get("category") or "").strip().lower()
        categories = {item["code"]: item for item in configured_categories(active_only=True)}
        category = categories.get(category_code)
        if not category:
            return Response({"detail": "Choose an active concern category."}, status=400)

        description = str(request.data.get("description") or "").strip()
        if len(description) < MIN_DESCRIPTION_LENGTH:
            return Response({"detail": f"Describe the concern using at least {MIN_DESCRIPTION_LENGTH} characters."}, status=400)
        if len(description) > MAX_DESCRIPTION_LENGTH:
            return Response({"detail": f"Description cannot exceed {MAX_DESCRIPTION_LENGTH:,} characters."}, status=400)

        uploads = request.FILES.getlist("evidence")
        if len(uploads) > settings.PROJECT_CONCERN_MAX_FILES:
            return Response({"detail": f"Attach no more than {settings.PROJECT_CONCERN_MAX_FILES} files."}, status=400)

        prepared_files = []
        total_bytes = 0
        checksums = set()
        for upload in uploads:
            raw_filename = os.path.basename(str(upload.name or "evidence"))
            filename = "".join(character for character in raw_filename if character >= " " and character not in {"\r", "\n"})[:255] or "evidence"
            extension = Path(filename).suffix.lower().lstrip(".")
            if extension not in ALLOWED_EVIDENCE_EXTENSIONS:
                return Response({"detail": f"{filename} is not a supported file type."}, status=400)
            if upload.size <= 0 or upload.size > settings.PROJECT_CONCERN_MAX_FILE_BYTES:
                return Response({"detail": f"{filename} must be no larger than 5 MB."}, status=400)
            data = upload.read(settings.PROJECT_CONCERN_MAX_FILE_BYTES + 1)
            if len(data) != upload.size or len(data) > settings.PROJECT_CONCERN_MAX_FILE_BYTES:
                return Response({"detail": f"The size of {filename} could not be verified."}, status=400)
            total_bytes += len(data)
            if total_bytes > settings.PROJECT_CONCERN_MAX_TOTAL_BYTES:
                return Response({"detail": "Attachments cannot exceed 15 MB in total."}, status=400)
            try:
                canonical_type = validate_uploaded_document(filename, upload.content_type, data, extension)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            checksum = hashlib.sha256(data).hexdigest()
            if checksum in checksums:
                return Response({"detail": f"{filename} duplicates another selected attachment."}, status=400)
            checksums.add(checksum)
            prepared_files.append((filename, extension, canonical_type, data, checksum))

        try:
            with transaction.atomic():
                report = ProjectConcernReport.objects.create(
                    reference_code=_new_reference(),
                    project=project,
                    project_id_snapshot=project.id,
                    project_title_snapshot=project.name,
                    project_agency_snapshot=_project_agency(project),
                    reporting_mode=mode,
                    reporter_email=reporter_email or None,
                    category_code=category["code"],
                    category_label_snapshot=category["label"],
                    description=description,
                    client_submission_id=submission_id,
                    abuse_fingerprint=fingerprint,
                    acknowledgement_delivery_status=(
                        ProjectConcernReport.DELIVERY_PENDING
                        if mode == ProjectConcernReport.MODE_EMAIL
                        else ProjectConcernReport.DELIVERY_NOT_APPLICABLE
                    ),
                )
                for filename, extension, content_type, data, checksum in prepared_files:
                    ProjectConcernEvidence.objects.create(
                        report=report,
                        original_filename=filename,
                        storage_name=f"{uuid.uuid4().hex}.{extension}",
                        content_type=content_type,
                        extension=extension,
                        size_bytes=len(data),
                        checksum_sha256=checksum,
                        content=data,
                    )
        except IntegrityError:
            existing = ProjectConcernReport.objects.filter(client_submission_id=submission_id).first()
            if not existing:
                return Response({"detail": "The report could not be accepted. Please try again."}, status=500)
            report = existing

        deliver_project_concern(report.id)
        report.refresh_from_db()
        if report.receiver_delivery_status != report.DELIVERY_SENT or (
            report.reporting_mode == report.MODE_EMAIL
            and report.acknowledgement_delivery_status != report.DELIVERY_SENT
        ):
            dispatch_project_concern_delivery(report.id)
            report.refresh_from_db()
        return Response(
            _delivery_payload(report),
            status=201 if report.receiver_delivery_status == report.DELIVERY_SENT else 202,
        )


class ProjectConcernPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class AdminProjectConcernListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        queryset = ProjectConcernReport.objects.all().prefetch_related("evidence_files")
        q = str(request.query_params.get("q") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(reference_code__icontains=q)
                | Q(project_title_snapshot__icontains=q)
                | Q(project_agency_snapshot__icontains=q)
                | Q(category_label_snapshot__icontains=q)
            )
        mode = str(request.query_params.get("reporting_mode") or "").strip()
        if mode in {ProjectConcernReport.MODE_ANONYMOUS, ProjectConcernReport.MODE_EMAIL}:
            queryset = queryset.filter(reporting_mode=mode)
        delivery = str(request.query_params.get("delivery_status") or "").strip()
        if delivery in dict(ProjectConcernReport.DELIVERY_CHOICES):
            queryset = queryset.filter(receiver_delivery_status=delivery)
        category = str(request.query_params.get("category") or "").strip()
        if category:
            queryset = queryset.filter(category_code=category)
        paginator = ProjectConcernPagination()
        page = paginator.paginate_queryset(queryset.order_by("-created_at"), request)
        return paginator.get_paginated_response([_serialize_admin_report(item) for item in page])


class AdminProjectConcernDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get_object(self, reference):
        return ProjectConcernReport.objects.prefetch_related("evidence_files").filter(reference_code=reference).first()

    def get(self, request, reference):
        report = self.get_object(reference)
        if not report:
            return Response({"detail": "Report not found."}, status=404)
        return Response(_serialize_admin_report(report, detail=True))


class AdminProjectConcernRetryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request, reference):
        report = ProjectConcernReport.objects.filter(reference_code=reference).first()
        if not report:
            return Response({"detail": "Report not found."}, status=404)
        result = deliver_project_concern(report.id)
        report.refresh_from_db()
        if result.get("status") == "pending_retry":
            dispatch_project_concern_delivery(report.id)
        _log_activity(
            request,
            "api_action",
            project=report.project,
            details={
                "action": "project_concern_delivery_retry",
                "reference": report.reference_code,
                "receiver_status": report.receiver_delivery_status,
                "acknowledgement_status": report.acknowledgement_delivery_status,
            },
        )
        return Response(_serialize_admin_report(report, detail=True))


class AdminProjectConcernEvidenceDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request, reference, evidence_id):
        evidence = ProjectConcernEvidence.objects.select_related("report", "report__project").filter(
            pk=evidence_id,
            report__reference_code=reference,
        ).first()
        if not evidence:
            return Response({"detail": "Evidence not found."}, status=404)
        _log_activity(
            request,
            "api_action",
            project=evidence.report.project,
            details={
                "action": "project_concern_evidence_download",
                "reference": evidence.report.reference_code,
                "evidence_id": evidence.id,
            },
        )
        response = HttpResponse(bytes(evidence.content), content_type=evidence.content_type)
        safe_name = f"{evidence.report.reference_code}-Evidence-{evidence.id}.{evidence.extension}"
        response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response
