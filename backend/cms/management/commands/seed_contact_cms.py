from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from cms.models import CMSPage, CMSPageSection
from cms.services.publishing import publish_page


CONTACT_SECTIONS = [
    {
        "section_key": "contact-hero",
        "section_type": "text",
        "order": 1,
        "content_json": {
            "title": "Contact RDC-NCR",
            "subtitle": "Get in touch with the Regional Development Council - National Capital Region. We're here to help with inquiries, partnership opportunities, and collaborative projects.",
        },
    },
    {
        "section_key": "main-office",
        "section_type": "contact_info",
        "order": 2,
        "content_json": {
            "title": "Main Office Information",
            "addressLabel": "Address",
            "address": "16th Floor, MMDA Head Office, Dofia Julia Vargas Avenue corner Molawe St., Barangay Ugong, Pasig City",
            "emailLabel": "Email",
            "email": "rdc.ncr@mmda.gov.ph",
            "phoneLabel": "Phone",
            "phone": "+63 (2) 1234-5678",
            "hoursLabel": "Office Hours",
            "officeHours": "Monday - Friday: 7:00 AM - 4:00 PM\nSaturday, Sunday & Holidays: Closed",
        },
    },
    {
        "section_key": "location-map",
        "section_type": "location_map",
        "order": 3,
        "content_json": {
            "title": "RDC-NCR Location",
            "subtitle": "MMDA Head Office, Pasig City",
            "badgeLabel": "Live Location",
        },
    },
    {
        "section_key": "message-form",
        "section_type": "form_intro",
        "order": 4,
        "content_json": {
            "title": "Send Us a Message",
            "subtitle": "Have a question or inquiry? Fill out the form below and we'll get back to you as soon as possible.",
            "successTitle": "Thank You!",
            "successMessage": "Your inquiry has been received. We'll respond within 24-48 business hours.",
            "namePlaceholder": "Your full name",
            "emailPlaceholder": "your.email@example.com",
            "subjectPlaceholder": "What is your inquiry about?",
            "messagePlaceholder": "Please describe your inquiry in detail...",
            "submitLabel": "Send Message",
            "loadingLabel": "Sending...",
        },
    },
]


class Command(BaseCommand):
    help = "Create or refresh the published CMS Contact page snapshot."

    def handle(self, *args, **options):
        user = self._default_user()
        target_keys = {section["section_key"] for section in CONTACT_SECTIONS}

        with transaction.atomic():
            page, created = CMSPage.objects.get_or_create(
                slug="contact",
                defaults={
                    "title": "Contact",
                    "created_by": user,
                    "updated_by": user,
                },
            )
            page.title = "Contact"
            page.has_unpublished_changes = True
            if user:
                page.updated_by = user
                if created:
                    page.created_by = user
            page.save()

            for index, section in enumerate(page.sections.order_by("id"), start=1):
                section.order = 1000 + index
                section.save(update_fields=["order", "updated_at"])

            for section_data in CONTACT_SECTIONS:
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
            next_order = len(CONTACT_SECTIONS) + 1
            for offset, section in enumerate(extra_sections):
                section.order = next_order + offset
                section.is_visible = False
                section.save(update_fields=["order", "is_visible", "updated_at"])

        published = publish_page(page, user=user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Published CMS Contact page with {len(published.published_snapshot_json.get('sections', []))} sections."
            )
        )

    def _default_user(self):
        User = get_user_model()
        return User.objects.filter(is_superuser=True).order_by("id").first()
