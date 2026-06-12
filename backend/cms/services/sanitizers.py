from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse


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

