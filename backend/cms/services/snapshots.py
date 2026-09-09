from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from cms.services.sanitizers import sanitize_public_html, sanitize_public_structure, sanitize_public_text


def _portable_media_references(value):
    if isinstance(value, dict):
        return {key: _portable_media_references(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_portable_media_references(child) for child in value]
    if not isinstance(value, str):
        return value

    media_url = str(getattr(settings, "MEDIA_URL", "/media/") or "/media/")
    media_path = media_url if media_url.startswith("/") else "/media/"
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.path.startswith(media_path):
        portable = parsed.path
        if parsed.query:
            portable += f"?{parsed.query}"
        return portable
    return value


def build_page_snapshot(page):
    published_at = timezone.now()
    sections = []
    for section in page.sections.filter(status="published", is_visible=True).order_by("order", "id"):
        sections.append(
            {
                "sectionKey": section.section_key,
                "sectionType": section.section_type,
                "order": section.order,
                "schemaVersion": section.schema_version,
                "content": _portable_media_references(sanitize_public_structure(section.content_json or {})),
            }
        )

    return {
        "title": sanitize_public_text(page.title),
        "slug": page.slug,
        "publishedAt": published_at.isoformat(),
        "sections": sections,
    }


def build_article_snapshot(article):
    published_at = timezone.now()
    thumbnail_url = article.thumbnail.resolved_public_url if article.thumbnail and not article.thumbnail.is_archived else ""
    return {
        "title": sanitize_public_text(article.title),
        "slug": article.slug,
        "category": sanitize_public_text(article.category),
        "summary": sanitize_public_text(article.summary),
        "body": sanitize_public_html(article.body),
        "thumbnailUrl": _portable_media_references(thumbnail_url),
        "featured": article.featured,
        "author": sanitize_public_text(article.author),
        "publicationDate": article.publication_date.isoformat() if article.publication_date else "",
        "publishedAt": published_at.isoformat(),
    }


def build_page_draft_snapshot(page):
    return {
        "title": page.title,
        "slug": page.slug,
        "status": page.status,
        "hasUnpublishedChanges": page.has_unpublished_changes,
        "sections": [
            {
                "id": section.id,
                "sectionKey": section.section_key,
                "sectionType": section.section_type,
                "order": section.order,
                "schemaVersion": section.schema_version,
                "isVisible": section.is_visible,
                "status": section.status,
                "content": section.content_json or {},
            }
            for section in page.sections.order_by("order", "id")
        ],
    }


def build_article_draft_snapshot(article):
    return {
        "title": article.title,
        "slug": article.slug,
        "category": article.category,
        "summary": article.summary,
        "body": article.body,
        "thumbnail": article.thumbnail_id,
        "featured": article.featured,
        "author": article.author,
        "publication_date": article.publication_date.isoformat() if article.publication_date else None,
        "status": article.status,
        "hasUnpublishedChanges": article.has_unpublished_changes,
    }
