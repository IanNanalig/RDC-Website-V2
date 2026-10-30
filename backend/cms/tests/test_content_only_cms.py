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

    def test_only_five_pages_are_editable_while_all_public_pages_remain_registered(self):
        modules = self.client.get("/api/admin/cms/modules/")
        self.assertEqual(modules.status_code, 200)
        self.assertEqual(
            {row["slug"] for row in modules.data},
            {"home", "regional-profile", "publications", "about-rdc", "contact"},
        )
        pages = self.client.get("/api/admin/cms/pages/?view=summary")
        self.assertEqual(pages.status_code, 200)
        rows = pages.data.get("results", pages.data)
        self.assertNotIn("news", {row["slug"] for row in rows})
        self.assertNotIn("projects-dashboard", {row["slug"] for row in rows})
        self.assertEqual(self.client.get("/api/admin/cms/modules/news/").status_code, 404)
        self.assertEqual(self.client.get("/api/admin/cms/modules/projects-dashboard/").status_code, 404)
        news = CMSPage.objects.get(slug="news")
        projects = CMSPage.objects.get(slug="projects-dashboard")
        self.assertEqual(self.client.get(f"/api/admin/cms/pages/{news.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/admin/cms/pages/{projects.pk}/publish/").status_code, 404)
        self.assertEqual(self.client.patch(
            f"/api/admin/cms/sections/{news.sections.first().pk}/",
            {"content_json": {"title": "Not editable"}},
            format="json",
        ).status_code, 404)
        self.assertEqual(self.client.get("/api/public/cms/pages/news/").status_code, 200)
        self.assertEqual(self.client.get("/api/public/cms/pages/projects-dashboard/").status_code, 200)

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

    def test_legacy_carousel_identity_is_persisted_and_survives_title_change(self):
        section = CMSPageSection.objects.get(page__slug="home", section_key="hero-carousel")
        content = dict(section.content_json)
        slides = [dict(row) for row in content.get("slides") or []]
        self.assertTrue(slides)
        slides[0].pop("id", None)
        slides[0].pop("key", None)
        content["slides"] = slides
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        stable_key = saved.data["content_json"]["slides"][0]["id"]
        renamed = dict(saved.data["content_json"])
        renamed["slides"] = [dict(row) for row in renamed["slides"]]
        renamed["slides"][0]["title"] = "Renamed without changing identity"
        renamed_response = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": renamed}, format="json",
        )
        self.assertEqual(renamed_response.status_code, 200, renamed_response.data)
        self.assertEqual(renamed_response.data["content_json"]["slides"][0]["id"], stable_key)
        self.assertEqual(CMSCarouselItem.objects.filter(stable_key=stable_key).count(), 1)

    def test_unrelated_published_carousel_record_does_not_block_home_publish(self):
        CMSCarouselItem.objects.create(
            stable_key="unrelated-published-carousel",
            title="Unrelated migrated item",
            status="published",
            published_at=timezone.now(),
            published_snapshot_json={"id": "unrelated-published-carousel", "title": "Unrelated migrated item"},
        )
        page = CMSPage.objects.get(slug="home")
        response = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def test_publication_category_and_document_identities_survive_title_edits(self):
        page = CMSPage.objects.get(slug="publications")
        section = page.sections.get(section_key="publication-catalog")
        content = dict(section.content_json)
        categories = [dict(row) for row in content.get("categories") or []]
        self.assertTrue(categories)
        categories[0]["documents"] = [dict(row) for row in categories[0].get("documents") or []]
        categories[0].pop("id", None)
        categories[0].pop("code", None)
        if categories[0]["documents"]:
            categories[0]["documents"][0].pop("id", None)
        content["categories"] = categories
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        saved_categories = saved.data["content_json"]["categories"]
        category_code = saved_categories[0]["code"]
        document_key = saved_categories[0]["documents"][0]["id"] if saved_categories[0].get("documents") else ""
        renamed = dict(saved.data["content_json"])
        renamed["categories"] = [dict(row) for row in renamed["categories"]]
        renamed["categories"][0]["documents"] = [dict(row) for row in renamed["categories"][0].get("documents") or []]
        renamed["categories"][0]["title"] = "Renamed publication category"
        if renamed["categories"][0]["documents"]:
            renamed["categories"][0]["documents"][0]["title"] = "Renamed publication document"
        renamed_response = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": renamed}, format="json",
        )
        self.assertEqual(renamed_response.status_code, 200, renamed_response.data)
        self.assertEqual(renamed_response.data["content_json"]["categories"][0]["code"], category_code)
        if document_key:
            self.assertEqual(renamed_response.data["content_json"]["categories"][0]["documents"][0]["id"], document_key)
        published = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)

    def test_genuine_published_carousel_removal_requires_archive_then_publishes(self):
        page = CMSPage.objects.get(slug="home")
        section = page.sections.get(section_key="hero-carousel")
        content = dict(section.content_json)
        slides = [dict(row) for row in content.get("slides") or []]
        self.assertGreater(len(slides), 0)
        removed_key = slides[0].get("id") or slides[0].get("key")
        item = CMSCarouselItem.objects.get(stable_key=removed_key)
        content["slides"] = slides[1:]
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        blocked = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(str(blocked.data.get("code")), "published_content_requires_archive")
        archived = self.client.post(f"/api/admin/cms/carousel-items/{item.pk}/archive/", {}, format="json")
        self.assertEqual(archived.status_code, 200, archived.data)
        published = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)

    def test_collection_archive_and_restore_keep_draft_json_in_sync(self):
        section = CMSPageSection.objects.get(page__slug="home", section_key="hero-carousel")
        first = next(row for row in section.content_json["slides"] if isinstance(row, dict))
        item = CMSCarouselItem.objects.get(stable_key=first["id"])
        archived = self.client.post(f"/api/admin/cms/carousel-items/{item.pk}/archive/", {}, format="json")
        self.assertEqual(archived.status_code, 200, archived.data)
        section.refresh_from_db()
        self.assertNotIn(item.stable_key, {row.get("id") for row in section.content_json["slides"] if isinstance(row, dict)})
        restored = self.client.post(f"/api/admin/cms/carousel-items/{item.pk}/restore/", {}, format="json")
        self.assertEqual(restored.status_code, 200, restored.data)
        section.refresh_from_db()
        self.assertIn(item.stable_key, {row.get("id") for row in section.content_json["slides"] if isinstance(row, dict)})

    def test_normalized_content_mutation_marks_owning_page_unpublished(self):
        page = CMSPage.objects.get(slug="home")
        page.has_unpublished_changes = False
        page.status = "published"
        page.save(update_fields=["has_unpublished_changes", "status"])
        response = self.client.post(
            "/api/admin/cms/carousel-items/",
            {"stable_key": "new-api-carousel", "title": "API carousel", "sort_order": 999},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        page.refresh_from_db()
        self.assertTrue(page.has_unpublished_changes)
        self.assertEqual(page.status, "draft")

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

