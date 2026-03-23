import json
import os
import re
import difflib
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail, EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import get_random_string
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
    Project,
    PublicChatFAQ,
    PublicContent,
    SystemSetting,
    User,
    UserActivity,
)
from .serializers import AccessRequestSerializer, PasswordResetRequestSerializer, ProjectSerializer, UserActivitySerializer, UserSerializer


ENCODING_WINDOW_KEY = "portal_encoding_window"
PASSWORD_SETUP_TTL_HOURS = 24
PASSWORD_RESET_WINDOW_SECONDS = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_WINDOW", 3600))
PASSWORD_RESET_LIMIT_EMAIL = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_EMAIL", 2))
PASSWORD_RESET_LIMIT_IP = int(getattr(settings, "PASSWORD_RESET_RATE_LIMIT_IP", 5))

PUBLIC_CHAT_MAX_SUGGESTIONS = 6
PUBLIC_CHAT_MIN_SCORE = 1.0

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


def _get_encoding_window_config():
    default = {"enabled": True, "start_at": "", "end_at": ""}
    setting = SystemSetting.objects.filter(key=ENCODING_WINDOW_KEY).first()
    if not setting or not setting.value:
        return default
    try:
        data = json.loads(setting.value)
        return {
            "enabled": bool(data.get("enabled", True)),
            "start_at": str(data.get("start_at", "") or ""),
            "end_at": str(data.get("end_at", "") or ""),
        }
    except Exception:
        return default


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


def _resolve_encoding_window_state():
    config = _get_encoding_window_config()
    if not config["enabled"]:
        return {
            **config,
            "is_open": False,
            "message": "Encoding is currently closed by admin.",
        }

    start_at = _parse_iso_datetime(config["start_at"]) if config["start_at"] else None
    end_at = _parse_iso_datetime(config["end_at"]) if config["end_at"] else None

    # If no range is configured, encoding remains open.
    if not start_at and not end_at:
        return {
            **config,
            "is_open": True,
            "message": "Encoding is open.",
        }

    now = timezone.now()
    is_open = True
    if start_at and now < start_at:
        is_open = False
    if end_at and now > end_at:
        is_open = False

    if is_open:
        msg = "Encoding is open."
    else:
        msg = "Encoding is outside the active admin schedule."

    return {
        **config,
        "is_open": is_open,
        "message": msg,
    }


def _send_setup_email(user: User, token: PasswordSetupToken, purpose: str = "create"):
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
    link = f"{frontend_base}/setup-password?token={token.token}"
    is_reset = purpose == "reset"
    subject = "RDC Portal Password Reset" if is_reset else "RDC Portal Account Setup"
    if is_reset:
        message = (
            "A password reset was approved for your RDC Portal account.\n\n"
            "Please click the link below to set a new password (valid for 24 hours):\n"
            f"{link}\n\n"
            "If you did not request this reset, please contact the RDC Portal administrator immediately."
        )
    else:
        message = (
            "Your RDC Portal account has been created.\n\n"
            "Please click the link below to set your password (valid for 24 hours):\n"
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


class PublicChatAskView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        question = str(request.data.get("question") or "").strip()
        if not question:
            return Response({"detail": "Question is required."}, status=400)

        language = _detect_language(question)
        suggested = _get_top_questions(PUBLIC_CHAT_MAX_SUGGESTIONS) or _default_suggestions(language)

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
            return Response(
                {
                    "answer": answer,
                    "confidence": 0.0,
                    "sources": [],
                    "language": language,
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

        normalized = _normalize_text(question)
        faq, created = PublicChatFAQ.objects.get_or_create(
            question_normalized=normalized,
            defaults={
                "question_sample": _sanitize_question_sample(question),
                "count": 1,
                "last_asked": timezone.now(),
                "last_matched_content": best,
            },
        )
        if not created:
            faq.count += 1
            faq.last_asked = timezone.now()
            faq.last_matched_content = best
            if not faq.question_sample:
                faq.question_sample = _sanitize_question_sample(question)
            faq.save(update_fields=["count", "last_asked", "last_matched_content", "question_sample"])

        if not best or best_score < PUBLIC_CHAT_MIN_SCORE:
            fallback = (
                "I can help with questions about the RDC-NCR public website. "
                "Try asking about News, Publications, Projects, or Regional Profile."
            )
            if language == "tl":
                fallback = (
                    "Makakatulong ako sa mga tanong tungkol sa pampublikong website ng RDC-NCR. "
                    "Subukang magtanong tungkol sa News, Publications, Projects, o Regional Profile."
                )
            alternatives = []
            for score, content in ranked[:2]:
                if score > 0 and content.url:
                    alternatives.append({"title": content.title, "url": content.url})
            if alternatives:
                alt_note = (
                    "These pages might be related to your question."
                    if language == "en"
                    else "Baka makatulong ang mga pahinang ito sa tanong mo."
                )
                return Response(
                    {
                        "answer": f"{fallback} {alt_note}",
                        "confidence": 0.2,
                        "sources": alternatives,
                        "language": language,
                        "suggested_questions": suggested,
                    }
                )
            return Response(
                {
                    "answer": fallback,
                    "confidence": 0.2,
                    "sources": [],
                    "language": language,
                    "suggested_questions": suggested,
                }
            )

        if best.slug == "contact" or contact_intent:
            answer, include_map, include_email = _build_contact_answer(question, language)
        else:
            answer = _build_generic_answer(question, best, language)

        confidence = min(1.0, best_score / max(1.0, len(question_tokens) + 1))
        sources = [{"title": best.title, "url": best.url}] if best.url else []
        if best.slug == "contact" or contact_intent:
            if include_map:
                sources.append(
                    {"title": "RDC-NCR Office Location (Google Maps)", "url": PUBLIC_CONTACT_MAP_URL}
                )
            if include_email:
                sources.append({"title": "Email RDC-NCR", "url": f"mailto:{PUBLIC_CONTACT_EMAIL}"})
        return Response(
            {
                "answer": answer,
                "confidence": round(confidence, 2),
                "sources": sources,
                "language": language,
                "suggested_questions": suggested,
            }
        )


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


def _strip_validator_meta(profile_data):
    if not isinstance(profile_data, dict):
        return {}
    return {
        key: value
        for key, value in profile_data.items()
        if key not in ("validator_review", "contributor_snapshot")
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


class ProjectPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        role = getattr(request.user, "role", "")
        if role in ("admin", "validator"):
            return True
        if request.method in permissions.SAFE_METHODS:
            return obj.created_by_id == request.user.id
        return obj.created_by_id == request.user.id


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

        edited_fields = _json_diff(contributor_snapshot, edited_profile)
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
        project.profile_data = profile_data
        project.save(update_fields=list(dict.fromkeys(update_fields)))
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
        return Project.objects.filter(created_by=self.request.user).order_by("-created_at")

    def _ensure_encoding_open(self):
        state = _resolve_encoding_window_state()
        if not state["is_open"]:
            raise PermissionDenied(state["message"])

    def _ensure_mutable_project(self, project):
        if project.status != "planning":
            raise PermissionDenied("Submitted/validated projects are view-only for contributors.")

    def create(self, request, *args, **kwargs):
        self._ensure_encoding_open()
        response = super().create(request, *args, **kwargs)
        if response.status_code == status.HTTP_201_CREATED:
            project_id = response.data.get("id")
            project = Project.objects.filter(id=project_id).first()
            _log_activity(request, "project_create", project, {"status": response.data.get("status")})
        return response

    def update(self, request, *args, **kwargs):
        self._ensure_encoding_open()
        self._ensure_mutable_project(self.get_object())
        response = super().update(request, *args, **kwargs)
        _log_activity(request, "project_update", self.get_object(), {"status": response.data.get("status") if hasattr(response, "data") else ""})
        return response

    def partial_update(self, request, *args, **kwargs):
        self._ensure_encoding_open()
        self._ensure_mutable_project(self.get_object())
        response = super().partial_update(request, *args, **kwargs)
        _log_activity(request, "project_update", self.get_object(), {"partial": True})
        return response

    def destroy(self, request, *args, **kwargs):
        raise PermissionDenied("Only admin can delete projects")

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        self._ensure_encoding_open()
        self._ensure_mutable_project(self.get_object())
        return super().submit(request, pk=pk)


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

        enabled = bool(request.data.get("enabled", True))
        start_at = str(request.data.get("start_at", "") or "")
        end_at = str(request.data.get("end_at", "") or "")

        if start_at:
            _parse_iso_datetime(start_at)
        if end_at:
            _parse_iso_datetime(end_at)
        if start_at and end_at and _parse_iso_datetime(start_at) > _parse_iso_datetime(end_at):
            return Response({"detail": "start_at cannot be after end_at"}, status=400)

        payload = {"enabled": enabled, "start_at": start_at, "end_at": end_at}
        SystemSetting.objects.update_or_create(
            key=ENCODING_WINDOW_KEY,
            defaults={"value": json.dumps(payload)},
        )
        return Response(_resolve_encoding_window_state())


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
        return Response({"id": u.id, "username": u.username, "email": u.email, "role": _frontend_role(u.role)})


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

        refresh = RefreshToken.for_user(user)
        _log_activity(request, "login", details={"username": user.username})
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": _frontend_role(user.role),
                    "must_change_password": user.must_change_password,
                },
            }
        )


class SetupPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token_value = (request.data.get("token") or "").strip()
        new_password = request.data.get("new_password") or ""
        if not token_value:
            return Response({"detail": "Token is required."}, status=400)
        token = PasswordSetupToken.objects.select_related("user").filter(token=token_value).first()
        if not token or not token.is_valid():
            return Response({"detail": "Token is invalid or expired."}, status=400)
        policy_error = _validate_password_policy(new_password)
        if policy_error:
            return Response({"detail": policy_error}, status=400)
        user = token.user
        user.set_password(new_password)
        user.must_change_password = False
        user.last_password_change = timezone.now()
        user.save(update_fields=["password", "must_change_password", "last_password_change"])
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
        limit_raw = request.query_params.get("limit")

        if role_filter:
            qs = qs.filter(role=role_filter)
        if event_filter:
            qs = qs.filter(event=event_filter)
        if user_filter:
            qs = qs.filter(user__username__icontains=user_filter)

        limit = 50
        if limit_raw:
            try:
                limit = max(1, min(200, int(limit_raw)))
            except Exception:
                limit = 50

        serializer = UserActivitySerializer(qs[:limit], many=True)
        return Response(serializer.data)
