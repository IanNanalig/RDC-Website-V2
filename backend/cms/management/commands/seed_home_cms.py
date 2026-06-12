from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import CMSPage, CMSPageSection
from cms.services.publishing import publish_page


HOME_SECTIONS = [
    {
        "section_key": "hero-carousel",
        "section_type": "hero_carousel",
        "order": 1,
        "content_json": {
            "slides": [
                {
                    "title": "Regional Development Council NCR",
                    "subtitle": "Planning a sustainable and resilient Metro Manila",
                    "imageKey": "photo1",
                    "button1": {"text": "View Plans", "link": "/publications"},
                    "button2": {"text": "Latest Reports", "link": "/publications"},
                },
                {
                    "title": "Building a Better Future",
                    "subtitle": "Collaborative governance for Metro Manila's growth",
                    "imageKey": "photo2",
                    "button1": {"text": "View Projects", "link": "/Projects"},
                    "button2": {"text": "Read News", "link": "/news"},
                },
                {
                    "title": "Strategic Development",
                    "subtitle": "Empowering communities through effective planning",
                    "imageKey": "photo3",
                    "button1": {"text": "View Dashboard", "link": "/Projects"},
                    "button2": {"text": "About RDC", "link": "/about-rdc"},
                },
            ]
        },
    },
    {
        "section_key": "development-plans",
        "section_type": "document_group",
        "order": 2,
        "content_json": {
            "title": "Development Plans and Frameworks",
            "items": [
                {
                    "title": "Metro Manila Greenprint 2030",
                    "category": "Sustainability Framework",
                    "icon": "leaf",
                    "link": "/publications?category=greenprint",
                },
                {
                    "title": "Regional Development Plan",
                    "category": "Comprehensive Plan",
                    "icon": "file",
                    "link": "/publications?category=rdp",
                },
                {
                    "title": "SDG Catch-up Plan",
                    "category": "Development Goals",
                    "icon": "target",
                    "link": "/publications?category=sdg",
                },
            ],
        },
    },
    {
        "section_key": "investment-programming",
        "section_type": "document_group",
        "order": 3,
        "content_json": {
            "title": "Investment Programming",
            "items": [
                {
                    "title": "Regional Development Investment Program",
                    "category": "Investment Portfolio",
                    "icon": "chart-line",
                    "link": "/publications?category=rdip",
                    "quickLinks": [
                        {"label": "RDIP DOCUMENTS", "link": "/publications?category=rdip"},
                        {"label": "RDIP DASHBOARD", "link": "/Projects"},
                    ],
                }
            ],
        },
    },
    {
        "section_key": "monitoring-evaluation",
        "section_type": "document_group",
        "order": 4,
        "content_json": {
            "title": "Monitoring and Evaluation",
            "items": [
                {
                    "title": "Regional Development Report",
                    "category": "Annual Report",
                    "icon": "chart-bar",
                    "link": "/publications?category=rdr",
                },
                {
                    "title": "Regional Project Monitoring and Evaluation System",
                    "category": "Monitoring System",
                    "icon": "clipboard",
                    "link": "/publications?category=rpmes",
                },
            ],
        },
    },
    {
        "section_key": "dashboard-teaser",
        "section_type": "dashboard_teaser",
        "order": 5,
        "content_json": {
            "title": "Regional Development Dashboard",
            "buttonLabel": "View Full Dashboard ->",
            "buttonLink": "/Projects",
        },
    },
    {
        "section_key": "latest-media",
        "section_type": "news_preview",
        "order": 6,
        "content_json": {
            "title": "Latest Media Releases",
            "viewAllLabel": "View all ->",
            "viewAllLink": "/news",
        },
    },
    {
        "section_key": "upcoming-events",
        "section_type": "events_preview",
        "order": 7,
        "content_json": {
            "title": "Upcoming Events",
            "subtitle": "Calendar & Meetings",
            "buttonLabel": "View Full Calendar",
            "calendarTitle": "Public Events and Meetings",
            "calendarSubtitle": "Published schedules from the RDC-NCR public website.",
        },
    },
]


class Command(BaseCommand):
    help = "Create or refresh the published CMS Home page snapshot."

    def handle(self, *args, **options):
        user = self._default_user()
        target_keys = {section["section_key"] for section in HOME_SECTIONS}

        with transaction.atomic():
            page, created = CMSPage.objects.get_or_create(
                slug="home",
                defaults={
                    "title": "Home",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            page.title = "Home"
            page.has_unpublished_changes = True
            if user:
                page.updated_by = user
                if created:
                    page.created_by = user
            page.save()

            for index, section in enumerate(page.sections.order_by("id"), start=1):
                section.order = 1000 + index
                section.save(update_fields=["order", "updated_at"])

            for section_data in HOME_SECTIONS:
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
            next_order = len(HOME_SECTIONS) + 1
            for offset, section in enumerate(extra_sections):
                section.order = next_order + offset
                section.is_visible = False
                section.save(update_fields=["order", "is_visible", "updated_at"])

        published = publish_page(page, user=user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Published CMS home page with {len(published.published_snapshot_json.get('sections', []))} sections."
            )
        )

    def _default_user(self):
        User = get_user_model()
        return User.objects.filter(is_superuser=True).order_by("id").first()
