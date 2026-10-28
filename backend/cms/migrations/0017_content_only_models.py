from datetime import date

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


WORKFLOW_FIELDS = [
    ("status", models.CharField(choices=[("draft", "Draft"), ("submitted", "Submitted for review"), ("published", "Published"), ("rejected", "Rejected"), ("archived", "Archived")], default="draft", max_length=20)),
    ("published_snapshot_json", models.JSONField(blank=True, default=dict)),
    ("has_unpublished_changes", models.BooleanField(default=True)),
    ("review_notes", models.TextField(blank=True)),
    ("published_at", models.DateTimeField(blank=True, null=True)),
    ("archived_at", models.DateTimeField(blank=True, null=True)),
    ("created_at", models.DateTimeField(auto_now_add=True)),
    ("updated_at", models.DateTimeField(auto_now=True)),
    ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
    ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
    ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
    ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
]


def _section(page, key, published=False):
    source = page.published_snapshot_json if published else None
    if published:
        for row in (source or {}).get("sections", []):
            if row.get("sectionKey") == key:
                return row.get("content") if isinstance(row.get("content"), dict) else {}
        return {}
    row = page.sections.filter(section_key=key).first()
    return row.content_json if row and isinstance(row.content_json, dict) else {}


def _key(value, fallback):
    return (slugify(str(value or "")) or fallback)[:120]


def _snapshot_status(draft, published):
    return (
        "published" if published else "draft",
        bool(published and draft != published),
    )


def import_legacy_content(apps, schema_editor):
    CMSPage = apps.get_model("cms", "CMSPage")
    Carousel = apps.get_model("cms", "CMSCarouselItem")
    Category = apps.get_model("cms", "CMSPublicationCategory")
    Document = apps.get_model("cms", "CMSPublicationDocument")
    Resolution = apps.get_model("cms", "CMSResolution")
    Issue = apps.get_model("cms", "CMSLegacyMigrationIssue")

    home = CMSPage.objects.filter(slug="home").first()
    if home:
        draft_rows = _section(home, "hero-carousel").get("slides", [])
        published_rows = _section(home, "hero-carousel", True).get("slides", [])
        published_by_key = {
            _key(row.get("id") or row.get("key") or row.get("title"), f"slide-{index}"): row
            for index, row in enumerate(published_rows, 1) if isinstance(row, dict)
        }
        for index, row in enumerate(draft_rows, 1):
            if not isinstance(row, dict):
                Issue.objects.create(page_slug="home", section_key="hero-carousel", item_path=f"slides[{index - 1}]", reason="Carousel item is not an object.", legacy_payload={"value": row})
                continue
            stable_key = _key(row.get("id") or row.get("key") or row.get("title"), f"slide-{index}")
            published = published_by_key.get(stable_key, {})
            status, changed = _snapshot_status(row, published)
            first = row.get("button1") if isinstance(row.get("button1"), dict) else {}
            second = row.get("button2") if isinstance(row.get("button2"), dict) else {}
            Carousel.objects.update_or_create(stable_key=stable_key, defaults={
                "title": str(row.get("title") or "Untitled slide"),
                "description": str(row.get("subtitle") or row.get("description") or ""),
                "legacy_image_url": str(row.get("imageUrl") or row.get("image") or row.get("imageKey") or ""),
                "primary_label": str(first.get("text") or ""), "primary_url": str(first.get("link") or ""),
                "secondary_label": str(second.get("text") or ""), "secondary_url": str(second.get("link") or ""),
                "sort_order": index, "status": status, "published_snapshot_json": published,
                "has_unpublished_changes": changed, "published_at": home.published_at if published else None,
            })
        featured_defaults = {
            "development-plans": "greenprint",
            "investment-programming": "rdip",
            "monitoring-evaluation": "rdr",
        }
        for section_key, category_code in featured_defaults.items():
            section = home.sections.filter(section_key=section_key).first()
            if section:
                content = dict(section.content_json or {})
                content.setdefault("featuredCategoryCode", category_code)
                section.content_json = content
                section.save(update_fields=["content_json"])
        published_snapshot = dict(home.published_snapshot_json or {})
        published_sections = list(published_snapshot.get("sections") or [])
        for row in published_sections:
            section_key = row.get("sectionKey") if isinstance(row, dict) else ""
            if section_key in featured_defaults and isinstance(row.get("content"), dict):
                row["content"].setdefault("featuredCategoryCode", featured_defaults[section_key])
        if published_sections:
            published_snapshot["sections"] = published_sections
            home.published_snapshot_json = published_snapshot
            home.save(update_fields=["published_snapshot_json"])

    publications = CMSPage.objects.filter(slug="publications").first()
    if publications:
        draft_categories = _section(publications, "publication-catalog").get("categories", [])
        published_categories = _section(publications, "publication-catalog", True).get("categories", [])
        pub_by_code = {
            _key(row.get("id") or row.get("code") or row.get("title"), f"category-{index}"): row
            for index, row in enumerate(published_categories, 1) if isinstance(row, dict)
        }
        for category_index, row in enumerate(draft_categories, 1):
            if not isinstance(row, dict):
                Issue.objects.create(page_slug="publications", section_key="publication-catalog", item_path=f"categories[{category_index - 1}]", reason="Publication category is not an object.", legacy_payload={"value": row})
                continue
            code = _key(row.get("id") or row.get("code") or row.get("title"), f"category-{category_index}")
            published = pub_by_code.get(code, {})
            status, changed = _snapshot_status(row, published)
            category, _ = Category.objects.update_or_create(code=code, defaults={
                "name": str(row.get("title") or "Publication Category"), "description": str(row.get("description") or ""),
                "icon": str(row.get("icon") or "document"), "color": str(row.get("color") or ""),
                "sort_order": category_index, "status": status, "published_snapshot_json": published,
                "has_unpublished_changes": changed, "published_at": publications.published_at if published else None,
            })
            published_docs = published.get("documents", []) if isinstance(published, dict) else []
            pub_docs_by_key = {
                _key(item.get("id") or item.get("title"), f"document-{index}"): item
                for index, item in enumerate(published_docs, 1) if isinstance(item, dict)
            }
            for document_index, item in enumerate(row.get("documents", []), 1):
                if not isinstance(item, dict):
                    Issue.objects.create(page_slug="publications", section_key="publication-catalog", item_path=f"categories[{category_index - 1}].documents[{document_index - 1}]", reason="Publication document is not an object.", legacy_payload={"value": item})
                    continue
                doc_key = _key(item.get("id") or item.get("title"), f"document-{document_index}")
                stable_key = _key(f"{code}-{doc_key}", f"{code}-document-{document_index}")
                published_doc = pub_docs_by_key.get(doc_key, {})
                doc_status, doc_changed = _snapshot_status(item, published_doc)
                year = str(item.get("year") or "").strip()
                publication_date = date(int(year), 1, 1) if year.isdigit() and 1900 <= int(year) <= 2200 else None
                Document.objects.update_or_create(stable_key=stable_key, defaults={
                    "category": category, "title": str(item.get("title") or "Untitled publication"),
                    "description": str(item.get("description") or ""), "publication_date": publication_date,
                    "document_type": str(item.get("fileType") or "PDF"),
                    "external_url": str(item.get("url") or ""), "legacy_file_size": str(item.get("fileSize") or ""),
                    "sort_order": document_index, "status": doc_status,
                    "published_snapshot_json": published_doc, "has_unpublished_changes": doc_changed,
                    "published_at": publications.published_at if published_doc else None,
                })

    about = CMSPage.objects.filter(slug="about-rdc").first()
    if about:
        draft_years = _section(about, "resolutions-archive").get("years", [])
        for year_index, year_row in enumerate(draft_years, 1):
            if not isinstance(year_row, dict):
                Issue.objects.create(page_slug="about-rdc", section_key="resolutions-archive", item_path=f"years[{year_index - 1}]", reason="Resolution year is not an object.", legacy_payload={"value": year_row})
                continue
            raw_year = str(year_row.get("year") or year_row.get("title") or "")
            digits = "".join(character for character in raw_year if character.isdigit())
            if len(digits) < 4:
                Issue.objects.create(page_slug="about-rdc", section_key="resolutions-archive", item_path=f"years[{year_index - 1}]", reason="Resolution group has no valid year.", legacy_payload=year_row)
                continue
            year = int(digits[:4])
            rows = year_row.get("resolutions") or year_row.get("items") or year_row.get("documents") or []
            for item_index, item in enumerate(rows, 1):
                if not isinstance(item, dict):
                    continue
                number = str(item.get("number") or item.get("resolutionNumber") or item.get("title") or f"Resolution {item_index}")
                stable_key = _key(item.get("id") or f"{year}-{number}", f"resolution-{year}-{item_index}")
                Resolution.objects.update_or_create(stable_key=stable_key, defaults={
                    "resolution_number": number, "title": str(item.get("title") or number),
                    "description": str(item.get("description") or ""), "year": year,
                    "external_url": str(item.get("url") or item.get("link") or ""), "sort_order": item_index,
                    "status": "published" if about.published_at else "draft",
                    "published_snapshot_json": item if about.published_at else {},
                    "has_unpublished_changes": False, "published_at": about.published_at,
                })


class Migration(migrations.Migration):

    dependencies = [("cms", "0016_project_concern_categories")]

    operations = [
        migrations.CreateModel(
            name="CMSLegacyMigrationIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("page_slug", models.SlugField(max_length=120)), ("section_key", models.SlugField(max_length=120)),
                ("item_path", models.CharField(blank=True, max_length=250)), ("reason", models.CharField(max_length=500)),
                ("legacy_payload", models.JSONField(blank=True, default=dict)), ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["page_slug", "section_key", "item_path", "id"]},
        ),
        migrations.CreateModel(
            name="CMSCarouselItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *WORKFLOW_FIELDS,
                ("stable_key", models.SlugField(max_length=120, unique=True)), ("title", models.CharField(max_length=220)),
                ("description", models.TextField(blank=True)), ("legacy_image_url", models.CharField(blank=True, max_length=1000)),
                ("primary_label", models.CharField(blank=True, max_length=120)), ("primary_url", models.CharField(blank=True, max_length=500)),
                ("secondary_label", models.CharField(blank=True, max_length=120)), ("secondary_url", models.CharField(blank=True, max_length=500)),
                ("sort_order", models.PositiveIntegerField(default=1)),
                ("image", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="carousel_items", to="cms.cmsmediaasset")),
            ], options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="CMSPublicationCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), *WORKFLOW_FIELDS,
                ("code", models.SlugField(max_length=80, unique=True)), ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)), ("icon", models.CharField(blank=True, max_length=80)),
                ("color", models.CharField(blank=True, max_length=120)), ("sort_order", models.PositiveIntegerField(default=1)),
            ], options={"ordering": ["sort_order", "name", "id"]},
        ),
        migrations.CreateModel(
            name="CMSPublicationDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), *WORKFLOW_FIELDS,
                ("stable_key", models.SlugField(max_length=120, unique=True)), ("title", models.CharField(max_length=250)),
                ("description", models.TextField(blank=True)), ("publication_date", models.DateField(blank=True, db_index=True, null=True)),
                ("document_type", models.CharField(default="PDF", max_length=50)), ("external_url", models.CharField(blank=True, max_length=1000)),
                ("legacy_file_size", models.CharField(blank=True, max_length=40)), ("sort_order", models.PositiveIntegerField(default=1)),
                ("attachment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="publication_documents", to="cms.cmsmediaasset")),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="documents", to="cms.cmspublicationcategory")),
            ], options={"ordering": ["category__sort_order", "sort_order", "title", "id"]},
        ),
        migrations.CreateModel(
            name="CMSResolution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), *WORKFLOW_FIELDS,
                ("stable_key", models.SlugField(max_length=120, unique=True)), ("resolution_number", models.CharField(max_length=120)),
                ("title", models.CharField(max_length=250)), ("description", models.TextField(blank=True)),
                ("year", models.PositiveSmallIntegerField(db_index=True)), ("resolution_date", models.DateField(blank=True, db_index=True, null=True)),
                ("external_url", models.CharField(blank=True, max_length=1000)), ("sort_order", models.PositiveIntegerField(default=1)),
                ("attachment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="rdc_resolutions", to="cms.cmsmediaasset")),
            ], options={"ordering": ["-year", "sort_order", "resolution_number", "id"]},
        ),
        migrations.AddIndex(model_name="cmslegacymigrationissue", index=models.Index(fields=["page_slug", "section_key", "resolved_at"], name="cms_cmslega_page_sl_23854a_idx")),
        migrations.RunPython(import_legacy_content, migrations.RunPython.noop),
    ]

