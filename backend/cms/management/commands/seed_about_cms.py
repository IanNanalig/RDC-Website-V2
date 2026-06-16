from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import CMSPage, CMSPageSection
from cms.services.publishing import publish_page


ABOUT_SECTIONS = [
    {
        "section_key": "about-hero",
        "section_type": "text",
        "order": 1,
        "content_json": {
            "title": "About Regional Development Council - NCR",
            "subtitle": "Mandates, functions, and organizational structure guiding sustainable development in Metro Manila",
        },
    },
    {
        "section_key": "legal-basis",
        "section_type": "document_group",
        "order": 2,
        "content_json": {
            "title": "Legal Basis & Framework",
            "subtitle": "The foundation documents that define our mandate, structure, and operational guidelines",
            "items": [
                {
                    "id": "eo113",
                    "title": "Executive Order No. 113",
                    "description": "Redefining the functions and composition of the Regional Development Council, establishing the framework for regional planning and development coordination.",
                    "icon": "document",
                    "fileType": "PDF",
                    "fileSize": "1.1 MB",
                    "pages": 24,
                },
                {
                    "id": "mmda",
                    "title": "MMDA Resolution No. 02-47",
                    "description": "Metropolitan Manila Development Authority resolution establishing coordination mechanisms and procedures for regional development activities.",
                    "icon": "scale",
                    "fileType": "PDF",
                    "fileSize": "10.8 MB",
                    "pages": 32,
                },
                {
                    "id": "manual",
                    "title": "RDC-NCR Manual",
                    "description": "Comprehensive operational manual detailing the policies, procedures, and guidelines for the functioning of the Regional Development Council.",
                    "icon": "book",
                    "fileType": "PDF",
                    "fileSize": "5.6 MB",
                    "pages": 56,
                    "url": "https://online.fliphtml5.com/igerd/gdgp/#p=32",
                },
            ],
        },
    },
    {
        "section_key": "committees",
        "section_type": "document_group",
        "order": 3,
        "content_json": {
            "title": "Committees",
            "subtitle": "Click on any committee to view detailed information, functions, and members",
            "items": [
                {
                    "id": "executive",
                    "title": "Executive Committee",
                    "description": "Acts on matters requiring immediate RDC attention",
                    "icon": "crown",
                },
                {
                    "id": "sectoral",
                    "title": "Sectoral Committees",
                    "description": "Four specialized development committees",
                    "icon": "building",
                },
                {
                    "id": "special",
                    "title": "Special Committees",
                    "description": "Technical and specialized advisory committees",
                    "icon": "search",
                },
                {
                    "id": "affiliate",
                    "title": "Affiliate Committees",
                    "description": "Support committees under RDC umbrella",
                    "icon": "handshake",
                },
                {
                    "id": "advisory",
                    "title": "Advisory Committees",
                    "description": "Expert consultation bodies",
                    "icon": "lightbulb",
                },
            ],
        },
    },
    {
        "section_key": "organization-structure",
        "section_type": "text",
        "order": 4,
        "content_json": {
            "title": "RDC-NCR Organizational Structure",
            "subtitle": "Clear governance framework showing decision-making flow and reporting lines",
        },
    },
    {
        "section_key": "resolutions-archive",
        "section_type": "text",
        "order": 5,
        "content_json": {
            "title": "RDC-NCR Resolutions Archive",
            "subtitle": "Complete historical record of all RDC-NCR resolutions from 2010 to present",
            "legendTitle": "Document Type Legend",
            "categoryTitle": "Resolution Categories Summary",
        },
    },
]


class Command(BaseCommand):
    help = "Create or refresh the published CMS About RDC page snapshot."

    def handle(self, *args, **options):
        user = self._default_user()
        target_keys = {section["section_key"] for section in ABOUT_SECTIONS}

        with transaction.atomic():
            page, created = CMSPage.objects.get_or_create(
                slug="about-rdc",
                defaults={
                    "title": "About RDC",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            page.title = "About RDC"
            page.has_unpublished_changes = True
            if user:
                page.updated_by = user
                if created:
                    page.created_by = user
            page.save()

            for index, section in enumerate(page.sections.order_by("id"), start=1):
                section.order = 1000 + index
                section.save(update_fields=["order", "updated_at"])

            for section_data in ABOUT_SECTIONS:
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
            next_order = len(ABOUT_SECTIONS) + 1
            for offset, section in enumerate(extra_sections):
                section.order = next_order + offset
                section.is_visible = False
                section.save(update_fields=["order", "is_visible", "updated_at"])

        published = publish_page(page, user=user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Published CMS About RDC page with {len(published.published_snapshot_json.get('sections', []))} sections."
            )
        )

    def _default_user(self):
        User = get_user_model()
        return User.objects.filter(is_superuser=True).order_by("id").first()
