from copy import deepcopy

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cms.management.commands.seed_publications_cms import PUBLICATION_CATEGORIES
from cms.models import CMSPageSection, CMSRevision
from cms.services.publishing import create_section_update_revision, mark_page_changed


def _normalized(value):
    return str(value or "").strip().casefold()


def _matching_index(items, default_item):
    default_id = _normalized(default_item.get("id"))
    default_title = _normalized(default_item.get("title"))

    if default_id:
        for index, item in enumerate(items):
            if isinstance(item, dict) and _normalized(item.get("id")) == default_id:
                return index

    if default_title:
        for index, item in enumerate(items):
            if isinstance(item, dict) and _normalized(item.get("title")) == default_title:
                return index

    return None


def _fill_missing_fields(existing, defaults, *, excluded=()):
    merged = deepcopy(existing)
    for key, value in defaults.items():
        if key not in excluded and key not in merged:
            merged[key] = deepcopy(value)
    return merged


def merge_publication_categories(content, default_categories=PUBLICATION_CATEGORIES):
    """Add missing built-in categories/documents without replacing CMS-authored data."""
    merged_content = deepcopy(content) if isinstance(content, dict) else {}
    current_categories = merged_content.get("categories")
    categories = deepcopy(current_categories) if isinstance(current_categories, list) else []
    added_categories = []
    added_documents = []
    warnings = []

    for default_category in default_categories:
        category_index = _matching_index(categories, default_category)
        if category_index is None:
            new_category = deepcopy(default_category)
            new_category.setdefault("isVisible", True)
            for document in new_category.get("documents", []):
                if isinstance(document, dict):
                    document.setdefault("isVisible", True)
            categories.append(new_category)
            added_categories.append(default_category.get("id") or default_category.get("title"))
            continue

        existing_category = categories[category_index]
        merged_category = _fill_missing_fields(existing_category, default_category, excluded=("documents",))
        existing_documents = existing_category.get("documents")
        if existing_documents is not None and not isinstance(existing_documents, list):
            warnings.append(
                f"Skipped documents for {default_category.get('id')}: existing documents value is not a list."
            )
            categories[category_index] = merged_category
            continue

        documents = deepcopy(existing_documents) if isinstance(existing_documents, list) else []
        for default_document in default_category.get("documents", []):
            document_index = _matching_index(documents, default_document)
            if document_index is None:
                new_document = deepcopy(default_document)
                new_document.setdefault("isVisible", True)
                documents.append(new_document)
                added_documents.append(
                    f"{default_category.get('id')}:{default_document.get('id') or default_document.get('title')}"
                )
            else:
                documents[document_index] = _fill_missing_fields(documents[document_index], default_document)

        merged_category["documents"] = documents
        categories[category_index] = merged_category

    merged_content["categories"] = categories
    return merged_content, {
        "added_categories": added_categories,
        "added_documents": added_documents,
        "warnings": warnings,
    }


class Command(BaseCommand):
    help = (
        "Add missing built-in publication categories and documents to the CMS draft "
        "without overwriting custom content or publishing the page."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the changes without updating the database.",
        )

    def handle(self, *args, **options):
        try:
            section = CMSPageSection.objects.select_related("page").get(
                page__slug="publications",
                section_key="publication-catalog",
            )
        except CMSPageSection.DoesNotExist as exc:
            raise CommandError("The Publications CMS catalog section does not exist.") from exc

        merged_content, result = merge_publication_categories(section.content_json)
        changed = merged_content != section.content_json

        if options["dry_run"]:
            self._write_result(result, changed, prefix="Dry run: ")
            return

        if changed:
            user = self._default_user()
            with transaction.atomic():
                section = CMSPageSection.objects.select_for_update().select_related("page").get(pk=section.pk)
                status_before = section.status
                merged_content, result = merge_publication_categories(section.content_json)
                changed = merged_content != section.content_json
                if changed:
                    section.content_json = merged_content
                    section.status = "draft"
                    section.lock_owner = None
                    section.lock_acquired_at = None
                    section.save(
                        update_fields=[
                            "content_json",
                            "status",
                            "lock_owner",
                            "lock_acquired_at",
                            "updated_at",
                        ]
                    )
                    mark_page_changed(section.page, user)
                    create_section_update_revision(
                        section,
                        user=user,
                        action=CMSRevision.ACTION_UPDATE,
                        status_before=status_before,
                    )

        self._write_result(result, changed)

    def _write_result(self, result, changed, prefix=""):
        added_categories = result["added_categories"]
        added_documents = result["added_documents"]
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{len(added_categories)} categor{'y' if len(added_categories) == 1 else 'ies'} "
                f"and {len(added_documents)} document{' was' if len(added_documents) == 1 else 's were'} added."
            )
        )
        if added_categories:
            self.stdout.write(f"Categories: {', '.join(added_categories)}")
        if added_documents:
            self.stdout.write(f"Documents: {', '.join(added_documents)}")
        for warning in result["warnings"]:
            self.stdout.write(self.style.WARNING(warning))
        if changed:
            self.stdout.write(f"{prefix}The CMS draft changes; the published Publications page remains unchanged.")
        else:
            self.stdout.write(f"{prefix}No database changes are needed.")

    def _default_user(self):
        User = get_user_model()
        return User.objects.filter(is_superuser=True).order_by("id").first()
