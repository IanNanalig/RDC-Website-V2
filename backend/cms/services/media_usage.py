from django.db.models import Prefetch

from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection


def get_media_usages(media: CMSMediaAsset):
    return get_media_usage_map([media]).get(media.pk, [])


def get_media_usage_map(media_assets):
    """Resolve CMS usages for many assets while scanning CMS content only once."""
    assets = [media for media in media_assets if media.pk is not None]
    usage_map = {media.pk: [] for media in assets}
    if not assets:
        return usage_map

    media_ids = {str(media.pk): media.pk for media in assets}
    reference_index = {}
    for media in assets:
        for reference in _media_references(media):
            reference_index.setdefault(reference, set()).add(media.pk)

    sections = CMSPageSection.objects.only("id", "page_id", "section_key", "content_json")
    pages = CMSPage.objects.only("id", "title", "slug", "published_snapshot_json").prefetch_related(
        Prefetch("sections", queryset=sections)
    )
    for page in pages:
        _append_usage(
            usage_map,
            _json_media_ids(page.published_snapshot_json, media_ids, reference_index),
            {
                "type": "page",
                "title": page.title,
                "slug": page.slug,
                "location": "Published page snapshot",
                "is_public": True,
            },
        )
        for section in page.sections.all():
            _append_usage(
                usage_map,
                _json_media_ids(section.content_json, media_ids, reference_index),
                {
                    "type": "section",
                    "title": page.title,
                    "slug": page.slug,
                    "location": f"Draft section: {section.section_key}",
                    "is_public": False,
                },
            )

    for article in CMSArticle.objects.only(
        "id", "title", "slug", "thumbnail_id", "published_snapshot_json"
    ):
        if article.thumbnail_id in usage_map:
            usage_map[article.thumbnail_id].append(
                {
                    "type": "article",
                    "title": article.title,
                    "slug": article.slug,
                    "location": "Editable news thumbnail",
                    "is_public": False,
                }
            )
        _append_usage(
            usage_map,
            _json_media_ids(article.published_snapshot_json, media_ids, reference_index),
            {
                "type": "article",
                "title": article.title,
                "slug": article.slug,
                "location": "Published news snapshot",
                "is_public": True,
            },
        )

    return usage_map


def media_is_used(media: CMSMediaAsset) -> bool:
    return bool(get_media_usages(media))


def _media_references(media: CMSMediaAsset):
    references = {media.file.name}
    public_url = media.resolved_public_url
    if public_url:
        references.add(public_url)
    return {reference for reference in references if reference}


def _append_usage(usage_map, media_ids, usage):
    for media_id in media_ids:
        usage_map[media_id].append(dict(usage))


def _json_media_ids(value, media_ids, reference_index):
    matches = set()
    _collect_json_media_ids(value, media_ids, reference_index, matches)
    return matches


def _collect_json_media_ids(value, media_ids, reference_index, matches):
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).lower()
            if normalized_key in {"mediaassetid", "coverassetid", "thumbnail", "thumbnailid"}:
                media_pk = media_ids.get(str(child))
                if media_pk is not None:
                    matches.add(media_pk)
            _collect_json_media_ids(child, media_ids, reference_index, matches)
        return

    if isinstance(value, list):
        for child in value:
            _collect_json_media_ids(child, media_ids, reference_index, matches)
        return

    if isinstance(value, str):
        for reference, referenced_ids in reference_index.items():
            if reference in value:
                matches.update(referenced_ids)
