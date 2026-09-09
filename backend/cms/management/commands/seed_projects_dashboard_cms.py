from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import CMSPage, CMSPageSection
from cms.services.publishing import publish_page


PROJECTS_DASHBOARD_SECTIONS = [
    {
        "section_key": "projects-hero",
        "section_type": "text",
        "order": 1,
        "content_json": {
            "title": "RDIP Projects Dashboard",
            "subtitle": "Explore, filter, and visualize NCR Regional Development projects",
            "body": "Dashboard figures come from endorsed public project records and are not manually entered in the CMS.",
        },
    },
    {
        "section_key": "projects-updates",
        "section_type": "text",
        "order": 2,
        "content_json": {
            "title": "Latest validator-approved project progress",
            "subtitle": "Recently Updated",
            "body": "Only endorsed public updates are shown here.",
        },
    },
    {
        "section_key": "projects-data-note",
        "section_type": "text",
        "order": 3,
        "content_json": {
            "title": "About this dashboard",
            "subtitle": "Published project information",
            "body": "Project totals, budgets, statuses, locations, and progress updates are sourced from records that completed the RDC-NCR portal review workflow.",
        },
    },
]


class Command(BaseCommand):
    help = "Create or refresh the published CMS Projects Dashboard page snapshot."

    def handle(self, *args, **options):
        user = self._default_user()
        target_keys = {section["section_key"] for section in PROJECTS_DASHBOARD_SECTIONS}

        with transaction.atomic():
            page, created = CMSPage.objects.get_or_create(
                slug="projects-dashboard",
                defaults={
                    "title": "Projects Dashboard",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            page.title = "Projects Dashboard"
            page.has_unpublished_changes = True
            if user:
                page.updated_by = user
                if created:
                    page.created_by = user
            page.save()

            for index, section in enumerate(page.sections.order_by("id"), start=1):
                section.order = 1000 + index
                section.save(update_fields=["order", "updated_at"])

            for section_data in PROJECTS_DASHBOARD_SECTIONS:
                CMSPageSection.objects.update_or_create(
                    page=page,
                    section_key=section_data["section_key"],
                    defaults={
                        "section_type": section_data["section_type"],
                        "order": section_data["order"],
                        "content_json": section_data["content_json"],
                        "schema_version": 1,
                        "is_visible": True,
                    },
                )

            extra_sections = page.sections.exclude(section_key__in=target_keys).order_by("order", "id")
            next_order = len(PROJECTS_DASHBOARD_SECTIONS) + 1
            for offset, section in enumerate(extra_sections):
                section.order = next_order + offset
                section.save(update_fields=["order", "updated_at"])

        published = publish_page(page, user=user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Published CMS Projects Dashboard page with {len(published.published_snapshot_json.get('sections', []))} sections."
            )
        )

    def _default_user(self):
        User = get_user_model()
        return User.objects.filter(is_superuser=True).order_by("id").first()
