from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import CMSPage, CMSPageSection
from cms.services.publishing import publish_page


PUBLICATION_CATEGORIES = [
    {
        "id": "greenprint",
        "title": "Greenprint 2030",
        "description": "Strategic environmental and sustainability framework for Metro Manila",
        "icon": "leaf",
        "color": "from-green-600 to-emerald-500",
        "documents": [
            {"id": "gp1", "title": "Greenprint 2030 Full Document", "year": "2023", "fileType": "PDF", "fileSize": "6.9 MB"},
            {"id": "gp2", "title": "Green Print Brochure", "year": "2023", "fileType": "PDF", "fileSize": "2.8 MB"},
        ],
    },
    {
        "id": "rdp",
        "title": "Regional Development Plans (RDP-NCR)",
        "description": "Comprehensive development blueprints and strategic plans",
        "icon": "clipboard",
        "color": "from-blue-600 to-cyan-500",
        "documents": [
            {"id": "rdp1", "title": "RDP-NCR 2023-2028 (Full Version)", "year": "2023", "fileType": "PDF", "fileSize": "36.4 MB"},
            {"id": "rdp2", "title": "RDP-NCR 2023-2028 (Abridged Version)", "year": "2023", "fileType": "PDF", "fileSize": "10.6 MB"},
            {"id": "rdp3", "title": "RDP-NCR 2023-2028 Brochure", "year": "2023", "fileType": "PDF", "fileSize": "2.2 MB"},
            {"id": "rdp4", "title": "RDP-NCR 2017-2022 (Full Version)", "year": "2023", "fileType": "PDF", "fileSize": "8.0 MB"},
            {"id": "rdp5", "title": "RDP-NCR 2017-2022 (Abridged Version)", "year": "2023", "fileType": "PDF", "fileSize": "1.1 MB"},
            {"id": "rdp6", "title": "RDP-NCR 2017-2022 Brochure", "year": "2023", "fileType": "PDF", "fileSize": "5.3 MB"},
        ],
    },
    {
        "id": "rdip",
        "title": "Regional Development Investment Program (RDIP)",
        "description": "Priority investment programs and infrastructure projects",
        "icon": "briefcase",
        "color": "from-purple-600 to-indigo-500",
        "documents": [
            {"id": "rdip1", "title": "RDIP-NCR 2023-2028", "year": "2023", "fileType": "PDF", "fileSize": "12.4 MB"},
            {"id": "rdip2", "title": "RDIP-NCR 2020-2022", "year": "2020", "fileType": "PDF", "fileSize": "10.4 MB"},
            {"id": "rdip3", "title": "RDIP Updated List 2024", "year": "2024", "fileType": "PDF", "fileSize": "1.9 MB"},
            {"id": "rdip4", "title": "RDIP Updated List 2023", "year": "2023", "fileType": "PDF", "fileSize": "7.3 MB"},
        ],
    },
    {
        "id": "rdr",
        "title": "Regional Development Report (RDR)",
        "description": "Annual progress reports and development outcomes",
        "icon": "chart-bar",
        "color": "from-orange-600 to-red-500",
        "documents": [
            {"id": "rdr1", "title": "RDR 2023", "year": "2023", "fileType": "PDF", "fileSize": "43.6 MB"},
        ],
    },
    {
        "id": "res",
        "title": "Regional Economic Situationer (RES)",
        "description": "Economic performance and trends analysis",
        "icon": "trend",
        "color": "from-teal-600 to-green-500",
        "documents": [
            {"id": "res1", "title": "RES Annual 2021", "year": "2024", "fileType": "PDF", "fileSize": "7.9 MB"},
            {"id": "res2", "title": "RES Annual 2022", "year": "2024", "fileType": "PDF", "fileSize": "10.5 MB"},
            {"id": "res4", "title": "RES Annual 2023", "year": "2023", "fileType": "PDF", "fileSize": "17.8 MB"},
        ],
    },
    {
        "id": "sdg",
        "title": "SDG Catch-Up Plan",
        "description": "Sustainable Development Goals acceleration strategies",
        "icon": "target",
        "color": "from-pink-600 to-rose-500",
        "documents": [
            {"id": "sdg1", "title": "SDG Catch-Up Plan 2023-2028", "year": "2023", "fileType": "PDF", "fileSize": "3.1 MB"},
            {"id": "sdg2", "title": "SDG Progress Report 2023", "year": "2023", "fileType": "PDF", "fileSize": "2.4 MB"},
            {"id": "sdg3", "title": "SDG Monitoring Framework", "year": "2024", "fileType": "PDF", "fileSize": "1.5 MB"},
        ],
    },
    {
        "id": "rpmes",
        "title": "Regional Project Monitoring and Evaluation System (RPMES)",
        "description": "Regional Project Monitoring and Evaluation System",
        "icon": "gear",
        "color": "from-slate-600 to-gray-500",
        "documents": [
            {"id": "rpmes3", "title": "RPMES Operational Guidelines", "year": "2024", "fileType": "PDF", "fileSize": "8.4 MB"},
        ],
    },
    {
        "id": "rrp",
        "title": "Rehabilitation & Recovery Plan for the National Capital Region (RRP-NCR)",
        "description": "Post-disaster recovery and resilience strategies",
        "icon": "refresh",
        "color": "from-yellow-600 to-orange-500",
        "documents": [
            {"id": "rrp1", "title": "RRP-NCR with Investment Program (Full Document)", "year": "2024", "fileType": "PDF", "fileSize": "31.5 MB"},
            {"id": "rrp2", "title": "RRP-NCR (Abridge Version)", "year": "2023", "fileType": "PDF", "fileSize": "2.5 MB"},
        ],
    },
]


PUBLICATIONS_SECTIONS = [
    {
        "section_key": "publication-catalog",
        "section_type": "publication_catalog",
        "order": 1,
        "content_json": {
            "title": "Publications & Official Documents",
            "subtitle": "Plans, reports, and development programs for the National Capital Region",
            "browseTitle": "Browse by Category",
            "browseSubtitle": "Select a category to view available documents",
            "categories": PUBLICATION_CATEGORIES,
        },
    },
]


class Command(BaseCommand):
    help = "Create or refresh the published CMS Publications page snapshot."

    def handle(self, *args, **options):
        user = self._default_user()
        target_keys = {section["section_key"] for section in PUBLICATIONS_SECTIONS}

        with transaction.atomic():
            page, created = CMSPage.objects.get_or_create(
                slug="publications",
                defaults={
                    "title": "Publications",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            page.title = "Publications"
            page.has_unpublished_changes = True
            if user:
                page.updated_by = user
                if created:
                    page.created_by = user
            page.save()

            for index, section in enumerate(page.sections.order_by("id"), start=1):
                section.order = 1000 + index
                section.save(update_fields=["order", "updated_at"])

            for section_data in PUBLICATIONS_SECTIONS:
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
            next_order = len(PUBLICATIONS_SECTIONS) + 1
            for offset, section in enumerate(extra_sections):
                section.order = next_order + offset
                section.is_visible = False
                section.save(update_fields=["order", "is_visible", "updated_at"])

        published = publish_page(page, user=user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Published CMS Publications page with {len(published.published_snapshot_json.get('sections', []))} sections."
            )
        )

    def _default_user(self):
        User = get_user_model()
        return User.objects.filter(is_superuser=True).order_by("id").first()
