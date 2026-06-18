from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection


def get_media_usages(media: CMSMediaAsset):
    media_id = str(media.pk)
    references = _media_references(media)
    usages = []

    for page in CMSPage.objects.prefetch_related("sections").all():
        if _json_references_media(page.published_snapshot_json, media_id, references):
            usages.append(
                {
                    "type": "page",
                    "title": page.title,
                    "slug": page.slug,
                    "location": "Published page snapshot",
                    "is_public": True,
                }
            )
        for section in page.sections.all():
            if _json_references_media(section.content_json, media_id, references):
                usages.append(
                    {
                        "type": "section",
                        "title": page.title,
                        "slug": page.slug,
                        "location": f"Draft section: {section.section_key}",
                        "is_public": False,
                    }
                )

    for article in CMSArticle.objects.select_related("thumbnail").all():
        if article.thumbnail_id == media.pk:
            usages.append(
                {
                    "type": "article",
                    "title": article.title,
                    "slug": article.slug,
                    "location": "Editable news thumbnail",
                    "is_public": False,
                }
            )
        if _json_references_media(article.published_snapshot_json, media_id, references):
            usages.append(
                {
                    "type": "article",
                    "title": article.title,
                    "slug": article.slug,
                    "location": "Published news snapshot",
                    "is_public": True,
                }
            )

    return usages


def media_is_used(media: CMSMediaAsset) -> bool:
    return bool(get_media_usages(media))


def _media_references(media: CMSMediaAsset):
    references = {media.file.name}
    public_url = media.public_url
    if public_url:
        references.add(public_url)
    return {reference for reference in references if reference}


def _json_references_media(value, media_id: str, references: set[str]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).lower()
            if normalized_key in {"mediaassetid", "coverassetid", "thumbnail", "thumbnailid"}:
                if str(child) == media_id:
                    return True
            if _json_references_media(child, media_id, references):
                return True
        return False

    if isinstance(value, list):
        return any(_json_references_media(item, media_id, references) for item in value)

    if isinstance(value, str):
        return any(reference in value for reference in references)

    return False
