import re
from uuid import uuid4
from urllib.parse import parse_qs, unquote, urlsplit

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from rest_framework import serializers


HOME_DOCUMENTS = {"development-plans", "investment-programming", "monitoring-evaluation"}
LIMITS = {
    "hero-carousel": {"slides.*.title": 50, "slides.*.imageAlt": 50, "slides.*.subtitle": 100,
                      "slides.*.button1.text": 20, "slides.*.button2.text": 20},
    "legal-basis": {"title": 50, "subtitle": 100, "items.*.title": 50, "items.*.description": 250},
    "resolutions-archive": {
        "title": 50, "subtitle": 100, "legendTitle": 25, "legendItems.*.label": 25,
        "years.*.resolutions.*.title": 100, "years.*.resolutions.*.description": 500,
        "years.*.resolutions.*.legendTitle": 25, "years.*.resolutions.*.legendItems.*.label": 25,
    },
    "committees": {
        "title": 25, "subtitle": 100, "items.*.title": 50, "items.*.description": 1000,
        "items.*.functions": 1000, "items.*.subCommittees.*.title": 50,
        "items.*.subCommittees.*.description": 1000, "items.*.subCommittees.*.functions": 1000,
        "items.*.content.functions": 1000, "items.*.content.subCommittees.*.title": 50,
        "items.*.content.subCommittees.*.description": 1000,
        "items.*.content.subCommittees.*.functions": 1000,
    },
    "regional-overview": {"paragraphs.*": 500, "stats.*.label": 25, "stats.*.value": 25, "stats.*.subtext": 25},
    "lgu-directory": {"items.*.name": 25, "items.*.title": 25},
    "main-office": {"title": 25, "address": 150, "officeHours": 150, "email": 50, "phone": 50},
    "location-map": {"title": 25, "subtitle": 50},
    "publication-catalog": {"categories.*.title": 100, "categories.*.coverAlt": 100, "categories.*.description": 250,
                            "categories.*.documents.*.title": 100, "categories.*.documents.*.coverAlt": 100},
    **{key: {"title": 50, "items.*.title": 25, "items.*.description": 50} for key in HOME_DOCUMENTS},
}


def _identity(item):
    if isinstance(item, dict):
        identifier = item.get("id") or item.get("code") or item.get("key") or item.get("year")
        return identifier if isinstance(identifier, (str, int)) else None
    return None


def _values(value, previous, path, label=()):
    if not path:
        yield ".".join(label), value, previous
        return
    key, *tail = path
    if key == "*" and isinstance(value, list):
        old = previous if isinstance(previous, list) else []
        by_identity = {identity: row for row in old if (identity := _identity(row))}
        for index, row in enumerate(value):
            identity = _identity(row)
            match = by_identity.get(identity)
            if not identity:
                match = row if row in old else (old[index] if index < len(old) else None)
            yield from _values(row, match, tail, (*label, str(index + 1)))
    elif isinstance(value, dict):
        previous = previous if isinstance(previous, dict) else {}
        yield from _values(value.get(key), previous.get(key), tail, (*label, key))


def google_map_location(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        url = urlsplit(str(value).strip())
    except ValueError:
        return ""
    if url.scheme != "https" or url.netloc.lower() not in {"google.com", "www.google.com", "maps.google.com"}:
        return ""
    if not (url.path in {"", "/", "/maps", "/maps/"} or url.path.startswith(("/maps/place/", "/maps/search/"))):
        return ""
    params = parse_qs(url.query)
    query = (params.get("q") or params.get("query") or [""])[0].strip()
    if not query and url.path.startswith("/maps/place/"):
        query = unquote(url.path.split("/")[3]).replace("+", " ").strip()
    return query if 0 < len(query) <= 500 else ""


def validate_section_refinements(section_key, value, previous):
    errors = {}
    for path, limit in LIMITS.get(section_key, {}).items():
        for label, current, old in _values(value, previous, path.split(".")):
            if current == old:
                continue
            text = "\n".join(str(item) for item in current) if isinstance(current, list) else current
            if isinstance(text, str) and len(text) > limit:
                errors[label] = f"Use {limit} characters or fewer."
    if section_key == "hero-carousel":
        slides = value.get("slides")
        old_slides = previous.get("slides")
        if isinstance(slides, list) and len(slides) > max(10, len(old_slides) if isinstance(old_slides, list) else 0):
            errors["slides"] = "The Hero Carousel can have up to 10 slides."
    if section_key == "main-office":
        email, phone = value.get("email"), value.get("phone")
        if email and email != previous.get("email"):
            try:
                validate_email(str(email))
            except DjangoValidationError:
                errors["email"] = "Enter a valid email address."
        if phone and phone != previous.get("phone") and (
            not re.fullmatch(r"(?:[+0-9(). ,/#x;-]|ext\.?)+", str(phone), flags=re.IGNORECASE)
            or not re.search(r"[0-9]", str(phone))
        ):
            errors["phone"] = "Enter a valid phone number."
    if section_key == "location-map":
        map_url = value.get("googleMapsLocation")
        if map_url and not google_map_location(map_url):
            errors["googleMapsLocation"] = "Enter a full Google Maps place link, or a Maps URL containing q or query."
    if errors:
        raise serializers.ValidationError(errors)


def preserve_card_identities(section_key, value):
    if section_key not in HOME_DOCUMENTS | {"legal-basis"}:
        return value
    seen = set()
    for row in value.get("items") or []:
        if not isinstance(row, dict):
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            identifier = f"card-{uuid4()}"
            row["id"] = identifier
        seen.add(identifier)
    return value
