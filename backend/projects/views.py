from __future__ import annotations

import json
import io
import csv
import os
import re
import string
import difflib
import urllib.parse
import urllib.request
import hashlib
import hmac
import secrets
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, EmailMessage
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q, Value, TextField, CharField
from django.db.models.functions import Cast, Coalesce, Concat, NullIf
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from cms.form_schema import FormSchemaError, validate_simplified_answers
from rest_framework_simplejwt.tokens import AccessToken
from .authentication import SESSION_IDLE_TIMEOUT
from .models import (
    AccessRequest,
    Agency,
    Notification,
    PasswordResetChallenge,
    PasswordSetupToken,
    PortalSession,
    ProfileEditRequest,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    ProjectSupportingDocument,
    Project,
    ProjectCollaboratingAgency,
    ProjectComment,
    ProjectRevision,
    PublicEvent,
    SystemSetting,
    User,
    UserInvitation,
    UserActivity,
)
from .serializers import (
    AccessRequestSerializer,
    NotificationSerializer,
    ProjectCommentSerializer,
    PublicEventSerializer,
    PublicProjectSerializer,
    PublicProjectSummarySerializer,
    ProjectSerializer,
    ProjectFormMigrationSummarySerializer,
    ProjectSummarySerializer,
    ProjectRevisionSerializer,
    ProjectRevisionSummarySerializer,
    UserActivitySerializer,
    UserSerializer,
    ProjectPriorityAnalysisSerializer,
    ProjectSupportingDocumentSerializer,
)
from .public_summary import build_public_summary
from .project_status import (
    NOT_IMPLEMENTED_LEGACY_VALUES,
    ONGOING_LEGACY_VALUES,
    canonical_implementation_status,
)
from .priority_scoring import analyze_project, confirm_analysis, ensure_analysis_guidance, has_matching_confirmation
from .document_policy import (
    PROJECT_DOCUMENT_MAX_TOTAL_BYTES,
    active_project_documents,
    resolve_project_document_policy,
    validate_project_documents_for_submit,
)
from .document_assessments import (
    dispatch_document_assessment,
    dispatch_document_processing,
    ensure_queued_assessment,
    serialize_document_assessment,
)
from .utils import derive_ncr_lgus, format_project_locations
from .form_migrations import (
    analyze_profile_migration,
    migration_eligibility,
    prepare_project_migration,
    saved_form_marker,
)
from .file_validation import validate_uploaded_document


ENCODING_WINDOW_KEY = "portal_encoding_window"
PROGRESS_UPDATE_WINDOW_KEY = "portal_progress_update_window"
PASSWORD_SETUP_TTL_HOURS = 24
REGISTRATION_INVITE_PREFIX = "invite:"
REGISTRATION_INVITE_SALT = "rdc-registration-invite-v1"
BATCH_INVITE_PREVIEW_SALT = "rdc-batch-registration-preview-v1"
BATCH_ARCHIVE_PREVIEW_SALT = "rdc-batch-archive-preview-v1"
BATCH_FORM_MIGRATION_PREVIEW_SALT = "rdc-batch-form-migration-preview-v1"
PASSWORD_RESET_WINDOW_SECONDS = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_WINDOW", 3600))
PASSWORD_RESET_LIMIT_EMAIL = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_EMAIL", 3))
PASSWORD_RESET_LIMIT_IP = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_IP", 10))
PASSWORD_RESET_OTP_TTL_SECONDS = int(getattr(settings, "PASSWORD_RESET_OTP_TTL_SECONDS", 600))
PASSWORD_RESET_TOKEN_TTL_SECONDS = int(getattr(settings, "PASSWORD_RESET_TOKEN_TTL_SECONDS", 600))
PASSWORD_RESET_RESEND_COOLDOWN_SECONDS = int(getattr(settings, "PASSWORD_RESET_RESEND_COOLDOWN_SECONDS", 60))
PASSWORD_RESET_MAX_ATTEMPTS = int(getattr(settings, "PASSWORD_RESET_MAX_ATTEMPTS", 5))
ACCOUNT_AGENCIES = {
    "MMDA": "Metropolitan Manila Development Authority",
    "DPWH": "Department of Public Works and Highways",
    "DENR": "Department of Environment and Natural Resources",
    "RDC-NCR": "Regional Development Council National Capital Region",
    "DILG": "Department of the Interior and Local Government",
    "DEPDev": "Department of Economy, Planning, and Development",
    "DBM": "Department of Budget and Management",
    "DA": "Department of Agriculture",
    "DAR": "Department of Agrarian Reform",
    "DepEd": "Department of Education",
    "DOH": "Department of Health",
    "DHSUD": "Department of Human Settlements and Urban Development",
    "DICT": "Department of Information and Communications Technology",
    "DOLE": "Department of Labor and Employment",
    "DOST": "Department of Science and Technology",
    "DSWD": "Department of Social Welfare and Development",
    "DOT": "Department of Tourism",
    "DTI": "Department of Trade and Industry",
    "DOTr": "Department of Transportation",
    "TESDA": "Technical Education and Skills Development Authority",
    "CHED": "Commission on Higher Education",
    "PSA": "Philippine Statistics Authority",
}
INTERNAL_ACCOUNT_ROLES = {"admin", "validator", "content_editor"}


def _normalize_account_agency(value):
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        return ""
    try:
        agency = Agency.objects.filter(
            Q(code__iexact=normalized) | Q(name__iexact=normalized),
            is_active=True,
        ).only("code").first()
        if agency:
            return agency.code
    except Exception:
        # Keep startup and historical migrations compatible before the catalog table exists.
        pass
    normalized_value = normalized.casefold()
    return next(
        (
            code
            for code, full_name in ACCOUNT_AGENCIES.items()
            if code.casefold() == normalized_value or full_name.casefold() == normalized_value
        ),
        "",
    )


def _active_agency_options():
    try:
        rows = list(Agency.objects.filter(is_active=True).order_by("code").values("code", "name"))
        if rows:
            return rows
    except Exception:
        pass
    return [{"code": code, "name": name} for code, name in ACCOUNT_AGENCIES.items()]


def _agency_for_value(value, *, active_only=False):
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        return None
    queryset = Agency.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    return queryset.filter(Q(code__iexact=normalized) | Q(name__iexact=normalized)).first()


def _project_primary_agency_code(project):
    agency = getattr(project, "primary_agency", None)
    if agency is not None:
        return agency.code
    raw = str(getattr(project, "agency", "") or "").strip()
    return _normalize_account_agency(raw) or raw


def _is_primary_agency_contributor(user, project):
    if getattr(user, "role", "") not in ("staff", "employee"):
        return False
    user_code = _normalize_account_agency(getattr(user, "agency", ""))
    primary_code = _project_primary_agency_code(project)
    return bool(user_code and primary_code and user_code.casefold() == primary_code.casefold())


def _is_collaborating_agency_contributor(user, project):
    if getattr(user, "role", "") not in ("staff", "employee") or project.status == "planning":
        return False
    user_code = _normalize_account_agency(getattr(user, "agency", ""))
    return bool(
        user_code
        and ProjectCollaboratingAgency.objects.filter(
            project=project,
            agency__code__iexact=user_code,
            agency__is_active=True,
        ).exists()
    )


def _validate_collaborating_agencies(profile_data, primary_agency):
    simplified = _simplified_from_profile(profile_data)
    if "collaboratingAgencies" not in simplified:
        return None
    values = simplified.get("collaboratingAgencies")
    if values in (None, ""):
        values = []
    if not isinstance(values, list):
        return "Collaborating Agencies must be a list."
    if len(values) > 20:
        return "Select no more than 20 collaborating agencies."
    normalized = [str(value or "").strip() for value in values]
    if any(not value for value in normalized):
        return "Collaborating Agencies contains an empty selection."
    if len({value.casefold() for value in normalized}) != len(normalized):
        return "A collaborating agency can only be selected once."
    primary_code = getattr(primary_agency, "code", "") or str(primary_agency or "")
    resolved = []
    for value in normalized:
        agency = _agency_for_value(value, active_only=True)
        if agency is None:
            return f"Unknown or inactive collaborating agency: {value}."
        if primary_code and agency.code.casefold() == primary_code.casefold():
            return "The primary agency cannot also be a collaborating agency."
        resolved.append(agency)
    return resolved


def _sync_project_collaborators(project, profile_data, actor=None):
    simplified = _simplified_from_profile(profile_data)
    if "collaboratingAgencies" not in simplified:
        return
    resolved = _validate_collaborating_agencies(profile_data, project.primary_agency or project.agency)
    if isinstance(resolved, str):
        raise ValidationError(resolved)
    target_ids = {agency.id for agency in resolved}
    existing_links = list(
        ProjectCollaboratingAgency.objects.filter(project=project).select_related("agency")
    )
    existing_ids = {link.agency_id for link in existing_links}
    existing_codes = sorted(link.agency.code for link in existing_links)
    ProjectCollaboratingAgency.objects.filter(project=project).exclude(agency_id__in=target_ids).delete()
    ProjectCollaboratingAgency.objects.bulk_create(
        [
            ProjectCollaboratingAgency(project=project, agency=agency, added_by=actor)
            for agency in resolved
            if agency.id not in existing_ids
        ],
        ignore_conflicts=True,
    )
    target_codes = sorted(agency.code for agency in resolved)
    if actor and existing_codes != target_codes:
        UserActivity.objects.create(
            user=actor,
            actor_username=getattr(actor, "username", "") or "",
            actor_full_name=_user_display_name(actor),
            role=getattr(actor, "role", "") or "",
            event="api_action",
            project=project,
            project_id_snapshot=project.id,
            project_title_snapshot=_project_title(project),
            details={
                "action": "project_collaborators_updated",
                "before": existing_codes,
                "after": target_codes,
            },
        )


def _same_saved_account_agency(left, right):
    return " ".join(str(left or "").split()).casefold() == " ".join(str(right or "").split()).casefold()


def _user_display_name(user):
    return (user.get_full_name() or user.username or "").strip()


def _validate_person_name(value):
    if not isinstance(value, str):
        return "Enter a valid name."
    value = value.strip()
    if not value:
        return "This field is required."
    if len(value) > 150:
        return "Must be 150 characters or fewer."
    if not any(character.isalpha() for character in value) or any(
        not (character.isalpha() or character in " '-") for character in value
    ):
        return "Use letters, spaces, apostrophes, or hyphens only."
    return ""

PUBLIC_CHAT_MAX_SUGGESTIONS = 6
PUBLIC_CHAT_MIN_SCORE = 1.0
PUBLIC_CHAT_DIRECT_CONFIDENCE = 0.62
PUBLIC_CHAT_RELATED_CONFIDENCE = 0.60
PUBLIC_PROJECTS_CACHE_TTL_SECONDS = 3600
PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL = "public, no-cache, must-revalidate"
PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION = 4
PUBLIC_PROJECTS_CACHE_VERSION_KEY = "public_projects:version"


class PublicChatRateThrottle(SimpleRateThrottle):
    scope = "public_chat"
    rate = getattr(settings, "GROQ_PUBLIC_CHAT_RATE", "20/min")

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_ok = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            db_ok = False

        return Response(
            {
                "status": "ok" if db_ok else "degraded",
                "database": "ok" if db_ok else "unavailable",
                "timezone": settings.TIME_ZONE,
            },
            status=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


TAGALOG_HINTS = {
    "saan",
    "paano",
    "ano",
    "anong",
    "bakit",
    "kailan",
    "alin",
    "nasaan",
    "mga",
    "ang",
    "ng",
    "sa",
    "para",
    "tungkol",
    "dito",
    "doon",
    "po",
    "opo",
    "magkano",
    "ganito",
    "ganyan",
    "hindi",
    "oo",
    "salamat",
    "pwede",
    "pede",
    "puwede",
    "kasi",
    "ngayon",
    "sino",
    "paki",
}

PUBLIC_CHAT_BLOCKLIST = [
    "password",
    "admin",
    "database",
    "sql",
    "hack",
    "exploit",
    "token",
    "api key",
    "apikey",
    "credentials",
    "login",
    "reset",
    "otp",
    "bypass",
    "dump",
]

CONTACT_KEYWORDS = {
    "contact",
    "contact us",
    "contact form",
    "message",
    "send message",
    "magpadala",
    "mensahe",
    "magmessage",
    "mag-message",
    "mag message",
    "inquiry",
    "inquiries",
    "email",
    "e-mail",
    "email address",
    "reach",
    "reach out",
    "pakikipag-ugnayan",
    "pakipag-ugnayan",
    "makipag-ugnayan",
    "address",
    "location",
    "office",
    "opisina",
    "map",
    "maps",
    "directions",
    "direksyon",
}

PUBLIC_CONTACT_MAP_URL = (
    "https://www.google.com/maps/dir/?api=1&destination=MMDA+Head+Office,+Julia+Vargas+Avenue,+Pasig,+Metro+Manila"
)
PUBLIC_CONTACT_ADDRESS = (
    "16th Floor, MMDA Head Office, Dofia Julia Vargas Avenue corner Molawe St., "
    "Barangay Ugong, Pasig City"
)
PUBLIC_CONTACT_EMAIL = "rdc.ncr@mmda.gov.ph"
PUBLIC_CONTACT_HOURS_EN = "Monday - Friday: 7:00 AM - 4:00 PM; Saturday, Sunday & Holidays: Closed"
PUBLIC_CONTACT_HOURS_TL = "Lunes hanggang Biyernes: 7:00 AM - 4:00 PM; Sabado, Linggo at Holidays: Sarado"

CONTACT_MESSAGE_TERMS = {
    "message",
    "send message",
    "mensahe",
    "magpadala",
    "magmessage",
    "mag-message",
    "mag message",
    "inquiry",
    "tanong",
    "contact",
}
CONTACT_EMAIL_TERMS = {"email", "e-mail", "gmail", "mail", "email address"}
CONTACT_ADDRESS_TERMS = {
    "address",
    "location",
    "office",
    "opisina",
    "map",
    "maps",
    "directions",
    "direksyon",
    "makapunta",
    "papunta",
    "punta",
    "get there",
    "how to get there",
    "how can i get there",
}
CONTACT_HOURS_TERMS = {"hours", "office hours", "oras", "bukas", "schedule", "open", "time", "available"}
CONTACT_INTENT_TERMS = CONTACT_KEYWORDS | CONTACT_EMAIL_TERMS | CONTACT_ADDRESS_TERMS | CONTACT_HOURS_TERMS
INTENT_PUBLICATIONS = {
    "publication",
    "publications",
    "document",
    "documents",
    "rdip",
    "rdip-ncr",
    "pdf",
    "brochure",
    "download",
    "manual",
    "annex",
    "forms",
}
INTENT_NEWS = {
    "news",
    "balita",
    "update",
    "updates",
    "announcement",
    "announcements",
    "advisory",
    "event",
    "events",
    "calendar",
    "schedule",
    "meeting",
    "forum",
}
INTENT_PROJECTS = {"project", "projects", "dashboard", "portfolio", "investment", "pipeline", "public projects"}
INTENT_PROFILE = {
    "regional profile",
    "profile",
    "statistics",
    "indicator",
    "indicators",
    "ncr data",
    "data",
    "lgu",
    "lgus",
    "local government",
    "cities",
    "city",
    "municipality",
    "metro manila",
    "pateros",
    "population",
    "economy",
    "area",
}
INTENT_ABOUT = {
    "about",
    "mandate",
    "structure",
    "committee",
    "committees",
    "council",
    "rdc-ncr",
    "organizational",
    "resolution",
    "resolutions",
}
INTENT_HOME = {"home", "main page", "homepage", "start"}

INTENT_KEYWORDS = {
    "contact": CONTACT_INTENT_TERMS,
    "publications": INTENT_PUBLICATIONS,
    "news": INTENT_NEWS,
    "projects-dashboard": INTENT_PROJECTS,
    "regional-profile": INTENT_PROFILE,
    "about-rdc": INTENT_ABOUT,
    "home": INTENT_HOME,
}


def _build_contact_answer(raw: str, language: str):
    normalized = _normalize_text(raw)
    wants_email = any(term in normalized for term in CONTACT_EMAIL_TERMS)
    wants_address = any(term in normalized for term in CONTACT_ADDRESS_TERMS)
    wants_hours = any(term in normalized for term in CONTACT_HOURS_TERMS)
    wants_message = any(term in normalized for term in CONTACT_MESSAGE_TERMS)

    if not (wants_email or wants_address or wants_hours or wants_message):
        wants_message = True

    lines = []
    if language == "tl":
        if wants_message:
            lines.append("Para magpadala ng mensahe, gamitin ang Contact page ng RDC-NCR.")
        if wants_email:
            lines.append(f"Email: {PUBLIC_CONTACT_EMAIL}")
        if wants_address:
            lines.append(f"Address: {PUBLIC_CONTACT_ADDRESS}.")
        if wants_hours:
            lines.append(f"Office hours: {PUBLIC_CONTACT_HOURS_TL}.")
    else:
        if wants_message:
            lines.append("To send a message, use the RDC-NCR Contact page.")
        if wants_email:
            lines.append(f"Email: {PUBLIC_CONTACT_EMAIL}")
        if wants_address:
            lines.append(f"Address: {PUBLIC_CONTACT_ADDRESS}.")
        if wants_hours:
            lines.append(f"Office hours: {PUBLIC_CONTACT_HOURS_EN}.")

    include_map = wants_address or ("map" in normalized) or ("directions" in normalized)
    include_email = wants_email
    return "\n".join(lines), include_map, include_email


SYNONYM_MAP = {
    "san": {"saan"},
    "sna": {"saan"},
    "pano": {"paano"},
    "pnu": {"paano"},
    "anu": {"ano"},
    "ano": {"anong"},
    "pwd": {"pwede", "pede"},
    "pede": {"pwede"},
    "puwede": {"pwede"},
    "msg": {"message", "mensahe"},
    "chat": {"message", "mensahe"},
    "email": {"e-mail", "mail"},
    "mapa": {"map", "maps"},
    "kalendaryo": {"calendar", "schedule", "events"},
    "calendar": {"schedule", "events"},
    "oras": {"hours", "schedule"},
    "balita": {"news", "updates"},
    "update": {"updates", "news"},
    "updates": {"news"},
    "dokumento": {"documents", "document", "publications"},
    "document": {"documents", "publications"},
    "documents": {"publications"},
    "download": {"documents", "publications"},
    "proyekto": {"project", "projects", "dashboard"},
    "projects": {"project", "dashboard"},
    "dashboard": {"projects"},
    "profile": {"regional", "regional profile"},
    "mandato": {"mandate", "about"},
    "komite": {"committee", "committees"},
    "lgus": {"lgu", "local government"},
    "lgu": {"lgus", "local government"},
    "opisina": {"office", "address", "location"},
}


def _expand_tokens(tokens: set) -> set:
    expanded = set(tokens)
    for token in tokens:
        for synonym in SYNONYM_MAP.get(token, set()):
            expanded.add(synonym)
    return expanded


def _phrase_tokens(raw: str) -> set:
    normalized = _normalize_text(raw)
    parts = [p for p in normalized.split() if p]
    phrases = set()
    for i in range(len(parts) - 1):
        phrases.add(f"{parts[i]} {parts[i + 1]}")
    for i in range(len(parts) - 2):
        phrases.add(f"{parts[i]} {parts[i + 1]} {parts[i + 2]}")
    return phrases


def _fuzzy_match(token: str, candidate: str, threshold: float = 0.86) -> bool:
    if not token or not candidate:
        return False
    if token == candidate:
        return True
    ratio = difflib.SequenceMatcher(a=token, b=candidate).ratio()
    return ratio >= threshold


def _fuzzy_overlap(tokens: set, candidates: set) -> int:
    if not tokens or not candidates:
        return 0
    matches = 0
    for token in tokens:
        for candidate in candidates:
            if _fuzzy_match(token, candidate):
                matches += 1
                break
    return matches


def _intent_score(normalized: str, tokens: set, phrases: set, keywords: set) -> float:
    score = 0.0
    for kw in keywords:
        if " " in kw:
            if kw in normalized or kw in phrases:
                score += 2.5
            continue
        if kw in tokens:
            score += 1.8
        elif _fuzzy_overlap({kw}, tokens):
            score += 1.0
    return score


def _detect_intent_slug(raw: str) -> str | None:
    normalized = _normalize_text(raw)
    tokens = _expand_tokens(_tokenize(normalized, "tl"))
    phrases = _phrase_tokens(normalized)

    scores = {}
    for slug, keywords in INTENT_KEYWORDS.items():
        scores[slug] = _intent_score(normalized, tokens, phrases, keywords)

    best_slug = None
    best_score = 0.0
    for slug, score in scores.items():
        if score > best_score:
            best_score = score
            best_slug = slug

    return best_slug if best_score >= 2.0 else None


def _build_generic_answer(question: str, content: PublicContent, language: str) -> str:
    normalized = _normalize_text(question)
    slug = content.slug
    if slug == "publications":
        if language == "tl":
            if any(term in normalized for term in {"rdip", "manual", "annex", "brochure"}):
                return "Makikita ang RDIP at iba pang dokumento (manuals, annexes, brochure) sa Publications page."
            if any(term in normalized for term in {"download", "pdf", "document", "documents"}):
                return "Makikita ang mga dokumento sa Publications page. Pumili ng kategorya at i-click ang View o Download."
            return "Para sa mga dokumento ng RDC-NCR, pumunta sa Publications page."
        if any(term in normalized for term in {"rdip", "manual", "annex", "brochure"}):
            return "RDIP and other documents (manuals, annexes, brochures) are available on the Publications page."
        if any(term in normalized for term in {"download", "pdf", "document", "documents"}):
            return "You can access documents on the Publications page. Pick a category and click View or Download."
        return "For RDC-NCR documents, visit the Publications page."
    if slug == "news":
        if language == "tl":
            if any(term in normalized for term in {"calendar", "schedule", "events", "meeting"}):
                return "Walang hiwalay na calendar page. Para sa schedules o events, tingnan ang News page (announcements)."
            return "Makikita ang mga balita at anunsyo sa News page."
        if any(term in normalized for term in {"calendar", "schedule", "events", "meeting"}):
            return "There isn’t a separate calendar page yet. Schedules and events are posted in News announcements."
        return "You can read updates and announcements on the News page."
    if slug == "projects-dashboard":
        if language == "tl":
            if any(term in normalized for term in {"filter", "status", "agency", "ahensya"}):
                return "Sa Projects Dashboard, puwede kang mag‑filter ayon sa ahensya o status at makita ang project details."
            return "Pumunta sa Projects Dashboard page para makita ang public project data at gamitin ang filters."
        if any(term in normalized for term in {"filter", "status", "agency"}):
            return "In the Projects Dashboard you can filter by agency or status and view project details."
        return "Go to the Projects Dashboard page to view public project data and use filters."
    if slug == "regional-profile":
        if any(term in normalized for term in {"lgu", "lgus", "local government", "cities", "city", "municipality", "sakop", "coverage"}):
            if language == "tl":
                return (
                    "Ang NCR ay binubuo ng 16 na lungsod at 1 munisipalidad: "
                    "Caloocan, Malabon, Navotas, Valenzuela, Quezon City, Marikina, Pasig, "
                    "Taguig, Makati, Manila, Mandaluyong, San Juan, Pasay, Parañaque, Las Piñas, "
                    "Muntinlupa, at ang munisipalidad ng Pateros."
                )
            return (
                "NCR is composed of 16 cities and 1 municipality: Caloocan, Malabon, Navotas, "
                "Valenzuela, Quezon City, Marikina, Pasig, Taguig, Makati, Manila, Mandaluyong, "
                "San Juan, Pasay, Parañaque, Las Piñas, Muntinlupa, and the municipality of Pateros."
            )
        if language == "tl":
            return "Makikita ang NCR statistics at indicators sa Regional Profile page."
        return "NCR statistics and indicators are available on the Regional Profile page."
    if slug == "about-rdc":
        if any(term in normalized for term in {"resolution", "resolutions"}):
            if language == "tl":
                return "Makikita sa About RDC page ang Resolutions Archive ng RDC-NCR."
            return "The About RDC page contains the RDC-NCR Resolutions Archive."
        if any(term in normalized for term in {"lgu", "lgus", "mayor", "mayors"}):
            if language == "tl":
                return "Sa About RDC organizational structure, nakalista ang 17 MM Mayors bilang voting members."
            return "The About RDC organizational structure lists 17 MM Mayors as voting members."
        if language == "tl":
            return "Ang About RDC page ay may mandato, istruktura, at mga komite ng RDC-NCR."
        return "The About RDC page covers the RDC-NCR mandate, structure, and committees."
    if slug == "home":
        if language == "tl":
            return "Sa Home page may mabilis na links papunta sa News, Publications, Projects, at iba pang public pages."
        return "The Home page provides quick links to News, Publications, Projects, and other public pages."
    base_text = content.body or content.summary or ""
    snippet = _select_relevant_snippet(base_text, _expand_tokens(_tokenize(question, language)), language)
    if language == "tl":
        return f"Narito ang impormasyon mula sa pampublikong website: {snippet}"
    return f"Here is what I found on the RDC-NCR public website: {snippet}"


def _frontend_role(role: str):
    return "employee" if role == "staff" else role


def _is_content_manager(user):
    return getattr(user, "role", "") in {"admin", "content_editor"}


def _is_admin_user(user):
    return getattr(user, "role", "") == "admin"


def _build_unique_username(email: str, display_name: str = ""):
    local = (email or "").split("@")[0].strip().lower()
    local = re.sub(r"[^a-z0-9._-]+", "", local)
    if not local:
        local = re.sub(r"[^a-z0-9]+", "", (display_name or "").lower()) or "user"
    base = local[:18]
    candidate = base
    idx = 1
    while User.objects.filter(username=candidate).exists():
        idx += 1
        candidate = f"{base}{idx}"
    return candidate


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def _location_hint(request):
    # This is best-effort and depends on proxy/CDN headers.
    city = request.META.get("HTTP_X_CITY") or request.META.get("HTTP_X_APPENGINE_CITY")
    region = request.META.get("HTTP_X_REGION") or request.META.get("HTTP_X_APPENGINE_REGION")
    country = request.META.get("HTTP_X_COUNTRY") or request.META.get("HTTP_X_APPENGINE_COUNTRY")
    parts = [p for p in [city, region, country] if p]
    return ", ".join(parts)


def _advance_user_session(user, request=None, *, revocation_reason="credential_change"):
    previous_version = int(getattr(user, "session_version", 0) or 0)
    user.session_version = previous_version + 1
    now = timezone.now()
    PortalSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=now,
        revocation_reason=revocation_reason,
    )
    user.last_session_at = now
    if request is not None:
        user.last_session_ip = _client_ip(request)
        user.last_session_user_agent = (request.META.get("HTTP_USER_AGENT", "") or "")[:1000]
    user.save(
        update_fields=[
            "session_version",
            "last_session_at",
            "last_session_ip",
            "last_session_user_agent",
        ]
    )
    return previous_version, user.session_version


def _issue_session_access_token(user, session):
    access = AccessToken.for_user(user)
    access["session_version"] = int(user.session_version or 0)
    access["portal_session_id"] = session.pk
    return str(access)


def _login_user_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": _frontend_role(user.role),
        "must_change_password": user.must_change_password,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "agency": user.agency,
        "agency_head": user.agency_head,
        "office": user.office,
        "division": user.division,
        "position": user.position,
        "contact_number": user.contact_number,
        "phone_number": user.phone_number,
    }


def _active_browser_session(refresh_token):
    if not isinstance(refresh_token, str) or not refresh_token:
        return None
    digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
    session = PortalSession.objects.select_related("user").filter(
        refresh_token_digest=digest,
        revoked_at__isnull=True,
    ).first()
    if not session:
        return None
    now = timezone.now()
    reason = ""
    if not session.user.is_active:
        reason = "logout"
    elif session.session_version != session.user.session_version:
        reason = "new_login"
    elif not session.remember_me and now - session.last_activity_at >= SESSION_IDLE_TIMEOUT:
        reason = "idle_timeout"
    if reason:
        PortalSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(
            revoked_at=now,
            revocation_reason=reason,
        )
        return None
    return session


def _log_activity(request, event: str, project=None, details=None):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return
    UserActivity.objects.create(
        user=user,
        role=user.role,
        event=event,
        project=project,
        ip_address=_client_ip(request),
        location_hint=_location_hint(request),
        details=details or {},
    )


def _log_unauthenticated_activity(request, event: str, details=None):
    """Capture security attempts without claiming that the target account acted."""
    safe_details = dict(details or {})
    if "attempted_email" in safe_details:
        safe_details["attempted_email"] = str(safe_details["attempted_email"])[:254]
    UserActivity.objects.create(
        actor_username="Unauthenticated",
        actor_full_name="Unauthenticated",
        role="unauthenticated",
        event=event,
        ip_address=_client_ip(request)[:64],
        location_hint=_location_hint(request)[:255],
        details=safe_details,
    )


def _project_title(project):
    return getattr(project, "title", "") or getattr(project, "name", "") or "Project"


def _project_review_status(project):
    profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
    review = profile_data.get("validator_review")
    if not isinstance(review, dict):
        return ""
    status_value = str(review.get("review_status") or "").lower()
    return "endorsed" if status_value == "validated" else status_value


def _project_needs_revision(project):
    return getattr(project, "status", "") == "proposed" and _project_review_status(project) == "reviewed"


def _is_simplified_profile(profile_data):
    if not isinstance(profile_data, dict):
        return False
    marker = str(profile_data.get("submission_type") or "").strip().lower()
    if marker == "detailed":
        return False
    return marker == "simplified" or isinstance(profile_data.get("simplified_form"), dict)


def _saved_contributor_form_marker(profile_data):
    """Return the saved form key/version for a simplified project."""
    if not _is_simplified_profile(profile_data):
        return None
    marker = profile_data.get("form_schema")
    marker = marker if isinstance(marker, dict) else {}
    key = str(marker.get("key") or "simplified-rdip").strip() or "simplified-rdip"
    try:
        version = int(marker.get("version") or 1)
    except (TypeError, ValueError):
        version = 1
    return key, max(version, 1)


def _normalize_location_for_form_schema(profile_data, schema):
    """Convert a legacy text location when opting a project into a multi-select form."""
    if not isinstance(profile_data, dict) or not isinstance(schema, dict):
        return profile_data, ""
    location_field = next(
        (
            field
            for section in schema.get("sections", [])
            if isinstance(section, dict)
            for field in section.get("fields", [])
            if isinstance(field, dict) and field.get("key") == "location" and field.get("type") == "multiselect_dropdown"
        ),
        None,
    )
    if location_field is None:
        return profile_data, ""
    simplified = profile_data.get("simplified_form")
    if not isinstance(simplified, dict):
        return profile_data, ""

    options = [
        option for option in location_field.get("options", [])
        if isinstance(option, dict) and str(option.get("value") or "").strip()
    ]
    allowed_values = {str(option["value"]) for option in options}
    raw = simplified.get("location")
    if isinstance(raw, list):
        selected = [str(value).strip() for value in raw if str(value).strip()]
        unsupported = [value for value in selected if value not in allowed_values]
        if unsupported:
            return profile_data, "The saved project contains location choices that are not available in the current form."
    else:
        text = str(raw or "").strip()
        selected = []
        if text:
            option_lookup = {
                str(candidate).strip().casefold(): str(option["value"])
                for option in options
                for candidate in (option.get("value"), option.get("label"))
                if str(candidate or "").strip()
            }
            direct = option_lookup.get(text.casefold())
            if direct:
                selected = [direct]
            else:
                selected = [value for value in derive_ncr_lgus(text) if value in allowed_values]
            if not selected:
                return profile_data, (
                    "The saved text location does not match any location choice in the current form. "
                    "Keep the project on its existing form until its location can be corrected."
                )

    upgraded = deepcopy(profile_data)
    upgraded_simplified = deepcopy(simplified)
    upgraded_simplified["location"] = selected
    upgraded["simplified_form"] = upgraded_simplified
    return upgraded, ""


def _upgrade_profile_form_marker(profile_data, source_profile_data, target_schema=None):
    """Upgrade an editable snapshot to the source project's newer form marker."""
    if not isinstance(profile_data, dict):
        return profile_data, None
    saved_marker = _saved_contributor_form_marker(profile_data)
    source_marker = _saved_contributor_form_marker(source_profile_data)
    if saved_marker is None or source_marker is None:
        return profile_data, None
    saved_key, saved_version = saved_marker
    source_key, source_version = source_marker
    if saved_key != source_key or saved_version >= source_version:
        return profile_data, None
    upgraded = deepcopy(profile_data)
    upgraded, location_error = _normalize_location_for_form_schema(upgraded, target_schema)
    if location_error:
        return profile_data, {"error": location_error}
    upgraded["form_schema"] = {"key": source_key, "version": source_version}
    return upgraded, {
        "form_key": source_key,
        "previous_form_version": saved_version,
        "new_form_version": source_version,
    }


def _project_link(project, recipient):
    role = getattr(recipient, "role", "")
    suffix = "/simplified"
    if role == "admin":
        return f"/admin/projects/{project.id}/view{suffix}"
    if role == "validator":
        return f"/validator/projects/{project.id}/review{suffix}"
    return f"/employee/projects/{project.id}/view"


def _revision_review_link(revision, role):
    suffix = "/simplified"
    base = (
        f"/validator/projects/{revision.project_id}/review"
        if role == "validator"
        else f"/admin/projects/{revision.project_id}/view"
    )
    return f"{base}{suffix}?revision={revision.id}"


def _active_validators():
    return User.objects.filter(role="validator", is_active=True)


def _project_employee_recipients(project):
    if project.created_by_id:
        return User.objects.filter(id=project.created_by_id, is_active=True)
    agency = (project.agency or "").strip()
    if not agency:
        return User.objects.none()
    return User.objects.filter(role="staff", is_active=True, agency__iexact=agency)


def _admins():
    return User.objects.filter(role="admin", is_active=True)


def _notify_user(
    recipient,
    *,
    event_type,
    title,
    message,
    project=None,
    actor=None,
    comment=None,
    dedupe_key=None,
    link_path=None,
):
    if not recipient or not getattr(recipient, "is_active", True):
        return None
    defaults = {
        "actor": actor if getattr(actor, "is_authenticated", False) else None,
        "project": project,
        "comment": comment,
        "event_type": event_type,
        "title": title,
        "message": message,
        "link_path": link_path if link_path is not None else (_project_link(project, recipient) if project else ""),
    }
    if dedupe_key:
        notification, _ = Notification.objects.get_or_create(
            recipient=recipient,
            dedupe_key=f"{dedupe_key}:u{recipient.id}",
            defaults=defaults,
        )
        return notification
    return Notification.objects.create(recipient=recipient, **defaults)


def _notify_many(recipients, **kwargs):
    sent = []
    actor = kwargs.get("actor")
    actor_id = getattr(actor, "id", None)
    seen = set()
    for recipient in recipients:
        if not recipient or recipient.id in seen or recipient.id == actor_id:
            continue
        seen.add(recipient.id)
        notification = _notify_user(recipient, **kwargs)
        if notification:
            sent.append(notification)
    return sent


def _priority_group(value):
    if value == "high":
        return "priority"
    if value in ("medium", "low"):
        return "non_priority"
    return ""


def _priority_label(value):
    if value == "high":
        return "Priority"
    if value in ("medium", "low"):
        return "Non-Priority"
    return ""


def _latest_project_confirmation(project):
    return ProjectPriorityConfirmation.objects.filter(analysis__project=project).order_by("-created_at").first()


def _workflow_status_for_project(project):
    review_status = _project_review_status(project)
    if review_status == "reviewed":
        return "needs_revision"
    if review_status == "rejected":
        return "rejected"
    if review_status == "endorsed" or getattr(project, "validated", False) or getattr(project, "status", "") == "completed":
        return "validated"
    if getattr(project, "status", "") == "proposed":
        return "pending_validation"
    if getattr(project, "status", "") == "planning":
        return "draft"
    return getattr(project, "status", "") or ""


def _filter_projects_for_workflow(qs, workflow):
    workflow = str(workflow or "").strip().lower().replace("-", "_")
    if workflow in ("", "all"):
        return qs
    projects = list(qs)
    if workflow in ("priority", "non_priority"):
        ids = []
        for project in projects:
            confirmation = _latest_project_confirmation(project)
            if confirmation and _priority_group(confirmation.final_priority) == workflow:
                ids.append(project.id)
        return Project.objects.filter(id__in=ids)
    aliases = {
        "pending": "pending_validation",
        "pending_validation": "pending_validation",
        "needs_revision": "needs_revision",
        "revision": "needs_revision",
        "validated": "validated",
        "approved": "validated",
        "rejected": "rejected",
        "draft": "draft",
    }
    expected = aliases.get(workflow, workflow)
    ids = [project.id for project in projects if _workflow_status_for_project(project) == expected]
    return Project.objects.filter(id__in=ids)


def _filter_admin_project_selection(qs, data):
    """Apply the same user-facing filters used by the administrator project list."""
    search = str(data.get("search") or data.get("q") or "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(agency__icontains=search)
            | Q(implementing_agency__icontains=search)
            | Q(created_by__username__icontains=search)
            | Q(created_by__first_name__icontains=search)
            | Q(created_by__last_name__icontains=search)
        )
    workflow = data.get("workflow") or data.get("status")
    return _filter_projects_for_workflow(qs, workflow)


def _selected_admin_projects(data, *, include_archived=False):
    raw_ids = data.get("project_ids")
    if raw_ids is None:
        raw_ids = data.get("ids")
    if isinstance(raw_ids, str):
        raw_ids = [item.strip() for item in raw_ids.split(",") if item.strip()]
    if raw_ids is not None and not isinstance(raw_ids, list):
        raise ValueError("project_ids must be a list.")
    if raw_ids:
        try:
            ids = list(dict.fromkeys(int(item) for item in raw_ids))
        except (TypeError, ValueError) as exc:
            raise ValueError("Project identifiers must be numbers.") from exc
        if len(ids) > 5000:
            raise ValueError("A batch can contain at most 5,000 projects.")
        return Project.objects.filter(id__in=ids).order_by("id")
    if str(data.get("all_matching") or "").lower() not in {"1", "true", "yes"}:
        raise ValueError("Select at least one project or choose all matching projects.")
    qs = Project.objects.all()
    if not include_archived:
        qs = qs.filter(archived=False, is_active=True)
    return _filter_admin_project_selection(qs, data).order_by("id")


def _archive_ineligibility(project):
    if project.archived or not project.is_active:
        return "This project is already archived."
    if project.status == "proposed" or _project_needs_revision(project):
        return "Projects pending validation or returned for correction cannot be archived."
    active_update = project.revisions.filter(
        revision_type="progress_update",
        state__in=("draft", "submitted", "validator_draft", "reviewed"),
    ).exists()
    if active_update:
        return "This project has an active progress update."
    return ""


def _archive_project(request, project):
    """Archive one eligible project. The caller must lock the row for batch use."""
    reason = _archive_ineligibility(project)
    if reason:
        return False, reason
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    simplified = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
    implementation_status = canonical_implementation_status(simplified.get("status")) if simplified else ""
    project.archived = True
    project.is_active = False
    project.save(update_fields=["archived", "is_active", "updated_at"])
    _log_activity(request, "project_archive", project, {
        "archived": True,
        "implementation_status": implementation_status,
    })
    _notify_many(
        _project_employee_recipients(project),
        event_type="project_archived",
        title="Project archived",
        message=(
            f"{_project_title(project)} was archived by an administrator. "
            "It is no longer shown in your active projects list."
        ),
        project=project,
        actor=request.user,
        link_path="/employee/projects",
        dedupe_key=f"project:{project.id}:archived:{project.updated_at.isoformat()}",
    )
    return True, ""


def _batch_project_row(project, reason=""):
    marker = saved_form_marker(project.profile_data)
    return {
        "id": project.id,
        "title": _project_title(project),
        "agency": project.agency or project.implementing_agency or "",
        "workflow_status": _workflow_status_for_project(project),
        "form_version": marker[1] if marker else None,
        "eligible": not bool(reason),
        "reason": reason,
    }


def _migration_preview_row(project, *, version_cache=None):
    eligible, reason = migration_eligibility(project)
    source_profile = project.profile_data
    draft = project.revisions.filter(
        revision_type="progress_update", state="draft"
    ).order_by("-updated_at").first()
    if draft is not None:
        source_profile = draft.profile_data_snapshot
    analysis = analyze_profile_migration(source_profile, version_cache=version_cache) if eligible else {}
    if eligible and not analysis.get("compatible"):
        reason = "; ".join(analysis.get("issues") or ["This form cannot be migrated safely."])
    if eligible and analysis.get("already_current"):
        reason = "This project already uses the latest contributor form."
    row = _batch_project_row(project, reason)
    row.update({
        "source_version": analysis.get("source_version", row["form_version"]),
        "target_version": analysis.get("target_version"),
        "attention_fields": analysis.get("attention_fields", []),
        "eligible": eligible and analysis.get("compatible", False) and not analysis.get("already_current", False),
    })
    return row


def _get_window_config(key):
    default = {
        "configured": False,
        "config_error": False,
        "enabled": False,
        "manual_open": False,
        "start_at": "",
        "end_at": "",
    }
    setting = SystemSetting.objects.filter(key=key).first()
    if not setting or not setting.value:
        return default
    try:
        data = json.loads(setting.value)
        return {
            "configured": True,
            "config_error": False,
            "enabled": bool(data.get("enabled", False)),
            "manual_open": bool(data.get("manual_open", False)),
            "start_at": str(data.get("start_at", "") or ""),
            "end_at": str(data.get("end_at", "") or ""),
        }
    except Exception:
        return {**default, "configured": True, "config_error": True}


def _get_encoding_window_config():
    return _get_window_config(ENCODING_WINDOW_KEY)


def _parse_iso_datetime(raw):
    if not raw:
        return None
    value = str(raw).strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _resolve_window_state(config, label, action_label):
    public_config = {
        "enabled": config["enabled"],
        "manual_open": config.get("manual_open", False),
        "start_at": config["start_at"],
        "end_at": config["end_at"],
    }
    now = timezone.now()
    server_now = now.isoformat()

    def state(status_code, message, is_open=False):
        return {
            **public_config,
            "is_open": is_open,
            "status_code": status_code,
            "message": message,
            "server_now": server_now,
        }

    if config["config_error"]:
        return state("schedule_invalid", f"{label} schedule is invalid. Please contact the administrator.")

    if not config["configured"]:
        return state("schedule_not_configured", f"{label} is closed until an administrator sets a schedule.")

    if not config["enabled"]:
        return state("closed_by_admin", f"{label} is currently closed by the administrator.")

    if config.get("manual_open"):
        return state("open_by_admin", f"{action_label} is open until an administrator closes it.", is_open=True)

    if not config["start_at"] or not config["end_at"]:
        return state("schedule_not_configured", f"{label} is closed until a complete schedule is configured.")

    try:
        start_at = _parse_iso_datetime(config["start_at"])
        end_at = _parse_iso_datetime(config["end_at"])
    except (TypeError, ValueError):
        return state("schedule_invalid", f"{label} schedule is invalid. Please contact the administrator.")

    if not start_at or not end_at or start_at >= end_at:
        return state("schedule_invalid", f"{label} schedule is invalid. Please contact the administrator.")

    if now < start_at:
        return state(
            "scheduled_not_started",
            f"{label} opens on {timezone.localtime(start_at).strftime('%b %d, %Y %I:%M %p')} Philippine Standard Time.",
        )
    if now >= end_at:
        return state(
            "scheduled_ended",
            f"{label} closed on {timezone.localtime(end_at).strftime('%b %d, %Y %I:%M %p')} Philippine Standard Time.",
        )
    return state(
        "scheduled_open",
        f"{action_label} is open until {timezone.localtime(end_at).strftime('%b %d, %Y %I:%M %p')} Philippine Standard Time.",
        is_open=True,
    )


def _resolve_encoding_window_state():
    return _resolve_window_state(
        _get_encoding_window_config(),
        "Contributor encoding",
        "Contributor encoding",
    )


def _resolve_progress_update_window_state():
    return _resolve_window_state(
        _get_window_config(PROGRESS_UPDATE_WINDOW_KEY),
        "Project progress updates",
        "Project progress updating",
    )


RESET_PASSWORD_TOKEN_PREFIX = "reset_"


PASSWORD_RESET_GENERIC_MESSAGE = (
    "If this email is registered, a password reset code has been sent. "
    "Check your inbox and spam folder."
)


def _password_reset_email_fingerprint(email: str) -> str:
    normalized = str(email or "").strip().casefold().encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        b"rdc-password-reset:" + normalized,
        hashlib.sha256,
    ).hexdigest()


def _record_password_reset_event(request, event, challenge, details=None):
    payload = {
        "challenge_id": challenge.pk,
        "email_fingerprint": challenge.email_fingerprint,
        **(details or {}),
    }
    if challenge.user_id:
        payload["target_user_id"] = challenge.user_id
    actor = getattr(request, "user", None)
    if actor and actor.is_authenticated:
        UserActivity.objects.create(
            user=actor,
            role=actor.role,
            event=event,
            ip_address=_client_ip(request)[:64],
            location_hint=_location_hint(request)[:255],
            details=payload,
        )
    else:
        _log_unauthenticated_activity(request, event, payload)


def _send_password_reset_otp(user: User, otp: str):
    message = (
        "A password reset was requested for your RDC Portal account.\n\n"
        f"Your one-time verification code is: {otp}\n\n"
        "This code expires in 10 minutes and can be used once. "
        "If you did not request this reset, you can ignore this email."
    )
    delivered = send_mail(
        "RDC Portal Password Reset Code",
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    if not delivered:
        raise RuntimeError("The password reset email was not delivered.")


def _issue_password_reset_challenge(request, email: str):
    normalized_email = str(email or "").strip().lower()
    validate_email(normalized_email)
    now = timezone.now()
    fingerprint = _password_reset_email_fingerprint(normalized_email)
    ip = _client_ip(request)[:64]
    window_start = now - timedelta(seconds=PASSWORD_RESET_WINDOW_SECONDS)

    latest = PasswordResetChallenge.objects.filter(
        email_fingerprint=fingerprint,
    ).order_by("-created_at").first()
    if latest and latest.resend_available_at > now:
        retry_after = max(1, int((latest.resend_available_at - now).total_seconds()))
        return None, Response(
            {"detail": f"Please wait {retry_after} seconds before requesting another code.", "retry_after": retry_after},
            status=429,
        )
    if PasswordResetChallenge.objects.filter(
        email_fingerprint=fingerprint,
        created_at__gte=window_start,
    ).count() >= PASSWORD_RESET_LIMIT_EMAIL:
        return None, Response({"detail": "Too many requests. Please try again later."}, status=429)
    if ip and PasswordResetChallenge.objects.filter(
        requested_ip=ip,
        created_at__gte=window_start,
    ).count() >= PASSWORD_RESET_LIMIT_IP:
        return None, Response({"detail": "Too many requests. Please try again later."}, status=429)

    user = User.objects.filter(email__iexact=normalized_email).first()
    otp = f"{secrets.randbelow(1_000_000):06d}"
    with transaction.atomic():
        superseded_at = timezone.now()
        PasswordResetChallenge.objects.select_for_update().filter(
            email_fingerprint=fingerprint,
            status__in=[PasswordResetChallenge.STATUS_PENDING, PasswordResetChallenge.STATUS_VERIFIED],
        ).update(
            status=PasswordResetChallenge.STATUS_SUPERSEDED,
            superseded_at=superseded_at,
            otp_digest="",
            reset_token_digest="",
        )
        if user:
            PasswordSetupToken.objects.filter(
                user=user,
                token__startswith=RESET_PASSWORD_TOKEN_PREFIX,
                used_at__isnull=True,
            ).update(used_at=superseded_at)
        challenge = PasswordResetChallenge.objects.create(
            user=user,
            email_fingerprint=fingerprint,
            otp_digest=make_password(otp),
            delivery_status=(
                PasswordResetChallenge.DELIVERY_PENDING
                if user
                else PasswordResetChallenge.DELIVERY_NOT_APPLICABLE
            ),
            expires_at=now + timedelta(seconds=PASSWORD_RESET_OTP_TTL_SECONDS),
            resend_available_at=now + timedelta(seconds=PASSWORD_RESET_RESEND_COOLDOWN_SECONDS),
            requested_ip=ip,
            requested_user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:255],
        )

    delivered = False
    if user:
        try:
            _send_password_reset_otp(user, otp)
            delivered = True
            challenge.delivery_status = PasswordResetChallenge.DELIVERY_SENT
        except Exception:
            challenge.delivery_status = PasswordResetChallenge.DELIVERY_FAILED
        challenge.save(update_fields=["delivery_status"])
    _record_password_reset_event(
        request,
        "auth_reset_request",
        challenge,
        {"action": "otp_requested", "delivery_status": challenge.delivery_status},
    )
    return {"challenge": challenge, "delivered": delivered}, None


def _send_password_changed_notice(user: User):
    send_mail(
        "RDC Portal Password Changed",
        (
            "The password for your RDC Portal account was changed successfully.\n\n"
            "If you did not make this change, contact the RDC Portal administrator immediately."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def _send_registration_invitation(email: str, token: str):
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    link = f"{frontend_base}/setup-password?token={urllib.parse.quote(token, safe='')}"
    message = (
        "An RDC Portal administrator invited you to complete your account registration.\n\n"
        "Complete your profile and set your password using this link (valid for 24 hours):\n"
        f"{link}\n\n"
        "Your account will remain inactive until an administrator activates it.\n"
        "If you did not expect this invitation, please contact the RDC Portal administrator."
    )
    delivered = send_mail(
        "RDC Portal Registration Invitation", message, settings.DEFAULT_FROM_EMAIL,
        [email], fail_silently=False,
    )
    if not delivered:
        raise RuntimeError("The registration invitation email was not delivered.")


def _issue_registration_invitation(request, email: str, role: str, agency: str = "", batch_key: str = ""):
    email = str(email or "").strip().lower()
    normalized_agency = _normalize_account_agency(agency)
    agency_locked = role in INTERNAL_ACCOUNT_ROLES or bool(normalized_agency)
    if role in INTERNAL_ACCOUNT_ROLES:
        normalized_agency = "RDC-NCR"
    signed = signing.dumps(
        {
            "email": email,
            "role": role,
            "agency": normalized_agency,
            "agency_locked": agency_locked,
            "nonce": get_random_string(32),
        },
        salt=REGISTRATION_INVITE_SALT,
    )
    token = f"{REGISTRATION_INVITE_PREFIX}{signed}"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    actor = request.user
    with transaction.atomic():
        now = timezone.now()
        UserInvitation.objects.select_for_update().filter(
            email__iexact=email,
            status=UserInvitation.STATUS_SENT,
            expires_at__gte=now,
        ).update(status=UserInvitation.STATUS_REVOKED, revoked_at=now)
        invitation = UserInvitation.objects.create(
            email=email,
            role=role,
            agency=normalized_agency,
            agency_locked=agency_locked,
            token_digest=digest,
            status=UserInvitation.STATUS_PENDING,
            invited_by=actor,
            batch_key=str(batch_key or "")[:64],
            expires_at=now + timedelta(hours=PASSWORD_SETUP_TTL_HOURS),
        )
    try:
        _send_registration_invitation(email, token)
    except Exception:
        UserInvitation.objects.filter(pk=invitation.pk).update(status=UserInvitation.STATUS_DELIVERY_FAILED)
        raise
    invitation.status = UserInvitation.STATUS_SENT
    invitation.sent_at = timezone.now()
    invitation.save(update_fields=["status", "sent_at"])
    activity = UserActivity.objects.create(
        user=actor,
        actor_username=actor.username,
        actor_full_name=_user_display_name(actor),
        role=actor.role,
        event="registration_invitation_sent",
        ip_address=_client_ip(request)[:64],
        location_hint=_location_hint(request)[:255],
        details={
            "email": email,
            "role": role,
            "agency": normalized_agency,
            "agency_locked": agency_locked,
            "invitation_record_id": invitation.id,
            "token_digest": digest,
            "batch_key": str(batch_key or "")[:64],
        },
    )
    return activity


def _registration_invitation(token: str):
    if not token.startswith(REGISTRATION_INVITE_PREFIX):
        return None
    try:
        payload = signing.loads(
            token[len(REGISTRATION_INVITE_PREFIX):],
            salt=REGISTRATION_INVITE_SALT,
            max_age=PASSWORD_SETUP_TTL_HOURS * 3600,
        )
    except signing.BadSignature:
        return None
    if not isinstance(payload, dict):
        return None
    email = str(payload.get("email") or "").strip().lower()
    role = str(payload.get("role") or "")
    if not email or role not in ("admin", "validator", "staff", "content_editor") or not payload.get("nonce"):
        return None
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = UserInvitation.objects.filter(
        token_digest=digest,
        email__iexact=email,
        role=role,
        status=UserInvitation.STATUS_SENT,
        expires_at__gte=timezone.now(),
    ).first()
    if invitation:
        payload["agency"] = invitation.agency
        payload["agency_locked"] = invitation.agency_locked
        if User.objects.filter(email__iexact=email).exists():
            return None
        return payload, invitation
    invitations = UserActivity.objects.filter(event="registration_invitation_sent", details__email=email)
    latest = invitations.order_by("-id").first()
    if not latest or latest.details.get("token_digest") != digest or latest.details.get("role") != role:
        return None
    if UserActivity.objects.filter(event="registration_completed", details__invitation_id=latest.id).exists():
        return None
    if User.objects.filter(email__iexact=email).exists():
        return None
    return payload, latest


def _rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    if limit <= 0:
        return False
    current = cache.get(key)
    if current is None:
        cache.set(key, 1, timeout=window_seconds)
        return False
    if current >= limit:
        return True
    try:
        cache.incr(key)
    except Exception:
        cache.set(key, current + 1, timeout=window_seconds)
    return False


def _verify_turnstile(token: str, ip: str = "") -> bool:
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "") or ""
    if not secret:
        return True
    if not token:
        return False
    data = urllib.parse.urlencode(
        {
            "secret": secret,
            "response": token,
            "remoteip": ip,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return bool(payload.get("success"))
    except Exception:
        return False


CHAT_REPLACEMENTS = {
    "rdcncr": "rdc ncr",
    "rdc-ncr": "rdc ncr",
    "rdc ncr": "rdc ncr",
    "lgus": "lgu",
    "l.g.u": "lgu",
    "mmda": "mmda",
    "pls": "please",
    "plz": "please",
}


def _normalize_text(raw: str) -> str:
    text = (raw or "").lower()
    for key, value in CHAT_REPLACEMENTS.items():
        text = text.replace(key, value)
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sanitize_question_sample(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[email]", text)
    text = re.sub(r"\b\d{6,}\b", "[number]", text)
    return text[:255]


def _detect_language(raw: str) -> str:
    normalized = _normalize_text(raw)
    tokens = set(normalized.split())
    if tokens.intersection(TAGALOG_HINTS):
        return "tl"
    return "en"


def _tokenize(raw: str, language: str) -> set:
    normalized = _normalize_text(raw)
    tokens = [t for t in normalized.split() if len(t) > 1]
    if language == "tl":
        stop = {
            "ang",
            "ng",
            "sa",
            "mga",
            "na",
            "ay",
            "para",
            "ito",
            "iyan",
            "iyon",
            "po",
            "opo",
            "daw",
        }
    else:
        stop = {
            "the",
            "and",
            "or",
            "for",
            "with",
            "this",
            "that",
            "from",
            "what",
            "where",
            "how",
            "can",
            "are",
            "is",
            "to",
            "in",
        }
    return {t for t in tokens if t not in stop}


def _contains_blocked_topic(raw: str) -> bool:
    normalized = (raw or "").lower()
    return any(term in normalized for term in PUBLIC_CHAT_BLOCKLIST)


def _contact_intent(raw: str) -> bool:
    normalized = _normalize_text(raw)
    return any(term in normalized for term in CONTACT_INTENT_TERMS)


def _score_content(question_tokens: set, question_phrases: set, content: PublicContent, contact_intent: bool) -> float:
    title_tokens = _tokenize(content.title, content.language)
    summary_tokens = _tokenize(content.summary, content.language)
    body_tokens = _tokenize(content.body, content.language)
    tag_tokens = {str(t).lower() for t in (content.tags or [])}
    title_phrases = _phrase_tokens(content.title)
    summary_phrases = _phrase_tokens(content.summary or "")
    tag_phrases = {t for t in (content.tags or []) if isinstance(t, str) and " " in t}

    score = 0.0
    score += len(question_tokens.intersection(title_tokens)) * 2.5
    score += len(question_tokens.intersection(tag_tokens)) * 2.0
    score += len(question_tokens.intersection(summary_tokens)) * 1.2
    score += len(question_tokens.intersection(body_tokens)) * 0.8
    score += len(question_phrases.intersection(title_phrases)) * 2.5
    score += len(question_phrases.intersection(summary_phrases)) * 1.8
    score += len(question_phrases.intersection(tag_phrases)) * 2.0
    score += _fuzzy_overlap(question_tokens, title_tokens) * 0.8
    score += _fuzzy_overlap(question_tokens, tag_tokens) * 0.6
    if contact_intent and content.slug == "contact":
        score += 8.0
    return score


def _select_relevant_snippet(text: str, question_tokens: set, language: str) -> str:
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    best_sentence = ""
    best_score = 0
    for sentence in sentences:
        tokens = _tokenize(sentence, language)
        score = len(tokens.intersection(question_tokens))
        if score > best_score:
            best_score = score
            best_sentence = sentence
    return best_sentence if best_sentence else sentences[0]


def _default_suggestions(language: str):
    if language == "tl":
        return [
            "Saan ko makikita ang mga dokumento ng RDIP?",
            "Paano makita ang public projects dashboard?",
            "Saan mababasa ang balita ng RDC-NCR?",
            "Ano ang tungkol sa RDC-NCR?",
        ]
    return [
        "Where can I download RDIP documents?",
        "How do I view the public projects dashboard?",
        "Where can I read RDC-NCR news?",
        "What is the RDC-NCR and its role?",
    ]


def _get_top_questions(limit: int):
    qs = PublicChatFAQ.objects.order_by("-count", "-last_asked").values_list("question_sample", flat=True)[:limit]
    return [q for q in qs if q]


def _public_chat_sources(content: PublicContent | None, extra=None):
    sources = []
    if content and content.url:
        sources.append({"title": content.title, "url": content.url})
    for item in extra or []:
        if item and item not in sources:
            sources.append(item)
    return sources


def _public_chat_related_links(ranked, exclude_slug="", limit=3):
    links = []
    seen = set()
    for score, content in ranked:
        if score <= 0 or not content.url or content.slug == exclude_slug or content.url in seen:
            continue
        links.append({"title": content.title, "url": content.url})
        seen.add(content.url)
        if len(links) >= limit:
            break
    return links


def _public_chat_confidence(score: float, token_count: int, intent_locked=False, forced_contact=False):
    if forced_contact:
        return 0.92
    if intent_locked:
        return 0.78
    return min(1.0, max(0.0, score / max(3.0, token_count * 1.5)))


def _public_chat_answer_type(confidence: float, has_match: bool):
    if not has_match:
        return "fallback"
    if confidence >= PUBLIC_CHAT_DIRECT_CONFIDENCE:
        return "direct"
    if confidence >= PUBLIC_CHAT_RELATED_CONFIDENCE:
        return "related"
    return "fallback"


def _public_chat_update_faq(normalized: str, question: str, matched_content):
    if not normalized:
        return
    faq, created = PublicChatFAQ.objects.get_or_create(
        question_normalized=normalized,
        defaults={
            "question_sample": _sanitize_question_sample(question),
            "count": 1,
            "last_asked": timezone.now(),
            "last_matched_content": matched_content,
        },
    )
    if not created:
        faq.count += 1
        faq.last_asked = timezone.now()
        faq.last_matched_content = matched_content
        if not faq.question_sample:
            faq.question_sample = _sanitize_question_sample(question)
        faq.save(update_fields=["count", "last_asked", "last_matched_content", "question_sample"])


def _public_chat_record_interaction(request, question: str, normalized: str, language: str, matched_content, confidence: float, answer_type: str):
    return PublicChatInteraction.objects.create(
        question_normalized=normalized[:255],
        question_sample=_sanitize_question_sample(question),
        language=language,
        matched_content=matched_content,
        confidence=round(confidence, 2),
        answer_type=answer_type,
        ip_address=_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:255],
    )


def _public_chat_track_gap(question: str, normalized: str, language: str, matched_content):
    if not normalized:
        return
    sample = _sanitize_question_sample(question)
    fallback_title = f"Chatbot gap: {sample[:80]}"
    gap, created = PublicChatKnowledgeGap.objects.get_or_create(
        question_normalized=normalized[:255],
        defaults={
            "question_sample": sample,
            "language": language,
            "count": 1,
            "last_asked": timezone.now(),
            "suggested_title": fallback_title[:200],
            "suggested_summary": sample,
            "suggested_body": sample,
            "suggested_tags": ["chatbot-gap", language],
            "matched_content": matched_content,
        },
    )
    if not created and gap.status == "pending":
        gap.count += 1
        gap.last_asked = timezone.now()
        gap.question_sample = gap.question_sample or sample
        gap.matched_content = matched_content
        gap.save(update_fields=["count", "last_asked", "question_sample", "matched_content"])


def _money(value) -> str:
    try:
        return f"PHP {int(round(float(value or 0))):,}"
    except Exception:
        return "PHP 0"


def _public_dashboard_chat_answer(question: str, language: str):
    normalized = _normalize_text(question)
    metric_terms = {
        "total",
        "count",
        "how many",
        "ilan",
        "budget",
        "investment",
        "agency",
        "agencies",
        "ongoing",
        "completed",
        "status",
        "dashboard",
        "project",
        "projects",
        "updated",
        "filter",
        "map",
        "table",
    }
    if not any(term in normalized for term in metric_terms):
        return None
    if not any(term in normalized for term in {"project", "projects", "dashboard", "budget", "investment", "ongoing", "completed", "agency", "agencies"}):
        return None

    qs = Project.objects.filter(validated=True, archived=False, is_active=True)
    total_projects = qs.count()
    total_budget = 0
    agencies = set()
    ongoing = 0
    completed = 0
    updated = 0
    for project in qs:
        profile = project.profile_data if isinstance(project.profile_data, dict) else {}
        simplified = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
        status_value = str(simplified.get("status") or project.status or "").strip().lower()
        agency_value = str(simplified.get("agencyName") or project.agency or "").strip()
        if agency_value:
            agencies.add(agency_value)
        try:
            total_budget += int(project.budget or 0)
        except Exception:
            pass
        if status_value == "ongoing":
            ongoing += 1
        if status_value == "completed":
            completed += 1
        if status_value == "updated":
            updated += 1

    if language == "tl":
        answer = (
            f"Sa public Projects Dashboard, may {total_projects} validated project(s), "
            f"kabuuang investment na {_money(total_budget)}, {ongoing} ongoing, "
            f"{completed} completed, at {len(agencies)} agency/agencies na sakop. "
            "Puwede mong gamitin ang filters, table, visual charts, at map para masuri ang mga proyekto."
        )
    else:
        answer = (
            f"The public Projects Dashboard currently has {total_projects} validated project(s), "
            f"a total investment of {_money(total_budget)}, {ongoing} ongoing project(s), "
            f"{completed} completed project(s), and {len(agencies)} covered agency/agencies. "
            "Use the filters, table, visual charts, and map to explore the data."
        )
    if "updated" in normalized:
        answer += (
            f" It also tracks {updated} project(s) with RDIP status marked Updated."
            if language == "en"
            else f" May {updated} project(s) din na may RDIP status na Updated."
        )
    return {
        "answer": answer,
        "sources": [{"title": "Projects Dashboard", "url": "/dashboard"}],
        "related_links": [{"title": "Open Projects Dashboard", "url": "/dashboard"}],
    }


def _compose_public_content_answer(question: str, content: PublicContent, language: str) -> str:
    tokens = _expand_tokens(_tokenize(question, language))
    text = content.body or content.summary or content.title
    snippet = _select_relevant_snippet(text, tokens, language)
    summary = content.summary.strip() if content.summary else ""
    if language == "tl":
        if snippet and snippet != summary:
            return f"Base sa {content.title}, {snippet}"
        return f"Nasa {content.title} page ang impormasyong ito: {summary or snippet or content.title}."
    if snippet and snippet != summary:
        return f"Based on the {content.title} page: {snippet}"
    return f"The {content.title} page covers this: {summary or snippet or content.title}."


class PublicChatAskView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PublicChatRateThrottle]

    def post(self, request):
        question = str(request.data.get("question") or "").strip()
        if not question:
            return Response({"detail": "Question is required."}, status=400)

        language = _detect_language(question)
        suggested = _get_top_questions(PUBLIC_CHAT_MAX_SUGGESTIONS) or _default_suggestions(language)
        normalized = _normalize_text(question)

        if _contains_blocked_topic(question):
            answer = (
                "I can only answer questions about the RDC-NCR public website. "
                "Please ask about the public pages, documents, or dashboard."
            )
            if language == "tl":
                answer = (
                    "Makakasagot lang ako tungkol sa pampublikong website ng RDC-NCR. "
                    "Magtanong tungkol sa mga public page, dokumento, o dashboard."
                )
            interaction = _public_chat_record_interaction(
                request, question, normalized, language, None, 0.0, "blocked"
            )
            return Response(
                {
                    "answer": answer,
                    "confidence": 0.0,
                    "answer_type": "blocked",
                    "sources": [],
                    "related_links": [],
                    "language": language,
                    "interaction_id": interaction.id,
                    "suggested_questions": suggested,
                }
            )

        dashboard_answer = _public_dashboard_chat_answer(question, language)
        if dashboard_answer:
            _public_chat_update_faq(normalized, question, None)
            interaction = _public_chat_record_interaction(
                request, question, normalized, language, None, 0.86, "direct"
            )
            return Response(
                {
                    "answer": dashboard_answer["answer"],
                    "confidence": 0.86,
                    "answer_type": "direct",
                    "sources": dashboard_answer["sources"],
                    "related_links": dashboard_answer["related_links"],
                    "language": language,
                    "interaction_id": interaction.id,
                    "suggested_questions": suggested,
                }
            )

        question_tokens = _expand_tokens(_tokenize(question, language))
        question_phrases = _phrase_tokens(question)
        contact_intent = _contact_intent(question)
        intent_slug = _detect_intent_slug(question)
        content_qs = PublicContent.objects.filter(language=language)
        if not content_qs.exists():
            content_qs = PublicContent.objects.all()

        best = None
        best_score = 0.0
        forced_contact = False
        intent_locked = False
        ranked = []
        if intent_slug:
            intent_match = content_qs.filter(slug=intent_slug).first()
            if intent_match:
                best = intent_match
                best_score = PUBLIC_CHAT_MIN_SCORE + 1.0
                forced_contact = intent_slug == "contact"
                intent_locked = True
        if contact_intent and not best:
            contact_match = content_qs.filter(slug="contact").first()
            if contact_match:
                best = contact_match
                best_score = PUBLIC_CHAT_MIN_SCORE + 1.0
                forced_contact = True
        if not forced_contact and not intent_locked:
            for content in content_qs:
                score = _score_content(question_tokens, question_phrases, content, contact_intent)
                ranked.append((score, content))
                if score > best_score:
                    best_score = score
                    best = content
            ranked.sort(key=lambda item: item[0], reverse=True)

        _public_chat_update_faq(normalized, question, best)

        if not contact_intent and getattr(best, "slug", "") != "contact":
            ordered_content = []
            seen_content_ids = set()
            if best:
                ordered_content.append(best)
                seen_content_ids.add(best.pk)
            for _score, content in ranked:
                if content.pk not in seen_content_ids:
                    ordered_content.append(content)
                    seen_content_ids.add(content.pk)
            if len(ordered_content) < 8:
                for content in content_qs:
                    if content.pk not in seen_content_ids:
                        ordered_content.append(content)
                        seen_content_ids.add(content.pk)
                    if len(ordered_content) >= 8:
                        break
            try:
                from ai_engine.groq_chat import answer_public_question

                groq_answer = answer_public_question(
                    question,
                    language,
                    [
                        {
                            "slug": content.slug,
                            "title": content.title,
                            "url": content.url,
                            "summary": content.summary,
                            "body": content.body,
                        }
                        for content in ordered_content
                    ],
                )
            except Exception:
                groq_answer = None
            if groq_answer and groq_answer.get("answered"):
                selected_slugs = set(groq_answer.get("source_slugs") or [])
                selected_content = [content for content in ordered_content if content.slug in selected_slugs]
                if not selected_content and best:
                    selected_content = [best]
                sources = _public_chat_sources(None, [
                    {"title": content.title, "url": content.url}
                    for content in selected_content
                    if content.url
                ])
                related_links = _public_chat_related_links(ranked, exclude_slug=getattr(best, "slug", ""))
                confidence = float(groq_answer.get("confidence") or 0)
                answer_type = _public_chat_answer_type(confidence, True)
                interaction = _public_chat_record_interaction(
                    request,
                    question,
                    normalized,
                    language,
                    selected_content[0] if selected_content else best,
                    confidence,
                    answer_type,
                )
                return Response(
                    {
                        "answer": groq_answer["answer"],
                        "confidence": round(confidence, 2),
                        "answer_type": answer_type,
                        "sources": sources,
                        "related_links": related_links,
                        "language": language,
                        "interaction_id": interaction.id,
                        "suggested_questions": suggested,
                        "ai_provider": "groq",
                        "ai_model": groq_answer.get("model"),
                        "used_backup_model": bool(groq_answer.get("used_backup")),
                    }
                )

        if not best or best_score < PUBLIC_CHAT_MIN_SCORE:
            contact_content = content_qs.filter(slug="contact").first()
            contact_url = contact_content.url if contact_content and contact_content.url else "/contact"
            if language == "tl":
                fallback = (
                    "Wala akong tiyak na sagot para diyan sa pampublikong website. "
                    "Para sa espesyal na tanong o paglilinaw, puwede kang magpadala ng mensahe sa Contact page."
                )
            else:
                fallback = (
                    "That question isn’t covered in the RDC-NCR public website content. "
                    "For a specific inquiry, please message us via the Contact page."
                )
            sources = []
            if contact_url:
                sources.append({"title": "Contact", "url": contact_url})
            if PUBLIC_CONTACT_EMAIL:
                sources.append({"title": "Email RDC-NCR", "url": f"mailto:{PUBLIC_CONTACT_EMAIL}"})
            alternatives = []
            for score, content in ranked[:2]:
                if score > 0 and content.url:
                    alternatives.append({"title": content.title, "url": content.url})
            if alternatives:
                alt_note = (
                    "These pages might also be related to your question."
                    if language == "en"
                    else "Baka makatulong din ang mga pahinang ito sa tanong mo."
                )
                sources = alternatives + sources
                _public_chat_track_gap(question, normalized, language, best)
                interaction = _public_chat_record_interaction(
                    request, question, normalized, language, best, 0.2, "fallback"
                )
                return Response(
                    {
                        "answer": f"{fallback} {alt_note}",
                        "confidence": 0.2,
                        "answer_type": "fallback",
                        "sources": sources,
                        "related_links": alternatives,
                        "language": language,
                        "interaction_id": interaction.id,
                        "suggested_questions": suggested,
                    }
                )
            _public_chat_track_gap(question, normalized, language, None)
            interaction = _public_chat_record_interaction(
                request, question, normalized, language, None, 0.2, "fallback"
            )
            return Response(
                {
                    "answer": fallback,
                    "confidence": 0.2,
                    "answer_type": "fallback",
                    "sources": sources,
                    "related_links": [],
                    "language": language,
                    "interaction_id": interaction.id,
                    "suggested_questions": suggested,
                }
            )

        if best.slug == "contact" or contact_intent:
            answer, include_map, include_email = _build_contact_answer(question, language)
        else:
            answer = _compose_public_content_answer(question, best, language)

        confidence = _public_chat_confidence(best_score, len(question_tokens), intent_locked, forced_contact)
        answer_type = _public_chat_answer_type(confidence, True)
        if answer_type == "fallback":
            contact_content = content_qs.filter(slug="contact").first()
            contact_url = contact_content.url if contact_content and contact_content.url else "/contact"
            if language == "tl":
                fallback = (
                    "Wala akong tiyak na sagot para diyan sa pampublikong website. "
                    "Para sa espesyal na tanong o paglilinaw, puwede kang magpadala ng mensahe sa Contact page."
                )
            else:
                fallback = (
                    "That question isn't covered in the RDC-NCR public website content. "
                    "For a specific inquiry, please message us via the Contact page."
                )
            sources = [{"title": "Contact", "url": contact_url}]
            if PUBLIC_CONTACT_EMAIL:
                sources.append({"title": "Email RDC-NCR", "url": f"mailto:{PUBLIC_CONTACT_EMAIL}"})
            related_links = _public_chat_related_links(ranked, exclude_slug=getattr(best, "slug", ""))
            _public_chat_track_gap(question, normalized, language, best)
            interaction = _public_chat_record_interaction(
                request, question, normalized, language, best, 0.2, "fallback"
            )
            return Response(
                {
                    "answer": fallback,
                    "confidence": 0.2,
                    "answer_type": "fallback",
                    "sources": sources,
                    "related_links": related_links,
                    "language": language,
                    "interaction_id": interaction.id,
                    "suggested_questions": suggested,
                }
            )
        sources = _public_chat_sources(best)
        if best.slug == "contact" or contact_intent:
            if include_map:
                sources.append(
                    {"title": "RDC-NCR Office Location (Google Maps)", "url": PUBLIC_CONTACT_MAP_URL}
                )
            if include_email:
                sources.append({"title": "Email RDC-NCR", "url": f"mailto:{PUBLIC_CONTACT_EMAIL}"})
        related_links = _public_chat_related_links(ranked, exclude_slug=best.slug)
        interaction = _public_chat_record_interaction(
            request, question, normalized, language, best, confidence, answer_type
        )
        return Response(
            {
                "answer": answer,
                "confidence": round(confidence, 2),
                "answer_type": answer_type,
                "sources": sources,
                "related_links": related_links,
                "language": language,
                "interaction_id": interaction.id,
                "suggested_questions": suggested,
            }
        )


class PublicChatFeedbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        interaction_id = request.data.get("interaction_id")
        feedback = str(request.data.get("feedback") or "").strip().lower()
        if feedback not in ("up", "down"):
            return Response({"detail": "Invalid feedback."}, status=400)
        interaction = PublicChatInteraction.objects.filter(pk=interaction_id).first()
        if not interaction:
            return Response({"detail": "Interaction not found."}, status=404)
        interaction.feedback = feedback
        interaction.save(update_fields=["feedback"])
        return Response({"status": "recorded"})


class PublicChatFAQView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        limit = PUBLIC_CHAT_MAX_SUGGESTIONS
        raw_limit = request.query_params.get("limit")
        if raw_limit:
            try:
                limit = max(1, min(12, int(raw_limit)))
            except Exception:
                limit = PUBLIC_CHAT_MAX_SUGGESTIONS

        questions = _get_top_questions(limit)
        return Response({"questions": questions})


class AdminChatKnowledgeGapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can manage chatbot learning.")
        status_filter = (request.query_params.get("status") or "pending").strip().lower()
        qs = PublicChatKnowledgeGap.objects.all()
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        try:
            limit = max(1, min(100, int(request.query_params.get("limit") or 25)))
        except Exception:
            limit = 25
        serializer = PublicChatKnowledgeGapSerializer(qs[:limit], many=True)
        return Response({"results": serializer.data, "count": qs.count()})


def _coerce_tags(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


class AdminChatKnowledgeGapApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can approve chatbot learning.")
        gap = PublicChatKnowledgeGap.objects.filter(pk=pk).first()
        if not gap:
            return Response({"detail": "Knowledge gap not found."}, status=404)
        if gap.status != "pending":
            return Response({"detail": "Knowledge gap was already reviewed."}, status=400)

        title = str(request.data.get("title") or gap.suggested_title or gap.question_sample or "RDC-NCR Public Information").strip()
        summary = str(request.data.get("summary") or gap.suggested_summary or gap.question_sample or "").strip()
        body = str(request.data.get("body") or gap.suggested_body or summary).strip()
        url = str(request.data.get("url") or "").strip()
        tags = _coerce_tags(request.data.get("tags")) or gap.suggested_tags or ["chatbot-approved"]
        language = str(request.data.get("language") or gap.language or "en").strip()[:10]
        slug = str(request.data.get("slug") or "").strip()
        if not slug:
            slug = slugify(title)[:120] or f"chat-gap-{gap.id}"
        content, _ = PublicContent.objects.update_or_create(
            slug=slug,
            language=language,
            defaults={
                "title": title[:200],
                "summary": summary,
                "body": body,
                "url": url,
                "tags": tags,
            },
        )
        gap.status = "approved"
        gap.approved_content = content
        gap.reviewed_by = request.user
        gap.reviewed_at = timezone.now()
        gap.review_notes = str(request.data.get("notes") or "").strip()
        gap.save(update_fields=["status", "approved_content", "reviewed_by", "reviewed_at", "review_notes"])
        _log_activity(
            request,
            "chat_knowledge_approved",
            details={"gap_id": gap.id, "content_slug": content.slug, "language": language},
        )
        _log_activity(
            request,
            "chat_content_updated",
            details={"content_slug": content.slug, "title": content.title, "language": language},
        )
        return Response(PublicChatKnowledgeGapSerializer(gap).data)


class AdminChatKnowledgeGapRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can reject chatbot learning.")
        gap = PublicChatKnowledgeGap.objects.filter(pk=pk).first()
        if not gap:
            return Response({"detail": "Knowledge gap not found."}, status=404)
        if gap.status != "pending":
            return Response({"detail": "Knowledge gap was already reviewed."}, status=400)
        gap.status = "rejected"
        gap.reviewed_by = request.user
        gap.reviewed_at = timezone.now()
        gap.review_notes = str(request.data.get("notes") or "").strip()
        gap.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
        _log_activity(
            request,
            "chat_knowledge_rejected",
            details={"gap_id": gap.id, "question": gap.question_sample},
        )
        return Response(PublicChatKnowledgeGapSerializer(gap).data)


def _parse_bool_query(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


class PublicEventViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = PublicEventSerializer

    def get_queryset(self):
        qs = PublicEvent.objects.filter(status="published")
        event_type = (self.request.query_params.get("type") or "").strip().lower()
        month = (self.request.query_params.get("month") or "").strip()
        q = (self.request.query_params.get("q") or "").strip()
        include_past = _parse_bool_query(self.request.query_params.get("include_past"), False)
        if event_type and event_type != "all":
            qs = qs.filter(event_type=event_type)
        if month:
            try:
                month_dt = datetime.strptime(month, "%Y-%m")
                qs = qs.filter(start_at__year=month_dt.year, start_at__month=month_dt.month)
            except ValueError:
                qs = qs.none()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(location__icontains=q))
        if getattr(self, "action", "") == "list" and not include_past:
            qs = qs.filter(start_at__gte=timezone.now())
            return qs.order_by("start_at", "title")
        if getattr(self, "action", "") == "list" and include_past:
            return qs.order_by("-start_at", "title")
        return qs.order_by("start_at", "title")

    def list(self, request, *args, **kwargs):
        try:
            limit = max(1, min(50, int(request.query_params.get("limit") or 20)))
        except Exception:
            limit = 20
        qs = self.get_queryset()
        data = PublicEventSerializer(qs[:limit], many=True).data
        return _conditional_public_response(request, {"results": data, "count": qs.count()})

    def retrieve(self, request, *args, **kwargs):
        payload = self.get_serializer(self.get_object()).data
        return _conditional_public_response(request, payload)


class AdminEventViewSet(viewsets.ModelViewSet):
    serializer_class = PublicEventSerializer
    permission_classes = [IsAuthenticated]
    queryset = PublicEvent.objects.all().order_by("-updated_at", "-start_at")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not _is_content_manager(request.user):
            raise PermissionDenied("Only admin or content editors can manage public events.")

    def get_queryset(self):
        qs = PublicEvent.objects.all().order_by("-updated_at", "-start_at")
        if self.action == "list":
            qs = qs.filter(status="archived") if self.request.query_params.get("archived") == "1" else qs.exclude(status="archived")
        if _is_admin_user(self.request.user):
            return qs
        if self.action == "list" and self.request.query_params.get("archived") == "1":
            return qs
        return qs.filter(created_by=self.request.user)

    def _ensure_editor_can_change(self, event):
        if _is_admin_user(self.request.user):
            return
        if event.created_by_id != self.request.user.id:
            raise PermissionDenied("Content editors can only manage their own event drafts.")
        if event.status not in {"draft", "rejected"}:
            raise PermissionDenied("Submitted, published, or archived events are locked for content editors.")

    def _ensure_admin_action(self):
        if not _is_admin_user(self.request.user):
            raise PermissionDenied("Only admin can approve, reject, or archive public events.")

    def perform_create(self, serializer):
        event = serializer.save(created_by=self.request.user, status="draft")
        _log_activity(
            self.request,
            "cms_event_created",
            details={"event_id": event.id, "title": event.title, "status": event.status},
        )

    def perform_update(self, serializer):
        self._ensure_editor_can_change(serializer.instance)
        event = serializer.save()
        _log_activity(
            self.request,
            "cms_event_updated",
            details={"event_id": event.id, "title": event.title, "status": event.status},
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        event = self.get_object()
        self._ensure_editor_can_change(event)
        if event.status not in {"draft", "rejected"}:
            return Response({"detail": "Only draft or rejected events can be submitted."}, status=400)
        event.status = "submitted"
        event.submitted_by = request.user
        event.review_notes = ""
        event.save(update_fields=["status", "submitted_by", "review_notes", "updated_at"])
        _log_activity(request, "cms_event_submitted", details={"event_id": event.id, "title": event.title})
        return Response(PublicEventSerializer(event).data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        self._ensure_admin_action()
        event = self.get_object()
        if event.status == "archived":
            return Response({"detail": "Archived events cannot be published."}, status=400)
        event.status = "published"
        event.reviewed_by = request.user
        event.published_at = timezone.now()
        event.review_notes = str(request.data.get("review_notes") or "").strip()
        event.save(update_fields=["status", "reviewed_by", "published_at", "review_notes", "updated_at"])
        _log_activity(request, "cms_event_published", details={"event_id": event.id, "title": event.title})
        return Response(PublicEventSerializer(event).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        self._ensure_admin_action()
        event = self.get_object()
        if event.status not in {"submitted", "draft"}:
            return Response({"detail": "Only submitted or draft events can be rejected."}, status=400)
        event.status = "rejected"
        event.reviewed_by = request.user
        event.review_notes = str(request.data.get("review_notes") or "Rejected by admin review.").strip()
        event.save(update_fields=["status", "reviewed_by", "review_notes", "updated_at"])
        _log_activity(
            request,
            "cms_event_rejected",
            details={"event_id": event.id, "title": event.title, "notes": event.review_notes},
        )
        return Response(PublicEventSerializer(event).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        self._ensure_admin_action()
        event = self.get_object()
        event.status = "archived"
        event.reviewed_by = request.user
        event.archived_at = timezone.now()
        event.save(update_fields=["status", "reviewed_by", "archived_at", "updated_at"])
        _log_activity(request, "cms_event_archived", details={"event_id": event.id, "title": event.title})
        return Response(PublicEventSerializer(event).data)

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        self._ensure_admin_action()
        event = self.get_object()
        if event.status != "archived":
            return Response({"detail": "Only archived events can be unarchived."}, status=400)
        event.status = "draft"
        event.reviewed_by = request.user
        event.archived_at = None
        event.published_at = None
        event.save(
            update_fields=["status", "reviewed_by", "archived_at", "published_at", "updated_at"]
        )
        _log_activity(request, "cms_event_unarchived", details={"event_id": event.id, "title": event.title, "status": "draft"})
        return Response(PublicEventSerializer(event).data)

    def destroy(self, request, *args, **kwargs):
        event = self.get_object()
        _log_activity(
            request, "cms_event_deleted",
            details={"event_id": event.id, "title": event.title, "status": event.status},
        )
        return super().destroy(request, *args, **kwargs)


def _validate_password_policy(password: str):
    if len(password) < 12:
        return "Password must be at least 12 characters."
    if not re.search(r"[A-Z]", password):
        return "Password must include an uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must include a lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must include a number."
    if not any(character in string.punctuation for character in password):
        return "Password must include a symbol."
    return ""


SYSTEM_MANAGED_PROFILE_KEYS = {
    "validator_review",
    "validator_revision_access",
    "contributor_snapshot",
    "public_summary",
    "public_summary_override",
    "simplified_form_meta",
}

DETAILED_DERIVED_PROFILE_FIELDS = {
    "submission_type",
    "templateName",
    "uploadedFiles",
    "priorityAnalysisFacts",
    "mainFundingSources",
}


def _revision_field_key(profile_data, path):
    path = str(path or "").strip()
    if not path or path == "(root)":
        return ""
    simplified = (
        profile_data.get("simplified_form")
        if isinstance(profile_data, dict)
        else None
    )
    if isinstance(simplified, dict):
        if not path.startswith("simplified_form."):
            return ""
        parts = path.split(".")[1:]
        if not parts:
            return ""
        root = parts[0]
        if root in ("fundingRequirementTotal", "actualApprovedTotal", "priorityAnalysisFacts"):
            return ""
        if root == "custom_fields":
            return parts[1] if len(parts) > 1 else ""
        return root
    root = path.split(".")[0]
    if root in SYSTEM_MANAGED_PROFILE_KEYS or root in DETAILED_DERIVED_PROFILE_FIELDS:
        return ""
    return root


def _available_revision_fields(profile_data):
    if not isinstance(profile_data, dict):
        return set()
    simplified = profile_data.get("simplified_form")
    if isinstance(simplified, dict):
        fields = {
            str(key)
            for key in simplified.keys()
            if str(key) not in ("fundingRequirementTotal", "actualApprovedTotal", "priorityAnalysisFacts", "custom_fields")
        }
        custom = simplified.get("custom_fields")
        if isinstance(custom, dict):
            fields.update(str(key) for key in custom.keys())
        marker = profile_data.get("form_schema") if isinstance(profile_data.get("form_schema"), dict) else {}
        try:
            from cms.models import CMSContributorFormVersion
            from .document_policy import current_document_policy, document_policy_from_schema

            version = CMSContributorFormVersion.objects.filter(
                form__key=str(marker.get("key") or "simplified-rdip"),
                version_number=marker.get("version"),
            ).first()
            if version:
                document_policy = document_policy_from_schema(
                    version.schema_json,
                    form_key=version.form.key,
                    form_version=version.version_number,
                )
                if document_policy.get("field_key"):
                    fields.add(str(document_policy["field_key"]))
            if not version or not document_policy.get("field_key"):
                document_policy = current_document_policy(str(marker.get("key") or "simplified-rdip"))
                if document_policy.get("field_key"):
                    fields.add(str(document_policy["field_key"]))
        except (TypeError, ValueError):
            pass
        return fields
    return {
        str(key)
        for key in profile_data.keys()
        if str(key) not in SYSTEM_MANAGED_PROFILE_KEYS
        and str(key) not in DETAILED_DERIVED_PROFILE_FIELDS
        and str(key) != "form_schema"
    }


def _clean_revision_editable_fields(raw_fields, profile_data):
    if not isinstance(raw_fields, list):
        return None
    available = _available_revision_fields(profile_data)
    cleaned = []
    for raw in raw_fields:
        field = str(raw or "").strip()
        if not field or field not in available or field in cleaned:
            continue
        cleaned.append(field)
    return cleaned[:300]


def _restricted_revision_changes(before_profile, after_profile, editable_fields):
    if editable_fields is None:
        return []
    allowed = {str(field) for field in editable_fields}
    blocked = []
    reference = before_profile if isinstance(before_profile, dict) else after_profile
    for change in _json_diff(before_profile or {}, after_profile or {}):
        field = _revision_field_key(reference, change.get("field"))
        if field and field not in allowed and field not in blocked:
            blocked.append(field)
    return blocked


def _restricted_project_display_changes(project, request_data, editable_fields, profile_data):
    if editable_fields is None:
        return []
    simplified = isinstance((profile_data or {}).get("simplified_form"), dict)
    mappings = {
        "title": "projectActivity" if simplified else "projectTitle",
        "description": "description",
        "agency": "agencyName" if simplified else "officeUnit",
        "budget": "fundingRequirementByYear" if simplified else "totalProjectCost",
    }
    current = {
        "title": project.name,
        "description": project.description,
        "agency": project.agency,
        "budget": project.budget,
    }
    allowed = {str(field) for field in editable_fields}
    blocked = []
    for request_key, permission_key in mappings.items():
        if request_key not in request_data or permission_key in allowed:
            continue
        incoming = request_data.get(request_key)
        existing = current.get(request_key)
        if request_key == "budget":
            try:
                changed = int(incoming or 0) != int(existing or 0)
            except (TypeError, ValueError):
                changed = True
        else:
            changed = str(incoming or "").strip() != str(existing or "").strip()
        if changed:
            blocked.append(permission_key)
    return blocked


def _strip_validator_meta(profile_data):
    if not isinstance(profile_data, dict):
        return {}
    return {
        key: value
        for key, value in profile_data.items()
        if key not in SYSTEM_MANAGED_PROFILE_KEYS
    }


def _validator_review_source(profile_data):
    contributor_snapshot = profile_data.get("contributor_snapshot")
    if not isinstance(contributor_snapshot, dict):
        contributor_snapshot = _strip_validator_meta(profile_data)
    review = profile_data.get("validator_review")
    if isinstance(review, dict):
        # A contributor's resubmission supersedes any older validator working copy.
        if str(review.get("review_status") or "").lower() == "draft" and review.get("resubmitted_at"):
            return contributor_snapshot
        if isinstance(review.get("working_copy"), dict):
            return review["working_copy"]
    return contributor_snapshot


def _validator_answers_unchanged(incoming, saved):
    if not isinstance(incoming, dict) or not isinstance(saved, dict):
        return False
    received_answers = _strip_validator_meta(incoming)
    saved_answers = _strip_validator_meta(saved)
    # A review draft can add this server-side marker to older submissions.
    if "form_schema" not in received_answers and "form_schema" in saved_answers:
        received_answers["form_schema"] = saved_answers["form_schema"]
    return received_answers == saved_answers


def _diff_string(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value)


def _is_empty_equivalent(value):
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return True
        if stripped in {"0", "0.0", "0.00"}:
            return True
        return False
    if isinstance(value, bool):
        return value is False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _json_diff(before, after, path=""):
    changes = []
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before.keys()) | set(after.keys()))
        for key in keys:
            if not path and (key in SYSTEM_MANAGED_PROFILE_KEYS or key == "form_schema"):
                continue
            before_has = key in before
            after_has = key in after
            if before_has and not after_has and _is_empty_equivalent(before.get(key)):
                continue
            if after_has and not before_has and _is_empty_equivalent(after.get(key)):
                continue
            next_path = f"{path}.{key}" if path else str(key)
            changes.extend(_json_diff(before.get(key), after.get(key), next_path))
        return changes

    if isinstance(before, list) and isinstance(after, list):
        max_len = max(len(before), len(after))
        for idx in range(max_len):
            before_has = idx < len(before)
            after_has = idx < len(after)
            before_value = before[idx] if before_has else None
            after_value = after[idx] if after_has else None

            if before_has and not after_has and _is_empty_equivalent(before_value):
                continue
            if after_has and not before_has and _is_empty_equivalent(after_value):
                continue

            next_path = f"{path}.{idx}" if path else str(idx)
            changes.extend(_json_diff(before_value, after_value, next_path))
        return changes

    if _is_empty_equivalent(before) and _is_empty_equivalent(after):
        return changes

    if before != after:
        changes.append(
            {
                "field": path or "(root)",
                "before": _diff_string(before),
                "after": _diff_string(after),
            }
        )
    return changes


def _nested_diff_value(data, path):
    value = data
    for key in str(path or "").split("."):
        if not key or not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _validator_edited_fields(before, after):
    changes = _json_diff(before, after)
    normalized = {}
    order = []
    for entry in changes:
        field = str(entry.get("field") or "")
        grouped_field = ""
        if field.startswith("simplified_form.sdgSelections."):
            grouped_field = "simplified_form.sdgSelections"
        elif field.startswith("sdgSelections."):
            grouped_field = "sdgSelections"

        if grouped_field:
            before_values = _nested_diff_value(before, grouped_field)
            after_values = _nested_diff_value(after, grouped_field)
            entry = {
                "field": grouped_field,
                "before": ", ".join(str(value) for value in before_values) if isinstance(before_values, list) else "",
                "after": ", ".join(str(value) for value in after_values) if isinstance(after_values, list) else "",
            }
            field = grouped_field

        if field not in normalized:
            order.append(field)
        normalized[field] = entry
    return [normalized[field] for field in order]


def _parse_year_value(value):
    try:
        n = int(str(value or "").strip())
    except Exception:
        return None
    if n < 1900 or n > 2200:
        return None
    return n


def _validate_simplified_funding(profile_data):
    if not isinstance(profile_data, dict):
        return None
    simplified = profile_data.get("simplified_form")
    if not isinstance(simplified, dict):
        return None
    start = _parse_year_value(simplified.get("startYear"))
    end = _parse_year_value(simplified.get("endYear"))
    if start is None or end is None:
        return "Start Year and End Year must be valid years."
    if end < start:
        return "End Year must be the same as or later than Start Year."
    if end - start > 15:
        return "Year range is too large (max 15 years)."
    allowed = set()
    if start <= 2022:
        allowed.add("2022_prior")
        first = max(2023, start)
    else:
        first = start
    for year in range(first, end + 1):
        allowed.add(str(year))
    for field in ("fundingRequirementByYear", "actualFundingByYear"):
        raw = simplified.get(field) or {}
        if not isinstance(raw, dict):
            return f"{field} must be an object."
        for key in raw.keys():
            key_str = str(key)
            if key_str not in allowed:
                return f"{field} contains out-of-range key: {key_str}."
    return None


def _manila_funding_year():
    return timezone.localtime(timezone.now(), ZoneInfo("Asia/Manila")).year


def _contributor_project_scope(user, prefix=""):
    scope = Q(**{f"{prefix}created_by": user})
    agency = _normalize_account_agency(getattr(user, "agency", ""))
    if agency:
        scope |= Q(**{f"{prefix}primary_agency__code__iexact": agency})
        # Collaboration becomes official only after submission; planning drafts
        # remain private to the primary agency even if draft answers name a
        # future collaborator.
        collaborator_scope = Q(
            **{f"{prefix}collaborating_agency_links__agency__code__iexact": agency}
        ) & ~Q(**{f"{prefix}status": "planning"})
        scope |= collaborator_scope
        # Compatibility for projects not backfilled yet.
        scope |= Q(**{f"{prefix}agency__iexact": agency})
    return scope


def _same_agency_value(left, right):
    return " ".join(str(left or "").split()).casefold() == " ".join(str(right or "").split()).casefold()


def _funding_value(value):
    raw = str(value if value is not None else "").strip().replace(",", "")
    if not raw:
        return ""
    try:
        return Decimal(raw)
    except InvalidOperation:
        return raw


def _validate_contributor_simplified_write(user, incoming_profile, *, project=None, existing_profile=None, incoming_agency=None):
    existing_simplified = existing_profile.get("simplified_form") if isinstance(existing_profile, dict) else None
    if project is not None and isinstance(existing_simplified, dict) and not _same_agency_value(incoming_agency, project.agency):
        return "Project agency is locked and cannot be changed by a contributor."
    if not isinstance(incoming_profile, dict):
        return None
    simplified = incoming_profile.get("simplified_form")
    if isinstance(existing_simplified, dict) and not isinstance(simplified, dict):
        return "The simplified form cannot be removed from an existing project."
    if not isinstance(simplified, dict):
        return None

    if project is None:
        account_agency = str(getattr(user, "agency", "") or "").strip()
        if not account_agency:
            return "Your account has no agency. Ask an administrator to update it before creating a project."
        account_agency_record = _agency_for_value(account_agency, active_only=True)
        if account_agency_record is None:
            return "Your account agency is not active in the agency catalog. Ask an administrator to correct it."
        if not _same_agency_value(incoming_agency, account_agency) or not _same_agency_value(simplified.get("agencyName"), account_agency):
            return "Agency Name must match your account agency."
        previous = {}
        primary_agency = account_agency_record
    else:
        if not project.primary_agency_id:
            # The data migration normally fills this relation. Retain a safe
            # compatibility path for known active catalog values created by
            # older integrations between deployments; unknown/inactive values
            # still require Administrator correction.
            legacy_primary_code = _normalize_account_agency(project.agency)
            if not legacy_primary_code:
                return "This project has no valid primary agency. Ask an administrator to correct it before editing."
            primary_agency = legacy_primary_code
        else:
            primary_agency = project.primary_agency
        if not _is_primary_agency_contributor(user, project):
            return "Only contributors from the primary agency can modify this project."
        previous = existing_profile.get("simplified_form") if isinstance(existing_profile, dict) else {}
        if not isinstance(previous, dict):
            previous = {}
        saved_form_agency = previous.get("agencyName") or ""
        incoming_form_agency = simplified.get("agencyName") or ""
        unchanged_agency = _same_agency_value(incoming_form_agency, saved_form_agency)
        legacy_agency_fill = not saved_form_agency and _same_agency_value(incoming_form_agency, project.agency)
        if not unchanged_agency and not legacy_agency_fill:
            return "Agency Name is locked and cannot be changed by a contributor."

    collaborators = _validate_collaborating_agencies(incoming_profile, primary_agency)
    if isinstance(collaborators, str):
        return collaborators

    incoming_actual = simplified.get("actualFundingByYear") or {}
    previous_actual = previous.get("actualFundingByYear") or {}
    if not isinstance(incoming_actual, dict) or not isinstance(previous_actual, dict):
        return "Actual/Approved Funding must be an object."
    year = _manila_funding_year()
    for key in set(incoming_actual) | set(previous_actual):
        key = str(key)
        if key == "2022_prior" and year >= 2022:
            continue
        if key.isdigit() and int(key) <= year:
            continue
        if _funding_value(incoming_actual.get(key)) != _funding_value(previous_actual.get(key)):
            label = "2022 & Prior" if key == "2022_prior" else key
            return f"Actual/Approved Funding for {label} is read-only. Only {year} and earlier years may be changed."
    return None


def _normalize_simplified_field_path(path: str) -> str:
    if path.startswith("sdgSelections."):
        return "sdgSelections"
    return path


def _collect_simplified_field_paths(simplified):
    if not isinstance(simplified, dict):
        return set()
    paths = set()
    for key, value in simplified.items():
        if key in ("fundingRequirementTotal", "actualApprovedTotal"):
            continue
        if key in ("fundingRequirementByYear", "actualFundingByYear", "custom_fields") and isinstance(value, dict):
            for sub_key in value.keys():
                paths.add(f"{key}.{sub_key}")
        else:
            paths.add(str(key))
    return paths


def _apply_simplified_meta(incoming_profile, existing_profile, user):
    if not isinstance(incoming_profile, dict):
        return incoming_profile, [], []
    simplified = incoming_profile.get("simplified_form")
    if not isinstance(simplified, dict):
        return incoming_profile, [], []
    previous = {}
    if isinstance(existing_profile, dict) and isinstance(existing_profile.get("simplified_form"), dict):
        previous = existing_profile.get("simplified_form") or {}

    diff = _json_diff(previous, simplified)
    changed_fields = []
    before_values = {}
    changes_by_field = {}
    for entry in diff:
        raw_field = str(entry.get("field") or "")
        if not raw_field or raw_field == "(root)":
            continue
        if raw_field in ("fundingRequirementTotal", "actualApprovedTotal"):
            continue
        normalized = _normalize_simplified_field_path(raw_field)
        before_value = str(entry.get("before") or "")
        after_value = str(entry.get("after") or "")
        if raw_field.startswith("sdgSelections."):
            before_list = previous.get("sdgSelections") if isinstance(previous, dict) else []
            after_list = simplified.get("sdgSelections") if isinstance(simplified, dict) else []
            before_value = ", ".join([str(v) for v in before_list]) if isinstance(before_list, list) else str(before_list or "")
            after_value = ", ".join([str(v) for v in after_list]) if isinstance(after_list, list) else str(after_list or "")
        if normalized not in before_values:
            before_values[normalized] = before_value
        if normalized not in changes_by_field:
            changes_by_field[normalized] = {"field": normalized, "before": before_value, "after": after_value}
        if normalized not in changed_fields:
            changed_fields.append(normalized)

    valid_paths = _collect_simplified_field_paths(simplified)
    meta_source = incoming_profile.get("simplified_form_meta")
    if not isinstance(meta_source, dict) and isinstance(existing_profile, dict):
        meta_source = existing_profile.get("simplified_form_meta")
    field_edits = {}
    if isinstance(meta_source, dict):
        edits_raw = meta_source.get("field_edits")
        if isinstance(edits_raw, dict):
            for key, value in edits_raw.items():
                if str(key) in valid_paths:
                    field_edits[str(key)] = value

    if changed_fields:
        display_name = _user_display_name(user)
        timestamp = timezone.now().isoformat()
        for field in changed_fields:
            field_edits[field] = {
                "by": user.username,
                "name": display_name,
                "at": timestamp,
                "before": before_values.get(field, ""),
            }
        incoming_profile["simplified_form_meta"] = {
            "field_edits": field_edits,
            "last_edit": {"by": user.username, "name": display_name, "at": timestamp},
        }
    else:
        incoming_profile["simplified_form_meta"] = {
            "field_edits": field_edits,
            "last_edit": meta_source.get("last_edit") if isinstance(meta_source, dict) else {},
        }

    # Always keep an up-to-date deterministic public summary for reviewers/public dashboard.
    try:
        incoming_profile["public_summary"] = build_public_summary(simplified)
    except Exception:
        # Never block a save on summary generation issues.
        pass
    changes = [changes_by_field[field] for field in changed_fields if field in changes_by_field]
    return incoming_profile, changed_fields, changes


def _simplified_from_profile(profile_data):
    if isinstance(profile_data, dict) and isinstance(profile_data.get("simplified_form"), dict):
        return profile_data.get("simplified_form") or {}
    return {}


def _rdip_status_from_profile(profile_data):
    return str(_simplified_from_profile(profile_data).get("status") or "").strip()


def _is_completed_rdip_project(project):
    return _rdip_status_from_profile(project.profile_data).lower() == "completed"


def _project_public_summary(profile_data):
    if isinstance(profile_data, dict):
        summary = profile_data.get("public_summary")
        if isinstance(summary, dict):
            return summary
        simplified = profile_data.get("simplified_form")
        if isinstance(simplified, dict):
            return build_public_summary(simplified)
    return {}


def _next_revision_number(project):
    latest = project.revisions.order_by("-revision_number").first()
    return (latest.revision_number if latest else 0) + 1


def _safe_revision_changes(before_profile, after_profile):
    before = _simplified_from_profile(before_profile)
    after = _simplified_from_profile(after_profile)
    changes = []
    seen = set()
    for entry in _json_diff(before, after):
        raw_field = str(entry.get("field") or "")
        if not raw_field or raw_field == "(root)" or raw_field in ("fundingRequirementTotal", "actualApprovedTotal"):
            continue
        field = _normalize_simplified_field_path(raw_field)
        if raw_field.startswith("sdgSelections."):
            entry = {
                "field": "sdgSelections",
                "before": ", ".join(str(v) for v in before.get("sdgSelections", []) if str(v).strip()),
                "after": ", ".join(str(v) for v in after.get("sdgSelections", []) if str(v).strip()),
            }
            field = "sdgSelections"
        if field in seen:
            continue
        seen.add(field)
        changes.append(
            {
                "field": field,
                "before": str(entry.get("before") or ""),
                "after": str(entry.get("after") or ""),
            }
        )
    return changes[:50]


def _ensure_public_revision(project, user=None):
    if not project.validated:
        return None
    current = project.revisions.filter(state="endorsed", is_public_current=True).first()
    if current:
        return current
    profile = deepcopy(project.profile_data) if isinstance(project.profile_data, dict) else {}
    if isinstance(profile.get("simplified_form"), dict):
        profile["public_summary"] = build_public_summary(profile["simplified_form"])
    ProjectRevision.objects.filter(project=project, is_public_current=True).update(is_public_current=False)
    revision = ProjectRevision.objects.create(
        project=project,
        revision_number=_next_revision_number(project),
        revision_type="initial_submission",
        state="endorsed",
        profile_data_snapshot=profile,
        public_summary_snapshot=_project_public_summary(profile),
        changed_fields=[],
        is_public_current=True,
        created_by=project.created_by,
        submitted_by=project.created_by,
        reviewed_by=user,
        endorsed_by=user,
        submitted_at=project.updated_at or timezone.now(),
        reviewed_at=project.updated_at or timezone.now(),
        endorsed_at=project.updated_at or timezone.now(),
    )
    return revision


def _apply_revision_to_project(revision, user):
    project = revision.project
    profile = deepcopy(revision.profile_data_snapshot) if isinstance(revision.profile_data_snapshot, dict) else {}
    simplified = _simplified_from_profile(profile)
    if simplified:
        profile["public_summary"] = build_public_summary(simplified)
    project.name = str(simplified.get("projectActivity") or simplified.get("program") or project.name or "Untitled Project")
    project.description = str(simplified.get("description") or simplified.get("objective") or project.description or "")
    project.agency = str(simplified.get("agencyName") or project.agency or "")
    project.implementing_agency = project.agency or project.implementing_agency or "N/A"
    try:
        project.year = int(str(simplified.get("startYear") or project.year or "").strip())
    except Exception:
        pass
    summary = _project_public_summary(profile)
    key_facts = summary.get("key_facts") if isinstance(summary, dict) else {}
    try:
        project.budget = int(round(float(key_facts.get("funding_requirement_total") or project.budget or 0)))
    except Exception:
        pass
    project.cost = project.budget or 0
    project.profile_data = profile
    project.status = "completed"
    project.validated = True
    project.save(
        update_fields=[
            "name",
            "description",
            "agency",
            "implementing_agency",
            "year",
            "budget",
            "cost",
            "profile_data",
            "status",
            "validated",
            "updated_at",
        ]
    )
    _sync_project_collaborators(project, profile, user)
    ProjectRevision.objects.filter(project=project, state="endorsed", is_public_current=True).exclude(
        id=revision.id
    ).update(is_public_current=False)
    revision.profile_data_snapshot = profile
    revision.public_summary_snapshot = summary if isinstance(summary, dict) else {}
    revision.state = "endorsed"
    revision.is_public_current = True
    revision.reviewed_by = user
    revision.endorsed_by = user
    revision.reviewed_at = timezone.now()
    revision.endorsed_at = timezone.now()
    revision.save(
        update_fields=[
            "profile_data_snapshot",
            "public_summary_snapshot",
            "state",
            "is_public_current",
            "reviewed_by",
            "endorsed_by",
            "reviewed_at",
            "endorsed_at",
            "updated_at",
        ]
    )
    return project


class ProjectPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        role = getattr(request.user, "role", "")
        if role in ("admin", "validator"):
            return True
        if request.method in permissions.SAFE_METHODS:
            if role in ("staff", "employee"):
                return _is_primary_agency_contributor(request.user, obj) or _is_collaborating_agency_contributor(request.user, obj)
            return False
        if role in ("staff", "employee"):
            return _is_primary_agency_contributor(request.user, obj)
        return False


class EmployeeRolePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ("staff", "employee")
        )


class ValidatorRolePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == "validator"
        )


class AdminOnlyPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related(
            "actor",
            "project",
            "comment",
        )
        unread = (self.request.query_params.get("unread") or "").strip().lower()
        if unread in ("1", "true", "yes"):
            qs = qs.filter(read_at__isnull=True)
        return qs

    def list(self, request, *args, **kwargs):
        try:
            limit = max(1, min(50, int(request.query_params.get("limit") or 30)))
        except Exception:
            limit = 30
        qs = self.filter_queryset(self.get_queryset())[:limit]
        results = self.get_serializer(qs, many=True).data
        include_meta = (request.query_params.get("include_meta") or "").strip().lower() in ("1", "true", "yes")
        if include_meta:
            unread_count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
            return Response({"results": results, "unread_count": unread_count})
        return Response(results)

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
        return Response({"unread_count": count})

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
            _log_activity(
                request, "notification_read", notification.project,
                {"notification_id": notification.id, "event_type": notification.event_type},
            )
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=now)
        if updated:
            _log_activity(request, "notification_read_all", details={"updated": updated})
        return Response({"updated": updated, "read_at": now})


def _project_queryset_with_related(qs, *, prefetch_priority=True):
    qs = qs.select_related("created_by", "primary_agency").prefetch_related(
        "collaborating_agency_links__agency"
    )
    if not prefetch_priority:
        return qs
    latest_confirmations = ProjectPriorityConfirmation.objects.order_by("-created_at")
    latest_analyses = ProjectPriorityAnalysis.objects.prefetch_related(
        Prefetch("confirmations", queryset=latest_confirmations)
    ).order_by("-created_at")[:1]
    return qs.prefetch_related(
        Prefetch("priority_analyses", queryset=latest_analyses, to_attr="_latest_priority_analyses")
    )


def _project_summary_queryset(qs, *, prefetch_priority=True):
    """Load only columns required by the compact project-list serializer."""
    qs = qs.only(
        "id", "name", "agency", "budget", "completion", "status", "updated_at",
        "validated", "profile_data", "primary_agency_id", "created_by_id", "created_by__username",
        "created_by__first_name", "created_by__last_name",
    )
    return _project_queryset_with_related(qs, prefetch_priority=prefetch_priority)


def _project_list_queryset(qs, request, *, prefetch_priority=True):
    if request.query_params.get("view") == "summary":
        return _project_summary_queryset(qs, prefetch_priority=prefetch_priority)
    return _project_queryset_with_related(qs, prefetch_priority=prefetch_priority)


def _can_access_project_documents(user, project):
    role = getattr(user, "role", "")
    if role == "admin":
        return True
    if project.archived:
        return False
    if role == "validator":
        return project.status == "proposed"
    if role in ("staff", "employee"):
        return _is_primary_agency_contributor(user, project) or _is_collaborating_agency_contributor(user, project)
    return False


def _can_change_project_documents(user, project, field_key):
    if getattr(user, "role", "") not in ("staff", "employee") or not _is_primary_agency_contributor(user, project):
        return False
    if project.status == "planning":
        return True
    if not _project_needs_revision(project):
        return False
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    review = profile.get("validator_review") if isinstance(profile.get("validator_review"), dict) else {}
    editable = review.get("editable_fields")
    return isinstance(editable, list) and field_key in editable


def _validate_uploaded_document(filename, content_type, data, extension):
    return validate_uploaded_document(filename, content_type, data, extension)


class ProjectSupportingDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSupportingDocumentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        queryset = ProjectSupportingDocument.objects.filter(removed_at__isnull=True).select_related(
            "project", "project__created_by", "project__primary_agency", "uploaded_by"
        )
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        role = getattr(self.request.user, "role", "")
        if role == "admin":
            return queryset
        if role == "validator":
            return queryset.filter(project__status="proposed", project__archived=False, project__is_active=True)
        if role in ("staff", "employee"):
            return queryset.filter(
                _contributor_project_scope(self.request.user, prefix="project__"),
                project__archived=False,
            ).distinct()
        return queryset.none()

    def create(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") not in ("staff", "employee"):
            raise PermissionDenied("Only contributors can upload project supporting documents.")
        try:
            project = Project.objects.get(pk=int(request.data.get("project") or 0))
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Project not found."}, status=404)
        policy = resolve_project_document_policy(project, persist=True)
        if not policy:
            from .document_policy import current_document_policy

            policy = current_document_policy("simplified-rdip")
            if policy:
                project.supporting_document_policy = policy
                project.save(update_fields=["supporting_document_policy", "updated_at"])
        if not policy:
            return Response({"detail": "This project form has no active supporting-document field."}, status=400)
        field_key = str(request.data.get("field_key") or policy.get("field_key") or "")
        if field_key != policy.get("field_key") or not _can_change_project_documents(request.user, project, field_key):
            raise PermissionDenied("Supporting documents are not editable for this project.")
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "Choose a file to upload."}, status=400)
        filename = os.path.basename(str(upload.name or "document"))[:255]
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in set(policy.get("allowed_extensions") or []):
            return Response({"detail": f"{filename} is not an allowed file type."}, status=400)
        max_file_bytes = min(int(policy.get("max_file_bytes") or 0), 20 * 1024 * 1024)
        if upload.size <= 0 or upload.size > max_file_bytes:
            return Response({"detail": f"{filename} must be no larger than {max_file_bytes // (1024 * 1024)} MB."}, status=400)
        data = upload.read(max_file_bytes + 1)
        if len(data) != upload.size or len(data) > max_file_bytes:
            return Response({"detail": "The uploaded file size could not be verified."}, status=400)
        try:
            canonical_type = _validate_uploaded_document(filename, upload.content_type, data, extension)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        checksum = hashlib.sha256(data).hexdigest()
        try:
            with transaction.atomic():
                locked_project = Project.objects.select_for_update().get(pk=project.pk)
                documents = list(active_project_documents(locked_project))
                if len(documents) >= min(int(policy.get("max_files") or 10), 10):
                    return Response({"detail": "The maximum number of supporting documents has been reached."}, status=400)
                if sum(item.size_bytes for item in documents) + len(data) > PROJECT_DOCUMENT_MAX_TOTAL_BYTES:
                    return Response({"detail": "Supporting documents cannot exceed 200 MB per project."}, status=400)
                if any(item.checksum_sha256 == checksum for item in documents):
                    return Response({"detail": f"{filename} is already attached to this project."}, status=409)
                document = ProjectSupportingDocument.objects.create(
                    project=locked_project,
                    field_key=field_key,
                    form_key=str(policy.get("form_key") or "simplified-rdip"),
                    form_version=int(policy.get("form_version") or 1),
                    original_filename=filename,
                    content_type=canonical_type,
                    extension=extension,
                    size_bytes=len(data),
                    checksum_sha256=checksum,
                    content=data,
                    uploaded_by=request.user,
                )
        except IntegrityError:
            return Response({"detail": f"{filename} is already attached to this project."}, status=409)
        queued = dispatch_document_processing(document.id)
        if not queued:
            document.processing_error = "The document worker is unavailable. Retry processing when it is online."
            document.save(update_fields=["processing_error", "updated_at"])
        else:
            # Eager local-development tasks complete before ``delay`` returns.
            # Refresh so the response immediately reports Ready or Failed
            # instead of returning the stale Queued instance.
            document.refresh_from_db()
        _log_activity(
            request,
            "supporting_document_uploaded",
            project,
            {"document_id": document.id, "filename": filename, "size_bytes": len(data)},
        )
        return Response(self.get_serializer(document).data, status=201)

    def destroy(self, request, *args, **kwargs):
        document = self.get_object()
        if not _can_change_project_documents(request.user, document.project, document.field_key):
            raise PermissionDenied("Supporting documents are not editable for this project.")
        document.removed_at = timezone.now()
        document.content = b""
        document.extracted_text = ""
        document.save(update_fields=["removed_at", "content", "extracted_text", "updated_at"])
        _log_activity(
            request,
            "supporting_document_removed",
            document.project,
            {"document_id": document.id, "filename": document.original_filename},
        )
        return Response(status=204)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        if not _can_access_project_documents(request.user, document.project):
            raise PermissionDenied("You cannot access this project's supporting documents.")
        response = HttpResponse(bytes(document.content), content_type=document.content_type)
        safe_name = document.original_filename.replace('"', "")
        response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        document = self.get_object()
        if not _can_change_project_documents(request.user, document.project, document.field_key):
            raise PermissionDenied("Supporting documents are not editable for this project.")
        document.extraction_status = ProjectSupportingDocument.EXTRACTION_QUEUED
        document.processing_error = ""
        document.save(update_fields=["extraction_status", "processing_error", "updated_at"])
        if not dispatch_document_processing(document.id):
            document.processing_error = "The document worker is unavailable. Try again later."
            document.save(update_fields=["processing_error", "updated_at"])
            return Response(self.get_serializer(document).data, status=503)
        document.refresh_from_db()
        return Response(self.get_serializer(document).data)

    @action(detail=False, methods=["get"], url_path="assessment-status")
    def assessment_status(self, request):
        try:
            project = Project.objects.get(pk=int(request.query_params.get("project") or 0))
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Project not found."}, status=404)
        if not _can_access_project_documents(request.user, project):
            raise PermissionDenied("You cannot access this project's supporting documents.")
        return Response(serialize_document_assessment(project))

    @action(detail=False, methods=["post"], url_path="retry-assessment")
    def retry_assessment(self, request):
        try:
            project = Project.objects.get(pk=int(request.data.get("project") or 0))
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Project not found."}, status=404)
        if getattr(request.user, "role", "") not in {"validator", "admin"} or not _can_access_project_documents(request.user, project):
            raise PermissionDenied("Only an assigned validator or administrator can retry this assessment.")
        documents = list(active_project_documents(project))
        if not documents or any(item.extraction_status != "ready" for item in documents):
            return Response({"detail": "All active documents must be ready before assessment."}, status=400)
        assessment, created = ensure_queued_assessment(project)
        if assessment is None:
            return Response({"detail": "This project has no supporting-document policy."}, status=400)
        if not created:
            assessment.status = "queued"
            assessment.error_message = ""
            assessment.save(update_fields=["status", "error_message", "updated_at"])
        if not dispatch_document_assessment(assessment.id):
            assessment.status = "unavailable"
            assessment.error_message = "The document assessment worker is unavailable."
            assessment.save(update_fields=["status", "error_message", "updated_at"])
            return Response(serialize_document_assessment(project), status=503)
        return Response(serialize_document_assessment(project))


class BaseProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, ProjectPermission]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        project = serializer.instance
        if getattr(self.request.user, "role", "") in ("staff", "employee"):
            agency = _agency_for_value(getattr(self.request.user, "agency", ""), active_only=True)
            if agency and project.primary_agency_id != agency.id:
                project.primary_agency = agency
                project.agency = agency.code
                project.implementing_agency = agency.code
                project.save(update_fields=["primary_agency", "agency", "implementing_agency", "updated_at"])
        if getattr(self.request.user, "role", "") not in ("staff", "employee"):
            return
        if project.status == "planning":
            _notify_many(
                _admins(),
                event_type="contributor_project_draft_created",
                title="Contributor project draft created",
                message=(
                    f"{_user_display_name(self.request.user)} "
                    f"created a draft: {_project_title(project)}"
                ),
                project=project,
                actor=self.request.user,
                dedupe_key=f"project:{project.id}:contributor-draft:admins",
            )
        elif project.status == "proposed":
            _notify_many(
                _active_validators(),
                event_type="project_submitted",
                title="New project submitted",
                message=f"New project submitted for validation: {_project_title(project)}",
                project=project,
                actor=self.request.user,
                dedupe_key=f"project:{project.id}:submitted:validators",
            )

    def get_serializer_class(self):
        if getattr(self, "action", "") == "list" and self.request.query_params.get("view") == "summary":
            if (self.request.query_params.get("scope") or "").strip().lower() == "update_forms":
                return ProjectFormMigrationSummarySerializer
            return ProjectSummarySerializer
        return ProjectSerializer

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", "")
        if role == "admin":
            qs = Project.objects.all().order_by("-created_at")
        elif role == "validator":
            qs = Project.objects.filter(Q(status="proposed") | Q(status="planning")).order_by("-created_at")
        else:
            qs = Project.objects.filter(created_by=user).order_by("-created_at")
        workflow = self.request.query_params.get("workflow") or self.request.query_params.get("status")
        qs = _filter_projects_for_workflow(qs, workflow).order_by("-created_at")
        return _project_list_queryset(
            qs, self.request,
            prefetch_priority=getattr(self, "action", "") == "list",
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        project = self.get_object()
        if request.user.role != "admin" and not _is_primary_agency_contributor(request.user, project):
            raise PermissionDenied("Only contributors from the primary agency or an administrator can submit this project.")
        if not _is_simplified_profile(project.profile_data):
            return Response({"detail": "Only projects created with the simplified form can be submitted."}, status=400)
        project_form_marker = project.profile_data.get("form_schema") if isinstance(project.profile_data, dict) else None
        versioned_form = isinstance(project_form_marker, dict) and project_form_marker.get("legacy") is not True
        if (
            isinstance(project.profile_data, dict)
            and isinstance(project.profile_data.get("simplified_form"), dict)
            and not isinstance(project.profile_data.get("form_schema"), dict)
        ):
            project.profile_data["form_schema"] = {"key": "simplified-rdip", "version": 1, "legacy": True}
        try:
            validate_simplified_answers(project.profile_data, require_complete=versioned_form)
        except FormSchemaError as exc:
            return Response({"detail": str(exc)}, status=400)
        collaborators = _validate_collaborating_agencies(project.profile_data, project.primary_agency or project.agency)
        if isinstance(collaborators, str):
            return Response({"detail": collaborators}, status=400)
        document_error = validate_project_documents_for_submit(project)
        if document_error:
            return Response({"detail": document_error, "code": "supporting_documents_not_ready"}, status=400)
        was_needs_revision = _project_needs_revision(project)
        if project.status == "planning":
            project.status = "proposed"
            # Refresh deterministic public summary on submit.
            if isinstance(project.profile_data, dict):
                try:
                    sf = project.profile_data.get("simplified_form")
                    if isinstance(sf, dict):
                        project.profile_data["public_summary"] = build_public_summary(sf)
                except Exception:
                    pass
                project.save(update_fields=["status", "profile_data", "updated_at"])
            else:
                project.save(update_fields=["status", "updated_at"])
            _sync_project_collaborators(project, project.profile_data, request.user)
            _log_activity(request, "project_submit", project, {"status": project.status})
            _notify_user(
                request.user,
                event_type="project_submit_confirmation",
                title="Project submitted successfully",
                message=f"{_project_title(project)} was submitted for validation.",
                project=project,
                actor=None,
                dedupe_key=f"project:{project.id}:submitted:employee",
            )
            _notify_many(
                _active_validators(),
                event_type="project_submitted",
                title="New project submitted",
                message=f"New project submitted for validation: {_project_title(project)}",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:submitted:validators",
            )
        elif was_needs_revision:
            profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
            review = profile_data.get("validator_review")
            if isinstance(review, dict):
                next_review = dict(review)
                next_review["review_status"] = "draft"
                next_review["resubmitted_by_id"] = request.user.id
                next_review["resubmitted_at"] = timezone.now().isoformat()
                profile_data["validator_review"] = next_review
                project.profile_data = profile_data
                project.save(update_fields=["profile_data", "updated_at"])
            else:
                project.save(update_fields=["updated_at"])
            _sync_project_collaborators(project, project.profile_data, request.user)
            _log_activity(request, "project_submit", project, {"status": project.status, "revision_resubmitted": True})
            _notify_many(
                _active_validators(),
                event_type="project_revision_resubmitted",
                title="Project revision submitted",
                message=f"{_user_display_name(request.user)} resubmitted {_project_title(project)} for validation.",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:revision-resubmitted:{project.updated_at.isoformat()}",
            )
        return Response({"status": project.status})

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        project = self.get_object()
        role = getattr(request.user, "role", "")
        if role not in ("validator", "admin"):
            raise PermissionDenied("Only validator/admin can validate")

        action_value = (request.data.get("action") or "").lower()
        profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
        if not _is_simplified_profile(profile_data):
            return Response({"detail": "This project does not use the supported simplified form and cannot be reviewed."}, status=400)
        existing_review = profile_data.get("validator_review")
        if isinstance(existing_review, dict):
            existing_status = str(existing_review.get("review_status") or "").lower()
        else:
            existing_status = ""
        if existing_status in ("endorsed", "validated") and action_value not in ("endorse", "validate", "approve"):
            return Response({"detail": "Endorsed reviews are final and cannot be reverted."}, status=400)
        contributor_snapshot = profile_data.get("contributor_snapshot")
        if not isinstance(contributor_snapshot, dict):
            contributor_snapshot = _strip_validator_meta(profile_data)
            profile_data["contributor_snapshot"] = deepcopy(contributor_snapshot)

        incoming_edited = request.data.get("edited_profile_data")
        review_baseline = _validator_review_source(profile_data)
        if role == "validator" and incoming_edited is not None and not _validator_answers_unchanged(incoming_edited, review_baseline):
            return Response(
                {"detail": "Contributor answers are read-only for validators. Request revisions instead."},
                status=400,
            )
        if role == "validator" or incoming_edited is None:
            edited_profile = deepcopy(review_baseline)
        else:
            if not isinstance(incoming_edited, dict):
                return Response({"detail": "edited_profile_data must be a JSON object"}, status=400)
            edited_profile = incoming_edited
        if not _is_simplified_profile(edited_profile):
            return Response({"detail": "Only simplified-form project data can be reviewed."}, status=400)

        edited_marker = edited_profile.get("form_schema")
        contributor_marker = contributor_snapshot.get("form_schema")
        versioned_form = (
            isinstance(edited_marker, dict) and edited_marker.get("legacy") is not True
        ) or (
            isinstance(contributor_marker, dict) and contributor_marker.get("legacy") is not True
        )
        if not isinstance(edited_profile.get("form_schema"), dict):
            marker = contributor_snapshot.get("form_schema")
            edited_profile["form_schema"] = deepcopy(marker) if isinstance(marker, dict) else {
                "key": "simplified-rdip", "version": 1, "legacy": True,
            }
        try:
            validate_simplified_answers(
                edited_profile,
                require_complete=versioned_form and action_value in ("endorse", "approve", "validate"),
            )
        except FormSchemaError as exc:
            return Response({"detail": str(exc)}, status=400)

        funding_error = _validate_simplified_funding(edited_profile)
        if funding_error:
            return Response({"detail": funding_error}, status=400)

        if "editable_fields" in request.data:
            editable_fields = _clean_revision_editable_fields(
                request.data.get("editable_fields"),
                contributor_snapshot,
            )
            if editable_fields is None:
                return Response({"detail": "editable_fields must be a list."}, status=400)
        elif isinstance(existing_review, dict) and isinstance(existing_review.get("editable_fields"), list):
            editable_fields = _clean_revision_editable_fields(
                existing_review.get("editable_fields"),
                contributor_snapshot,
            )
        else:
            # Compatibility for an older frontend during a staggered deployment.
            editable_fields = None

        edited_fields = _validator_edited_fields(contributor_snapshot, edited_profile)
        review_notes = str(request.data.get("comment") or request.data.get("notes") or "").strip()
        reviewed_at = timezone.now().isoformat()
        update_fields = ["profile_data", "updated_at"]
        if action_value in ("save_reviewed", "reviewed", "review", "save", "reject") and not review_notes:
            return Response({"detail": "A comment/reason is required for Needs Revision or Rejected decisions."}, status=400)

        warning = ""
        if action_value in ("save_draft", "draft"):
            review_state = "draft"
            project.validated = False
            event = "validator_draft"
        elif action_value in ("save_reviewed", "reviewed", "review", "save"):
            if editable_fields == []:
                return Response(
                    {"detail": "Select at least one field the contributor may revise."},
                    status=400,
                )
            review_state = "reviewed"
            project.validated = False
            event = "validator_reviewed"
        elif action_value in ("endorse", "approve", "validate"):
            if project.priority_analysis_eligible and not has_matching_confirmation(project, edited_profile):
                return Response(
                    {
                        "detail": (
                            "Run and confirm the AI-assisted priority analysis for the current validator copy "
                            "before endorsing this project."
                        )
                    },
                    status=400,
                )
            review_state = "endorsed"
            project.status = "completed"
            project.validated = True
            update_fields.extend(["status", "validated"])
            event = "validator_endorsed"
            if existing_status not in ("reviewed", "endorsed", "validated"):
                warning = "Endorsed without a prior reviewed state."
        elif action_value == "reject":
            review_state = "rejected"
            project.status = "planning"
            project.validated = False
            update_fields.extend(["status", "validated"])
            event = "project_reject"
        else:
            return Response({"detail": "action must be save_draft/save_reviewed/endorse/reject"}, status=400)

        next_review = {
            "review_status": review_state,
            "reviewed_by_id": request.user.id,
            "reviewed_by_username": request.user.username,
            "reviewed_at": reviewed_at,
            "review_notes": review_notes,
            "edited": len(edited_fields) > 0,
            "edited_fields_count": len(edited_fields),
            "edited_fields": edited_fields[:300],
            "working_copy": edited_profile,
        }
        if editable_fields is not None:
            next_review["editable_fields"] = editable_fields
        profile_data["validator_review"] = next_review
        # Refresh deterministic public summary from the contributor-visible simplified form.
        try:
            sf = profile_data.get("simplified_form")
            if isinstance(sf, dict):
                profile_data["public_summary"] = build_public_summary(sf)
        except Exception:
            pass
        project.profile_data = profile_data
        project.save(update_fields=list(dict.fromkeys(update_fields)))
        if review_state == "endorsed":
            _ensure_public_revision(project, request.user)
        details = {
            "status": project.status,
            "review_status": review_state,
            "edited": len(edited_fields) > 0,
            "edited_fields_count": len(edited_fields),
            "editable_fields_count": len(editable_fields or []),
        }
        if warning:
            details["warning"] = warning
        _log_activity(request, event, project, details)
        if role == "validator" and review_state == "draft":
            _notify_user(
                request.user,
                event_type="validator_review_draft_saved",
                title="Review draft saved",
                message=f"Your review draft was saved: {_project_title(project)}",
                project=project,
                actor=request.user,
            )
            _notify_many(
                _admins(),
                event_type="validator_review_draft_saved_admin",
                title="Validator review draft saved",
                message=f"{_user_display_name(request.user)} saved a review draft for {_project_title(project)}.",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:validator-review-draft:{reviewed_at}",
            )
        elif role == "validator" and review_state == "endorsed":
            _notify_user(
                request.user,
                event_type="validator_project_validated",
                title="Project validated",
                message=f"You validated and endorsed: {_project_title(project)}",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:validator:{request.user.id}:validated",
            )
        if review_state == "reviewed":
            _notify_many(
                _project_employee_recipients(project),
                event_type="project_needs_revision",
                title="Project needs revision",
                message=review_notes or "Your project submission requires additional information.",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:needs-revision:{reviewed_at}",
            )
        elif review_state == "endorsed" and existing_status not in ("endorsed", "validated"):
            _notify_many(
                _admins(),
                event_type="project_endorsed_admin",
                title="Project validated and endorsed",
                message=f"{_user_display_name(request.user)} validated and endorsed {_project_title(project)}.",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:endorsed:admins",
            )
            _notify_many(
                _project_employee_recipients(project),
                event_type="project_validated",
                title="Project validated and endorsed",
                message=f"Your project submission has been validated and endorsed: {_project_title(project)}",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:validated",
            )
        elif review_state == "rejected" and existing_status != "rejected":
            _notify_many(
                _project_employee_recipients(project),
                event_type="project_rejected",
                title="Project rejected",
                message=review_notes or "Your project submission has been rejected.",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:rejected",
            )
        return Response(
            {
                "status": project.status,
                "review_status": review_state,
                "edited": len(edited_fields) > 0,
                "edited_fields_count": len(edited_fields),
                "editable_fields": editable_fields or [],
                "reviewed_at": reviewed_at,
                "warning": warning,
            }
        )

    @action(detail=True, methods=["get"], url_path="priority-analysis")
    def priority_analysis(self, request, pk=None):
        project = self.get_object()
        role = getattr(request.user, "role", "")
        if role not in ("validator", "admin"):
            raise PermissionDenied("Only validator/admin can view priority analysis.")
        analyses = list(
            project.priority_analyses.select_related("validator", "rule_set").prefetch_related(
                "confirmations__validator"
            )
        )
        for index, analysis in enumerate(analyses):
            ensure_analysis_guidance(analysis)
            if index == 0:
                from ai_engine.services import ensure_learning_assessment
                analysis._current_learning_assessment = ensure_learning_assessment(analysis)
        serializer = ProjectPriorityAnalysisSerializer(analyses, many=True)
        return Response(
            {
                "eligible": bool(project.priority_analysis_eligible),
                "analyses": serializer.data,
            }
        )

    @action(detail=True, methods=["post"], url_path="priority-analysis/run")
    def priority_analysis_run(self, request, pk=None):
        project = self.get_object()
        if getattr(request.user, "role", "") != "validator":
            raise PermissionDenied("Only validators can run priority analysis.")
        if not project.priority_analysis_eligible:
            return Response({"detail": "Legacy projects are excluded from priority analysis enforcement."}, status=400)
        if not _is_simplified_profile(project.profile_data):
            return Response({"detail": "Priority analysis is available only for simplified-form projects."}, status=400)
        if project.status not in ("proposed", "planning"):
            return Response({"detail": "Priority analysis is available before endorsement only."}, status=400)
        document_assessment = serialize_document_assessment(project)
        if document_assessment.get("status") == "missing":
            return Response(
                {"detail": "Upload the required supporting documents before running AI Assistant analysis.", "document_assessment": document_assessment},
                status=409,
            )
        if document_assessment.get("status") == "pending":
            assessment, _created = ensure_queued_assessment(project)
            if assessment and not dispatch_document_assessment(assessment.id):
                assessment.status = "unavailable"
                assessment.error_message = "The document assessment worker is unavailable. Retry when it is online."
                assessment.save(update_fields=["status", "error_message", "updated_at"])
            document_assessment = serialize_document_assessment(project)
        if document_assessment.get("status") in {"queued", "processing"}:
            return Response(
                {
                    "processing": True,
                    "detail": "The AI Assistant is reading the supporting documents before scoring the project.",
                    "document_assessment": document_assessment,
                },
                status=202,
            )
        if document_assessment.get("status") == "unavailable" and not document_assessment.get("id"):
            return Response(
                {
                    "detail": "Retry or replace the supporting documents that could not be prepared before running AI Assistant analysis.",
                    "document_assessment": document_assessment,
                },
                status=409,
            )

        incoming_snapshot = request.data.get("edited_profile_data")
        if incoming_snapshot is not None and not isinstance(incoming_snapshot, dict):
            return Response({"detail": "edited_profile_data must be a JSON object."}, status=400)
        profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
        snapshot = _validator_review_source(profile_data)
        if incoming_snapshot is not None and not _validator_answers_unchanged(incoming_snapshot, snapshot):
            return Response(
                {"detail": "Contributor answers are read-only for validators. Request revisions instead."},
                status=400,
            )
        snapshot = deepcopy(snapshot)
        supplements = request.data.get("supplements")
        if not isinstance(supplements, dict):
            supplements = {}
        supplements = dict(supplements)
        supplements.pop("supporting_document_evidence", None)
        if document_assessment.get("status") in {"pass", "fail"}:
            supplements["supporting_document_evidence"] = {
                "status": document_assessment.get("status"),
                "collective_sufficient": document_assessment.get("collective_sufficient"),
                "summary": document_assessment.get("summary"),
                "files": document_assessment.get("document_results") or [],
            }
        analysis, reused = analyze_project(project, request.user, snapshot, supplements)
        ai_provider = (
            analysis.suggested_scores.get("ai_provider")
            if isinstance(analysis.suggested_scores, dict)
            and isinstance(analysis.suggested_scores.get("ai_provider"), dict)
            else {}
        )
        _log_activity(
            request,
            "priority_analysis_reused" if reused else "priority_analysis_run",
            project,
            {
                "analysis_id": analysis.id,
                "score": float(analysis.base_score),
                "priority": analysis.suggested_priority,
                "reused": reused,
                "ai_provider": ai_provider.get("name") or "local",
                "ai_model": ai_provider.get("model") or "",
                "used_backup_model": bool(ai_provider.get("used_backup")),
                "ai_mode": ai_provider.get("mode") or "",
            },
        )
        return Response(
            {
                "eligible": True,
                "reused": reused,
                "analysis": ProjectPriorityAnalysisSerializer(analysis).data,
            }
        )

    @action(
        detail=True,
        methods=["post"],
        url_path=r"priority-analysis/(?P<analysis_id>\d+)/confirm",
    )
    def priority_analysis_confirm(self, request, pk=None, analysis_id=None):
        project = self.get_object()
        if getattr(request.user, "role", "") != "validator":
            raise PermissionDenied("Only validators can confirm priority analysis.")
        profile = project.profile_data if isinstance(project.profile_data, dict) else {}
        review = profile.get("validator_review") if isinstance(profile.get("validator_review"), dict) else {}
        if project.status not in ("proposed", "planning") or str(review.get("review_status") or "").lower() in ("endorsed", "validated"):
            return Response({"detail": "Priority decisions are locked after endorsement."}, status=400)
        try:
            analysis = project.priority_analyses.get(pk=analysis_id)
        except ProjectPriorityAnalysis.DoesNotExist:
            return Response({"detail": "Priority analysis not found."}, status=404)
        previous_confirmation = _latest_project_confirmation(project)
        previous_group = _priority_group(previous_confirmation.final_priority) if previous_confirmation else ""
        try:
            confirmation = confirm_analysis(
                analysis,
                request.user,
                request.data.get("adjusted_scores"),
                str(request.data.get("final_priority") or analysis.suggested_priority),
                request.data.get("override_rationale"),
                request.data.get("confirmed_flags"),
                request.data.get("document_override") is True,
                request.data.get("document_override_rationale"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        event = (
            "priority_analysis_overridden"
            if confirmation.final_priority != analysis.suggested_priority
            else "priority_analysis_confirmed"
        )
        _log_activity(
            request,
            event,
            project,
            {
                "analysis_id": analysis.id,
                "suggested_priority": analysis.suggested_priority,
                "final_priority": confirmation.final_priority,
                "score": float(analysis.base_score),
            },
        )
        if confirmation.document_override:
            _log_activity(
                request,
                "document_assessment_overridden",
                project,
                {
                    "analysis_id": analysis.id,
                    "assessment_id": confirmation.document_assessment_id,
                    "rationale": confirmation.document_override_rationale,
                },
            )
        next_group = _priority_group(confirmation.final_priority)
        if next_group and next_group != previous_group:
            label = _priority_label(confirmation.final_priority)
            _notify_many(
                _project_employee_recipients(project),
                event_type=f"classification_{next_group}",
                title=f"Project classified as {label}",
                message=f"Your project has been classified as a {label.lower()} project.",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:priority-confirmation:{confirmation.id}",
            )
        return Response(ProjectPriorityAnalysisSerializer(analysis).data)

    @action(detail=True, methods=["post"], url_path="public-summary")
    def public_summary(self, request, pk=None):
        project = self.get_object()
        role = getattr(request.user, "role", "")
        if role not in ("admin", "validator"):
            raise PermissionDenied("Only admin/validator can set public summary override.")
        text = str(request.data.get("text") or "").strip()
        profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
        if not isinstance(profile_data, dict):
            profile_data = {}
        if text:
            profile_data["public_summary_override"] = {
                "updated_at": timezone.now().isoformat(),
                "updated_by": _user_display_name(request.user),
                "text": text,
            }
        else:
            profile_data.pop("public_summary_override", None)
        # Ensure base summary exists as well.
        try:
            sf = profile_data.get("simplified_form")
            if isinstance(sf, dict):
                profile_data["public_summary"] = build_public_summary(sf)
        except Exception:
            pass
        project.profile_data = profile_data
        project.save(update_fields=["profile_data", "updated_at"])
        _log_activity(request, "public_summary_overridden", project, {"has_override": bool(text)})
        return Response(
            {
                "has_override": bool(text),
                "public_summary_override": profile_data.get("public_summary_override") if text else None,
            }
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can archive")
        if request.data.get("confirm_archive") is not True:
            return Response({"detail": "Archive confirmation is required."}, status=400)
        with transaction.atomic():
            project = Project.objects.select_for_update().get(pk=self.get_object().pk)
            profile = project.profile_data if isinstance(project.profile_data, dict) else {}
            simplified = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
            implementation_status = canonical_implementation_status(simplified.get("status")) if simplified else ""
            expected = request.data.get("expected_implementation_status")
            if expected is not None and str(expected).strip() != implementation_status:
                return Response({
                    "detail": "Project status changed. Review the archive warning again.",
                    "implementation_status": implementation_status,
                }, status=409)
            archived, reason = _archive_project(request, project)
            if not archived:
                return Response({"detail": reason}, status=409)
        return Response({"status": "archived"})

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can restore projects")
        project = self.get_object()
        if not project.archived:
            return Response({"detail": "Project is not archived."}, status=400)
        project.archived = False
        project.is_active = True
        project.save(update_fields=["archived", "is_active", "updated_at"])
        _log_activity(request, "project_unarchive", project, {"archived": False})
        return Response({"status": "restored"})

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        project = self.get_object()
        role = getattr(request.user, "role", "")
        if role not in ("admin", "validator", "staff", "employee"):
            raise PermissionDenied("Unauthorized")
        if role in ("staff", "employee"):
            primary = _is_primary_agency_contributor(request.user, project)
            collaborator = _is_collaborating_agency_contributor(request.user, project)
            if not primary and not collaborator:
                raise PermissionDenied("You do not have access to these project comments.")
            if request.method.lower() == "post" and not primary:
                raise PermissionDenied("Collaborating agencies have read-only access and cannot post comments.")

        if request.method.lower() == "get":
            qs = ProjectComment.objects.filter(project=project).select_related("user")
            serializer = ProjectCommentSerializer(qs, many=True)
            return Response(serializer.data)

        comment_text = str(request.data.get("comment") or "").strip()
        if not comment_text:
            return Response({"detail": "Comment is required."}, status=400)
        comment = ProjectComment.objects.create(
            project=project,
            user=request.user,
            role=role,
            agency=request.user.agency or "",
            comment=comment_text,
        )
        _log_activity(request, "project_comment", project, {"comment": comment_text[:160]})
        if role == "validator":
            _notify_many(
                _project_employee_recipients(project),
                event_type="project_message",
                title="New project message",
                message=comment_text[:500],
                project=project,
                actor=request.user,
                comment=comment,
                dedupe_key=f"comment:{comment.id}:employee",
            )
        elif role in ("staff", "employee"):
            _notify_many(
                _active_validators(),
                event_type="project_message",
                title="Employee replied on project",
                message=f"{_user_display_name(request.user)} replied on {_project_title(project)}.",
                project=project,
                actor=request.user,
                comment=comment,
                dedupe_key=f"comment:{comment.id}:validators",
            )
        elif role == "admin":
            recipients = list(_project_employee_recipients(project)) + list(_active_validators())
            _notify_many(
                recipients,
                event_type="project_message",
                title="Admin project message",
                message=comment_text[:500],
                project=project,
                actor=request.user,
                comment=comment,
                dedupe_key=f"comment:{comment.id}:admin",
            )
        serializer = ProjectCommentSerializer(comment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can delete projects")
        project = self.get_object()
        _log_activity(
            request, "project_delete", project,
            {"project_id": project.id, "project_title": _project_title(project)},
        )
        return super().destroy(request, *args, **kwargs)


class ProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()

    def _contributor_write_error(self, request, project=None):
        if getattr(request.user, "role", "") not in ("staff", "employee"):
            return None
        profile_data = request.data.get("profile_data")
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except (TypeError, ValueError):
                profile_data = None
        return _validate_contributor_simplified_write(
            request.user, profile_data, project=project,
            existing_profile=project.profile_data if project is not None else None,
            incoming_agency=request.data.get("agency", project.agency if project is not None else None),
        )

    def create(self, request, *args, **kwargs):
        error = self._contributor_write_error(request)
        if error:
            return Response({"detail": error}, status=400)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") == "validator":
            raise PermissionDenied("Validators cannot edit contributor project fields. Use review actions instead.")
        project = self.get_object()
        error = self._contributor_write_error(request, project)
        if error:
            return Response({"detail": error}, status=400)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") == "validator":
            raise PermissionDenied("Validators cannot edit contributor project fields. Use review actions instead.")
        project = self.get_object()
        error = self._contributor_write_error(request, project)
        if error:
            return Response({"detail": error}, status=400)
        return super().partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        _log_activity(self.request, "project_create", serializer.instance, {"source": "general_api"})

    def perform_update(self, serializer):
        super().perform_update(serializer)
        _log_activity(self.request, "project_update", serializer.instance, {"source": "general_api"})


class EmployeeProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()
    permission_classes = [IsAuthenticated, EmployeeRolePermission, ProjectPermission]

    def get_queryset(self):
        # The scope is an OR over plain columns, so it cannot create duplicate rows;
        # avoid DISTINCT's extra sort/hash step on large contributor lists.
        qs = Project.objects.filter(_contributor_project_scope(self.request.user), archived=False).distinct().order_by("-created_at")
        workflow = self.request.query_params.get("workflow") or self.request.query_params.get("status")
        qs = _filter_projects_for_workflow(qs, workflow).order_by("-created_at")
        return _project_list_queryset(
            qs, self.request,
            prefetch_priority=getattr(self, "action", "") == "list",
        )

    def _ensure_encoding_open(self):
        state = _resolve_encoding_window_state()
        if not state["is_open"]:
            raise PermissionDenied(state["message"])

    def _ensure_progress_update_open(self):
        state = _resolve_progress_update_window_state()
        if not state["is_open"]:
            raise PermissionDenied(state["message"])

    def _ensure_project_write_open(self, project):
        if _project_needs_revision(project):
            return
        self._ensure_encoding_open()

    def _ensure_mutable_project(self, project):
        if project.status == "planning" or _project_needs_revision(project):
            return
        raise PermissionDenied("Submitted/validated projects are view-only for contributors.")

    def _revision_access_violation(self, project, data, incoming_profile):
        if not _project_needs_revision(project):
            return []
        existing_profile = project.profile_data if isinstance(project.profile_data, dict) else {}
        review = existing_profile.get("validator_review")
        if not isinstance(review, dict) or "editable_fields" not in review:
            return []
        editable_fields = review.get("editable_fields")
        if not isinstance(editable_fields, list):
            editable_fields = []
        contributor_snapshot = existing_profile.get("contributor_snapshot")
        if not isinstance(contributor_snapshot, dict):
            contributor_snapshot = _strip_validator_meta(existing_profile)
        blocked = _restricted_revision_changes(
            contributor_snapshot,
            incoming_profile if isinstance(incoming_profile, dict) else contributor_snapshot,
            editable_fields,
        )
        blocked.extend(
            _restricted_project_display_changes(
                project,
                data,
                editable_fields,
                contributor_snapshot,
            )
        )
        return list(dict.fromkeys(blocked))

    def create(self, request, *args, **kwargs):
        self._ensure_encoding_open()
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        changed_fields = []
        profile_data = data.get("profile_data")
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except Exception:
                profile_data = None
        if isinstance(profile_data, dict):
            # Initial save should establish the baseline, not mark every non-empty field as "edited".
            profile_data.pop("simplified_form_meta", None)
            # Generate a deterministic public summary for reviewers/public dashboard.
            try:
                simplified = profile_data.get("simplified_form")
                if isinstance(simplified, dict):
                    profile_data["public_summary"] = build_public_summary(simplified)
            except Exception:
                pass
            data["profile_data"] = profile_data
            changes = []
        else:
            changes = []
        contributor_error = _validate_contributor_simplified_write(
            request.user, profile_data, incoming_agency=data.get("agency")
        )
        if contributor_error:
            return Response({"detail": contributor_error}, status=400)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        project = serializer.instance
        _log_activity(
            request,
            "project_create",
            project,
            {
                "status": serializer.data.get("status"),
                "edited_fields_count": len(changed_fields),
                "changed_fields": changed_fields[:30],
                "changes": changes[:30],
            },
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        self._ensure_project_write_open(project)
        self._ensure_mutable_project(project)
        was_needs_revision = _project_needs_revision(project)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        changed_fields = []
        profile_data = data.get("profile_data")
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except Exception:
                profile_data = None
        contributor_error = _validate_contributor_simplified_write(
            request.user, profile_data, project=project, existing_profile=project.profile_data,
            incoming_agency=data.get("agency", project.agency),
        )
        if contributor_error:
            return Response({"detail": contributor_error}, status=400)
        blocked_fields = self._revision_access_violation(project, data, profile_data)
        if blocked_fields:
            return Response(
                {
                    "detail": "Only fields selected by the validator can be changed.",
                    "restricted_fields": blocked_fields,
                },
                status=400,
            )
        if isinstance(profile_data, dict):
            updated_profile, changed_fields, changes = _apply_simplified_meta(
                profile_data, project.profile_data or {}, request.user
            )
            if was_needs_revision:
                existing_profile = project.profile_data if isinstance(project.profile_data, dict) else {}
                existing_review = existing_profile.get("validator_review")
                if isinstance(existing_review, dict):
                    updated_profile["validator_review"] = existing_review
                updated_profile["contributor_snapshot"] = _strip_validator_meta(updated_profile)
                data["status"] = "proposed"
            data["profile_data"] = updated_profile
        else:
            changes = []
        serializer = self.get_serializer(project, data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        _log_activity(
            request,
            "project_update",
            project,
            {
                "status": serializer.data.get("status") if hasattr(serializer, "data") else "",
                "edited_fields_count": len(changed_fields),
                "changed_fields": changed_fields[:30],
                "changes": changes[:30],
            },
        )
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        project = self.get_object()
        self._ensure_project_write_open(project)
        self._ensure_mutable_project(project)
        was_needs_revision = _project_needs_revision(project)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        changed_fields = []
        profile_data = data.get("profile_data")
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except Exception:
                profile_data = None
        contributor_error = _validate_contributor_simplified_write(
            request.user, profile_data, project=project, existing_profile=project.profile_data,
            incoming_agency=data.get("agency", project.agency),
        )
        if contributor_error:
            return Response({"detail": contributor_error}, status=400)
        blocked_fields = self._revision_access_violation(project, data, profile_data)
        if blocked_fields:
            return Response(
                {
                    "detail": "Only fields selected by the validator can be changed.",
                    "restricted_fields": blocked_fields,
                },
                status=400,
            )
        if isinstance(profile_data, dict):
            updated_profile, changed_fields, changes = _apply_simplified_meta(
                profile_data, project.profile_data or {}, request.user
            )
            if was_needs_revision:
                existing_profile = project.profile_data if isinstance(project.profile_data, dict) else {}
                existing_review = existing_profile.get("validator_review")
                if isinstance(existing_review, dict):
                    updated_profile["validator_review"] = existing_review
                updated_profile["contributor_snapshot"] = _strip_validator_meta(updated_profile)
                data["status"] = "proposed"
            data["profile_data"] = updated_profile
        else:
            changes = []
        serializer = self.get_serializer(project, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        _log_activity(
            request,
            "project_update",
            project,
            {
                "partial": True,
                "edited_fields_count": len(changed_fields),
                "changed_fields": changed_fields[:30],
                "changes": changes[:30],
            },
        )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied("Only admin can delete projects")

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        project = self.get_object()
        if project.status == "proposed" and not _project_needs_revision(project):
            return Response({"status": project.status})
        self._ensure_project_write_open(project)
        self._ensure_mutable_project(project)
        return super().submit(request, pk=pk)

    @action(detail=True, methods=["post"], url_path="start-update")
    def start_update(self, request, pk=None):
        self._ensure_progress_update_open()
        project = self.get_object()
        if not _is_simplified_profile(project.profile_data):
            return Response({"detail": "Progress updates are available only for simplified-form projects."}, status=400)
        if not project.validated:
            return Response({"detail": "Only endorsed public projects can receive progress updates."}, status=400)
        if _is_completed_rdip_project(project):
            return Response({"detail": "Completed projects are read-only for progress updates."}, status=400)

        active = project.revisions.filter(
            revision_type="progress_update",
            state__in=["draft", "submitted", "validator_draft", "reviewed"],
        ).order_by("-updated_at").first()
        source_profile = active.profile_data_snapshot if active and active.state == "draft" else project.profile_data
        migration = analyze_profile_migration(source_profile)
        if not migration.get("compatible"):
            issues = migration.get("issues") or ["The saved form cannot be migrated safely."]
            issue_key = hashlib.sha256("|".join(issues).encode("utf-8")).hexdigest()[:16]
            _notify_many(
                _admins(),
                event_type="project_form_migration_blocked",
                title="Project form needs manual migration review",
                message=f"{_project_title(project)} could not be prepared for updating: {'; '.join(issues)}",
                project=project,
                actor=request.user,
                dedupe_key=f"project:{project.id}:form-migration-blocked:{issue_key}",
                link_path="/admin/projects/update-forms",
            )
            return Response({
                "detail": "This project cannot be opened for updating until an administrator resolves its form migration.",
                "code": "form_migration_required",
                "issues": issues,
            }, status=409)
        if migration.get("already_current"):
            if active:
                return Response(ProjectRevisionSerializer(active).data)
        else:
            prepared = prepare_project_migration(project, user=request.user, trigger="contributor_update")
            if prepared.get("status") == "prepared" and prepared.get("revision") is not None:
                revision = prepared["revision"]
                existing_draft_reused = active is not None and active.id == revision.id
                _log_activity(request, "project_revision_updated" if existing_draft_reused else "project_revision_created", project, {
                    "operation": "automatic_form_migration",
                    "revision_id": revision.id,
                    "revision_number": revision.revision_number,
                    "source_version": prepared.get("source_version"),
                    "target_version": prepared.get("target_version"),
                    "attention_fields": prepared.get("attention_fields") or [],
                })
                if not existing_draft_reused:
                    _notify_many(
                        _admins(),
                        event_type="contributor_progress_draft_created",
                        title="Contributor progress draft created",
                        message=(
                            f"{_user_display_name(request.user)} created progress update "
                            f"v{revision.revision_number} for {_project_title(project)}."
                        ),
                        project=project,
                        actor=request.user,
                        dedupe_key=f"project:{project.id}:revision:{revision.id}:contributor-draft:admins",
                        link_path=_revision_review_link(revision, "admin"),
                    )
                return Response(ProjectRevisionSerializer(revision).data, status=200 if existing_draft_reused else 201)
            if prepared.get("status") not in {"current", "migrated"}:
                issues = prepared.get("issues") or [prepared.get("reason") or "The form cannot be migrated safely."]
                issue_key = hashlib.sha256("|".join(issues).encode("utf-8")).hexdigest()[:16]
                _notify_many(
                    _admins(),
                    event_type="project_form_migration_blocked",
                    title="Project form needs manual migration review",
                    message=f"{_project_title(project)} could not be prepared for updating: {'; '.join(issues)}",
                    project=project,
                    actor=request.user,
                    dedupe_key=f"project:{project.id}:form-migration-blocked:{issue_key}",
                    link_path="/admin/projects/update-forms",
                )
                return Response({
                    "detail": "This project cannot be opened for updating until an administrator resolves its form migration.",
                    "code": "form_migration_required",
                    "issues": issues,
                }, status=409)

        current = _ensure_public_revision(project, request.user)
        base_profile = deepcopy(current.profile_data_snapshot if current else project.profile_data)
        if not isinstance(base_profile, dict):
            base_profile = {}
        base_profile, _ = _upgrade_profile_form_marker(base_profile, project.profile_data)
        revision = ProjectRevision.objects.create(
            project=project,
            revision_number=_next_revision_number(project),
            revision_type="progress_update",
            state="draft",
            profile_data_snapshot=base_profile,
            public_summary_snapshot=_project_public_summary(base_profile),
            changed_fields=[],
            created_by=request.user,
        )
        _log_activity(
            request,
            "project_revision_created",
            project,
            {"revision_id": revision.id, "revision_number": revision.revision_number, "revision_type": "progress_update"},
        )
        _notify_many(
            _admins(),
            event_type="contributor_progress_draft_created",
            title="Contributor progress draft created",
            message=(
                f"{_user_display_name(request.user)} created progress update "
                f"v{revision.revision_number} for {_project_title(project)}."
            ),
            project=project,
            actor=request.user,
            dedupe_key=f"project:{project.id}:revision:{revision.id}:contributor-draft:admins",
            link_path=_revision_review_link(revision, "admin"),
        )
        return Response(ProjectRevisionSerializer(revision).data, status=201)


class ProjectRevisionViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectRevisionSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if getattr(self, "action", "") == "list" and self.request.query_params.get("view") == "summary":
            return ProjectRevisionSummarySerializer
        return ProjectRevisionSerializer

    def get_queryset(self):
        role = getattr(self.request.user, "role", "")
        if self.action == "list" and self.request.query_params.get("view") == "summary":
            qs = ProjectRevision.objects.select_related("project", "created_by", "submitted_by").only(
                "id", "project_id", "project__name", "project__agency", "revision_number",
                "revision_type", "state", "profile_data_snapshot", "created_by_id",
                "created_by__username", "created_by__first_name",
                "created_by__last_name", "submitted_by_id", "submitted_by__username",
                "submitted_by__first_name", "submitted_by__last_name",
                "form_migration", "updated_at",
            ).order_by("-updated_at")
        else:
            qs = ProjectRevision.objects.select_related(
                "project",
                "created_by",
                "submitted_by",
                "reviewed_by",
                "endorsed_by",
            ).order_by("-updated_at")
        if self.action == "list":
            qs = qs.filter(project__archived=False)
        if role == "admin":
            return qs
        if role == "validator":
            # Contributor-created drafts are never reviewable. Apply this to
            # object lookups too, not only the queue list, so guessing a revision
            # URL cannot expose an unsubmitted snapshot.
            qs = qs.exclude(state="draft")
            scope = (self.request.query_params.get("scope") or "queue").strip().lower()
            if scope == "history":
                return qs.filter(state__in=["reviewed", "endorsed", "rejected", "superseded"])
            return qs.filter(state__in=["submitted", "validator_draft", "reviewed"])
        if role in ("staff", "employee"):
            agency = _normalize_account_agency(self.request.user.agency)
            if not agency:
                return qs.none()
            return qs.filter(
                Q(project__primary_agency__code__iexact=agency)
                | Q(project__primary_agency__isnull=True, project__agency__iexact=agency)
            )
        return qs.none()

    def _same_agency_or_admin_validator(self, revision):
        role = getattr(self.request.user, "role", "")
        if role in ("admin", "validator"):
            return True
        return _is_primary_agency_contributor(self.request.user, revision.project)

    def get_object(self):
        obj = super().get_object()
        if not self._same_agency_or_admin_validator(obj):
            raise PermissionDenied("You do not have access to this revision.")
        return obj

    def _ensure_progress_update_open(self):
        state = _resolve_progress_update_window_state()
        if not state["is_open"]:
            raise PermissionDenied(state["message"])

    def _ensure_contributor_editable(self, revision):
        if getattr(self.request.user, "role", "") not in ("staff", "employee"):
            raise PermissionDenied("Only contributors can edit progress update drafts.")
        if not _is_primary_agency_contributor(self.request.user, revision.project):
            raise PermissionDenied("Only contributors from the primary agency can edit this progress update.")
        profile = revision.profile_data_snapshot if isinstance(revision.profile_data_snapshot, dict) else {}
        access = profile.get("validator_revision_access")
        revision_requested = (
            revision.state == "reviewed"
            and isinstance(access, dict)
            and isinstance(access.get("editable_fields"), list)
            and bool(access.get("editable_fields"))
        )
        if revision.revision_type != "progress_update" or (
            revision.state != "draft" and not revision_requested
        ):
            raise PermissionDenied("Only draft or validator-returned progress updates can be edited by contributors.")
        if _is_completed_rdip_project(revision.project):
            raise PermissionDenied("Completed projects are read-only for progress updates.")
        self._ensure_progress_update_open()

    def update(self, request, *args, **kwargs):
        revision = self.get_object()
        self._ensure_contributor_editable(revision)
        profile_data = request.data.get("profile_data") or request.data.get("profile_data_snapshot")
        if not isinstance(profile_data, dict):
            return Response({"detail": "profile_data is required."}, status=400)
        if not _is_simplified_profile(profile_data):
            return Response({"detail": "Only simplified-form project updates are supported."}, status=400)
        funding_error = _validate_simplified_funding(profile_data)
        if funding_error:
            return Response({"detail": funding_error}, status=400)
        existing_profile = revision.profile_data_snapshot if isinstance(revision.profile_data_snapshot, dict) else {}
        contributor_error = _validate_contributor_simplified_write(
            request.user, profile_data, project=revision.project, existing_profile=existing_profile,
            incoming_agency=revision.project.agency,
        )
        if contributor_error:
            return Response({"detail": contributor_error}, status=400)
        access = existing_profile.get("validator_revision_access")
        if revision.state == "reviewed" and isinstance(access, dict):
            editable_fields = access.get("editable_fields")
            if not isinstance(editable_fields, list):
                editable_fields = []
            blocked_fields = _restricted_revision_changes(
                existing_profile,
                profile_data,
                editable_fields,
            )
            if blocked_fields:
                return Response(
                    {
                        "detail": "Only fields selected by the validator can be changed.",
                        "restricted_fields": blocked_fields,
                    },
                    status=400,
                )
        updated_profile, changed_fields, changes = _apply_simplified_meta(
            profile_data,
            existing_profile,
            request.user,
        )
        if isinstance(access, dict):
            updated_profile["validator_revision_access"] = deepcopy(access)
        current = _ensure_public_revision(revision.project, request.user)
        base_profile = current.profile_data_snapshot if current else revision.project.profile_data
        revision.profile_data_snapshot = updated_profile
        revision.public_summary_snapshot = _project_public_summary(updated_profile)
        revision.changed_fields = _safe_revision_changes(base_profile, updated_profile)
        revision.save(update_fields=["profile_data_snapshot", "public_summary_snapshot", "changed_fields", "updated_at"])
        _log_activity(
            request,
            "project_revision_updated",
            revision.project,
            {
                "revision_id": revision.id,
                "revision_number": revision.revision_number,
                "edited_fields_count": len(changed_fields),
                "changed_fields": changed_fields[:30],
                "changes": changes[:30],
            },
        )
        return Response(ProjectRevisionSerializer(revision).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Start progress updates from a project."}, status=405)

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Revision deletion is disabled for audit safety."}, status=405)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        revision = self.get_object()
        self._ensure_contributor_editable(revision)
        if not _is_simplified_profile(revision.profile_data_snapshot):
            return Response({"detail": "Only simplified-form progress updates can be submitted."}, status=400)
        revision_form_marker = (
            revision.profile_data_snapshot.get("form_schema")
            if isinstance(revision.profile_data_snapshot, dict)
            else None
        )
        versioned_form = isinstance(revision_form_marker, dict) and revision_form_marker.get("legacy") is not True
        if (
            isinstance(revision.profile_data_snapshot, dict)
            and isinstance(revision.profile_data_snapshot.get("simplified_form"), dict)
            and not isinstance(revision.profile_data_snapshot.get("form_schema"), dict)
        ):
            revision.profile_data_snapshot["form_schema"] = {
                "key": "simplified-rdip", "version": 1, "legacy": True,
            }
        try:
            validate_simplified_answers(revision.profile_data_snapshot, require_complete=versioned_form)
        except FormSchemaError as exc:
            return Response({"detail": str(exc)}, status=400)
        if not revision.changed_fields:
            current = _ensure_public_revision(revision.project, request.user)
            base_profile = current.profile_data_snapshot if current else revision.project.profile_data
            revision.changed_fields = _safe_revision_changes(base_profile, revision.profile_data_snapshot)
        revision.state = "submitted"
        revision.submitted_by = request.user
        revision.submitted_at = timezone.now()
        revision.save(update_fields=["state", "submitted_by", "submitted_at", "changed_fields", "updated_at"])
        _log_activity(
            request,
            "project_revision_submitted",
            revision.project,
            {"revision_id": revision.id, "revision_number": revision.revision_number, "changed_fields_count": len(revision.changed_fields or [])},
        )
        _notify_many(
            _active_validators(),
            event_type="progress_update_submitted",
            title="Progress update submitted",
            message=(
                f"{_user_display_name(request.user)} submitted progress update "
                f"v{revision.revision_number} for {_project_title(revision.project)}."
            ),
            project=revision.project,
            actor=request.user,
            dedupe_key=f"project:{revision.project_id}:revision:{revision.id}:submitted:validators",
            link_path=_revision_review_link(revision, "validator"),
        )
        return Response(ProjectRevisionSerializer(revision).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        if getattr(request.user, "role", "") not in ("validator", "admin"):
            raise PermissionDenied("Only validator/admin can review progress updates.")
        revision = self.get_object()
        action_value = (request.data.get("action") or "").strip().lower()
        if revision.state == "endorsed" and action_value not in ("endorse", "validate", "approve"):
            return Response({"detail": "Endorsed revisions are final and cannot be reverted."}, status=400)
        if revision.state not in ("submitted", "validator_draft", "reviewed", "endorsed"):
            return Response({"detail": "Only submitted progress updates can be reviewed."}, status=400)

        saved_profile = revision.profile_data_snapshot if isinstance(revision.profile_data_snapshot, dict) else {}
        if not _is_simplified_profile(saved_profile):
            return Response({"detail": "This revision does not use the supported simplified form and cannot be reviewed."}, status=400)
        edited_profile = request.data.get("edited_profile_data")
        validator_review = getattr(request.user, "role", "") == "validator"
        if validator_review and edited_profile is not None and not _validator_answers_unchanged(edited_profile, saved_profile):
            return Response(
                {"detail": "Contributor answers are read-only for validators. Request revisions instead."},
                status=400,
            )
        if validator_review or edited_profile is None:
            edited_profile = deepcopy(saved_profile)
        if not isinstance(edited_profile, dict):
            return Response({"detail": "edited_profile_data must be a JSON object."}, status=400)
        if not _is_simplified_profile(edited_profile):
            return Response({"detail": "Only simplified-form project data can be reviewed."}, status=400)
        base_marker = revision.profile_data_snapshot.get("form_schema") if isinstance(revision.profile_data_snapshot, dict) else None
        edited_marker = edited_profile.get("form_schema")
        versioned_form = (
            isinstance(edited_marker, dict) and edited_marker.get("legacy") is not True
        ) or (
            isinstance(base_marker, dict) and base_marker.get("legacy") is not True
        )
        if not isinstance(edited_profile.get("form_schema"), dict):
            edited_profile["form_schema"] = deepcopy(base_marker) if isinstance(base_marker, dict) else {
                "key": "simplified-rdip", "version": 1, "legacy": True,
            }
        try:
            validate_simplified_answers(
                edited_profile,
                require_complete=versioned_form and action_value in ("endorse", "validate", "approve"),
            )
        except FormSchemaError as exc:
            return Response({"detail": str(exc)}, status=400)
        funding_error = _validate_simplified_funding(edited_profile)
        if funding_error:
            return Response({"detail": funding_error}, status=400)

        existing_access = (
            revision.profile_data_snapshot.get("validator_revision_access")
            if isinstance(revision.profile_data_snapshot, dict)
            else None
        )
        if "editable_fields" in request.data:
            editable_fields = _clean_revision_editable_fields(
                request.data.get("editable_fields"),
                edited_profile,
            )
            if editable_fields is None:
                return Response({"detail": "editable_fields must be a list."}, status=400)
        elif isinstance(existing_access, dict) and isinstance(existing_access.get("editable_fields"), list):
            editable_fields = _clean_revision_editable_fields(
                existing_access.get("editable_fields"),
                edited_profile,
            )
        else:
            editable_fields = None

        if action_value in ("save_reviewed", "reviewed", "review", "save") and editable_fields == []:
            return Response(
                {"detail": "Select at least one field the contributor may revise."},
                status=400,
            )
        if editable_fields is not None and action_value in (
            "save_draft", "draft", "save_reviewed", "reviewed", "review", "save"
        ):
            edited_profile["validator_revision_access"] = {
                "editable_fields": editable_fields,
                "selected_by_id": request.user.id,
                "selected_at": timezone.now().isoformat(),
            }
        else:
            edited_profile.pop("validator_revision_access", None)

        current = _ensure_public_revision(revision.project, request.user)
        base_profile = current.profile_data_snapshot if current else revision.project.profile_data
        revision.profile_data_snapshot = edited_profile
        revision.public_summary_snapshot = _project_public_summary(edited_profile)
        revision.changed_fields = _safe_revision_changes(base_profile, edited_profile)
        revision.public_note = str(request.data.get("public_note") or request.data.get("notes") or "").strip()
        revision.reviewed_by = request.user
        revision.reviewed_at = timezone.now()

        if action_value in ("save_draft", "draft"):
            revision.state = "validator_draft"
            event = "project_revision_reviewed"
        elif action_value in ("save_reviewed", "reviewed", "review", "save"):
            revision.state = "reviewed"
            event = "project_revision_reviewed"
        elif action_value in ("endorse", "validate", "approve"):
            _apply_revision_to_project(revision, request.user)
            event = "project_revision_endorsed"
        elif action_value == "reject":
            revision.state = "rejected"
            event = "project_revision_rejected"
        else:
            return Response({"detail": "action must be save_draft/save_reviewed/endorse/reject"}, status=400)

        if action_value not in ("endorse", "validate", "approve"):
            revision.save(
                update_fields=[
                    "profile_data_snapshot",
                    "public_summary_snapshot",
                    "changed_fields",
                    "public_note",
                    "reviewed_by",
                    "reviewed_at",
                    "state",
                    "updated_at",
                ]
            )
        _log_activity(
            request,
            event,
            revision.project,
            {
                "revision_id": revision.id,
                "revision_number": revision.revision_number,
                "revision_state": revision.state,
                "changed_fields_count": len(revision.changed_fields or []),
                "editable_fields_count": len(editable_fields or []),
            },
        )
        if getattr(request.user, "role", "") == "validator" and revision.state == "validator_draft":
            _notify_user(
                request.user,
                event_type="validator_progress_draft_saved",
                title="Progress review draft saved",
                message=(
                    f"Your review draft for progress update v{revision.revision_number} was saved: "
                    f"{_project_title(revision.project)}"
                ),
                project=revision.project,
                actor=request.user,
                link_path=_revision_review_link(revision, "validator"),
            )
            _notify_many(
                _admins(),
                event_type="validator_progress_draft_saved_admin",
                title="Validator progress review draft saved",
                message=(
                    f"{_user_display_name(request.user)} saved a review draft for "
                    f"progress update v{revision.revision_number}: {_project_title(revision.project)}"
                ),
                project=revision.project,
                actor=request.user,
                dedupe_key=(
                    f"project:{revision.project_id}:revision:{revision.id}:"
                    f"validator-draft:{revision.reviewed_at.isoformat()}"
                ),
                link_path=_revision_review_link(revision, "admin"),
            )
        elif getattr(request.user, "role", "") == "validator" and revision.state == "endorsed":
            _notify_user(
                request.user,
                event_type="validator_progress_validated",
                title="Progress update validated",
                message=(
                    f"You validated and endorsed progress update v{revision.revision_number}: "
                    f"{_project_title(revision.project)}"
                ),
                project=revision.project,
                actor=request.user,
                dedupe_key=(
                    f"project:{revision.project_id}:revision:{revision.id}:"
                    f"validator:{request.user.id}:validated"
                ),
                link_path=_revision_review_link(revision, "validator"),
            )
        if revision.state == "reviewed":
            _notify_many(
                _project_employee_recipients(revision.project),
                event_type="progress_update_needs_revision",
                title="Progress update needs revision",
                message=revision.public_note or "Your progress update requires additional information.",
                project=revision.project,
                actor=request.user,
                dedupe_key=(
                    f"project:{revision.project_id}:revision:{revision.id}:"
                    f"needs-revision:{revision.reviewed_at.isoformat()}"
                ),
            )
        if revision.state == "endorsed":
            _notify_many(
                _admins(),
                event_type="progress_update_endorsed_admin",
                title="Progress update validated and endorsed",
                message=(
                    f"{_user_display_name(request.user)} validated and endorsed "
                    f"progress update v{revision.revision_number}: {_project_title(revision.project)}"
                ),
                project=revision.project,
                actor=request.user,
                dedupe_key=f"project:{revision.project_id}:revision:{revision.id}:endorsed:admins",
                link_path=_revision_review_link(revision, "admin"),
            )
            _notify_many(
                _project_employee_recipients(revision.project),
                event_type="progress_update_validated",
                title="Progress update validated and endorsed",
                message=(
                    f"Your progress update v{revision.revision_number} was validated and endorsed: "
                    f"{_project_title(revision.project)}"
                ),
                project=revision.project,
                actor=request.user,
                dedupe_key=f"project:{revision.project_id}:revision:{revision.id}:validated:contributor",
            )
        return Response(ProjectRevisionSerializer(revision).data)


class ValidatorProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()
    permission_classes = [IsAuthenticated, ValidatorRolePermission, ProjectPermission]

    def get_queryset(self):
        user = self.request.user
        scope = (self.request.query_params.get("scope") or "").strip().lower()
        if scope == "update_forms" or self.action == "update_form":
            raise PermissionDenied("Contributor-form migration is available only to administrators.")
        # Match both numeric and legacy string IDs. This lets the database filter
        # reviewer-owned records without loading every project's JSON payload into
        # Python on each Validation Queue, history, or detail request.
        reviewed_by_user = (
            Q(profile_data__validator_review__reviewed_by_id=user.id)
            | Q(profile_data__validator_review__reviewed_by_id=str(user.id))
        )
        visible_project_states = ("draft", "reviewed", "endorsed", "validated", "rejected")

        if self.action == "list":
            if scope == "history":
                qs = Project.objects.filter(archived=False).exclude(status="planning").filter(
                    reviewed_by_user,
                    profile_data__validator_review__review_status__in=("reviewed", "endorsed", "validated", "rejected"),
                ).order_by("-updated_at")
                workflow = self.request.query_params.get("workflow") or self.request.query_params.get("status")
                return _project_list_queryset(
                    _filter_projects_for_workflow(qs, workflow).order_by("-updated_at"),
                    self.request,
                    prefetch_priority=True,
                )
            qs = Project.objects.filter(archived=False).exclude(status="planning").filter(
                Q(status="proposed")
                | (reviewed_by_user & Q(profile_data__validator_review__review_status__in=("draft", "reviewed")))
            ).order_by("-created_at")
            workflow = self.request.query_params.get("workflow") or self.request.query_params.get("status")
            return _project_list_queryset(
                _filter_projects_for_workflow(qs, workflow).order_by("-created_at"),
                self.request,
                prefetch_priority=True,
            )

        qs = Project.objects.filter(archived=False).exclude(status="planning").filter(
            Q(status="proposed")
            | (reviewed_by_user & Q(profile_data__validator_review__review_status__in=visible_project_states))
        ).order_by("-created_at")
        workflow = self.request.query_params.get("workflow") or self.request.query_params.get("status")
        return _project_list_queryset(
            _filter_projects_for_workflow(qs, workflow).order_by("-created_at"),
            self.request,
            prefetch_priority=False,
        )

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("Use validator review actions instead of direct project edit.")

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied("Use validator review actions instead of direct project edit.")

    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied("Only admin can delete projects")

    @action(detail=True, methods=["post"], url_path="update-form")
    def update_form(self, request, pk=None):
        raise PermissionDenied("Contributor-form migration is available only to administrators.")


class AdminProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()
    permission_classes = [IsAuthenticated, AdminOnlyPermission, ProjectPermission]

    def perform_create(self, serializer):
        super().perform_create(serializer)
        _log_activity(self.request, "project_create", serializer.instance, {"source": "admin_api"})

    def perform_update(self, serializer):
        super().perform_update(serializer)
        _log_activity(self.request, "project_update", serializer.instance, {"source": "admin_api"})

    def get_queryset(self):
        qs = Project.objects.all().order_by("-created_at")
        if self.action == "list":
            qs = qs.filter(archived=self.request.query_params.get("archived") in {"1", "true", "yes"})
            if (self.request.query_params.get("scope") or "").strip().lower() == "update_forms":
                outdated_ids = []
                draft_profiles = {}
                version_cache = {}
                for project_id, profile in ProjectRevision.objects.filter(
                    project_id__in=qs.values("id"),
                    revision_type="progress_update",
                    state="draft",
                ).order_by("project_id", "-updated_at").values_list("project_id", "profile_data_snapshot"):
                    draft_profiles.setdefault(project_id, profile)
                for project in qs.only("id", "profile_data"):
                    source_profile = draft_profiles.get(project.id, project.profile_data)
                    analysis = analyze_profile_migration(source_profile, version_cache=version_cache)
                    if not analysis.get("already_current") and analysis.get("target_version"):
                        outdated_ids.append(project.id)
                qs = Project.objects.filter(id__in=outdated_ids)
        workflow = self.request.query_params.get("workflow") or self.request.query_params.get("status")
        return _project_list_queryset(
            _filter_projects_for_workflow(qs, workflow).order_by("-created_at"),
            self.request,
            prefetch_priority=getattr(self, "action", "") == "list"
            and (self.request.query_params.get("scope") or "").strip().lower() != "update_forms",
        )

    @action(detail=False, methods=["post"], url_path="batch-archive-preview")
    def batch_archive_preview(self, request):
        try:
            projects = list(_selected_admin_projects(request.data))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        rows = []
        eligible_ids = []
        for project in projects:
            reason = _archive_ineligibility(project)
            rows.append(_batch_project_row(project, reason))
            if not reason:
                eligible_ids.append(project.id)
        token = signing.dumps(
            {"project_ids": [project.id for project in projects]},
            salt=BATCH_ARCHIVE_PREVIEW_SALT,
        ) if projects else ""
        return Response({
            "rows": rows,
            "total": len(rows),
            "eligible": len(eligible_ids),
            "skipped": len(rows) - len(eligible_ids),
            "preview_token": token,
        })

    @action(detail=False, methods=["post"], url_path="batch-archive")
    def batch_archive(self, request):
        try:
            payload = signing.loads(
                str(request.data.get("preview_token") or ""),
                salt=BATCH_ARCHIVE_PREVIEW_SALT,
                max_age=15 * 60,
            )
        except signing.BadSignature:
            return Response({"detail": "The archive preview expired. Preview the selection again."}, status=400)
        ids = payload.get("project_ids") if isinstance(payload, dict) else None
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "The archive preview is invalid."}, status=400)
        rows = []
        archived = skipped = failed = 0
        for project_id in ids:
            try:
                with transaction.atomic():
                    project = Project.objects.select_for_update().get(pk=project_id)
                    success, reason = _archive_project(request, project)
                    if success:
                        archived += 1
                        rows.append({**_batch_project_row(project), "status": "archived"})
                    else:
                        skipped += 1
                        rows.append({**_batch_project_row(project, reason), "status": "skipped"})
            except Project.DoesNotExist:
                skipped += 1
                rows.append({"id": project_id, "title": "", "status": "skipped", "reason": "Project no longer exists."})
            except Exception:
                failed += 1
                rows.append({"id": project_id, "title": "", "status": "failed", "reason": "The project could not be archived."})
        _log_activity(request, "api_action", details={
            "operation": "batch_project_archive",
            "archived": archived,
            "skipped": skipped,
            "failed": failed,
            "requested": len(ids),
        })
        return Response({"archived": archived, "skipped": skipped, "failed": failed, "rows": rows})

    @action(detail=False, methods=["post"], url_path="form-migration-preview")
    def form_migration_preview(self, request):
        try:
            projects = list(_selected_admin_projects(request.data))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        version_cache = {}
        rows = [_migration_preview_row(project, version_cache=version_cache) for project in projects]
        token = signing.dumps(
            {"project_ids": [project.id for project in projects]},
            salt=BATCH_FORM_MIGRATION_PREVIEW_SALT,
        ) if projects else ""
        return Response({
            "rows": rows,
            "total": len(rows),
            "eligible": sum(1 for row in rows if row["eligible"]),
            "blocked": sum(1 for row in rows if not row["eligible"]),
            "preview_token": token,
        })

    @action(detail=False, methods=["post"], url_path="migrate-forms")
    def migrate_forms(self, request):
        try:
            payload = signing.loads(
                str(request.data.get("preview_token") or ""),
                salt=BATCH_FORM_MIGRATION_PREVIEW_SALT,
                max_age=15 * 60,
            )
        except signing.BadSignature:
            return Response({"detail": "The migration preview expired. Preview the selection again."}, status=400)
        ids = payload.get("project_ids") if isinstance(payload, dict) else None
        if not isinstance(ids, list) or not ids:
            return Response({"detail": "The migration preview is invalid."}, status=400)
        counts = {"migrated": 0, "prepared": 0, "attention": 0, "skipped": 0, "blocked": 0, "failed": 0}
        rows = []
        for project_id in ids:
            try:
                project = Project.objects.get(pk=project_id)
                result = prepare_project_migration(project, user=request.user, trigger="admin_batch")
                result_status = result.get("status", "failed")
                if result_status in counts:
                    counts[result_status] += 1
                elif result_status == "current":
                    counts["skipped"] += 1
                else:
                    counts["failed"] += 1
                attention = result.get("attention_fields") or []
                if result_status in {"migrated", "prepared"} and attention:
                    counts["attention"] += 1
                if result_status in {"migrated", "prepared"}:
                    _log_activity(request, "project_update", project, {
                        "operation": "contributor_form_migration",
                        "trigger": "admin_batch",
                        "migration_status": result_status,
                        "source_version": result.get("source_version"),
                        "target_version": result.get("target_version"),
                        "attention_fields": attention,
                        "revision_id": getattr(result.get("revision"), "id", None),
                    })
                rows.append({
                    "id": project.id,
                    "title": _project_title(project),
                    "status": result_status,
                    "source_version": result.get("source_version"),
                    "target_version": result.get("target_version"),
                    "attention_fields": attention,
                    "reason": result.get("reason") or "; ".join(result.get("issues") or []),
                    "revision_id": getattr(result.get("revision"), "id", None),
                })
            except Project.DoesNotExist:
                counts["skipped"] += 1
                rows.append({"id": project_id, "title": "", "status": "skipped", "reason": "Project no longer exists."})
            except Exception:
                counts["failed"] += 1
                rows.append({"id": project_id, "title": "", "status": "failed", "reason": "The form could not be migrated."})
        _log_activity(request, "api_action", details={"operation": "batch_form_migration", **counts, "requested": len(ids)})
        return Response({**counts, "rows": rows})

    @action(detail=True, methods=["post"], url_path="update-form")
    def update_form(self, request, pk=None):
        project = self.get_object()
        preview = _migration_preview_row(project)
        if not preview["eligible"]:
            return Response({"detail": preview["reason"], "migration": preview}, status=409)
        result = prepare_project_migration(project, user=request.user, trigger="admin_single")
        if result.get("status") not in {"migrated", "prepared", "current"}:
            return Response({"detail": result.get("reason") or "; ".join(result.get("issues") or [])}, status=409)
        _log_activity(request, "project_update", project, {
            "operation": "contributor_form_migration",
            "migration_status": result.get("status"),
            "source_version": result.get("source_version"),
            "target_version": result.get("target_version"),
        })
        return Response({
            "detail": "A latest-form update draft was prepared." if result.get("status") == "prepared" else "The project form was migrated.",
            "status": result.get("status"),
            "project_id": project.id,
            "source_version": result.get("source_version"),
            "target_version": result.get("target_version"),
            "attention_fields": result.get("attention_fields") or [],
            "revision_id": getattr(result.get("revision"), "id", None),
        })


class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    def update(self, request, *args, **kwargs):
        forbidden = set(request.data) - {"role", "is_active"}
        if forbidden:
            return Response({"detail": "Profile fields must be changed by their owner after approval."}, status=403)
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        before = {"role": serializer.instance.role, "is_active": serializer.instance.is_active}
        password_changed = "password" in serializer.validated_data
        user = serializer.save()
        _log_activity(
            self.request, "user_update",
            details={"target_user_id": user.id, "email": user.email, "before": before,
                     "after": {"role": user.role, "is_active": user.is_active},
                     "password_changed": password_changed},
        )

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        _log_activity(
            request, "user_delete",
            details={"target_user_id": user.id, "email": user.email, "role": user.role},
        )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def set_active(self, request, pk=None):
        user = self.get_object()
        active = bool(request.data.get("active", True))
        if user.id == request.user.id and not active:
            return Response({"detail": "You cannot deactivate your own account."}, status=400)
        user.is_active = active
        user.save(update_fields=["is_active"])
        _log_activity(
            request, "user_status_changed",
            details={"target_user_id": user.id, "email": user.email, "is_active": active},
        )
        return Response({"id": user.id, "is_active": user.is_active})

    def create(self, request, *args, **kwargs):
        email = (request.data.get("email") or "").strip().lower()
        role = (request.data.get("role") or "").strip().lower()
        if not email:
            return Response({"detail": "Email is required."}, status=400)
        try:
            validate_email(email)
        except ValidationError:
            return Response({"detail": "Enter a valid email address."}, status=400)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "Email already exists."}, status=400)
        if role == "contributor":
            role = "staff"
        elif role == "content-editor":
            role = "content_editor"
        if role not in ("admin", "validator", "staff", "content_editor"):
            return Response({"detail": "Invalid role."}, status=400)
        agency = "RDC-NCR" if role in INTERNAL_ACCOUNT_ROLES else _normalize_account_agency(request.data.get("agency"))
        if role in INTERNAL_ACCOUNT_ROLES and "agency" in request.data:
            if _normalize_account_agency(request.data.get("agency")) != "RDC-NCR":
                return Response({"detail": "Agency must be RDC-NCR for this user type."}, status=400)
        elif request.data.get("agency") and not agency:
            return Response({"detail": "Invalid agency."}, status=400)

        try:
            _issue_registration_invitation(request, email, role, agency=agency)
        except Exception:
            return Response({"detail": "Failed to send or record the registration invitation."}, status=500)

        return Response(
            {"detail": "Registration invitation sent.", "email": email,
             "role": "contributor" if role == "staff" else role, "invitation_sent": True},
            status=status.HTTP_202_ACCEPTED,
        )


def _normalize_invitation_role(value):
    role = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "contributor": "staff",
        "employee": "staff",
        "project_validator": "validator",
        "contenteditor": "content_editor",
    }.get(role, role)


def _has_pending_registration_invitation(email, now=None):
    now = now or timezone.now()
    if UserInvitation.objects.filter(
        email__iexact=email,
        status=UserInvitation.STATUS_SENT,
        expires_at__gte=now,
    ).exists():
        return True
    legacy = UserActivity.objects.filter(
        event="registration_invitation_sent",
        details__email=email,
        created_at__gte=now - timedelta(hours=PASSWORD_SETUP_TTL_HOURS),
    ).order_by("-id").first()
    if legacy is None:
        return False
    return not UserActivity.objects.filter(
        event="registration_completed", details__invitation_id=legacy.id,
    ).exists()


def _batch_invitation_entries(request):
    upload = request.FILES.get("file") if hasattr(request, "FILES") else None
    if upload:
        if not str(upload.name or "").lower().endswith(".csv"):
            raise ValueError("Upload a CSV file.")
        if upload.size > 1024 * 1024:
            raise ValueError("The CSV file must be 1 MB or smaller.")
        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("The CSV must use UTF-8 encoding.") from exc
        reader = csv.DictReader(io.StringIO(text))
        headers = {str(item or "").strip().lower() for item in (reader.fieldnames or [])}
        if "email" not in headers or not headers.issubset({"email", "role", "agency"}):
            raise ValueError("CSV headers must be email, role, and agency.")
        return [
            {str(key or "").strip().lower(): value for key, value in row.items()}
            for row in reader
        ]
    entries = request.data.get("entries", [])
    if isinstance(entries, str):
        try:
            entries = json.loads(entries)
        except json.JSONDecodeError as exc:
            raise ValueError("Entries must be a JSON list.") from exc
    if not isinstance(entries, list):
        raise ValueError("Entries must be a list.")
    return entries


class BatchInvitationOptionsView(APIView):
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    def get(self, request):
        return Response({
            "roles": [
                {"value": "contributor", "label": "Contributor"},
                {"value": "validator", "label": "Validator"},
                {"value": "content_editor", "label": "Content Editor"},
                {"value": "admin", "label": "Administrator"},
            ],
            "agencies": _active_agency_options(),
            "max_rows": 100,
            "csv_headers": ["email", "role", "agency"],
        })


class BatchInvitationPreviewView(APIView):
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    def post(self, request):
        try:
            entries = _batch_invitation_entries(request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        if not entries:
            return Response({"detail": "Add at least one invitation entry."}, status=400)
        if len(entries) > 100:
            return Response({"detail": "A batch can contain at most 100 entries."}, status=400)

        default_role = _normalize_invitation_role(request.data.get("default_role") or "contributor")
        default_agency_raw = str(request.data.get("default_agency") or "").strip()
        resend_pending = str(request.data.get("resend_pending") or "").lower() in {"1", "true", "yes"}
        seen = set()
        results = []
        valid = []
        now = timezone.now()
        for index, raw in enumerate(entries, start=1):
            raw = raw if isinstance(raw, dict) else {"email": str(raw or "")}
            email = str(raw.get("email") or "").strip().lower()
            role = _normalize_invitation_role(raw.get("role") or default_role)
            agency_raw = str(raw.get("agency") or default_agency_raw).strip()
            agency = "RDC-NCR" if role in INTERNAL_ACCOUNT_ROLES else _normalize_account_agency(agency_raw)
            row = {"row": index, "email": email, "role": "contributor" if role == "staff" else role, "agency": agency}
            reason = ""
            row_status = "valid"
            try:
                validate_email(email)
            except ValidationError:
                row_status, reason = "invalid", "Enter a valid email address."
            if row_status == "valid" and email in seen:
                row_status, reason = "duplicate", "This email is repeated in the batch."
            seen.add(email)
            if row_status == "valid" and role not in {"admin", "validator", "staff", "content_editor"}:
                row_status, reason = "invalid", "Select a valid user role."
            if row_status == "valid" and role == "staff" and agency_raw and not agency:
                row_status, reason = "invalid", "Select an approved agency."
            if row_status == "valid" and User.objects.filter(email__iexact=email).exists():
                row_status, reason = "existing_account", "An account already uses this email."
            pending = row_status == "valid" and _has_pending_registration_invitation(email, now)
            if pending and not resend_pending:
                row_status, reason = "pending_invitation", "A valid invitation is already pending."
            row.update({"status": row_status, "reason": reason})
            results.append(row)
            if row_status == "valid":
                valid.append({"row": index, "email": email, "role": role, "agency": agency})
        batch_key = get_random_string(32)
        preview_token = signing.dumps(
            {"batch_key": batch_key, "entries": valid}, salt=BATCH_INVITE_PREVIEW_SALT,
        ) if valid else ""
        return Response({
            "rows": results,
            "counts": {
                "total": len(results),
                "valid": len(valid),
                "skipped": len(results) - len(valid),
            },
            "preview_token": preview_token,
        })


class BatchInvitationSendView(APIView):
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    def post(self, request):
        token = str(request.data.get("preview_token") or "")
        try:
            payload = signing.loads(token, salt=BATCH_INVITE_PREVIEW_SALT, max_age=15 * 60)
        except signing.BadSignature:
            return Response({"detail": "The invitation preview expired. Preview the batch again."}, status=400)
        entries = payload.get("entries") if isinstance(payload, dict) else None
        batch_key = str(payload.get("batch_key") or "") if isinstance(payload, dict) else ""
        if not isinstance(entries, list) or not entries or len(entries) > 100:
            return Response({"detail": "The invitation preview is invalid."}, status=400)
        results = []
        sent = failed = skipped = 0
        for raw in entries:
            email = str(raw.get("email") or "").strip().lower()
            role = _normalize_invitation_role(raw.get("role"))
            agency = str(raw.get("agency") or "")
            if User.objects.filter(email__iexact=email).exists():
                skipped += 1
                results.append({"row": raw.get("row"), "email": email, "status": "skipped", "reason": "Account already exists."})
                continue
            if UserInvitation.objects.filter(email__iexact=email, batch_key=batch_key, status=UserInvitation.STATUS_SENT).exists():
                skipped += 1
                results.append({"row": raw.get("row"), "email": email, "status": "skipped", "reason": "This batch already sent the invitation."})
                continue
            try:
                _issue_registration_invitation(request, email, role, agency=agency, batch_key=batch_key)
                sent += 1
                results.append({"row": raw.get("row"), "email": email, "status": "sent", "reason": ""})
            except Exception:
                failed += 1
                results.append({"row": raw.get("row"), "email": email, "status": "failed", "reason": "The email could not be delivered."})
        _log_activity(request, "api_action", details={
            "operation": "batch_registration_invitation",
            "batch_key": batch_key,
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
        })
        return Response({"sent": sent, "failed": failed, "skipped": skipped, "rows": results})


class AccessRequestViewSet(viewsets.ModelViewSet):
    queryset = AccessRequest.objects.all().order_by("-created_at")
    serializer_class = AccessRequestSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsAuthenticated(), AdminOnlyPermission()]

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Access requests are disabled. Contact admin."}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        access_request = self.get_object()
        if access_request.status != "pending":
            return Response({"detail": "Request already reviewed."}, status=400)
        email = access_request.email.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "Email already exists."}, status=400)
        role = "validator" if access_request.requested_role == "validator" else "staff"
        try:
            _issue_registration_invitation(request, email, role)
        except Exception:
            return Response({"detail": "Failed to send or record the registration invitation."}, status=500)

        access_request.status = "approved"
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.review_notes = request.data.get("review_notes", "")
        access_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])

        _log_activity(
            request, "access_request_approved",
            details={"request_id": access_request.id, "email": email,
                     "role": role, "invitation_sent": True},
        )

        return Response(
            {
                "status": "approved",
                "email": email,
                "role": "contributor" if role == "staff" else role,
                "invitation_sent": True,
            }
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        access_request = self.get_object()
        if access_request.status != "pending":
            return Response({"detail": "Request already reviewed."}, status=400)
        access_request.status = "rejected"
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.review_notes = request.data.get("review_notes", "")
        access_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
        _log_activity(
            request, "access_request_rejected",
            details={"request_id": access_request.id, "email": access_request.email},
        )
        return Response({"status": "rejected"})


class PasswordResetOTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email") or "").strip().lower()
        captcha_token = str(request.data.get("captcha_token") or "").strip()
        if not email:
            return Response({"detail": "Email is required."}, status=400)
        if getattr(settings, "TURNSTILE_REQUIRED", False):
            if not _verify_turnstile(captcha_token, _client_ip(request)):
                return Response({"detail": "Captcha verification failed."}, status=400)
        try:
            _, error = _issue_password_reset_challenge(request, email)
        except ValidationError:
            return Response({"detail": "Enter a valid email address."}, status=400)
        if error:
            return error
        return Response(
            {
                "detail": PASSWORD_RESET_GENERIC_MESSAGE,
                "resend_after_seconds": PASSWORD_RESET_RESEND_COOLDOWN_SECONDS,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetOTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email") or "").strip().lower()
        otp = str(request.data.get("otp") or "").strip()
        if not email or not re.fullmatch(r"\d{6}", otp):
            return Response({"detail": "The code is invalid or expired."}, status=400)
        try:
            validate_email(email)
        except ValidationError:
            return Response({"detail": "The code is invalid or expired."}, status=400)
        fingerprint = _password_reset_email_fingerprint(email)
        now = timezone.now()
        with transaction.atomic():
            challenge = PasswordResetChallenge.objects.select_for_update().filter(
                email_fingerprint=fingerprint,
                status=PasswordResetChallenge.STATUS_PENDING,
            ).order_by("-created_at").first()
            if challenge is None:
                return Response({"detail": "The code is invalid or expired."}, status=400)
            if challenge.expires_at <= now:
                challenge.status = PasswordResetChallenge.STATUS_EXPIRED
                challenge.otp_digest = ""
                challenge.save(update_fields=["status", "otp_digest"])
                return Response({"detail": "The code is invalid or expired."}, status=400)
            if challenge.failed_attempts >= PASSWORD_RESET_MAX_ATTEMPTS:
                challenge.status = PasswordResetChallenge.STATUS_LOCKED
                challenge.otp_digest = ""
                challenge.save(update_fields=["status", "otp_digest"])
                return Response({"detail": "Too many invalid attempts. Request a new code."}, status=429)
            valid = bool(challenge.user_id and challenge.otp_digest and check_password(otp, challenge.otp_digest))
            if not valid:
                challenge.failed_attempts += 1
                fields = ["failed_attempts"]
                if challenge.failed_attempts >= PASSWORD_RESET_MAX_ATTEMPTS:
                    challenge.status = PasswordResetChallenge.STATUS_LOCKED
                    challenge.otp_digest = ""
                    fields.extend(["status", "otp_digest"])
                challenge.save(update_fields=fields)
                _record_password_reset_event(
                    request,
                    "api_action_failed",
                    challenge,
                    {
                        "action": "password_reset_otp_verify",
                        "attempts": challenge.failed_attempts,
                        "locked": challenge.status == PasswordResetChallenge.STATUS_LOCKED,
                    },
                )
                if challenge.status == PasswordResetChallenge.STATUS_LOCKED:
                    return Response({"detail": "Too many invalid attempts. Request a new code."}, status=429)
                return Response({"detail": "The code is invalid or expired."}, status=400)

            reset_token = secrets.token_urlsafe(32)
            challenge.status = PasswordResetChallenge.STATUS_VERIFIED
            challenge.verified_at = now
            challenge.expires_at = now + timedelta(seconds=PASSWORD_RESET_TOKEN_TTL_SECONDS)
            challenge.otp_digest = ""
            challenge.reset_token_digest = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
            challenge.save(update_fields=[
                "status", "verified_at", "expires_at", "otp_digest", "reset_token_digest",
            ])
        _record_password_reset_event(
            request,
            "api_action",
            challenge,
            {"action": "password_reset_otp_verified"},
        )
        return Response({"reset_token": reset_token, "expires_in": PASSWORD_RESET_TOKEN_TTL_SECONDS})


class PasswordResetOTPCompleteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        reset_token = str(request.data.get("reset_token") or "").strip()
        new_password = str(request.data.get("new_password") or "")
        confirm_password = str(request.data.get("confirm_password") or "")
        if not reset_token:
            return Response({"detail": "The password reset session is invalid or expired."}, status=400)
        token_digest = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()
        now = timezone.now()
        with transaction.atomic():
            challenge = PasswordResetChallenge.objects.select_for_update().filter(
                reset_token_digest=token_digest,
                status=PasswordResetChallenge.STATUS_VERIFIED,
            ).first()
            if challenge is None or challenge.expires_at <= now or not challenge.user_id:
                if challenge is not None and challenge.expires_at <= now:
                    challenge.status = PasswordResetChallenge.STATUS_EXPIRED
                    challenge.reset_token_digest = ""
                    challenge.save(update_fields=["status", "reset_token_digest"])
                return Response({"detail": "The password reset session is invalid or expired."}, status=400)
            if new_password != confirm_password:
                return Response({"detail": "Passwords do not match."}, status=400)
            policy_error = _validate_password_policy(new_password)
            if policy_error:
                return Response({"detail": policy_error}, status=400)

            user = User.objects.select_for_update().get(pk=challenge.user_id)
            user.set_password(new_password)
            user.must_change_password = False
            user.last_password_change = now
            user.save(update_fields=["password", "must_change_password", "last_password_change"])
            _advance_user_session(user, request, revocation_reason="credential_change")
            challenge.status = PasswordResetChallenge.STATUS_USED
            challenge.used_at = now
            challenge.reset_token_digest = ""
            challenge.save(update_fields=["status", "used_at", "reset_token_digest"])
            PasswordResetChallenge.objects.filter(
                user=user,
                status__in=[PasswordResetChallenge.STATUS_PENDING, PasswordResetChallenge.STATUS_VERIFIED],
            ).exclude(pk=challenge.pk).update(
                status=PasswordResetChallenge.STATUS_SUPERSEDED,
                superseded_at=now,
                otp_digest="",
                reset_token_digest="",
            )
            PasswordSetupToken.objects.filter(
                user=user,
                token__startswith=RESET_PASSWORD_TOKEN_PREFIX,
                used_at__isnull=True,
            ).update(used_at=now)

        notification_sent = True
        try:
            _send_password_changed_notice(user)
        except Exception:
            notification_sent = False
        challenge.user = user
        _record_password_reset_event(
            request,
            "auth_password_setup",
            challenge,
            {"action": "otp_password_reset", "notification_sent": notification_sent},
        )
        return Response({"status": "ok"})


class EncodingWindowView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        state = _resolve_encoding_window_state()
        role = getattr(request.user, "role", "")
        can_encode = state["is_open"] or role in ("admin", "validator")
        return Response(
            {
                **state,
                "can_encode": can_encode,
            }
        )

    def post(self, request):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can update encoding schedule.")

        enabled_raw = request.data.get("enabled", False)
        enabled = (
            enabled_raw.strip().lower() in ("1", "true", "yes", "on")
            if isinstance(enabled_raw, str)
            else bool(enabled_raw)
        )
        start_at = str(request.data.get("start_at", "") or "")
        end_at = str(request.data.get("end_at", "") or "")

        if enabled and (not start_at or not end_at):
            return Response({"detail": "Start and end date are required for a scheduled encoding window."}, status=400)

        if not enabled:
            start_at = ""
            end_at = ""
        else:
            try:
                parsed_start = _parse_iso_datetime(start_at)
                parsed_end = _parse_iso_datetime(end_at)
            except (TypeError, ValueError):
                return Response({"detail": "Start and end date must be valid date-time values."}, status=400)
            if not parsed_start or not parsed_end or parsed_start >= parsed_end:
                return Response({"detail": "Start date must be earlier than end date."}, status=400)
            start_at = parsed_start.isoformat()
            end_at = parsed_end.isoformat()

        previous = _resolve_encoding_window_state()
        payload = {"enabled": enabled, "start_at": start_at, "end_at": end_at}
        SystemSetting.objects.update_or_create(
            key=ENCODING_WINDOW_KEY,
            defaults={"value": json.dumps(payload)},
        )
        current = _resolve_encoding_window_state()
        _log_activity(
            request,
            "encoding_window_updated",
            details={
                "previous_mode": "Scheduled" if previous["enabled"] else "Closed",
                "previous_start_at": previous["start_at"],
                "previous_end_at": previous["end_at"],
                "previous_status": previous["status_code"],
                "new_mode": "Scheduled" if current["enabled"] else "Closed",
                "new_start_at": current["start_at"],
                "new_end_at": current["end_at"],
                "new_status": current["status_code"],
            },
        )
        return Response(current)


class ProgressUpdateWindowView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _eligible_count():
        return sum(
            1
            for project in Project.objects.filter(
                archived=False, is_active=True, validated=True
            ).only("id", "profile_data")
            if not _is_completed_rdip_project(project)
        )

    def get(self, request):
        state = _resolve_progress_update_window_state()
        return Response(
            {
                **state,
                "can_encode": state["is_open"],
                "can_update": state["is_open"],
                "can_manage": getattr(request.user, "role", "") == "admin",
                "eligible_project_count": self._eligible_count(),
            }
        )

    def post(self, request):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can update progress update window.")
        action_value = str(request.data.get("action") or "").strip().lower()
        enabled = bool(request.data.get("enabled", False))
        if action_value == "open":
            enabled = True
        elif action_value == "close":
            enabled = False
        manual_open = action_value == "open" or bool(request.data.get("manual_open", False))
        start_at = str(request.data.get("start_at") or "").strip()
        end_at = str(request.data.get("end_at") or "").strip()

        previous = _resolve_progress_update_window_state()
        if action_value in {"open", "close"} and not start_at and not end_at:
            start_at = previous.get("start_at", "")
            end_at = previous.get("end_at", "")

        if enabled and not manual_open and (not start_at or not end_at):
            return Response({"detail": "Start and end date are required for scheduled progress updates."}, status=400)
        if enabled and not manual_open:
            try:
                parsed_start = _parse_iso_datetime(start_at)
                parsed_end = _parse_iso_datetime(end_at)
            except (TypeError, ValueError):
                return Response({"detail": "Progress update schedule dates are invalid."}, status=400)
            if not parsed_start or not parsed_end or parsed_start >= parsed_end:
                return Response({"detail": "Start date must be earlier than end date."}, status=400)

        payload = {
            "enabled": enabled,
            "manual_open": manual_open if enabled else False,
            "start_at": start_at,
            "end_at": end_at,
        }
        SystemSetting.objects.update_or_create(
            key=PROGRESS_UPDATE_WINDOW_KEY,
            defaults={"value": json.dumps(payload)},
        )
        current = _resolve_progress_update_window_state()
        _log_activity(
            request,
            "progress_window_updated",
            details={
                "previous": {
                    "enabled": previous.get("enabled"),
                    "start_at": previous.get("start_at"),
                    "end_at": previous.get("end_at"),
                    "status_code": previous.get("status_code"),
                },
                "current": {
                    "enabled": current.get("enabled"),
                    "start_at": current.get("start_at"),
                    "end_at": current.get("end_at"),
                    "status_code": current.get("status_code"),
                },
            },
        )
        return Response({
            **current,
            "can_encode": current["is_open"],
            "can_update": current["is_open"],
            "can_manage": True,
            "eligible_project_count": self._eligible_count(),
        })


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, "role", "")
        if role == "admin":
            project_counts = Project.objects.aggregate(
                total_projects=Count("id"),
                draft_projects=Count("id", filter=Q(status="planning")),
                pending_projects=Count("id", filter=Q(status="proposed")),
                approved_projects=Count("id", filter=Q(status="completed")),
                archived_projects=Count("id", filter=Q(archived=True)),
                reviewed_projects=Count("id", filter=Q(profile_data__validator_review__review_status="reviewed")),
                validator_edited_projects=Count("id", filter=Q(profile_data__validator_review__edited=True)),
                review_draft=Count("id", filter=Q(profile_data__validator_review__review_status="draft")),
                review_reviewed=Count("id", filter=Q(profile_data__validator_review__review_status="reviewed")),
                review_endorsed=Count("id", filter=Q(profile_data__validator_review__review_status="endorsed")),
            )
            user_counts = User.objects.aggregate(
                users=Count("id"),
                admin_users=Count("id", filter=Q(role="admin")),
                validator_users=Count("id", filter=Q(role="validator")),
                contributor_users=Count("id", filter=Q(role="staff")),
            )
            data = {
                **project_counts,
                **user_counts,
            }
        elif role == "validator":
            data = Project.objects.filter(archived=False).aggregate(
                review_draft=Count("id", filter=Q(profile_data__validator_review__review_status="draft")),
                review_reviewed=Count("id", filter=Q(profile_data__validator_review__review_status="reviewed")),
                review_endorsed=Count("id", filter=Q(profile_data__validator_review__review_status="endorsed")),
            )
        else:
            my = Project.objects.filter(_contributor_project_scope(user), archived=False).distinct()
            data = my.aggregate(
                my_projects=Count("id"),
                draft_projects=Count("id", filter=Q(status="planning")),
                submitted_projects=Count("id", filter=Q(status="proposed")),
                approved_projects=Count("id", filter=Q(status="completed")),
            )
        response = Response(data)
        response["Cache-Control"] = "private, no-store"
        return response


class AnalyticsView(APIView):
    permission_classes = [AllowAny]

    def _path(self):
        return os.path.join(settings.BASE_DIR, "analytics.json")

    def _load(self):
        path = self._path()
        if not os.path.exists(path):
            data = {"pageviews": 0, "avg_daily": 0, "today": 0, "total_visitors": 0}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {"pageviews": 0, "avg_daily": 0, "today": 0, "total_visitors": 0}

    def _save(self, data):
        with open(self._path(), "w", encoding="utf-8") as f:
            json.dump(data, f)

    def get(self, request):
        return Response(self._load())

    def post(self, request):
        data = self._load()
        if (request.data or {}).get("action") != "visit":
            return Response({"error": "Unsupported action"}, status=400)
        data["pageviews"] = int(data.get("pageviews", 0)) + 1
        data["today"] = int(data.get("today", 0)) + 1
        data["total_visitors"] = int(data.get("total_visitors", 0)) + 1
        if not data.get("avg_daily"):
            data["avg_daily"] = data["pageviews"] // 30
        self._save(data)
        return Response(data)


class PublicContactView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        name = str(request.data.get("name") or "").strip()
        email = str(request.data.get("email") or "").strip()
        subject = str(request.data.get("subject") or "").strip()
        message = str(request.data.get("message") or "").strip()

        if not name or not email or not message:
            return Response(
                {"detail": "Name, email, and message are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"detail": "Email address is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receiver = getattr(settings, "CONTACT_RECEIVER_EMAIL", "")
        if not receiver:
            return Response(
                {"detail": "Contact receiver is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        safe_subject = subject or "Contact Form Inquiry"
        full_subject = f"[RDC Portal] {safe_subject}"
        body = (
            "New contact message received via RDC-NCR website.\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Subject: {subject or '-'}\n\n"
            "Message:\n"
            f"{message}\n"
        )

        try:
            email_msg = EmailMessage(
                full_subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [receiver],
                reply_to=[email],
            )
            email_msg.send(fail_silently=False)
        except Exception:
            return Response(
                {"detail": "Failed to send message. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"status": "sent"})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": _frontend_role(u.role),
                "first_name": u.first_name,
                "last_name": u.last_name,
                "agency": u.agency,
                "agency_head": u.agency_head,
                "office": u.office,
                "division": u.division,
                "position": u.position,
                "contact_number": u.contact_number,
                "phone_number": u.phone_number,
            }
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or request.data.get("username") or "").strip().lower()
        password = request.data.get("password") or ""
        active_browser_session = _active_browser_session(request.data.get("browser_refresh"))
        if active_browser_session:
            return Response(
                {
                    "active_session": True,
                    "detail": "This browser is already signed in. Continue with the active account.",
                    "user": _login_user_payload(active_browser_session.user),
                },
                status=409,
            )
        if not email:
            return Response({"detail": "Email is required."}, status=400)
        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            _log_unauthenticated_activity(
                request, "login_failed", {"attempted_email": email, "reason": "invalid_credentials"}
            )
            return Response({"detail": "Invalid credentials"}, status=401)
        if user.must_change_password:
            _log_unauthenticated_activity(
                request, "login_failed", {"attempted_email": email, "reason": "password_setup_required"}
            )
            return Response({"detail": "Password setup required. Check your email for the setup link."}, status=403)
        if not user.is_active:
            _log_unauthenticated_activity(
                request, "login_failed", {"attempted_email": email, "reason": "account_deactivated"}
            )
            return Response({"detail": "Account is deactivated. Contact admin."}, status=403)

        remember_me = request.data.get("remember_me") is True
        refresh_token = secrets.token_urlsafe(48)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            now = timezone.now()
            previous_session_version, session_version = _advance_user_session(
                user,
                request,
                revocation_reason="new_login",
            )
            portal_session = PortalSession.objects.create(
                user=user,
                session_version=session_version,
                refresh_token_digest=hashlib.sha256(refresh_token.encode("utf-8")).hexdigest(),
                remember_me=remember_me,
                last_activity_at=now,
            )
            access_token = _issue_session_access_token(user, portal_session)
            UserActivity.objects.create(
                user=user,
                role=user.role,
                event="login",
                ip_address=_client_ip(request),
                location_hint=_location_hint(request),
                details={
                    "email": user.email,
                    "session_version": session_version,
                    "replaced_previous_session": previous_session_version > 0,
                    "remember_me": remember_me,
                },
            )
        return Response(
            {
                "access": access_token,
                "refresh": refresh_token,
                "user": _login_user_payload(user),
            }
        )


class PortalSessionRefreshView(APIView):
    """Exchange a revocable browser refresh credential for a short-lived access token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.data.get("refresh") or ""
        if not isinstance(refresh_token, str) or not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=400)
        digest = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        with transaction.atomic():
            try:
                portal_session = PortalSession.objects.select_for_update().select_related("user").get(
                    refresh_token_digest=digest,
                )
            except PortalSession.DoesNotExist:
                return Response({"detail": "Session is invalid or has been revoked. Please log in again."}, status=401)

            user = portal_session.user
            if portal_session.revoked_at:
                detail = (
                    "This session expired because this account signed in from another browser or device."
                    if portal_session.revocation_reason == "new_login"
                    else "Session expired after 12 hours of inactivity. Please log in again."
                    if portal_session.revocation_reason == "idle_timeout"
                    else "This session has ended. Please log in again."
                )
                return Response({"detail": detail}, status=401)
            if not user.is_active or portal_session.session_version != user.session_version:
                portal_session.revoked_at = timezone.now()
                portal_session.revocation_reason = "new_login"
                portal_session.save(update_fields=["revoked_at", "revocation_reason"])
                return Response(
                    {"detail": "This session expired because this account signed in from another browser or device."},
                    status=401,
                )

            now = timezone.now()
            if not portal_session.remember_me and now - portal_session.last_activity_at >= SESSION_IDLE_TIMEOUT:
                portal_session.revoked_at = now
                portal_session.revocation_reason = "idle_timeout"
                portal_session.save(update_fields=["revoked_at", "revocation_reason"])
                return Response({"detail": "Session expired after 12 hours of inactivity. Please log in again."}, status=401)

            portal_session.last_activity_at = now
            portal_session.save(update_fields=["last_activity_at"])
            access_token = _issue_session_access_token(user, portal_session)
        return Response({"access": access_token, "refresh": refresh_token})


class PortalSessionActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # The authentication class records activity with a write throttle.
        return Response({"status": "ok"})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _log_activity(request, "logout", details={"session_version": request.user.session_version})
        session_id = request.auth.get("portal_session_id") if request.auth else None
        if session_id:
            PortalSession.objects.filter(
                pk=session_id,
                user=request.user,
                revoked_at__isnull=True,
            ).update(revoked_at=timezone.now(), revocation_reason="logout")
        _advance_user_session(request.user, request, revocation_reason="logout")
        return Response({"status": "ok"})


def _validate_setup_profile(request, role, saved_agency, new_password, agency_locked=None):
    required_fields = [
        "first_name", "last_name", "agency_head", "division", "position",
        "contact_number", "phone_number",
    ]
    agency_locked = role in INTERNAL_ACCOUNT_ROLES if agency_locked is None else bool(agency_locked)
    if not agency_locked:
        required_fields.append("agency")
    for field in ("first_name", "last_name"):
        error = _validate_person_name(request.data.get(field))
        if error:
            return None, Response({field: error}, status=400)
    missing = [field for field in required_fields if not str(request.data.get(field) or "").strip()]
    if missing:
        return None, Response({"detail": f"Missing required fields: {', '.join(missing)}"}, status=400)
    for field, pattern, message in (
        ("contact_number", r"02[0-9]{8}", "Enter a valid number: 02 xxxx xxxx"),
        ("phone_number", r"09[0-9]{9}", "Enter a valid number: 09xx xxx xxxx"),
    ):
        value = request.data.get(field)
        if not isinstance(value, str) or not re.fullmatch(pattern, value):
            return None, Response({field: message}, status=400)
    if agency_locked:
        if "agency" in request.data and not _same_saved_account_agency(request.data.get("agency"), saved_agency):
            return None, Response({"detail": "Agency is locked to the account's saved agency."}, status=400)
        agency = saved_agency
    else:
        agency = _normalize_account_agency(request.data.get("agency"))
        if not agency:
            return None, Response({"detail": "This is an invalid Agency"}, status=400)
    policy_error = _validate_password_policy(new_password)
    if policy_error:
        return None, Response({"detail": policy_error}, status=400)
    profile = {field: str(request.data.get(field) or "").strip() for field in required_fields if field != "agency"}
    profile["agency"] = agency
    # Registration exposes one canonical Agency / Office selection. Mirror the
    # normalized value into both legacy model fields so existing profile,
    # reporting, and export code remains compatible without divergent values.
    profile["office"] = agency
    return profile, None


class SetupPasswordView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token_value = (request.query_params.get("token") or "").strip()
        if not token_value:
            return Response({"detail": "Token is required."}, status=400)
        if token_value.startswith(REGISTRATION_INVITE_PREFIX):
            invitation = _registration_invitation(token_value)
            if not invitation:
                return Response({"detail": "Invitation is invalid, expired, or replaced. Ask an administrator to resend it."}, status=400)
            payload, _ = invitation
            role = payload["role"]
            assigned_agency = str(payload.get("agency") or ("RDC-NCR" if role in INTERNAL_ACCOUNT_ROLES else ""))
            agency_locked = bool(payload.get("agency_locked", role in INTERNAL_ACCOUNT_ROLES))
            return Response({
                "email": payload["email"],
                "setup_type": "invitation",
                "agency_locked": agency_locked,
                "agencies": _active_agency_options(),
                "profile": {"agency": assigned_agency},
            })
        token = PasswordSetupToken.objects.select_related("user").filter(token=token_value).first()
        if not token or not token.is_valid():
            return Response({"detail": "Token is invalid or expired."}, status=400)
        user = token.user
        if token.token.startswith(RESET_PASSWORD_TOKEN_PREFIX):
            return Response({"email": user.email, "setup_type": "password_reset"})
        return Response(
            {
                "email": user.email,
                "setup_type": "existing_account",
                "agency_locked": user.role in INTERNAL_ACCOUNT_ROLES,
                "agencies": _active_agency_options(),
                "profile": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "agency": user.agency,
                    "agency_head": user.agency_head,
                    "office": user.office,
                    "division": user.division,
                    "position": user.position,
                    "contact_number": user.contact_number,
                    "phone_number": user.phone_number,
                },
            }
        )

    def post(self, request):
        token_value = (request.data.get("token") or "").strip()
        new_password = request.data.get("new_password") or ""
        if not token_value:
            return Response({"detail": "Token is required."}, status=400)
        if token_value.startswith(REGISTRATION_INVITE_PREFIX):
            invitation = _registration_invitation(token_value)
            if not invitation:
                return Response({"detail": "Invitation is invalid, expired, or replaced. Ask an administrator to resend it."}, status=400)
            payload, activity = invitation
            role = payload["role"]
            assigned_agency = str(payload.get("agency") or ("RDC-NCR" if role in INTERNAL_ACCOUNT_ROLES else ""))
            agency_locked = bool(payload.get("agency_locked", role in INTERNAL_ACCOUNT_ROLES))
            profile, error = _validate_setup_profile(
                request, role, assigned_agency, new_password, agency_locked=agency_locked,
            )
            if error:
                return error
            try:
                with transaction.atomic():
                    if isinstance(activity, UserInvitation):
                        activity = UserInvitation.objects.select_for_update().get(pk=activity.pk)
                    else:
                        activity = UserActivity.objects.select_for_update().get(pk=activity.pk)
                    if not _registration_invitation(token_value):
                        return Response({"detail": "Invitation is no longer available."}, status=400)
                    invited_by = activity.invited_by if isinstance(activity, UserInvitation) else activity.user
                    user = User(
                        username=_build_unique_username(
                            payload["email"], f"{profile['first_name']} {profile['last_name']}".strip()
                        ),
                        email=payload["email"],
                        role=role,
                        created_by=invited_by,
                        is_staff=role == "admin",
                        is_active=False,
                        must_change_password=False,
                        last_password_change=timezone.now(),
                        **profile,
                    )
                    user.set_password(new_password)
                    user.save()
                    UserActivity.objects.create(
                        user=user, role=role, event="auth_password_setup",
                        ip_address=_client_ip(request)[:64],
                        location_hint=_location_hint(request)[:255],
                        details={"source": "invitation", "agency": user.agency},
                    )
                    UserActivity.objects.create(
                        user=user, role=role, event="registration_completed",
                        ip_address=_client_ip(request)[:64],
                        location_hint=_location_hint(request)[:255],
                        details={"email": user.email, "role": role, "is_active": False,
                                 "invitation_id": activity.id},
                    )
                    if isinstance(activity, UserInvitation):
                        activity.status = UserInvitation.STATUS_COMPLETED
                        activity.completed_at = timezone.now()
                        activity.save(update_fields=["status", "completed_at"])
                    _notify_many(
                        _admins(),
                        event_type="registration_awaiting_activation",
                        title="New account awaiting activation",
                        message=f"{_user_display_name(user)} ({user.email}) completed registration and is awaiting activation.",
                        actor=user,
                        link_path="/admin/users?tab=system-users",
                        dedupe_key=f"account:{user.id}:awaiting-activation",
                    )
            except IntegrityError:
                return Response({"detail": "Email already exists or this invitation has been used."}, status=400)
            return Response({"status": "ok", "account_status": "inactive", "requires_admin_activation": True})
        token = PasswordSetupToken.objects.select_related("user").filter(token=token_value).first()
        if not token or not token.is_valid():
            return Response({"detail": "Token is invalid or expired."}, status=400)
        if token.token.startswith(RESET_PASSWORD_TOKEN_PREFIX):
            policy_error = _validate_password_policy(new_password)
            if policy_error:
                return Response({"detail": policy_error}, status=400)
            with transaction.atomic():
                token = PasswordSetupToken.objects.select_for_update().select_related("user").get(pk=token.pk)
                if not token.is_valid():
                    return Response({"detail": "Token is invalid or expired."}, status=400)
                user = token.user
                user.set_password(new_password)
                user.must_change_password = False
                user.last_password_change = timezone.now()
                user.save(update_fields=["password", "must_change_password", "last_password_change"])
                _advance_user_session(user)
                PasswordSetupToken.objects.filter(
                    user=user, token__startswith=RESET_PASSWORD_TOKEN_PREFIX, used_at__isnull=True,
                ).update(used_at=timezone.now())
                UserActivity.objects.create(
                    user=user,
                    role=user.role,
                    event="auth_password_setup",
                    ip_address=_client_ip(request)[:64],
                    location_hint=_location_hint(request)[:255],
                    details={"source": "password_reset"},
                )
            return Response({"status": "ok"})
        user = token.user
        profile, error = _validate_setup_profile(request, user.role, user.agency, new_password)
        if error:
            return error
        for field, value in profile.items():
            setattr(user, field, value)
        user.set_password(new_password)
        user.must_change_password = False
        user.last_password_change = timezone.now()
        user.save(
            update_fields=[
                "first_name",
                "last_name",
                "agency",
                "agency_head",
                "office",
                "division",
                "position",
                "contact_number",
                "phone_number",
                "password",
                "must_change_password",
                "last_password_change",
            ]
        )
        _advance_user_session(user)
        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        UserActivity.objects.create(
            user=user,
            role=user.role,
            event="auth_password_setup",
            ip_address=_client_ip(request)[:64],
            location_hint=_location_hint(request)[:255],
            details={"source": "setup_token", "agency": user.agency},
        )
        return Response({"status": "ok"})


PROFILE_EDIT_FIELDS = {"first_name", "last_name", "agency_head", "office", "division", "position", "contact_number", "phone_number"}


def _profile_payload(user):
    activity = UserActivitySerializer(UserActivity.objects.filter(user=user).order_by("-created_at")[:10], many=True).data
    return {
        "id": user.id, "username": user.username,
        "first_name": user.first_name, "last_name": user.last_name,
        "email": user.email, "role": _frontend_role(user.role), "agency": user.agency,
        "agency_head": user.agency_head, "office": user.office, "division": user.division,
        "position": user.position, "contact_number": user.contact_number,
        "phone_number": user.phone_number, "date_joined": user.date_joined,
        "recent_activity": activity,
    }


def _profile_request_payload(item):
    return {
        "id": item.pk, "user_id": item.user_id, "user_name": _user_display_name(item.user),
        "user_email": item.user.email, "status": item.status, "created_at": item.created_at,
        "reviewed_at": item.reviewed_at, "reviewed_by": item.reviewed_by_id,
        "expires_at": item.expires_at, "used_at": item.used_at,
    }


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id=None):
        if user_id and user_id != request.user.pk and request.user.role != "admin":
            raise PermissionDenied("Only administrators can view other profiles.")
        user = User.objects.filter(pk=user_id or request.user.pk).first()
        if not user:
            raise Http404("Profile not found.")
        return Response(_profile_payload(user))

    def patch(self, request, user_id=None):
        if user_id and user_id != request.user.pk:
            raise PermissionDenied("Only the profile owner can edit it.")
        fields = set(request.data)
        if not fields or not fields.issubset(PROFILE_EDIT_FIELDS):
            return Response({"detail": "Only name, office, and contact fields may be edited."}, status=400)
        for field, pattern, message in (
            ("contact_number", r"02[0-9]{8}", "Enter a valid number: 02 xxxx xxxx"),
            ("phone_number", r"09[0-9]{9}", "Enter a valid number: 09xx xxx xxxx"),
        ):
            if field in fields:
                value = request.data.get(field)
                if not isinstance(value, str) or not re.fullmatch(pattern, value):
                    return Response({field: message}, status=400)
        for field in ("first_name", "last_name"):
            if field in fields:
                name_error = _validate_person_name(request.data.get(field))
                if name_error:
                    return Response({field: name_error}, status=400)
        with transaction.atomic():
            grant = ProfileEditRequest.objects.select_for_update().filter(
                user=request.user, status=ProfileEditRequest.STATUS_APPROVED,
                used_at__isnull=True, expires_at__gt=timezone.now(),
            ).order_by("-reviewed_at").first()
            if not grant:
                return Response({"detail": "An active administrator-approved profile edit is required."}, status=403)
            user = User.objects.select_for_update().get(pk=request.user.pk)
            for field in fields:
                value = request.data[field]
                if not isinstance(value, str) or len(value) > User._meta.get_field(field).max_length:
                    return Response({field: "Enter a valid value."}, status=400)
                setattr(user, field, value.strip())
            user.save(update_fields=list(fields))
            grant.status = ProfileEditRequest.STATUS_CONSUMED
            grant.used_at = timezone.now()
            grant.save(update_fields=["status", "used_at"])
            _log_activity(request, "profile_updated", details={"target_user_id": user.pk, "changed_fields": sorted(fields), "edit_request_id": grant.pk})
        return Response(_profile_payload(user))


class ProfileEditRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([_profile_request_payload(item) for item in ProfileEditRequest.objects.filter(user=request.user).select_related("user")[:10]])

    def post(self, request):
        existing = ProfileEditRequest.objects.filter(user=request.user, status="pending").first()
        if existing:
            return Response({"detail": "A profile edit request is already pending."}, status=409)
        grant = ProfileEditRequest.objects.filter(user=request.user, status="approved", used_at__isnull=True, expires_at__gt=timezone.now()).first()
        if grant:
            return Response({"detail": "You already have an unused profile edit approval."}, status=409)
        item = ProfileEditRequest.objects.create(user=request.user)
        _log_activity(request, "profile_edit_requested", details={"target_user_id": request.user.pk, "request_id": item.pk})
        return Response(_profile_request_payload(item), status=201)


class AdminProfileEditRequestView(APIView):
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    def get(self, request):
        items = ProfileEditRequest.objects.select_related("user", "reviewed_by").order_by("-created_at")[:100]
        return Response([_profile_request_payload(item) for item in items])


class AdminProfileEditDecisionView(APIView):
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    def post(self, request, request_id, decision):
        if decision not in {"approve", "reject"}:
            return Response({"detail": "Invalid decision."}, status=400)
        with transaction.atomic():
            item = ProfileEditRequest.objects.select_for_update().select_related("user").filter(pk=request_id).first()
            if not item:
                raise Http404("Profile edit request not found.")
            if item.status != ProfileEditRequest.STATUS_PENDING:
                return Response({"detail": "This request has already been reviewed."}, status=409)
            emergency = item.user_id == request.user.pk
            if emergency and User.objects.filter(role="admin", is_active=True).count() != 1:
                return Response({"detail": "Another administrator must review your request."}, status=403)
            item.status = ProfileEditRequest.STATUS_APPROVED if decision == "approve" else ProfileEditRequest.STATUS_REJECTED
            item.reviewed_at = timezone.now()
            item.reviewed_by = request.user
            item.expires_at = item.reviewed_at + timedelta(days=7) if decision == "approve" else None
            item.save(update_fields=["status", "reviewed_at", "reviewed_by", "expires_at"])
            _log_activity(request, "profile_edit_approved" if decision == "approve" else "profile_edit_rejected", details={"target_user_id": item.user_id, "request_id": item.pk, "emergency_self_approval": emergency})
        return Response(_profile_request_payload(item))


class AdminActivityView(APIView):
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    def get(self, request):
        qs = UserActivity.objects.select_related("user", "project").all()
        role_filter = (request.query_params.get("role") or "").strip()
        event_filter = (request.query_params.get("event") or "").strip()
        user_filter = (request.query_params.get("user") or "").strip()
        date_from_raw = (request.query_params.get("date_from") or "").strip()
        date_to_raw = (request.query_params.get("date_to") or "").strip()
        limit_raw = request.query_params.get("limit")
        offset_raw = request.query_params.get("offset")
        sort_by = (request.query_params.get("sort_by") or "").strip().lower()
        sort_direction = (request.query_params.get("sort_direction") or "asc").strip().lower()

        if role_filter:
            qs = qs.filter(role=role_filter)
        if event_filter:
            qs = qs.filter(event=event_filter)
        if user_filter:
            qs = qs.annotate(
                _joined_user_name=Concat("user__first_name", Value(" "), "user__last_name")
            )
            qs = qs.filter(
                Q(user__username__icontains=user_filter)
                | Q(user__first_name__icontains=user_filter)
                | Q(user__last_name__icontains=user_filter)
                | Q(_joined_user_name__icontains=user_filter)
                | Q(user__email__icontains=user_filter)
                | Q(actor_username__icontains=user_filter)
                | Q(actor_full_name__icontains=user_filter)
                | Q(details__attempted_email__icontains=user_filter)
                | Q(details__email__icontains=user_filter)
            )
        if date_from_raw:
            try:
                date_from = datetime.strptime(date_from_raw, "%Y-%m-%d").date()
                qs = qs.filter(created_at__date__gte=date_from)
            except ValueError:
                return Response({"detail": "date_from must use YYYY-MM-DD format."}, status=400)
        if date_to_raw:
            try:
                date_to = datetime.strptime(date_to_raw, "%Y-%m-%d").date()
                qs = qs.filter(created_at__date__lte=date_to)
            except ValueError:
                return Response({"detail": "date_to must use YYYY-MM-DD format."}, status=400)

        sort_fields = {
            "role": ("role",),
            "event": ("event",),
            "location": ("ip_address", "location_hint"),
            "timestamp": ("created_at",),
        }
        if sort_by == "user":
            qs = qs.annotate(
                _sort_user=Coalesce(
                    NullIf("actor_full_name", Value("")),
                    NullIf(Concat("user__first_name", Value(" "), "user__last_name"), Value(" ")),
                    NullIf("actor_username", Value("")),
                    "user__username",
                    Value(""),
                    output_field=CharField(),
                )
            )
            sort_fields["user"] = ("_sort_user",)
        elif sort_by in {"target", "project"}:
            qs = qs.annotate(
                _sort_target=Coalesce(
                    NullIf("project_title_snapshot", Value("")),
                    NullIf("project__name", Value("")),
                    NullIf(Cast("details__title", CharField()), Value("")),
                    NullIf(Cast("details__email", CharField()), Value("")),
                    NullIf(Cast("details__attempted_email", CharField()), Value("")),
                    NullIf(Cast("details__name", CharField()), Value("")),
                    NullIf(Cast("details__slug", CharField()), Value("")),
                    NullIf(Cast("details__key", CharField()), Value("")),
                    Value(""),
                    output_field=CharField(),
                )
            )
            sort_fields[sort_by] = ("_sort_target",)
        elif sort_by == "details":
            qs = qs.annotate(_sort_details=Cast("details", TextField()))
            sort_fields["details"] = ("_sort_details",)

        if sort_by in sort_fields and sort_direction in {"asc", "desc"}:
            prefix = "-" if sort_direction == "desc" else ""
            qs = qs.order_by(*(f"{prefix}{field}" for field in sort_fields[sort_by]), "id")
        else:
            qs = qs.order_by("-created_at", "-id")

        limit = 50
        if limit_raw:
            try:
                limit = max(1, min(200, int(limit_raw)))
            except Exception:
                limit = 50

        offset = 0
        if offset_raw:
            try:
                offset = max(0, int(offset_raw))
            except Exception:
                offset = 0

        total = qs.count()
        serializer = UserActivitySerializer(qs[offset : offset + limit], many=True)
        if (request.query_params.get("include_meta") or "").lower() in {"1", "true", "yes"}:
            return Response(
                {
                    "results": serializer.data,
                    "count": total,
                    "limit": limit,
                    "offset": offset,
                    "has_previous": offset > 0,
                    "has_next": offset + limit < total,
                    "event_options": sorted(UserActivity.objects.order_by().values_list("event", flat=True).distinct()),
                }
            )
        return Response(serializer.data)


class AgencyActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        include_meta = (request.query_params.get("include_meta") or "").lower() in {"1", "true", "yes"}
        limit = 10
        raw_limit = request.query_params.get("limit")
        if raw_limit:
            try:
                limit = max(1, min(100, int(raw_limit)))
            except Exception:
                limit = 10

        offset = 0
        raw_offset = request.query_params.get("offset")
        if raw_offset:
            try:
                offset = max(0, int(raw_offset))
            except Exception:
                offset = 0

        project_events = {"project_create", "project_update", "project_submit", "project_comment"}
        qs = UserActivity.objects.select_related("user", "project").filter(
            _contributor_project_scope(request.user, prefix="project__"),
            event__in=project_events,
        ).distinct().order_by("-created_at", "-id")
        total = qs.count()
        serializer = UserActivitySerializer(qs[offset : offset + limit], many=True)
        if include_meta:
            response = Response(
                {
                    "results": serializer.data,
                    "count": total,
                    "limit": limit,
                    "offset": offset,
                    "has_previous": offset > 0,
                    "has_next": offset + limit < total,
                }
            )
        else:
            response = Response(serializer.data)
        response["Cache-Control"] = "private, no-store"
        return response


def _get_public_projects_cache_version() -> str:
    """Database-derived version so every web worker observes a publish immediately."""
    state = Project.objects.filter(validated=True, archived=False, is_active=True).aggregate(
        count=Count("id"),
        updated_at=Max("updated_at"),
    )
    updated_at = state.get("updated_at")
    return f"{state.get('count') or 0}:{updated_at.isoformat() if updated_at else ''}"


def _etag(value) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f'"{hashlib.sha256(value.encode("utf-8")).hexdigest()}"'


def _conditional_public_response(request, payload, etag_seed=None):
    etag = _etag(payload if etag_seed is None else etag_seed)
    candidates = [value.strip() for value in request.META.get("HTTP_IF_NONE_MATCH", "").split(",")]
    response = Response(status=status.HTTP_304_NOT_MODIFIED) if etag in candidates else Response(payload)
    response["ETag"] = etag
    response["Cache-Control"] = PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL
    return response


def _hash_query(params: dict) -> str:
    # Stable key regardless of ordering.
    items = []
    for k in sorted(params.keys()):
        if k in {"_", "_ts", "_cms"}:
            continue
        items.append((k, str(params[k])))
    raw = urllib.parse.urlencode(items, doseq=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _filter_public_project_status(queryset, status_value):
    legacy_groups = {
        "not implemented": NOT_IMPLEMENTED_LEGACY_VALUES,
        "ongoing": ONGOING_LEGACY_VALUES,
    }
    aliases = legacy_groups.get(status_value.casefold())
    if aliases:
        selected = Q(profile_data__simplified_form__status__iexact=status_value)
        for alias in aliases:
            selected |= Q(profile_data__simplified_form__status__iexact=alias)
        return queryset.filter(selected)
    return queryset.filter(profile_data__simplified_form__status__iexact=status_value)


class PublicProjectsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only projects feed for the public website dashboard.
    Returns validated projects only (unless overridden by admin-only endpoints elsewhere).
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # Don't attempt JWT auth; avoids 401 on invalid Authorization header.
    serializer_class = PublicProjectSerializer

    def _base_queryset(self):
        endorsed_revisions = ProjectRevision.objects.filter(state="endorsed").order_by(
            "-endorsed_at", "-revision_number"
        )
        qs = Project.objects.filter(validated=True, archived=False, is_active=True).select_related(
            "primary_agency"
        ).prefetch_related("collaborating_agency_links__agency")
        if getattr(self, "action", "") == "list" and self.request.query_params.get("view") == "summary":
            latest_progress = endorsed_revisions.filter(revision_type="progress_update")[:1]
            return qs.annotate(
                _public_progress_update_count=Count(
                    "revisions",
                    filter=Q(revisions__state="endorsed", revisions__revision_type="progress_update"),
                )
            ).prefetch_related(
                Prefetch("revisions", queryset=endorsed_revisions[:1], to_attr="_public_latest_endorsed_revision"),
                Prefetch("revisions", queryset=latest_progress, to_attr="_public_latest_progress_revision"),
            )
        return qs.prefetch_related(
            Prefetch("revisions", queryset=endorsed_revisions, to_attr="_public_endorsed_revisions")
        )

    def get_serializer_class(self):
        if getattr(self, "action", "") == "list" and self.request.query_params.get("view") == "summary":
            return PublicProjectSummarySerializer
        return PublicProjectSerializer

    def _project_to_public_payload(self, project: Project) -> dict:
        return self.get_serializer(project).data

    def list(self, request, *args, **kwargs):
        version = _get_public_projects_cache_version()
        params = dict(request.query_params)
        cache_key = f"public_projects:list:v{PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION}:{version}:{_hash_query(params)}"
        etag_seed = f"projects-list:{PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION}:{version}:{_hash_query(params)}"
        if _etag(etag_seed) in [value.strip() for value in request.META.get("HTTP_IF_NONE_MATCH", "").split(",")]:
            return _conditional_public_response(request, [], etag_seed=etag_seed)
        cached = cache.get(cache_key)
        if cached is not None:
            return _conditional_public_response(request, cached, etag_seed=etag_seed)

        qs = self._base_queryset().order_by("-updated_at")

        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(description__icontains=q) | Q(agency__icontains=q)
                | Q(collaborating_agency_links__agency__code__icontains=q)
                | Q(collaborating_agency_links__agency__name__icontains=q)
            ).distinct()

        agency = (request.query_params.get("agency") or "").strip()
        if agency and agency.lower() != "all":
            qs = qs.filter(
                Q(agency__iexact=agency) | Q(profile_data__simplified_form__agencyName__iexact=agency)
                | Q(collaborating_agency_links__agency__code__iexact=agency)
                | Q(collaborating_agency_links__agency__name__iexact=agency)
            ).distinct()

        year_raw = (request.query_params.get("year") or "").strip()
        if year_raw and year_raw.lower() != "all":
            try:
                year = int(year_raw)
                qs = qs.filter(Q(year=year) | Q(profile_data__simplified_form__startYear=str(year)))
            except Exception:
                pass

        status_raw = (request.query_params.get("status") or "").strip()
        if status_raw and status_raw.lower() != "all":
            qs = _filter_public_project_status(qs, status_raw)

        # LGU filter is computed (from location text), so filter in Python after serialization.
        lgu_filter = (request.query_params.get("lgu") or "").strip()
        if lgu_filter.lower() == "unspecified":
            lgu_filter = "Unspecified"

        limit = 200
        offset = 0
        try:
            if request.query_params.get("limit"):
                limit = max(1, min(500, int(request.query_params.get("limit") or "200")))
            if request.query_params.get("offset"):
                offset = max(0, int(request.query_params.get("offset") or "0"))
        except Exception:
            limit = 200
            offset = 0

        # If we filter by computed LGU, do it before applying offset/limit so results are correct.
        if lgu_filter and lgu_filter.lower() != "all":
            all_payload = [self._project_to_public_payload(p) for p in qs]
            if lgu_filter == "Unspecified":
                filtered_payload = [p for p in all_payload if not p.get("lgus")]
            else:
                filtered_payload = [p for p in all_payload if lgu_filter in (p.get("lgus") or [])]
            payload = filtered_payload[offset : offset + limit]
        else:
            qs = qs[offset : offset + limit]
            payload = [self._project_to_public_payload(p) for p in qs]

        cache.set(cache_key, payload, timeout=PUBLIC_PROJECTS_CACHE_TTL_SECONDS)
        return _conditional_public_response(request, payload, etag_seed=etag_seed)

    def retrieve(self, request, *args, **kwargs):
        project = self._base_queryset().filter(pk=kwargs.get("pk")).first()
        if not project:
            return Response({"detail": "Not found."}, status=404)
        payload = self._project_to_public_payload(project)
        return _conditional_public_response(request, payload)


class PublicProjectsStatsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't attempt JWT auth.

    def get(self, request):
        version = _get_public_projects_cache_version()
        params = dict(request.query_params)
        cache_key = f"public_projects:stats:v{PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION}:{version}:{_hash_query(params)}"
        etag_seed = f"projects-stats:{PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION}:{version}:{_hash_query(params)}"
        if _etag(etag_seed) in [value.strip() for value in request.META.get("HTTP_IF_NONE_MATCH", "").split(",")]:
            return _conditional_public_response(request, {}, etag_seed=etag_seed)
        cached = cache.get(cache_key)
        if cached is not None:
            return _conditional_public_response(request, cached, etag_seed=etag_seed)

        qs = Project.objects.filter(validated=True, archived=False, is_active=True)

        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(agency__icontains=q))

        agency = (request.query_params.get("agency") or "").strip()
        if agency and agency.lower() != "all":
            qs = qs.filter(Q(agency__iexact=agency) | Q(profile_data__simplified_form__agencyName__iexact=agency))

        year_raw = (request.query_params.get("year") or "").strip()
        if year_raw and year_raw.lower() != "all":
            try:
                year = int(year_raw)
                qs = qs.filter(Q(year=year) | Q(profile_data__simplified_form__startYear=str(year)))
            except Exception:
                pass

        status_raw = (request.query_params.get("status") or "").strip()
        if status_raw and status_raw.lower() != "all":
            qs = _filter_public_project_status(qs, status_raw)

        projects = list(qs)
        lgu_filter = (request.query_params.get("lgu") or "").strip()
        if lgu_filter and lgu_filter.lower() != "all":
            def project_location(project):
                profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
                simplified = profile_data.get("simplified_form")
                simplified = simplified if isinstance(simplified, dict) else {}
                return simplified.get("location")

            if lgu_filter.lower() == "unspecified":
                projects = [
                    p
                    for p in projects
                    if not derive_ncr_lgus(project_location(p))
                ]
            else:
                projects = [
                    p
                    for p in projects
                    if lgu_filter
                    in derive_ncr_lgus(project_location(p))
                ]

        total_budget = 0
        by_status = {}
        by_agency = {}
        by_lgu = {}
        by_year = {}
        unspecified = 0
        last_updated_at = None

        for p in projects:
            total_budget += int(getattr(p, "budget", 0) or 0)
            if not last_updated_at or (getattr(p, "updated_at", None) and p.updated_at > last_updated_at):
                last_updated_at = p.updated_at
            sf = {}
            if isinstance(p.profile_data, dict) and isinstance(p.profile_data.get("simplified_form"), dict):
                sf = p.profile_data.get("simplified_form") or {}
            impl_status = canonical_implementation_status(
                sf.get("status") or getattr(p, "status", "")
            ) or "Unspecified"
            agency_name = str(sf.get("agencyName") or getattr(p, "agency", "") or "").strip() or "Other"
            location_raw = format_project_locations(sf.get("location"))
            lgus = derive_ncr_lgus(location_raw)
            if not lgus:
                unspecified += 1

            year_value = None
            try:
                year_value = int(str(sf.get("startYear") or "").strip())
            except Exception:
                year_value = getattr(p, "year", None)
            if isinstance(year_value, int) and 1900 <= year_value <= 2200:
                by_year[str(year_value)] = by_year.get(str(year_value), 0) + 1

            by_status[impl_status] = by_status.get(impl_status, 0) + 1
            by_agency[agency_name] = by_agency.get(agency_name, 0) + 1
            for lgu in lgus:
                by_lgu[lgu] = by_lgu.get(lgu, 0) + 1

        payload = {
            "total_projects": len(projects),
            "total_budget": total_budget,
            "by_status": by_status,
            "by_agency": by_agency,
            "by_lgu": by_lgu,
            "by_year": by_year,
            "unspecified_location_count": unspecified,
            "last_updated_at": last_updated_at.isoformat() if last_updated_at else None,
        }

        cache.set(cache_key, payload, timeout=PUBLIC_PROJECTS_CACHE_TTL_SECONDS)
        return _conditional_public_response(request, payload, etag_seed=etag_seed)
