from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.utils.html import strip_tags


ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "a",
    "h2",
    "h3",
    "h4",
    "blockquote",
}

ALLOWED_LINK_SCHEMES = {"http", "https", "mailto", ""}


def _safe_href(value):
    parsed = urlparse(value or "")
    if parsed.scheme.lower() not in ALLOWED_LINK_SCHEMES:
        return ""
    return value


class _PublicHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return

        if tag == "a":
            attr_map = {name.lower(): value for name, value in attrs}
            href = _safe_href(attr_map.get("href", ""))
            if not href:
                self.parts.append("<a>")
                return
            self.parts.append(
                f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">'
            )
            return

        self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ALLOWED_TAGS and tag != "br":
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")


def sanitize_public_html(value):
    """Return safe HTML for public snapshots without needing a runtime dependency."""
    if not value:
        return ""
    parser = _PublicHTMLSanitizer()
    parser.feed(str(value))
    parser.close()
    return "".join(parser.parts)


def sanitize_public_text(value):
    """Remove markup from values rendered by public React text fields."""
    if value is None:
        return ""
    return strip_tags(str(value))


def sanitize_public_link(value):
    """Keep ordinary public links while removing executable URI schemes."""
    if not value:
        return ""
    raw = str(value).strip()
    return raw if _safe_href(raw) else ""


def sanitize_public_structure(value, key=""):
    """Sanitize nested CMS section content before it enters a public snapshot."""
    if isinstance(value, dict):
        return {child_key: sanitize_public_structure(child, child_key) for child_key, child in value.items()}
    if isinstance(value, list):
        return [sanitize_public_structure(child, key) for child in value]
    if not isinstance(value, str):
        return value

    normalized_key = str(key).lower()
    if normalized_key.endswith(("url", "link", "website", "href")):
        return sanitize_public_link(value)
    return sanitize_public_text(value)

