from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import CMSPage, CMSPageSection
from cms.services.publishing import publish_page


REGION_PROFILE_SECTIONS = [
    {
        "section_key": "region-hero",
        "section_type": "text",
        "order": 1,
        "content_json": {
            "title": "NCR Region Profile",
            "subtitle": "Geography, demographics, economy, and development context of the National Capital Region",
        },
    },
    {
        "section_key": "regional-overview",
        "section_type": "cards",
        "order": 2,
        "content_json": {
            "title": "Regional Overview",
            "paragraphs": [
                "The National Capital Region (NCR), also known as Metropolitan Manila or Metro Manila, is the Philippines' political, economic, educational, and cultural center. It is the smallest region in the country, with a land area of 619.54 square kilometers, and the most densely populated, home to more than 13 million Filipinos.",
                "Located in central Luzon, NCR sits on the eastern coast of Manila Bay at the mouth of the Pasig River. It is bordered by Manila Bay to the west, Central Luzon to the north, Laguna de Bay to the south, and the Sierra Madre mountains to the east.",
                "NCR is the only region in the Philippines without provinces. It is composed of 17 local government units: 16 cities (Caloocan, Malabon, Navotas, Valenzuela, Quezon City, Marikina, Pasig, Taguig, Makati, Manila, Mandaluyong, San Juan, Pasay, Paranaque, Las Pinas, and Muntinlupa) and one municipality, Pateros.",
            ],
            "stats": [
                {
                    "label": "Population",
                    "value": "13.5M",
                    "subtext": "2020 Census",
                    "icon": "people",
                    "color": "from-blue-500 to-cyan-400",
                },
                {
                    "label": "GDP Share",
                    "value": "36%",
                    "subtext": "National GDP",
                    "icon": "gdp",
                    "color": "from-green-500 to-emerald-400",
                },
                {
                    "label": "Land Area",
                    "value": "619.57 km2",
                    "subtext": "Metro Manila",
                    "icon": "map",
                    "color": "from-purple-500 to-indigo-400",
                },
                {
                    "label": "Cities & Municipality",
                    "value": "16 + 1",
                    "subtext": "Pateros",
                    "icon": "building",
                    "color": "from-orange-500 to-red-400",
                },
                {
                    "label": "Key Sectors",
                    "value": "Services",
                    "subtext": "Finance, Trade, BPO",
                    "icon": "office",
                    "color": "from-pink-500 to-rose-400",
                },
            ],
        },
    },
    {
        "section_key": "geographic-coverage",
        "section_type": "location_map",
        "order": 3,
        "content_json": {
            "title": "Geographic Coverage",
            "subtitle": "Metro Manila comprises 16 cities and 1 municipality",
            "caption": "Political map showing the 16 cities and 1 municipality of NCR",
        },
    },
    {
        "section_key": "lgu-directory",
        "section_type": "document_group",
        "order": 4,
        "content_json": {
            "title": "Local Government Units",
            "items": [
                {"name": "Manila", "website": "https://www.manila.gov.ph", "type": "website"},
                {"name": "Quezon City", "website": "https://www.quezoncity.gov.ph", "type": "website"},
                {"name": "Caloocan", "website": "https://caloocancity.gov.ph", "type": "facebook"},
                {"name": "Las Pinas", "website": "https://laspinascity.gov.ph/", "type": "facebook"},
                {"name": "Makati", "website": "https://www.makati.gov.ph", "type": "website"},
                {"name": "Malabon", "website": "https://malabon.gov.ph", "type": "facebook"},
                {"name": "Mandaluyong", "website": "https://mandaluyong.gov.ph", "type": "facebook"},
                {"name": "Marikina", "website": "https://marikina.gov.ph", "type": "facebook"},
                {"name": "Muntinlupa", "website": "https://muntinlupacity.gov.ph", "type": "facebook"},
                {"name": "Navotas", "website": "https://navotas.gov.ph", "type": "facebook"},
                {"name": "Paranaque", "website": "https://paranaque.gov.ph", "type": "facebook"},
                {"name": "Pasay", "website": "https://pasay.gov.ph", "type": "facebook"},
                {"name": "Pasig", "website": "https://pasigcity.gov.ph", "type": "website"},
                {"name": "San Juan", "website": "https://sanjuancity.gov.ph", "type": "facebook"},
                {"name": "Taguig", "website": "https://taguig.gov.ph", "type": "website"},
                {"name": "Valenzuela", "website": "https://valenzuela.gov.ph", "type": "facebook"},
                {"name": "Pateros", "website": "https://www.pateros.gov.ph", "type": "facebook"},
            ],
        },
    },
]


class Command(BaseCommand):
    help = "Create or refresh the published CMS Region Profile page snapshot."

    def handle(self, *args, **options):
        user = self._default_user()
        target_keys = {section["section_key"] for section in REGION_PROFILE_SECTIONS}

        with transaction.atomic():
            page, created = CMSPage.objects.get_or_create(
                slug="regional-profile",
                defaults={
                    "title": "Region Profile",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            page.title = "Region Profile"
            page.has_unpublished_changes = True
            if user:
                page.updated_by = user
                if created:
                    page.created_by = user
            page.save()

            for index, section in enumerate(page.sections.order_by("id"), start=1):
                section.order = 1000 + index
                section.save(update_fields=["order", "updated_at"])

            for section_data in REGION_PROFILE_SECTIONS:
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
            next_order = len(REGION_PROFILE_SECTIONS) + 1
            for offset, section in enumerate(extra_sections):
                section.order = next_order + offset
                section.is_visible = False
                section.save(update_fields=["order", "is_visible", "updated_at"])

        published = publish_page(page, user=user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Published CMS Region Profile page with {len(published.published_snapshot_json.get('sections', []))} sections."
            )
        )

    def _default_user(self):
        User = get_user_model()
        return User.objects.filter(is_superuser=True).order_by("id").first()
