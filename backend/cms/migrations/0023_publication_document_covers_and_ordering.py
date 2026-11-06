from django.db import migrations, models
import django.db.models.deletion


DOCUMENT_LIMIT_BYTES = 50 * 1024 * 1024


def prepare_publications(apps, schema_editor):
    CMSMediaAsset = apps.get_model("cms", "CMSMediaAsset")
    CMSPageSection = apps.get_model("cms", "CMSPageSection")
    CMSPublicationCategory = apps.get_model("cms", "CMSPublicationCategory")
    CMSPublicationDocument = apps.get_model("cms", "CMSPublicationDocument")
    CMSSiteSetting = apps.get_model("cms", "CMSSiteSetting")

    setting, _ = CMSSiteSetting.objects.get_or_create(
        key="media-upload-max-bytes",
        defaults={
            "description": "Maximum upload size in bytes for each CMS media category.",
            "value_json": {},
        },
    )
    limits = dict(setting.value_json or {})
    limits["document"] = DOCUMENT_LIMIT_BYTES
    setting.value_json = limits
    setting.save(update_fields=["value_json"])

    # Assign every active or archived category one permanent number. Creation
    # order makes the highest number the newest without reusing old numbers.
    for number, category in enumerate(
        CMSPublicationCategory.objects.order_by("created_at", "id"),
        1,
    ):
        category.display_number = number
        category.icon = ""
        category.save(update_fields=["display_number", "icon", "updated_at"])

    section = CMSPageSection.objects.filter(
        page__slug="publications",
        section_key="publication-catalog",
    ).first()
    if not section or not isinstance(section.content_json, dict):
        return

    content = dict(section.content_json)
    categories = list(content.get("categories") or [])
    changed = False
    for category_index, row in enumerate(categories, 1):
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or row.get("id") or "").strip()
        category = CMSPublicationCategory.objects.filter(code=code).first() if code else None
        number = category.display_number if category else category_index
        if row.get("categoryNumber") != number:
            row["categoryNumber"] = number
            changed = True
        if category:
            snapshot = dict(category.published_snapshot_json or {})
            if snapshot:
                snapshot["categoryNumber"] = number
                snapshot.pop("icon", None)
                category.published_snapshot_json = snapshot
            category.save(update_fields=["published_snapshot_json", "updated_at"])

        for item in row.get("documents") or []:
            if not isinstance(item, dict):
                continue
            stable_key = str(item.get("id") or "").strip()
            cover_id = item.get("coverAssetId") or item.get("coverImageAssetId")
            if not stable_key or not cover_id:
                continue
            document = CMSPublicationDocument.objects.filter(stable_key=stable_key).first()
            cover = CMSMediaAsset.objects.filter(
                pk=cover_id,
                is_archived=False,
                file_type="image",
            ).first()
            if not document or not cover:
                continue
            document.cover_image = cover
            document.cover_alt_text = str(item.get("coverAlt") or "").strip()
            snapshot = dict(document.published_snapshot_json or {})
            if snapshot:
                try:
                    cover_url = cover.public_url or cover.file.url
                except ValueError:
                    cover_url = ""
                snapshot["coverAssetId"] = str(cover.pk)
                snapshot["coverImage"] = cover_url
                snapshot["coverAlt"] = document.cover_alt_text or cover.alt_text or document.title
                document.published_snapshot_json = snapshot
            document.save(update_fields=[
                "cover_image", "cover_alt_text", "published_snapshot_json", "updated_at",
            ])

    if changed:
        content["categories"] = categories
        section.content_json = content
        section.save(update_fields=["content_json", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0022_publication_category_cover"),
    ]

    operations = [
        migrations.AddField(
            model_name="cmspublicationcategory",
            name="display_number",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="cmspublicationdocument",
            name="cover_alt_text",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="cmspublicationdocument",
            name="cover_image",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="publication_document_covers",
                to="cms.cmsmediaasset",
            ),
        ),
        migrations.RunPython(prepare_publications, migrations.RunPython.noop),
    ]
