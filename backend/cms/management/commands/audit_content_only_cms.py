from django.core.management.base import BaseCommand

from cms.models import (
    CMSCarouselItem,
    CMSLegacyMigrationIssue,
    CMSPage,
    CMSPageSection,
    CMSPublicationCategory,
    CMSPublicationDocument,
    CMSResolution,
)
from cms.registry import FIXED_CMS_PAGE_REGISTRY
from cms.services.collections import publication_membership


class Command(BaseCommand):
    help = "Read-only audit of fixed CMS modules and normalized legacy imports."

    def add_arguments(self, parser):
        parser.add_argument("--archive-inventory", action="store_true", help="Count historical records excluded from the general CMS Archive.")

    def handle(self, *args, **options):
        missing_pages = []
        missing_sections = []
        extra_sections = []
        missing_identities = []
        for slug, definition in FIXED_CMS_PAGE_REGISTRY.items():
            page = CMSPage.objects.filter(slug=slug).prefetch_related("sections").first()
            if not page:
                missing_pages.append(slug)
                continue
            actual = {row.section_key for row in page.sections.all()}
            expected = {row[0] for row in definition["sections"]}
            missing_sections.extend(f"{slug}/{key}" for key in sorted(expected - actual))
            extra_sections.extend(f"{slug}/{key}" for key in sorted(actual - expected))
            for section in page.sections.all():
                content = section.content_json if isinstance(section.content_json, dict) else {}
                if slug == "home" and section.section_key == "hero-carousel":
                    missing_identities.extend(
                        f"{slug}/{section.section_key}/slides[{index}]"
                        for index, row in enumerate(content.get("slides") or [])
                        if isinstance(row, dict) and not (row.get("id") or row.get("key"))
                    )
                if slug == "publications" and section.section_key == "publication-catalog":
                    for category_index, row in enumerate(content.get("categories") or []):
                        if not isinstance(row, dict):
                            continue
                        if not (row.get("id") or row.get("code")):
                            missing_identities.append(f"{slug}/{section.section_key}/categories[{category_index}]")
                        missing_identities.extend(
                            f"{slug}/{section.section_key}/categories[{category_index}].documents[{document_index}]"
                            for document_index, item in enumerate(row.get("documents") or [])
                            if isinstance(item, dict) and not item.get("id")
                        )
                if slug == "about-rdc" and section.section_key == "resolutions-archive":
                    for year_index, year_row in enumerate(content.get("years") or []):
                        if not isinstance(year_row, dict):
                            continue
                        rows = year_row.get("resolutions") or year_row.get("items") or year_row.get("documents") or []
                        missing_identities.extend(
                            f"{slug}/{section.section_key}/years[{year_index}].resolutions[{item_index}]"
                            for item_index, item in enumerate(rows)
                            if isinstance(item, dict) and not item.get("id")
                        )

        self.stdout.write(f"Fixed modules: {len(FIXED_CMS_PAGE_REGISTRY) - len(missing_pages)}/{len(FIXED_CMS_PAGE_REGISTRY)}")
        self.stdout.write(f"Carousel items: {CMSCarouselItem.objects.count()}")
        self.stdout.write(f"Publication categories: {CMSPublicationCategory.objects.count()}")
        self.stdout.write(f"Publication documents: {CMSPublicationDocument.objects.count()}")
        self.stdout.write(f"Resolutions: {CMSResolution.objects.count()}")
        self.stdout.write(f"Unresolved migration issues: {CMSLegacyMigrationIssue.objects.filter(resolved_at__isnull=True).count()}")
        self.stdout.write(f"Collection rows missing stable identity: {len(missing_identities)}")
        for label, rows in (
            ("Missing page", missing_pages),
            ("Missing section", missing_sections),
            ("Preserved legacy section", extra_sections),
            ("Missing stable identity", missing_identities),
        ):
            for row in rows:
                self.stdout.write(self.style.WARNING(f"{label}: {row}"))

        if missing_pages or missing_sections:
            self.stderr.write(self.style.ERROR("Fixed CMS registry is incomplete."))
        else:
            self.stdout.write(self.style.SUCCESS("Fixed CMS registry is complete."))
        if options["archive_inventory"]:
            self.report_archive_inventory()

    def report_archive_inventory(self):
        archived_documents = CMSPublicationDocument.objects.filter(status="archived")
        for label, rows in (
            ("Carousel items", CMSCarouselItem.objects.filter(status="archived")),
            ("Publication categories", CMSPublicationCategory.objects.filter(status="archived")),
            ("Publication documents", archived_documents),
            ("Resolutions", CMSResolution.objects.filter(status="archived")),
        ):
            self.stdout.write(f"Historical archive records ({label}): {rows.count()}")
        catalog = CMSPageSection.objects.filter(
            page__slug="publications", section_key="publication-catalog",
        ).values_list("content_json", flat=True).first() or {}
        draft_categories = {code for code, _, _ in publication_membership(catalog)}
        self.stdout.write(
            f"Archived publication templates outside current draft categories: "
            f"{archived_documents.exclude(category__code__in=draft_categories).count()}"
        )
        self.stdout.write(
            f"Draft publication templates outside current draft categories: "
            f"{CMSPublicationDocument.objects.filter(status='draft').exclude(category__code__in=draft_categories).count()}"
        )
        self.stdout.write(
            f"Archived publication templates with archived media: "
            f"{archived_documents.filter(attachment__is_archived=True).count()}"
        )
        self.stdout.write(
            f"Archived publication templates without a media attachment or external URL: "
            f"{archived_documents.filter(attachment__isnull=True, external_url='').count()}"
        )
