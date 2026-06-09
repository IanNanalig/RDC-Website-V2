import json
import os
import re
import difflib
import urllib.parse
import urllib.request
import hashlib
from copy import deepcopy
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.db import connection, transaction
from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .models import (
    AccessRequest,
    PasswordResetRequest,
    PasswordSetupToken,
    ProjectPriorityAnalysis,
    Project,
    ProjectComment,
    ProjectRevision,
    PublicChatFAQ,
    PublicChatInteraction,
    PublicChatKnowledgeGap,
    PublicContent,
    SystemSetting,
    User,
    UserActivity,
)
from .serializers import (
    AccessRequestSerializer,
    PasswordResetRequestSerializer,
    ProjectCommentSerializer,
    PublicChatKnowledgeGapSerializer,
    PublicProjectSerializer,
    ProjectSerializer,
    ProjectRevisionSerializer,
    UserActivitySerializer,
    UserSerializer,
    ProjectPriorityAnalysisSerializer,
)
from .public_summary import build_public_summary
from .priority_scoring import analyze_project, confirm_analysis, has_matching_confirmation
from .utils import derive_ncr_lgus


ENCODING_WINDOW_KEY = "portal_encoding_window"
PROGRESS_UPDATE_WINDOW_KEY = "portal_progress_update_window"
PASSWORD_SETUP_TTL_HOURS = 24
PASSWORD_RESET_WINDOW_SECONDS = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_WINDOW", 3600))
PASSWORD_RESET_LIMIT_EMAIL = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_EMAIL", 2))
PASSWORD_RESET_LIMIT_IP = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_IP", 5))

PUBLIC_CHAT_MAX_SUGGESTIONS = 6
PUBLIC_CHAT_MIN_SCORE = 1.0
PUBLIC_CHAT_DIRECT_CONFIDENCE = 0.62
PUBLIC_CHAT_RELATED_CONFIDENCE = 0.60
PUBLIC_PROJECTS_CACHE_TTL_SECONDS = 3600
PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL = "public, max-age=0, must-revalidate"
PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION = 3
PUBLIC_PROJECTS_CACHE_VERSION_KEY = "public_projects:version"


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


def _build_unique_username(email: str, full_name: str = ""):
    local = (email or "").split("@")[0].strip().lower()
    local = re.sub(r"[^a-z0-9._-]+", "", local)
    if not local:
        local = re.sub(r"[^a-z0-9]+", "", (full_name or "").lower()) or "user"
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


def _advance_user_session(user, request=None):
    previous_version = int(getattr(user, "session_version", 0) or 0)
    user.session_version = previous_version + 1
    user.last_session_at = timezone.now()
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


def _issue_session_tokens(user):
    refresh = RefreshToken.for_user(user)
    refresh["session_version"] = int(user.session_version or 0)
    access = refresh.access_token
    access["session_version"] = int(user.session_version or 0)
    return str(access), str(refresh)


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


def _get_window_config(key):
    default = {
        "configured": False,
        "config_error": False,
        "enabled": False,
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


def _send_setup_email(user: User, token: PasswordSetupToken, purpose: str = "create"):
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    link = f"{frontend_base}/setup-password?token={token.token}"
    is_reset = purpose == "reset"
    subject = "RDC Portal Password Reset" if is_reset else "RDC Portal Account Setup"
    if is_reset:
        message = (
            "A password reset was approved for your RDC Portal account.\n\n"
            "Please click the link below to complete your profile and set a new password (valid for 24 hours):\n"
            f"{link}\n\n"
            "If you did not request this reset, please contact the RDC Portal administrator immediately."
        )
    else:
        message = (
            "Your RDC Portal account has been created.\n\n"
            "Please click the link below to complete your profile and set your password (valid for 24 hours):\n"
            f"{link}\n\n"
            "If you did not request this account, please contact the RDC Portal administrator."
        )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


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


def _validate_password_policy(password: str):
    if len(password) < 12:
        return "Password must be at least 12 characters."
    if not re.search(r"[A-Z]", password):
        return "Password must include an uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must include a lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must include a number."
    if not re.search(r"[\\W_]", password):
        return "Password must include a symbol."
    return ""


SYSTEM_MANAGED_PROFILE_KEYS = {
    "validator_review",
    "contributor_snapshot",
    "public_summary",
    "public_summary_override",
    "simplified_form_meta",
}


def _strip_validator_meta(profile_data):
    if not isinstance(profile_data, dict):
        return {}
    return {
        key: value
        for key, value in profile_data.items()
        if key not in SYSTEM_MANAGED_PROFILE_KEYS
    }


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
            if not path and key in SYSTEM_MANAGED_PROFILE_KEYS:
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
    start, end = (start, end) if start <= end else (end, start)
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
        if key in ("fundingRequirementByYear", "actualFundingByYear") and isinstance(value, dict):
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
        display_name = getattr(user, "full_name", "").strip() or user.get_full_name() or user.username
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
            if obj.created_by_id == request.user.id:
                return True
            if role in ("staff", "employee"):
                user_agency = (getattr(request.user, "agency", "") or "").strip().lower()
                project_agency = (getattr(obj, "agency", "") or "").strip().lower()
                return bool(user_agency and user_agency == project_agency)
            return False
        if obj.created_by_id == request.user.id:
            return True
        if role in ("staff", "employee") and getattr(obj, "status", "") == "planning":
            user_agency = (getattr(request.user, "agency", "") or "").strip().lower()
            project_agency = (getattr(obj, "agency", "") or "").strip().lower()
            return bool(user_agency and user_agency == project_agency)
        if role in ("staff", "employee") and getattr(view, "action", "") == "start_update":
            user_agency = (getattr(request.user, "agency", "") or "").strip().lower()
            project_agency = (getattr(obj, "agency", "") or "").strip().lower()
            return bool(user_agency and user_agency == project_agency)
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


class BaseProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, ProjectPermission]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", "")
        if role == "admin":
            return Project.objects.all().order_by("-created_at")
        if role == "validator":
            return Project.objects.filter(Q(status="proposed") | Q(status="planning")).order_by("-created_at")
        return Project.objects.filter(created_by=user).order_by("-created_at")

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        project = self.get_object()
        if project.created_by_id != request.user.id and request.user.role != "admin":
            raise PermissionDenied("Only owner or admin can submit")
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
            _log_activity(request, "project_submit", project, {"status": project.status})
        return Response({"status": project.status})

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        project = self.get_object()
        role = getattr(request.user, "role", "")
        if role not in ("validator", "admin"):
            raise PermissionDenied("Only validator/admin can validate")

        action_value = (request.data.get("action") or "").lower()
        profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
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
        if incoming_edited is None:
            existing_review = profile_data.get("validator_review")
            if isinstance(existing_review, dict) and isinstance(existing_review.get("working_copy"), dict):
                edited_profile = existing_review.get("working_copy")
            else:
                edited_profile = deepcopy(contributor_snapshot)
        else:
            if not isinstance(incoming_edited, dict):
                return Response({"detail": "edited_profile_data must be a JSON object"}, status=400)
            edited_profile = incoming_edited

        funding_error = _validate_simplified_funding(edited_profile)
        if funding_error:
            return Response({"detail": funding_error}, status=400)

        edited_fields = _validator_edited_fields(contributor_snapshot, edited_profile)
        review_notes = str(request.data.get("comment") or request.data.get("notes") or "").strip()
        reviewed_at = timezone.now().isoformat()
        update_fields = ["profile_data", "updated_at"]

        warning = ""
        if action_value in ("save_draft", "draft"):
            review_state = "draft"
            project.validated = False
            event = "validator_draft"
        elif action_value in ("save_reviewed", "reviewed", "review", "save"):
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

        profile_data["validator_review"] = {
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
        }
        if warning:
            details["warning"] = warning
        _log_activity(request, event, project, details)
        return Response(
            {
                "status": project.status,
                "review_status": review_state,
                "edited": len(edited_fields) > 0,
                "edited_fields_count": len(edited_fields),
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
        analyses = project.priority_analyses.select_related("validator", "rule_set").prefetch_related(
            "confirmations__validator"
        )
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
        if project.status not in ("proposed", "planning"):
            return Response({"detail": "Priority analysis is available before endorsement only."}, status=400)

        incoming_snapshot = request.data.get("edited_profile_data")
        if incoming_snapshot is not None and not isinstance(incoming_snapshot, dict):
            return Response({"detail": "edited_profile_data must be a JSON object."}, status=400)
        profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
        existing_review = profile_data.get("validator_review")
        if isinstance(incoming_snapshot, dict):
            snapshot = incoming_snapshot
        elif isinstance(existing_review, dict) and isinstance(existing_review.get("working_copy"), dict):
            snapshot = existing_review["working_copy"]
        else:
            snapshot = profile_data.get("contributor_snapshot")
            if not isinstance(snapshot, dict):
                snapshot = _strip_validator_meta(profile_data)
        supplements = request.data.get("supplements")
        if not isinstance(supplements, dict):
            supplements = {}
        analysis, reused = analyze_project(project, request.user, snapshot, supplements)
        _log_activity(
            request,
            "priority_analysis_reused" if reused else "priority_analysis_run",
            project,
            {
                "analysis_id": analysis.id,
                "score": float(analysis.base_score),
                "priority": analysis.suggested_priority,
                "reused": reused,
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
        try:
            analysis = project.priority_analyses.get(pk=analysis_id)
        except ProjectPriorityAnalysis.DoesNotExist:
            return Response({"detail": "Priority analysis not found."}, status=404)
        try:
            confirmation = confirm_analysis(
                analysis,
                request.user,
                request.data.get("adjusted_scores"),
                str(request.data.get("final_priority") or analysis.suggested_priority),
                request.data.get("override_rationale"),
                request.data.get("confirmed_flags"),
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
                "updated_by": getattr(request.user, "full_name", "").strip()
                or request.user.get_full_name()
                or request.user.username,
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
        project = self.get_object()
        project.archived = True
        project.is_active = False
        project.save(update_fields=["archived", "is_active", "updated_at"])
        _log_activity(request, "project_archive", project, {"archived": True})
        return Response({"status": "archived"})

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        project = self.get_object()
        role = getattr(request.user, "role", "")
        if role not in ("admin", "validator", "staff"):
            raise PermissionDenied("Unauthorized")
        if role == "staff":
            user_agency = (request.user.agency or "").strip()
            project_agency = (project.agency or "").strip()
            if not user_agency or user_agency.lower() != project_agency.lower():
                raise PermissionDenied("Only same-agency contributors can access comments.")

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
        serializer = ProjectCommentSerializer(comment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can delete projects")
        return super().destroy(request, *args, **kwargs)


class ProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()


class EmployeeProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()
    permission_classes = [IsAuthenticated, EmployeeRolePermission, ProjectPermission]

    def get_queryset(self):
        agency = (self.request.user.agency or "").strip()
        if agency:
            return Project.objects.filter(agency__iexact=agency).order_by("-created_at")
        return Project.objects.filter(created_by=self.request.user).order_by("-created_at")

    def _ensure_encoding_open(self):
        state = _resolve_encoding_window_state()
        if not state["is_open"]:
            raise PermissionDenied(state["message"])

    def _ensure_progress_update_open(self):
        state = _resolve_progress_update_window_state()
        if not state["is_open"]:
            raise PermissionDenied(state["message"])

    def _ensure_mutable_project(self, project):
        if project.status != "planning":
            raise PermissionDenied("Submitted/validated projects are view-only for contributors.")

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
        self._ensure_encoding_open()
        project = self.get_object()
        self._ensure_mutable_project(project)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        changed_fields = []
        profile_data = data.get("profile_data")
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except Exception:
                profile_data = None
        if isinstance(profile_data, dict):
            updated_profile, changed_fields, changes = _apply_simplified_meta(
                profile_data, project.profile_data or {}, request.user
            )
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
        self._ensure_encoding_open()
        project = self.get_object()
        self._ensure_mutable_project(project)
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        changed_fields = []
        profile_data = data.get("profile_data")
        if isinstance(profile_data, str):
            try:
                profile_data = json.loads(profile_data)
            except Exception:
                profile_data = None
        if isinstance(profile_data, dict):
            updated_profile, changed_fields, changes = _apply_simplified_meta(
                profile_data, project.profile_data or {}, request.user
            )
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
        self._ensure_encoding_open()
        self._ensure_mutable_project(self.get_object())
        return super().submit(request, pk=pk)

    @action(detail=True, methods=["post"], url_path="start-update")
    def start_update(self, request, pk=None):
        self._ensure_progress_update_open()
        project = self.get_object()
        if not project.validated:
            return Response({"detail": "Only endorsed public projects can receive progress updates."}, status=400)
        if _is_completed_rdip_project(project):
            return Response({"detail": "Completed projects are read-only for progress updates."}, status=400)

        active = project.revisions.filter(
            revision_type="progress_update",
            state__in=["draft", "submitted", "validator_draft", "reviewed"],
        ).order_by("-updated_at").first()
        if active:
            return Response(ProjectRevisionSerializer(active).data)

        current = _ensure_public_revision(project, request.user)
        base_profile = deepcopy(current.profile_data_snapshot if current else project.profile_data)
        if not isinstance(base_profile, dict):
            base_profile = {}
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
        return Response(ProjectRevisionSerializer(revision).data, status=201)


class ProjectRevisionViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectRevisionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        role = getattr(self.request.user, "role", "")
        qs = ProjectRevision.objects.select_related(
            "project",
            "created_by",
            "submitted_by",
            "reviewed_by",
            "endorsed_by",
        ).order_by("-updated_at")
        if role == "admin":
            return qs
        if role == "validator":
            scope = (self.request.query_params.get("scope") or "queue").strip().lower()
            if scope == "history":
                return qs.filter(state__in=["reviewed", "endorsed", "rejected", "superseded"])
            return qs.filter(state__in=["submitted", "validator_draft", "reviewed"])
        if role in ("staff", "employee"):
            agency = (self.request.user.agency or "").strip()
            if not agency:
                return qs.none()
            return qs.filter(project__agency__iexact=agency)
        return qs.none()

    def _same_agency_or_admin_validator(self, revision):
        role = getattr(self.request.user, "role", "")
        if role in ("admin", "validator"):
            return True
        user_agency = (self.request.user.agency or "").strip().lower()
        project_agency = (revision.project.agency or "").strip().lower()
        return bool(user_agency and user_agency == project_agency)

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
        if revision.revision_type != "progress_update" or revision.state != "draft":
            raise PermissionDenied("Only draft progress updates can be edited by contributors.")
        if _is_completed_rdip_project(revision.project):
            raise PermissionDenied("Completed projects are read-only for progress updates.")
        self._ensure_progress_update_open()

    def update(self, request, *args, **kwargs):
        revision = self.get_object()
        self._ensure_contributor_editable(revision)
        profile_data = request.data.get("profile_data") or request.data.get("profile_data_snapshot")
        if not isinstance(profile_data, dict):
            return Response({"detail": "profile_data is required."}, status=400)
        funding_error = _validate_simplified_funding(profile_data)
        if funding_error:
            return Response({"detail": funding_error}, status=400)
        updated_profile, changed_fields, changes = _apply_simplified_meta(
            profile_data,
            revision.profile_data_snapshot or {},
            request.user,
        )
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

        edited_profile = request.data.get("edited_profile_data")
        if edited_profile is None:
            edited_profile = revision.profile_data_snapshot
        if not isinstance(edited_profile, dict):
            return Response({"detail": "edited_profile_data must be a JSON object."}, status=400)
        funding_error = _validate_simplified_funding(edited_profile)
        if funding_error:
            return Response({"detail": funding_error}, status=400)

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
            },
        )
        return Response(ProjectRevisionSerializer(revision).data)


class ValidatorProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()
    permission_classes = [IsAuthenticated, ValidatorRolePermission, ProjectPermission]

    def get_queryset(self):
        user = self.request.user
        all_projects = Project.objects.all().order_by("-created_at")
        scope = (self.request.query_params.get("scope") or "").strip().lower()
        def review_status_for(project):
            pd = project.profile_data if isinstance(project.profile_data, dict) else {}
            vr = pd.get("validator_review")
            if not isinstance(vr, dict):
                return ""
            status = str(vr.get("review_status") or "").lower()
            return "endorsed" if status == "validated" else status

        def reviewed_by_validator(project):
            pd = project.profile_data if isinstance(project.profile_data, dict) else {}
            vr = pd.get("validator_review")
            if not isinstance(vr, dict):
                return False
            try:
                reviewed_by_id = int(vr.get("reviewed_by_id"))
            except (TypeError, ValueError):
                return False
            review_status = review_status_for(project)
            return reviewed_by_id == user.id and review_status in ("draft", "reviewed", "endorsed", "rejected")

        if self.action == "list":
            if scope == "history":
                ids = [
                    p.id
                    for p in all_projects
                    if reviewed_by_validator(p)
                    and review_status_for(p) in ("reviewed", "endorsed", "rejected")
                ]
                return Project.objects.filter(id__in=ids).order_by("-updated_at")
            draft_review_ids = [
                p.id
                for p in all_projects
                if reviewed_by_validator(p)
                and review_status_for(p) in ("draft", "reviewed")
            ]
            return Project.objects.filter(
                Q(status="proposed") | Q(id__in=draft_review_ids)
            ).order_by("-created_at")

        allowed_ids = [p.id for p in all_projects if p.status == "proposed" or reviewed_by_validator(p)]
        return Project.objects.filter(id__in=allowed_ids).order_by("-created_at")

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("Use validator review actions instead of direct project edit.")

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied("Use validator review actions instead of direct project edit.")

    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied("Only admin can delete projects")


class AdminProjectViewSet(BaseProjectViewSet):
    queryset = Project.objects.all()
    permission_classes = [IsAuthenticated, AdminOnlyPermission, ProjectPermission]

    def get_queryset(self):
        return Project.objects.all().order_by("-created_at")


class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, AdminOnlyPermission]

    @action(detail=True, methods=["post"])
    def set_active(self, request, pk=None):
        user = self.get_object()
        active = bool(request.data.get("active", True))
        if user.id == request.user.id and not active:
            return Response({"detail": "You cannot deactivate your own account."}, status=400)
        user.is_active = active
        user.save(update_fields=["is_active"])
        return Response({"id": user.id, "is_active": user.is_active})

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        if not user.email:
            return Response({"detail": "User has no email set."}, status=400)
        user.set_unusable_password()
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        _advance_user_session(user)
        token = PasswordSetupToken.objects.create(
            user=user,
            token=get_random_string(48),
            expires_at=timezone.now() + timedelta(hours=PASSWORD_SETUP_TTL_HOURS),
        )
        _send_setup_email(user, token)
        _log_activity(request, "auth_reset_approve", details={"email": user.email, "source": "admin_reset"})
        return Response({"id": user.id, "setup_link_sent": True})

    def create(self, request, *args, **kwargs):
        email = (request.data.get("email") or "").strip().lower()
        role = (request.data.get("role") or "").strip().lower()
        if not email:
            return Response({"detail": "Email is required."}, status=400)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": "Email already exists."}, status=400)
        if role == "contributor":
            role = "staff"
        if role not in ("admin", "validator", "staff"):
            return Response({"detail": "Invalid role."}, status=400)

        username = _build_unique_username(email)
        user = User(
            username=username,
            email=email,
            role=role,
            is_staff=role == "admin",
            created_by=request.user,
            must_change_password=True,
        )
        user.set_unusable_password()
        user.save()

        token = PasswordSetupToken.objects.create(
            user=user,
            token=get_random_string(48),
            expires_at=timezone.now() + timedelta(hours=PASSWORD_SETUP_TTL_HOURS),
        )
        try:
            _send_setup_email(user, token, purpose="create")
        except Exception as exc:
            token.delete()
            user.delete()
            return Response({"detail": f"Failed to send email: {exc}"}, status=500)

        _log_activity(request, "user_create", details={"email": user.email, "role": user.role})
        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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

        username = _build_unique_username(access_request.email, access_request.full_name)
        role = "validator" if access_request.requested_role == "validator" else "staff"

        user = User(
            username=username,
            email=access_request.email,
            role=role,
        )
        user.is_staff = role == "admin"
        user.set_unusable_password()
        user.must_change_password = True
        user.save()

        access_request.status = "approved"
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()
        access_request.review_notes = request.data.get("review_notes", "")
        access_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])

        token = PasswordSetupToken.objects.create(
            user=user,
            token=get_random_string(48),
            expires_at=timezone.now() + timedelta(hours=PASSWORD_SETUP_TTL_HOURS),
        )
        _send_setup_email(user, token, purpose="reset")

        return Response(
            {
                "status": "approved",
                "created_user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": "contributor" if user.role == "staff" else user.role,
                    "setup_link_sent": True,
                },
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
        return Response({"status": "rejected"})


class PasswordResetRequestViewSet(viewsets.ModelViewSet):
    queryset = PasswordResetRequest.objects.all().order_by("-created_at")
    serializer_class = PasswordResetRequestSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsAuthenticated(), AdminOnlyPermission()]

    def create(self, request, *args, **kwargs):
        email = (request.data.get("email") or "").strip().lower()
        captcha_token = (request.data.get("captcha_token") or "").strip()
        if not email:
            return Response({"detail": "Email is required."}, status=400)

        ip = _client_ip(request)
        if _rate_limit(f"pwdreset:ip:{ip}", PASSWORD_RESET_LIMIT_IP, PASSWORD_RESET_WINDOW_SECONDS):
            return Response({"detail": "Too many requests. Please try again later."}, status=429)
        if _rate_limit(f"pwdreset:email:{email}", PASSWORD_RESET_LIMIT_EMAIL, PASSWORD_RESET_WINDOW_SECONDS):
            return Response({"detail": "Too many requests. Please try again later."}, status=429)

        if getattr(settings, "TURNSTILE_REQUIRED", False):
            if not _verify_turnstile(captcha_token, ip):
                return Response({"detail": "Captcha verification failed."}, status=400)

        user = User.objects.filter(email__iexact=email).first()
        if user:
            PasswordResetRequest.objects.create(
                email=email,
                user=user,
                requested_ip=ip,
                requested_user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
            _log_activity(request, "auth_reset_request", details={"email": email})

        return Response(
            {"detail": "If this email is registered, your request has been sent to the administrator."},
            status=201,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        with transaction.atomic():
            reset_request = PasswordResetRequest.objects.select_for_update().filter(id=pk).first()
            if not reset_request or reset_request.status != "pending":
                return Response({"detail": "Request already reviewed."}, status=400)
            user = reset_request.user
            if not user or not user.email:
                reset_request.status = "rejected"
                reset_request.reviewed_by = request.user
                reset_request.reviewed_at = timezone.now()
                reset_request.review_notes = "No matching user/email."
                reset_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
                return Response({"detail": "No matching user/email."}, status=400)

            user.set_unusable_password()
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])
            _advance_user_session(user)
            token = PasswordSetupToken.objects.create(
                user=user,
                token=get_random_string(48),
                expires_at=timezone.now() + timedelta(hours=PASSWORD_SETUP_TTL_HOURS),
            )
            reset_request.status = "approved"
            reset_request.reviewed_by = request.user
            reset_request.reviewed_at = timezone.now()
            reset_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        _send_setup_email(user, token, purpose="reset")
        _log_activity(request, "auth_reset_approve", details={"email": reset_request.email})
        return Response({"status": "approved", "setup_link_sent": True})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        with transaction.atomic():
            reset_request = PasswordResetRequest.objects.select_for_update().filter(id=pk).first()
            if not reset_request or reset_request.status != "pending":
                return Response({"detail": "Request already reviewed."}, status=400)
            reset_request.status = "rejected"
            reset_request.reviewed_by = request.user
            reset_request.reviewed_at = timezone.now()
            reset_request.review_notes = str(request.data.get("review_notes") or "")
            reset_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"])
        _log_activity(request, "auth_reset_reject", details={"email": reset_request.email})
        return Response({"status": "rejected"})


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

    def get(self, request):
        state = _resolve_progress_update_window_state()
        role = getattr(request.user, "role", "")
        can_update = state["is_open"] or role in ("admin", "validator")
        return Response(
            {
                **state,
                "can_encode": can_update,
                "can_update": can_update,
            }
        )

    def post(self, request):
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only admin can update progress update window.")
        enabled = bool(request.data.get("enabled", False))
        start_at = str(request.data.get("start_at") or "").strip()
        end_at = str(request.data.get("end_at") or "").strip()

        if enabled and (not start_at or not end_at):
            return Response({"detail": "Start and end date are required for scheduled progress updates."}, status=400)
        if enabled:
            try:
                parsed_start = _parse_iso_datetime(start_at)
                parsed_end = _parse_iso_datetime(end_at)
            except (TypeError, ValueError):
                return Response({"detail": "Progress update schedule dates are invalid."}, status=400)
            if not parsed_start or not parsed_end or parsed_start >= parsed_end:
                return Response({"detail": "Start date must be earlier than end date."}, status=400)

        previous = _resolve_progress_update_window_state()
        payload = {"enabled": enabled, "start_at": start_at, "end_at": end_at}
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
        return Response({**current, "can_encode": current["is_open"], "can_update": current["is_open"]})


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, "role", "")
        if role == "admin":
            all_projects = Project.objects.all()
            reviewed_projects = 0
            validator_edited_projects = 0
            review_draft = 0
            review_reviewed = 0
            review_endorsed = 0
            for project in all_projects:
                pd = project.profile_data if isinstance(project.profile_data, dict) else {}
                vr = pd.get("validator_review")
                if isinstance(vr, dict):
                    if str(vr.get("review_status") or "").lower() == "reviewed":
                        reviewed_projects += 1
                    if bool(vr.get("edited")):
                        validator_edited_projects += 1
                    status = str(vr.get("review_status") or "").lower()
                    if status == "draft":
                        review_draft += 1
                    elif status == "reviewed":
                        review_reviewed += 1
                    elif status == "endorsed":
                        review_endorsed += 1
            admin_users = User.objects.filter(role="admin").count()
            validator_users = User.objects.filter(role="validator").count()
            contributor_users = User.objects.filter(role="staff").count()
            data = {
                "total_projects": all_projects.count(),
                "draft_projects": all_projects.filter(status="planning").count(),
                "pending_projects": all_projects.filter(status="proposed").count(),
                "approved_projects": all_projects.filter(status="completed").count(),
                "archived_projects": all_projects.filter(archived=True).count(),
                "reviewed_projects": reviewed_projects,
                "validator_edited_projects": validator_edited_projects,
                "users": User.objects.count(),
                "admin_users": admin_users,
                "validator_users": validator_users,
                "contributor_users": contributor_users,
                "review_draft": review_draft,
                "review_reviewed": review_reviewed,
                "review_endorsed": review_endorsed,
            }
        elif role == "validator":
            review_draft = 0
            review_reviewed = 0
            review_endorsed = 0
            for project in Project.objects.all():
                pd = project.profile_data if isinstance(project.profile_data, dict) else {}
                vr = pd.get("validator_review")
                if not isinstance(vr, dict):
                    continue
                status = str(vr.get("review_status") or "").lower()
                if status == "draft":
                    review_draft += 1
                elif status == "reviewed":
                    review_reviewed += 1
                elif status == "endorsed":
                    review_endorsed += 1
            data = {
                "review_draft": review_draft,
                "review_reviewed": review_reviewed,
                "review_endorsed": review_endorsed,
            }
        else:
            agency = (user.agency or "").strip()
            if agency:
                my = Project.objects.filter(agency__iexact=agency)
            else:
                my = Project.objects.filter(created_by=user)
            data = {
                "my_projects": my.count(),
                "draft_projects": my.filter(status="planning").count(),
                "submitted_projects": my.filter(status="proposed").count(),
                "approved_projects": my.filter(status="completed").count(),
            }
        return Response(data)


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
                "full_name": u.full_name,
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
        if not email:
            return Response({"detail": "Email is required."}, status=400)
        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            return Response({"detail": "Invalid credentials"}, status=401)
        if user.must_change_password:
            return Response({"detail": "Password setup required. Check your email for the setup link."}, status=403)
        if not user.is_active:
            return Response({"detail": "Account is deactivated. Contact admin."}, status=403)

        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user.pk)
            previous_session_version, session_version = _advance_user_session(user, request)
            access_token, refresh_token = _issue_session_tokens(user)
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
                },
            )
        return Response(
            {
                "access": access_token,
                "refresh": refresh_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": _frontend_role(user.role),
                    "must_change_password": user.must_change_password,
                    "full_name": user.full_name,
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


class SetupPasswordView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token_value = (request.query_params.get("token") or "").strip()
        if not token_value:
            return Response({"detail": "Token is required."}, status=400)
        token = PasswordSetupToken.objects.select_related("user").filter(token=token_value).first()
        if not token or not token.is_valid():
            return Response({"detail": "Token is invalid or expired."}, status=400)
        user = token.user
        return Response(
            {
                "email": user.email,
                "profile": {
                    "full_name": user.full_name,
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
        token = PasswordSetupToken.objects.select_related("user").filter(token=token_value).first()
        if not token or not token.is_valid():
            return Response({"detail": "Token is invalid or expired."}, status=400)
        required_fields = [
            "full_name",
            "agency",
            "agency_head",
            "office",
            "division",
            "position",
            "contact_number",
            "phone_number",
        ]
        missing = [f for f in required_fields if not str(request.data.get(f) or "").strip()]
        if missing:
            return Response({"detail": f"Missing required fields: {', '.join(missing)}"}, status=400)
        policy_error = _validate_password_policy(new_password)
        if policy_error:
            return Response({"detail": policy_error}, status=400)
        user = token.user
        user.full_name = str(request.data.get("full_name") or "").strip()
        user.agency = str(request.data.get("agency") or "").strip()
        user.agency_head = str(request.data.get("agency_head") or "").strip()
        user.office = str(request.data.get("office") or "").strip()
        user.division = str(request.data.get("division") or "").strip()
        user.position = str(request.data.get("position") or "").strip()
        user.contact_number = str(request.data.get("contact_number") or "").strip()
        user.phone_number = str(request.data.get("phone_number") or "").strip()
        user.set_password(new_password)
        user.must_change_password = False
        user.last_password_change = timezone.now()
        user.save(
            update_fields=[
                "full_name",
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
        return Response({"status": "ok"})


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

        if role_filter:
            qs = qs.filter(role=role_filter)
        if event_filter:
            qs = qs.filter(event=event_filter)
        if user_filter:
            qs = qs.filter(
                Q(user__username__icontains=user_filter)
                | Q(user__full_name__icontains=user_filter)
                | Q(user__email__icontains=user_filter)
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

        agency = (request.user.agency or "").strip()
        if not agency:
            if include_meta:
                return Response(
                    {
                        "results": [],
                        "count": 0,
                        "limit": limit,
                        "offset": offset,
                        "has_previous": False,
                        "has_next": False,
                    }
                )
            return Response([])
        project_events = {"project_create", "project_update", "project_submit", "project_comment"}
        qs = UserActivity.objects.select_related("user", "project").filter(
            project__agency__iexact=agency,
            event__in=project_events,
        ).order_by("-created_at", "-id")
        total = qs.count()
        serializer = UserActivitySerializer(qs[offset : offset + limit], many=True)
        if include_meta:
            return Response(
                {
                    "results": serializer.data,
                    "count": total,
                    "limit": limit,
                    "offset": offset,
                    "has_previous": offset > 0,
                    "has_next": offset + limit < total,
                }
            )
        return Response(serializer.data)


def _get_public_projects_cache_version() -> int:
    try:
        v = cache.get(PUBLIC_PROJECTS_CACHE_VERSION_KEY)
        if isinstance(v, int) and v >= 1:
            return v
    except Exception:
        pass
    try:
        cache.add(PUBLIC_PROJECTS_CACHE_VERSION_KEY, 1, None)
    except Exception:
        pass
    return 1


def _hash_query(params: dict) -> str:
    # Stable key regardless of ordering.
    items = []
    for k in sorted(params.keys()):
        if k == "_":
            continue
        items.append((k, str(params[k])))
    raw = urllib.parse.urlencode(items, doseq=True)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


class PublicProjectsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only projects feed for the public website dashboard.
    Returns validated projects only (unless overridden by admin-only endpoints elsewhere).
    """

    permission_classes = [AllowAny]
    authentication_classes = []  # Don't attempt JWT auth; avoids 401 on invalid Authorization header.
    serializer_class = PublicProjectSerializer

    def _base_queryset(self):
        return Project.objects.filter(validated=True, archived=False, is_active=True)

    def _project_to_public_payload(self, project: Project) -> dict:
        return PublicProjectSerializer(project).data

    def list(self, request, *args, **kwargs):
        version = _get_public_projects_cache_version()
        params = dict(request.query_params)
        cache_key = f"public_projects:list:v{PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION}:{version}:{_hash_query(params)}"
        cached = cache.get(cache_key)
        if cached is not None:
            resp = Response(cached)
            resp["Cache-Control"] = PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL
            return resp

        qs = self._base_queryset().order_by("-updated_at")

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
            qs = qs.filter(profile_data__simplified_form__status__iexact=status_raw)

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
        resp = Response(payload)
        resp["Cache-Control"] = PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL
        return resp

    def retrieve(self, request, *args, **kwargs):
        project = Project.objects.filter(validated=True, archived=False, is_active=True).filter(pk=kwargs.get("pk")).first()
        if not project:
            return Response({"detail": "Not found."}, status=404)
        payload = self._project_to_public_payload(project)
        resp = Response(payload)
        resp["Cache-Control"] = PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL
        return resp


class PublicProjectsStatsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Don't attempt JWT auth.

    def get(self, request):
        version = _get_public_projects_cache_version()
        params = dict(request.query_params)
        cache_key = f"public_projects:stats:v{PUBLIC_PROJECTS_PAYLOAD_SCHEMA_VERSION}:{version}:{_hash_query(params)}"
        cached = cache.get(cache_key)
        if cached is not None:
            resp = Response(cached)
            resp["Cache-Control"] = PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL
            return resp

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
            qs = qs.filter(profile_data__simplified_form__status__iexact=status_raw)

        projects = list(qs)
        lgu_filter = (request.query_params.get("lgu") or "").strip()
        if lgu_filter and lgu_filter.lower() != "all":
            def project_location(project):
                profile_data = project.profile_data if isinstance(project.profile_data, dict) else {}
                simplified = profile_data.get("simplified_form")
                simplified = simplified if isinstance(simplified, dict) else {}
                return str(simplified.get("location") or "")

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
            impl_status = str(sf.get("status") or getattr(p, "status", "") or "").strip() or "Unspecified"
            agency_name = str(sf.get("agencyName") or getattr(p, "agency", "") or "").strip() or "Other"
            location_raw = str(sf.get("location") or "").strip()
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
        resp = Response(payload)
        resp["Cache-Control"] = PUBLIC_PROJECTS_BROWSER_CACHE_CONTROL
        return resp
