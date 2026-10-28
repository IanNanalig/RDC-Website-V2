from __future__ import annotations

import csv
import logging
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

from django.db.models import OuterRef, Q, Subquery
from django.http import FileResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project, ProjectPriorityConfirmation, User, UserActivity
from .permissions import IsAdmin


logger = logging.getLogger(__name__)
MANILA = ZoneInfo("Asia/Manila")
PROJECT_FILTERS = {
    "search",
    "agency",
    "budget_min",
    "budget_max",
    "start_year",
    "end_year",
    "workflow_status",
    "implementation_status",
    "development_sector",
    "convergence_program",
    "funding_source",
    "rdp_main_chapter",
    "archive_state",
}
USER_FILTERS = {"search", "role", "agency", "account_status"}
WORKFLOW_LABELS = {
    "draft": "Draft",
    "pending_validation": "Pending Validation",
    "needs_revision": "Needs Revision",
    "validated": "Validated",
    "rejected": "Rejected",
}
ROLE_LABELS = {
    "admin": "Administrator",
    "validator": "Validator",
    "staff": "Contributor",
    "content_editor": "Content Editor",
}
ACCOUNT_STATUS_LABELS = {"active": "Active", "inactive": "Inactive"}
ARCHIVE_STATE_LABELS = {"active": "Active", "archived": "Archived", "all": "All"}


class ExportValidationError(ValueError):
    pass


def _text(value, *, maximum=250):
    value = " ".join(str(value or "").split())
    if len(value) > maximum:
        raise ExportValidationError(f"Filter values are limited to {maximum} characters.")
    return value


def _whole_number(value, label, *, minimum=0, maximum=None):
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        number = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ExportValidationError(f"{label} must be a whole number.")
    if not number.is_finite() or number != number.to_integral_value():
        raise ExportValidationError(f"{label} must be a whole number.")
    number = int(number)
    if number < minimum or (maximum is not None and number > maximum):
        if maximum is None:
            raise ExportValidationError(f"{label} must be at least {minimum}.")
        raise ExportValidationError(f"{label} must be between {minimum} and {maximum}.")
    return number


def _validate_request(query, *, include_format=False):
    category = str(query.get("category") or "").strip().lower()
    if category not in {"projects", "users"}:
        raise ExportValidationError("Category must be projects or users.")

    allowed = {"category"} | (PROJECT_FILTERS if category == "projects" else USER_FILTERS)
    if include_format:
        allowed.add("file_format")
    unknown = sorted(set(query.keys()) - allowed)
    if unknown:
        raise ExportValidationError(f"Unsupported filter: {unknown[0]}.")

    cleaned = {}
    for key in allowed - {"category", "file_format"}:
        value = _text(query.get(key))
        if value:
            cleaned[key] = value

    if category == "projects":
        cleaned["archive_state"] = cleaned.get("archive_state", "active").lower()
        if cleaned["archive_state"] not in ARCHIVE_STATE_LABELS:
            raise ExportValidationError("Archive state must be active, archived, or all.")
        if "workflow_status" in cleaned:
            cleaned["workflow_status"] = cleaned["workflow_status"].lower().replace("-", "_")
            if cleaned["workflow_status"] not in WORKFLOW_LABELS:
                raise ExportValidationError("Invalid workflow status.")
        for key, label in (("budget_min", "Minimum budget"), ("budget_max", "Maximum budget")):
            if key in cleaned:
                cleaned[key] = _whole_number(cleaned[key], label)
        for key, label in (("start_year", "Start year"), ("end_year", "End year")):
            if key in cleaned:
                cleaned[key] = _whole_number(cleaned[key], label, minimum=1900, maximum=2200)
        if cleaned.get("budget_min") is not None and cleaned.get("budget_max") is not None:
            if cleaned["budget_min"] > cleaned["budget_max"]:
                raise ExportValidationError("Minimum budget cannot be greater than maximum budget.")
    else:
        if "role" in cleaned:
            role = cleaned["role"].lower().replace("-", "_")
            if role in {"employee", "contributor"}:
                role = "staff"
            if role not in ROLE_LABELS:
                raise ExportValidationError("Invalid user role.")
            cleaned["role"] = role
        if "account_status" in cleaned:
            cleaned["account_status"] = cleaned["account_status"].lower()
            if cleaned["account_status"] not in ACCOUNT_STATUS_LABELS:
                raise ExportValidationError("Account status must be active or inactive.")

    export_format = None
    if include_format:
        export_format = str(query.get("file_format") or "").strip().lower()
        if export_format not in {"csv", "pdf"}:
            raise ExportValidationError("Format must be csv or pdf.")
    return category, cleaned, export_format


def _simplified(project):
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    value = profile.get("simplified_form")
    return value if isinstance(value, dict) else {}


def _review_status(project):
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    review = profile.get("validator_review")
    return str(review.get("review_status") or "").strip().lower() if isinstance(review, dict) else ""


def _workflow_status(project):
    review = _review_status(project)
    if review == "reviewed":
        return "needs_revision"
    if review == "rejected":
        return "rejected"
    if review == "endorsed" or project.validated or project.status == "completed":
        return "validated"
    if project.status == "proposed":
        return "pending_validation"
    if project.status == "planning":
        return "draft"
    return str(project.status or "")


def _project_queryset(filters):
    qs = Project.objects.select_related("created_by", "primary_agency").prefetch_related(
        "collaborating_agency_links__agency"
    ).order_by("-created_at", "-id")
    archive_state = filters.get("archive_state", "active")
    if archive_state != "all":
        qs = qs.filter(archived=archive_state == "archived")
    if filters.get("search"):
        search = filters["search"]
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(agency__icontains=search)
            | Q(profile_data__simplified_form__projectActivity__icontains=search)
            | Q(profile_data__simplified_form__description__icontains=search)
            | Q(created_by__username__icontains=search)
            | Q(created_by__first_name__icontains=search)
            | Q(created_by__last_name__icontains=search)
            | Q(collaborating_agency_links__agency__code__icontains=search)
            | Q(collaborating_agency_links__agency__name__icontains=search)
        ).distinct()
    if filters.get("agency"):
        qs = qs.filter(
            Q(profile_data__simplified_form__agencyName__iexact=filters["agency"])
            | Q(agency__iexact=filters["agency"])
        )
    json_filters = {
        "implementation_status": "status",
        "development_sector": "developmentSector",
        "funding_source": "fundingSource",
        "rdp_main_chapter": "rdpMainChapter",
    }
    for filter_name, json_key in json_filters.items():
        if filters.get(filter_name) is not None:
            lookup = {f"profile_data__simplified_form__{json_key}__iexact": str(filters[filter_name])}
            qs = qs.filter(**lookup)
    if filters.get("convergence_program"):
        if filters["convergence_program"] == "__none__":
            qs = qs.filter(
                Q(profile_data__simplified_form__pcbProgram__isnull=True)
                | Q(profile_data__simplified_form__pcbProgram="")
            )
        else:
            qs = qs.filter(profile_data__simplified_form__pcbProgram__iexact=filters["convergence_program"])

    canonical_filters = {key: filters.get(key) for key in (
        "agency", "budget_min", "budget_max", "start_year", "end_year"
    ) if filters.get(key) is not None and filters.get(key) != ""}
    if canonical_filters:
        ids = []
        for project in qs.select_related(None).only(
            "id", "agency", "budget", "year", "profile_data"
        ).iterator(chunk_size=500):
            sf = _simplified(project)
            agency = str(sf.get("agencyName") or project.agency or "").strip()
            budget = _project_budget(project, sf)
            start_year = str(sf.get("startYear") or project.year or "").strip()
            end_year = str(sf.get("endYear") or "").strip()
            if canonical_filters.get("agency") and agency.casefold() != str(canonical_filters["agency"]).casefold():
                continue
            if canonical_filters.get("budget_min") is not None and budget < canonical_filters["budget_min"]:
                continue
            if canonical_filters.get("budget_max") is not None and budget > canonical_filters["budget_max"]:
                continue
            if canonical_filters.get("start_year") is not None and start_year != str(canonical_filters["start_year"]):
                continue
            if canonical_filters.get("end_year") is not None and end_year != str(canonical_filters["end_year"]):
                continue
            ids.append(project.pk)
        qs = qs.filter(pk__in=ids)

    if filters.get("workflow_status"):
        expected = filters["workflow_status"]
        ids = [
            project.pk
            for project in qs.select_related(None).only(
                "id", "status", "validated", "profile_data"
            ).iterator(chunk_size=500)
            if _workflow_status(project) == expected
        ]
        qs = qs.filter(pk__in=ids)

    latest_priority = ProjectPriorityConfirmation.objects.filter(
        analysis__project_id=OuterRef("pk")
    ).order_by("-created_at").values("final_priority")[:1]
    return qs.annotate(export_priority=Subquery(latest_priority))


def _user_queryset(filters):
    qs = User.objects.all().order_by("username", "id")
    if filters.get("search"):
        search = filters["search"]
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(username__icontains=search)
            | Q(email__icontains=search)
        )
    if filters.get("role"):
        qs = qs.filter(role=filters["role"])
    if filters.get("agency") == "__none__":
        qs = qs.filter(Q(agency="") | Q(agency__isnull=True))
    elif filters.get("agency"):
        qs = qs.filter(agency__iexact=filters["agency"])
    if filters.get("account_status"):
        qs = qs.filter(is_active=filters["account_status"] == "active")
    return qs


def _queryset(category, filters):
    return _project_queryset(filters) if category == "projects" else _user_queryset(filters)


def _display_name(user):
    if not user:
        return ""
    return (user.get_full_name() or user.username or "").strip()


def _date_time(value):
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value, MANILA)
    return value.strftime("%Y-%m-%d %I:%M %p")


def _csv_date_time(value):
    if not value:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value, MANILA)
    # The leading apostrophe is Excel's text marker. It prevents narrow date/time
    # columns from rendering as ####### while preserving the complete timestamp.
    return "'" + value.strftime("%Y-%m-%d %I:%M:%S %p PHT")


def _project_budget(project, sf):
    try:
        raw_total = sf.get("fundingRequirementTotal")
        if raw_total not in (None, ""):
            return int(Decimal(str(raw_total).replace(",", "")))
        yearly = sf.get("fundingRequirementByYear")
        if isinstance(yearly, dict) and yearly:
            return int(sum(Decimal(str(item or 0).replace(",", "")) for item in yearly.values()))
    except (InvalidOperation, ValueError, TypeError, AttributeError):
        pass
    return int(project.budget or 0)


def _location(value):
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _priority_label(value):
    return {"high": "Priority", "low": "Non-Priority"}.get(str(value or "").lower(), "Not Reviewed")


PROJECT_CSV_HEADERS = [
    "Project ID", "Project/Activity", "Program", "Primary Agency", "Collaborating Agencies", "Contributor", "Location",
    "Description", "Objective", "Total Budget (PHP)", "Start Year", "End Year",
    "Funding Source", "Workflow Status", "Implementation Status", "Priority",
    "RDC-NCR Development Sector", "Convergence Program", "RDP-NCR Main Chapter",
    "Created", "Updated", "Archive State",
]
PROJECT_PDF_HEADERS = [
    "ID", "Project", "Primary Agency", "Collaborators", "Budget", "Period", "Workflow", "Implementation",
    "Development Sector", "Convergence Program", "Priority",
]
USER_CSV_HEADERS = [
    "User ID", "Name", "Username", "Email", "Role", "Agency", "Agency Head", "Office",
    "Division", "Position", "Office Contact Number", "Phone Number", "Account Status",
    "Date Joined", "Last Login",
]
USER_PDF_HEADERS = ["ID", "Name", "Email", "Role", "Agency", "Office / Division", "Status", "Date Joined"]


def _project_csv_row(project):
    sf = _simplified(project)
    collaborators = ", ".join(link.agency.code for link in project.collaborating_agency_links.all())
    return [
        project.pk,
        sf.get("projectActivity") or project.name,
        sf.get("program") or "",
        sf.get("agencyName") or project.agency or project.implementing_agency,
        collaborators,
        _display_name(project.created_by),
        _location(sf.get("location")),
        sf.get("description") or project.description,
        sf.get("objective") or "",
        _project_budget(project, sf),
        sf.get("startYear") or project.year or "",
        sf.get("endYear") or "",
        sf.get("fundingSource") or "",
        WORKFLOW_LABELS.get(_workflow_status(project), _workflow_status(project).replace("_", " ").title()),
        sf.get("status") or "",
        _priority_label(getattr(project, "export_priority", "")),
        sf.get("developmentSector") or "",
        sf.get("pcbProgram") or "Not part of a convergence program",
        sf.get("rdpMainChapter") or "",
        _csv_date_time(project.created_at),
        _csv_date_time(project.updated_at),
        "Archived" if project.archived else "Active",
    ]


def _project_pdf_row(project):
    sf = _simplified(project)
    collaborators = ", ".join(link.agency.code for link in project.collaborating_agency_links.all()) or "None"
    start = sf.get("startYear") or project.year or ""
    end = sf.get("endYear") or ""
    period = f"{start}-{end}" if start and end else str(start or end)
    return [
        project.pk,
        sf.get("projectActivity") or project.name,
        sf.get("agencyName") or project.agency or project.implementing_agency,
        collaborators,
        f"PHP {_project_budget(project, sf):,}",
        period,
        WORKFLOW_LABELS.get(_workflow_status(project), _workflow_status(project).replace("_", " ").title()),
        sf.get("status") or "",
        sf.get("developmentSector") or "",
        sf.get("pcbProgram") or "None",
        _priority_label(getattr(project, "export_priority", "")),
    ]


def _user_csv_row(user):
    return [
        user.pk, _display_name(user), user.username, user.email or "", ROLE_LABELS.get(user.role, user.role),
        user.agency or "", user.agency_head or "", user.office or "", user.division or "",
        user.position or "", user.contact_number or "", user.phone_number or "",
        "Active" if user.is_active else "Inactive", _csv_date_time(user.date_joined), _csv_date_time(user.last_login),
    ]


def _user_pdf_row(user):
    office = " / ".join(part for part in (user.office, user.division) if part)
    return [
        user.pk, _display_name(user), user.email or "", ROLE_LABELS.get(user.role, user.role),
        user.agency or "", office, "Active" if user.is_active else "Inactive", _date_time(user.date_joined),
    ]


def _csv_safe(value):
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if value.startswith(("\t", "\r")) or (stripped and stripped[0] in "=+-@"):
        return "'" + value
    return value


class _Echo:
    def write(self, value):
        return value


def _csv_stream(headers, rows: Iterable[list]):
    writer = csv.writer(_Echo(), lineterminator="\r\n")
    yield "\ufeff" + writer.writerow(headers)
    for row in rows:
        yield writer.writerow([_csv_safe(value) for value in row])


def _reportlab_font():
    import reportlab
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    name = "RDCExportVera"
    if name not in pdfmetrics.getRegisteredFontNames():
        font_path = Path(reportlab.__file__).resolve().parent / "fonts" / "Vera.ttf"
        pdfmetrics.registerFont(TTFont(name, str(font_path)))
    return name


def _wrap_pdf_text(value, width, font_name, font_size):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    text = " ".join(str(value if value is not None else "").replace("\n", " ").split()) or "-"
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        while stringWidth(current, font_name, font_size) > width and len(current) > 1:
            split_at = max(1, int(len(current) * width / stringWidth(current, font_name, font_size)))
            lines.append(current[:split_at])
            current = current[split_at:]
    if current:
        lines.append(current)
    return lines or ["-"]


def _filter_summary(category, filters):
    if not filters or (category == "projects" and filters == {"archive_state": "active"}):
        return "Filters: Active projects" if category == "projects" else "Filters: All users"
    labels = {
        "search": "Search", "agency": "Agency", "budget_min": "Minimum budget",
        "budget_max": "Maximum budget", "start_year": "Start year", "end_year": "End year",
        "workflow_status": "Workflow", "implementation_status": "Implementation status",
        "development_sector": "Development sector", "convergence_program": "Convergence program",
        "funding_source": "Funding source", "rdp_main_chapter": "RDP-NCR chapter",
        "archive_state": "Archive state", "role": "Role", "account_status": "Account status",
    }
    parts = []
    for key, value in filters.items():
        display = value
        if key == "workflow_status":
            display = WORKFLOW_LABELS.get(str(value), value)
        elif key == "archive_state":
            display = ARCHIVE_STATE_LABELS.get(str(value), value)
        elif key == "role":
            display = ROLE_LABELS.get(str(value), value)
        elif key == "account_status":
            display = ACCOUNT_STATUS_LABELS.get(str(value), value)
        elif key == "convergence_program" and value == "__none__":
            display = "No convergence program"
        elif key.startswith("budget_"):
            display = f"PHP {int(value):,}"
        parts.append(f"{labels.get(key, key.replace('_', ' ').title())}: {display}")
    return "Filters: " + "; ".join(parts)


def _pdf_file(category, filters, rows, count):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    headers = PROJECT_PDF_HEADERS if category == "projects" else USER_PDF_HEADERS
    proportions = ([0.035, 0.14, 0.08, 0.08, 0.08, 0.06, 0.085, 0.085, 0.12, 0.12, 0.075]
                   if category == "projects" else [0.04, 0.15, 0.20, 0.09, 0.12, 0.16, 0.08, 0.10])
    row_builder = _project_pdf_row if category == "projects" else _user_pdf_row
    output = tempfile.SpooledTemporaryFile(max_size=5 * 1024 * 1024, mode="w+b")
    width, height = landscape(A4)
    left = right = 24
    bottom = 28
    usable = width - left - right
    total = sum(proportions)
    col_widths = [usable * value / total for value in proportions]
    font_name = _reportlab_font()
    pdf = canvas.Canvas(output, pagesize=(width, height), pageCompression=1)
    page = 0
    y = 0
    body_size = 6.4
    line_height = 7.6

    def draw_page_header(first=False):
        nonlocal page, y
        page += 1
        pdf.setFillColor(colors.HexColor("#0f2a55"))
        pdf.rect(0, height - 46, width, 46, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont(font_name, 15 if first else 12)
        pdf.drawString(left, height - 29, f"RDC-NCR {category.title()} Export")
        pdf.setFont(font_name, 7)
        pdf.drawRightString(width - right, height - 27, f"Page {page}")
        y = height - 60
        if first:
            generated = timezone.localtime(timezone.now(), MANILA).strftime("Generated %B %d, %Y at %I:%M %p")
            pdf.setFillColor(colors.HexColor("#334155"))
            pdf.setFont(font_name, 8)
            pdf.drawString(left, y, f"{generated}  |  {count:,} matching record{'s' if count != 1 else ''}")
            y -= 13
            summary_lines = _wrap_pdf_text(_filter_summary(category, filters), usable, font_name, 7.2)
            pdf.setFont(font_name, 7.2)
            for line in summary_lines:
                pdf.drawString(left, y, line)
                y -= 9
            y -= 5
        draw_table_header()

    def draw_table_header():
        nonlocal y
        header_height = 24
        x = left
        pdf.setFillColor(colors.HexColor("#1d4e89"))
        pdf.rect(left, y - header_height, usable, header_height, fill=1, stroke=0)
        pdf.setFillColor(colors.white)
        pdf.setFont(font_name, 6.6)
        for header, col_width in zip(headers, col_widths):
            lines = _wrap_pdf_text(header, col_width - 6, font_name, 6.6)
            text_y = y - 9
            for line in lines[:2]:
                pdf.drawString(x + 3, text_y, line)
                text_y -= 7
            x += col_width
        y -= header_height

    draw_page_header(first=True)
    for row_index, item in enumerate(rows):
        values = row_builder(item)
        wrapped = [_wrap_pdf_text(value, col_width - 6, font_name, body_size)
                   for value, col_width in zip(values, col_widths)]
        row_height = max(18, max(len(lines) for lines in wrapped) * line_height + 6)
        if y - row_height < bottom:
            pdf.showPage()
            draw_page_header(first=False)
        if row_index % 2:
            pdf.setFillColor(colors.HexColor("#f1f5f9"))
            pdf.rect(left, y - row_height, usable, row_height, fill=1, stroke=0)
        pdf.setStrokeColor(colors.HexColor("#cbd5e1"))
        pdf.rect(left, y - row_height, usable, row_height, fill=0, stroke=1)
        pdf.setFillColor(colors.HexColor("#172033"))
        pdf.setFont(font_name, body_size)
        x = left
        for lines, col_width in zip(wrapped, col_widths):
            pdf.line(x, y, x, y - row_height)
            text_y = y - 9
            for line in lines:
                pdf.drawString(x + 3, text_y, line)
                text_y -= line_height
            x += col_width
        pdf.line(left + usable, y, left + usable, y - row_height)
        y -= row_height
    pdf.save()
    output.seek(0)
    return output


def _filename(category, export_format):
    stamp = timezone.localtime(timezone.now(), MANILA).strftime("%Y%m%d-%H%M%S")
    return f"rdc-ncr-{category}-{stamp}.{export_format}"


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", ""))[:64]


def _audit(request, event, *, category, export_format="", filters=None, count=None, filename="", error=""):
    details = {"action": "data_export", "category": category}
    if export_format:
        details["format"] = export_format
    if filters is not None:
        details["filters"] = filters
    if count is not None:
        details["record_count"] = count
    if filename:
        details["filename"] = filename
    if error:
        details["error"] = error[:200]
    UserActivity.objects.create(
        user=request.user,
        role=request.user.role,
        event=event,
        ip_address=_client_ip(request),
        details=details,
    )


def _values(values):
    return [{"value": value, "label": value} for value in sorted(values, key=str.casefold)]


def _project_options():
    agencies = set()
    implementation_statuses = set()
    sectors = set()
    convergence_programs = set()
    funding_sources = set()
    chapters = set()
    no_convergence = False
    for agency, profile in Project.objects.values_list("agency", "profile_data").iterator(chunk_size=500):
        sf = profile.get("simplified_form") if isinstance(profile, dict) else None
        sf = sf if isinstance(sf, dict) else {}
        canonical_agency = str(sf.get("agencyName") or agency or "").strip()
        if canonical_agency:
            agencies.add(canonical_agency)
        for target, key in (
            (implementation_statuses, "status"), (sectors, "developmentSector"),
            (funding_sources, "fundingSource"), (chapters, "rdpMainChapter"),
        ):
            value = str(sf.get(key) or "").strip()
            if value:
                target.add(value)
        convergence = str(sf.get("pcbProgram") or "").strip()
        if convergence:
            convergence_programs.add(convergence)
        else:
            no_convergence = True
    convergence = _values(convergence_programs)
    if no_convergence:
        convergence.insert(0, {"value": "__none__", "label": "No convergence program"})
    return {
        "agencies": _values(agencies),
        "workflow_statuses": [{"value": key, "label": label} for key, label in WORKFLOW_LABELS.items()],
        "implementation_statuses": _values(implementation_statuses),
        "development_sectors": _values(sectors),
        "convergence_programs": convergence,
        "funding_sources": _values(funding_sources),
        "rdp_main_chapters": _values(chapters),
        "archive_states": [{"value": key, "label": label} for key, label in ARCHIVE_STATE_LABELS.items()],
    }


def _user_options():
    agencies = {str(value).strip() for value in User.objects.values_list("agency", flat=True) if str(value or "").strip()}
    has_no_agency = User.objects.filter(Q(agency="") | Q(agency__isnull=True)).exists()
    agency_options = _values(agencies)
    if has_no_agency:
        agency_options.insert(0, {"value": "__none__", "label": "No agency"})
    return {
        "roles": [{"value": key, "label": ROLE_LABELS.get(key, label)} for key, label in User.ROLE_CHOICES],
        "agencies": agency_options,
        "account_statuses": [{"value": key, "label": label} for key, label in ACCOUNT_STATUS_LABELS.items()],
    }


class AdminExportOptionsView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        try:
            category, _, _ = _validate_request(request.query_params)
            options = _project_options() if category == "projects" else _user_options()
            return Response({"category": category, "options": options})
        except ExportValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"detail": "Export options could not be loaded."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminExportCountView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        try:
            category, filters, _ = _validate_request(request.query_params)
            count = _queryset(category, filters).count()
            return Response({"category": category, "count": count, "filters": filters})
        except ExportValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"detail": "Matching records could not be counted."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminExportDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        category = str(request.query_params.get("category") or "").strip().lower() or "unknown"
        export_format = str(request.query_params.get("file_format") or "").strip().lower()
        filters = None
        try:
            category, filters, export_format = _validate_request(request.query_params, include_format=True)
            queryset = _queryset(category, filters)
            count = queryset.count()
            if count == 0:
                raise ExportValidationError("No records match the selected criteria.")
            filename = _filename(category, export_format)
            rows = queryset.iterator(chunk_size=500)
            if export_format == "csv":
                headers = PROJECT_CSV_HEADERS if category == "projects" else USER_CSV_HEADERS
                row_builder = _project_csv_row if category == "projects" else _user_csv_row
                response = StreamingHttpResponse(
                    _csv_stream(headers, (row_builder(item) for item in rows)),
                    content_type="text/csv; charset=utf-8",
                )
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
            else:
                output = _pdf_file(category, filters, rows, count)
                response = FileResponse(output, as_attachment=True, filename=filename, content_type="application/pdf")
            response["Cache-Control"] = "no-store, private"
            response["X-Content-Type-Options"] = "nosniff"
            _audit(request, "api_action", category=category, export_format=export_format,
                   filters=filters, count=count, filename=filename)
            return response
        except ExportValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Administrator export generation failed")
            _audit(request, "api_action_failed", category=category, export_format=export_format,
                   filters=filters, error="Export generation failed")
            return Response({"detail": "The export could not be generated. Please try again."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
