from django.utils.html import strip_tags

from cms.models import CMSArticle, CMSPage
from projects.models import PublicContent


def sync_cms_content(obj):
    if isinstance(obj, CMSArticle):
        key = f"cms-news-{obj.pk}"
        if obj.status == CMSArticle.STATUS_ARCHIVED or not obj.published_snapshot_json:
            PublicContent.objects.filter(slug=key).delete()
            return
        data = obj.published_snapshot_json
        PublicContent.objects.update_or_create(
            slug=key,
            language="en",
            defaults={
                "title": str(data.get("title") or obj.title)[:200],
                "summary": str(data.get("summary") or ""),
                "body": strip_tags(str(data.get("body") or "")),
                "tags": ["cms", "news", str(data.get("category") or "updates").lower()],
                "url": f"/news/{data.get('slug') or obj.slug}",
            },
        )
        return

    if isinstance(obj, CMSPage):
        key = f"cms-page-{obj.pk}"
        if obj.status == CMSPage.STATUS_ARCHIVED or not obj.published_snapshot_json:
            PublicContent.objects.filter(slug=key).delete()
            return
        data = obj.published_snapshot_json
        chunks = []
        for section in data.get("sections") or []:
            chunks.extend(_text_values(section.get("content") or {}))
        PublicContent.objects.update_or_create(
            slug=key,
            language="en",
            defaults={
                "title": str(data.get("title") or obj.title)[:200],
                "summary": " ".join(chunks)[:500],
                "body": "\n".join(chunks),
                "tags": ["cms", "page", str(data.get("slug") or obj.slug)],
                "url": _page_url(str(data.get("slug") or obj.slug)),
            },
        )


def _text_values(value):
    if isinstance(value, dict):
        values = []
        for child in value.values():
            values.extend(_text_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(_text_values(child))
        return values
    if isinstance(value, str):
        text = strip_tags(value).strip()
        if text and not text.startswith(("http://", "https://", "/media/")):
            return [text]
    return []


def _page_url(slug):
    return {
        "home": "/",
        "about-rdc": "/about",
        "region-profile": "/regional-profile",
        "publications": "/publications",
        "projects-dashboard": "/projects",
        "contact": "/contact",
    }.get(slug, f"/{slug}")
