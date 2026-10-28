from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.models import (
    CMSCarouselItem,
    CMSPage,
    CMSPageSection,
    CMSPublicationCategory,
    CMSPublicationDocument,
)
from cms.services.snapshots import compose_public_page_snapshot
from projects.models import User


class ContentOnlyCMSTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="fixed-admin", email="fixed-admin@example.com", password="StrongTest123!", role="admin",
        )
        self.editor = User.objects.create_user(
            username="fixed-editor", email="fixed-editor@example.com", password="StrongTest123!", role="content_editor",
        )
        self.client.force_authenticate(self.admin)

    def test_fixed_module_registry_rejects_structural_mutations(self):
        page = CMSPage.objects.get(slug="contact")
        section = page.sections.get(section_key="contact-hero")
        self.assertEqual(self.client.post("/api/admin/cms/pages/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.patch(f"/api/admin/cms/pages/{page.pk}/", {"title": "Changed"}).status_code, 405)
        self.assertEqual(self.client.post("/api/admin/cms/sections/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/admin/cms/sections/{section.pk}/").status_code, 405)
        self.assertEqual(self.client.get("/api/admin/cms/modules/not-a-module/").status_code, 404)

    def test_module_contact_map_rejects_embed_html_and_invalid_coordinates(self):
        bad_html = self.client.patch(
            "/api/admin/cms/modules/contact/",
            {"sections": {"location-map": {"embedHtml": "<iframe src='bad'></iframe>"}}},
            format="json",
        )
        self.assertEqual(bad_html.status_code, 400)
        bad_coordinates = self.client.patch(
            "/api/admin/cms/modules/contact/",
            {"sections": {"location-map": {"mapQuery": "Pasig", "latitude": "91", "longitude": "121"}}},
            format="json",
        )
        self.assertEqual(bad_coordinates.status_code, 400)
        valid = self.client.patch(
            "/api/admin/cms/modules/contact/",
            {"sections": {"location-map": {"mapQuery": "MMDA Head Office, Pasig City", "latitude": "14.57", "longitude": "121.08"}}},
            format="json",
        )
        self.assertEqual(valid.status_code, 200, valid.data)

    def test_committee_codes_are_fixed(self):
        section = CMSPageSection.objects.get(page__slug="about-rdc", section_key="committees")
        content = dict(section.content_json)
        content["items"] = list(content["items"])[:-1]
        response = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("fixed", str(response.data).lower())

    def test_carousel_section_syncs_normalized_draft(self):
        section = CMSPageSection.objects.get(page__slug="home", section_key="hero-carousel")
        content = dict(section.content_json)
        slides = list(content.get("slides") or [])
        slides.insert(0, {
            "id": "new-fixed-slide", "title": "New fixed slide", "subtitle": "Draft copy",
            "imageKey": "photo1", "button1": {"text": "Read", "link": "/about"},
            "button2": {"text": "Contact", "link": "/contact"},
        })
        content["slides"] = slides
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        item = CMSCarouselItem.objects.get(stable_key="new-fixed-slide")
        self.assertEqual(item.status, "draft")
        self.assertTrue(item.has_unpublished_changes)

    def test_category_dependency_preview_and_guarded_archive(self):
        category = CMSPublicationCategory.objects.create(
            code="dependency-test", name="Dependency Test", status="published",
            published_at=CMSPage.objects.get(slug="publications").published_at,
            published_snapshot_json={"id": "dependency-test", "title": "Dependency Test"},
        )
        CMSPublicationDocument.objects.create(
            stable_key="dependency-test-document", category=category, title="Dependent document",
            status="published", published_at=category.published_at,
            published_snapshot_json={"id": "dependency-test-document", "title": "Dependent document"},
        )
        preview = self.client.get(f"/api/admin/cms/publication-categories/{category.pk}/dependencies/")
        self.assertEqual(preview.status_code, 200)
        blocked = self.client.post(f"/api/admin/cms/publication-categories/{category.pk}/archive/", {}, format="json")
        self.assertEqual(blocked.status_code, 409)
        archived = self.client.post(
            f"/api/admin/cms/publication-categories/{category.pk}/archive/",
            {"document_resolution": "archive_documents"}, format="json",
        )
        self.assertEqual(archived.status_code, 200, archived.data)
        category.refresh_from_db()
        self.assertEqual(category.status, "archived")

    def test_home_feature_reference_uses_published_category_and_documents(self):
        now = timezone.now()
        category = CMSPublicationCategory.objects.create(
            code="home-feature-test", name="Home Feature Test", status="published",
            published_at=now,
            published_snapshot_json={"id": "home-feature-test", "title": "Home Feature Test"},
        )
        CMSPublicationDocument.objects.create(
            stable_key="home-feature-test-document", category=category,
            title="Featured Document", external_url="https://example.com/featured.pdf",
            status="published", published_at=now,
            published_snapshot_json={
                "id": "home-feature-test-document", "title": "Featured Document",
                "url": "https://example.com/featured.pdf", "sortOrder": 1,
            },
        )
        page = CMSPage.objects.get(slug="home")
        snapshot = dict(page.published_snapshot_json)
        sections = list(snapshot["sections"])
        target = next(row for row in sections if row["sectionKey"] == "development-plans")
        target["content"] = {**target["content"], "featuredCategoryCode": category.code}
        snapshot["sections"] = sections
        page.published_snapshot_json = snapshot
        composed = compose_public_page_snapshot(page)
        content = next(
            row["content"] for row in composed["sections"]
            if row["sectionKey"] == "development-plans"
        )
        self.assertEqual(content["featuredCategory"]["title"], "Home Feature Test")
        self.assertEqual(content["featuredCategory"]["documents"][0]["title"], "Featured Document")

    def test_migration_audit_command_is_read_only_and_reports_registry(self):
        before = (CMSPage.objects.count(), CMSPageSection.objects.count())
        output = StringIO()
        call_command("audit_content_only_cms", stdout=output)
        self.assertIn("Fixed CMS registry is complete", output.getvalue())
        self.assertEqual(before, (CMSPage.objects.count(), CMSPageSection.objects.count()))

    def test_content_editor_cannot_publish_module(self):
        self.client.force_authenticate(self.editor)
        response = self.client.post("/api/admin/cms/modules/contact/publish/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

