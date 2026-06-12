from django.utils import timezone

from cms.services.sanitizers import sanitize_public_html


def build_page_snapshot(page):
    published_at = timezone.now()
    sections = []
    for section in page.sections.filter(is_visible=True).order_by("order", "id"):
        sections.append(
            {
                "sectionKey": section.section_key,
                "sectionType": section.section_type,
                "order": section.order,
                "schemaVersion": section.schema_version,
                "content": section.content_json or {},
            }
        )

    return {
        "title": page.title,
        "slug": page.slug,
        "publishedAt": published_at.isoformat(),
        "sections": sections,
    }


def build_article_snapshot(article):
    published_at = timezone.now()
    thumbnail_url = article.thumbnail.public_url if article.thumbnail and not article.thumbnail.is_archived else ""
    return {
        "title": article.title,
        "slug": article.slug,
        "category": article.category,
        "summary": article.summary,
        "body": sanitize_public_html(article.body),
        "thumbnailUrl": thumbnail_url,
        "featured": article.featured,
        "author": article.author,
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
        "status": article.status,
        "hasUnpublishedChanges": article.has_unpublished_changes,
    }

