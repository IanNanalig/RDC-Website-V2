from django.core.management.base import BaseCommand

from cms.models import (
    CMSCarouselItem,
    CMSLegacyMigrationIssue,
    CMSPage,
    CMSPublicationCategory,
    CMSPublicationDocument,
    CMSResolution,
)
from cms.registry import FIXED_CMS_PAGE_REGISTRY


class Command(BaseCommand):
    help = "Read-only audit of fixed CMS modules and normalized legacy imports."

    def handle(self, *args, **options):
        missing_pages = []
        missing_sections = []
        extra_sections = []
        for slug, definition in FIXED_CMS_PAGE_REGISTRY.items():
            page = CMSPage.objects.filter(slug=slug).prefetch_related("sections").first()
            if not page:
                missing_pages.append(slug)
                continue
            actual = {row.section_key for row in page.sections.all()}
            expected = {row[0] for row in definition["sections"]}
            missing_sections.extend(f"{slug}/{key}" for key in sorted(expected - actual))
            extra_sections.extend(f"{slug}/{key}" for key in sorted(actual - expected))

        self.stdout.write(f"Fixed modules: {len(FIXED_CMS_PAGE_REGISTRY) - len(missing_pages)}/{len(FIXED_CMS_PAGE_REGISTRY)}")
        self.stdout.write(f"Carousel items: {CMSCarouselItem.objects.count()}")
        self.stdout.write(f"Publication categories: {CMSPublicationCategory.objects.count()}")
        self.stdout.write(f"Publication documents: {CMSPublicationDocument.objects.count()}")
        self.stdout.write(f"Resolutions: {CMSResolution.objects.count()}")
        self.stdout.write(f"Unresolved migration issues: {CMSLegacyMigrationIssue.objects.filter(resolved_at__isnull=True).count()}")
        for label, rows in (
            ("Missing page", missing_pages),
            ("Missing section", missing_sections),
            ("Preserved legacy section", extra_sections),
        ):
            for row in rows:
                self.stdout.write(self.style.WARNING(f"{label}: {row}"))

        if missing_pages or missing_sections:
            self.stderr.write(self.style.ERROR("Fixed CMS registry is incomplete."))
        else:
            self.stdout.write(self.style.SUCCESS("Fixed CMS registry is complete."))
