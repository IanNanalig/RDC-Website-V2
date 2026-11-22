from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.models import (
    CMSCarouselItem,
    CMSArticle,
    CMSMediaAsset,
    CMSPage,
    CMSPageSection,
    CMSPublicationCategory,
    CMSPublicationDocument,
    CMSResolution,
)
from cms.services.snapshots import _publication_document_sort_key, compose_public_page_snapshot
from projects.models import PublicEvent, User, UserActivity


class ContentOnlyCMSTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="fixed-admin", email="fixed-admin@example.com", password="StrongTest123!", role="admin",
        )
        self.editor = User.objects.create_user(
            username="fixed-editor", email="fixed-editor@example.com", password="StrongTest123!", role="content_editor",
        )
        self.client.force_authenticate(self.admin)

    def test_publication_document_year_ranges_sort_newest_first(self):
        rows = [
            {"title": "RDP-NCR 2017-2022 Brochure", "sortOrder": 1},
            {"title": "RDP-NCR 2023-2028 Brochure", "sortOrder": 2},
            {"title": "Undated publication", "sortOrder": 3},
        ]
        ordered = sorted(rows, key=_publication_document_sort_key)
        self.assertEqual(
            [row["title"] for row in ordered],
            [
                "RDP-NCR 2023-2028 Brochure",
                "RDP-NCR 2017-2022 Brochure",
                "Undated publication",
            ],
        )

    def test_regional_map_uses_only_active_media_library_images(self):
        section = CMSPageSection.objects.get(page__slug="regional-profile", section_key="geographic-coverage")
        image = CMSMediaAsset.objects.create(
            file="cms/test-map.png", public_url="/media/test-map.png",
            file_type=CMSMediaAsset.FILE_TYPE_IMAGE,
        )
        content = {**section.content_json, "mapAssetId": image.pk, "mapImageUrl": "https://invalid.example/map.png"}
        saved = self.client.patch(
            "/api/admin/cms/modules/regional-profile/",
            {"sections": {"geographic-coverage": content}}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        section.refresh_from_db()
        self.assertEqual(section.content_json["mapImageUrl"], "/media/test-map.png")
        published = self.client.post("/api/admin/cms/modules/regional-profile/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        public = self.client.get("/api/public/cms/pages/regional-profile/")
        coverage = next(row["content"] for row in public.data["sections"] if row["sectionKey"] == "geographic-coverage")
        self.assertEqual(coverage["mapImageUrl"], "/media/test-map.png")
        image.is_archived = True
        image.save(update_fields=["is_archived"])
        public = self.client.get("/api/public/cms/pages/regional-profile/")
        coverage = next(row["content"] for row in public.data["sections"] if row["sectionKey"] == "geographic-coverage")
        self.assertNotIn("mapImageUrl", coverage)

    def test_regional_map_section_saves_as_editor_and_clear_publishes_fallback(self):
        section = CMSPageSection.objects.get(page__slug="regional-profile", section_key="geographic-coverage")
        image = CMSMediaAsset.objects.create(
            file="cms/map-replacement.png", public_url="/media/map-replacement.png",
            file_type=CMSMediaAsset.FILE_TYPE_IMAGE,
        )
        section_url = f"/api/admin/cms/sections/{section.pk}/"
        publish_url = "/api/admin/cms/modules/regional-profile/publish/"
        public_url = "/api/public/cms/pages/regional-profile/"

        def public_coverage():
            page = self.client.get(public_url)
            return next(row["content"] for row in page.data["sections"] if row["sectionKey"] == "geographic-coverage")

        self.client.force_authenticate(self.editor)
        response = self.client.patch(section_url, {
            "content_json": {**section.content_json, "mapAssetId": image.pk},
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotEqual(public_coverage().get("mapAssetId"), image.pk)
        self.assertEqual(self.client.post(publish_url, {}, format="json").status_code, 403)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(publish_url, {}, format="json").status_code, 200)
        self.assertEqual(public_coverage()["mapImageUrl"], "/media/map-replacement.png")
        section.refresh_from_db()
        unsafe = self.client.patch(section_url, {
            "content_json": {**section.content_json, "embedUrl": "https://example.test/embed"},
        }, format="json")
        self.assertEqual(unsafe.status_code, 400)
        cleared = self.client.patch(section_url, {
            "content_json": {**section.content_json, "mapAssetId": "", "mapImageUrl": ""},
        }, format="json")
        self.assertEqual(cleared.status_code, 200, cleared.data)
        self.assertEqual(self.client.post(publish_url, {}, format="json").status_code, 200)
        self.assertNotIn("mapImageUrl", public_coverage())

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

    def test_module_publish_endpoints_publish_publications_then_home(self):
        publication_section = CMSPageSection.objects.get(
            page__slug="publications", section_key="publication-catalog",
        )
        publication_content = dict(publication_section.content_json)
        publication_content["title"] = "Published module workflow title"
        saved_publications = self.client.patch(
            "/api/admin/cms/modules/publications/",
            {"sections": {"publication-catalog": publication_content}},
            format="json",
        )
        self.assertEqual(saved_publications.status_code, 200, saved_publications.data)
        published_publications = self.client.post(
            "/api/admin/cms/modules/publications/publish/", {}, format="json",
        )
        self.assertEqual(published_publications.status_code, 200, published_publications.data)
        self.assertEqual(published_publications.data["status"], "published")
        self.assertFalse(published_publications.data["has_unpublished_changes"])

        home_section = CMSPageSection.objects.get(page__slug="home", section_key="development-plans")
        home_content = dict(home_section.content_json)
        home_content["title"] = "Published Home workflow title"
        saved_home = self.client.patch(
            "/api/admin/cms/modules/home/",
            {"sections": {"development-plans": home_content}},
            format="json",
        )
        self.assertEqual(saved_home.status_code, 200, saved_home.data)
        published_home = self.client.post(
            "/api/admin/cms/modules/home/publish/", {}, format="json",
        )
        self.assertEqual(published_home.status_code, 200, published_home.data)
        self.assertEqual(published_home.data["status"], "published")
        self.assertFalse(published_home.data["has_unpublished_changes"])

        public_publications = self.client.get("/api/public/cms/pages/publications/")
        self.assertEqual(public_publications.status_code, 200)
        catalog = next(
            row for row in public_publications.data["sections"]
            if row["sectionKey"] == "publication-catalog"
        )
        self.assertEqual(catalog["content"]["title"], "Published module workflow title")
        public_home = self.client.get("/api/public/cms/pages/home/")
        self.assertEqual(public_home.status_code, 200)
        development_plans = next(
            row for row in public_home.data["sections"]
            if row["sectionKey"] == "development-plans"
        )
        self.assertEqual(development_plans["content"]["title"], "Published Home workflow title")

    def test_system_managed_home_sections_are_public_and_uneditable_for_both_roles(self):
        home = CMSPage.objects.get(slug="home")
        keys = {"dashboard-teaser", "latest-media", "upcoming-events"}
        rows = list(home.sections.filter(section_key__in=keys))
        saved_content = {section.pk: section.content_json for section in rows}
        self.assertEqual({section.section_key for section in rows}, keys)
        for user in (self.admin, self.editor):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                for url in ("/api/admin/cms/modules/home/", f"/api/admin/cms/pages/{home.pk}/"):
                    detail = self.client.get(url)
                    self.assertEqual(detail.status_code, 200)
                    editable = {section["section_key"] for section in detail.data["sections"]}
                    self.assertFalse(editable & keys)
                    self.assertIn("development-plans", editable)
                modules = self.client.get("/api/admin/cms/modules/").data
                module_home = next(module for module in modules if module["slug"] == "home")
                self.assertFalse(set(module_home["section_keys"]) & keys)
                blocked = self.client.patch("/api/admin/cms/modules/home/", {
                    "sections": {key: {"title": "Unexpected CMS change"} for key in keys},
                }, format="json")
                self.assertEqual(blocked.status_code, 400)
                for section in rows:
                    url = f"/api/admin/cms/sections/{section.pk}/"
                    self.assertEqual(self.client.patch(url, {"content_json": {}}, format="json").status_code, 404)
                    for action in ("lock", "unlock", "heartbeat"):
                        self.assertEqual(self.client.post(f"{url}{action}/", {}, format="json").status_code, 404)

        self.client.force_authenticate(user=None)
        public = self.client.get("/api/public/cms/pages/home/")
        self.assertEqual(public.status_code, 200)
        self.assertTrue(keys <= {section["sectionKey"] for section in public.data["sections"]})
        for section in rows:
            section.refresh_from_db()
            self.assertEqual(section.content_json, saved_content[section.pk])

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

    def test_about_organization_structure_is_fixed_and_preserves_spaced_copy(self):
        section = CMSPageSection.objects.get(page__slug="about-rdc", section_key="organization-structure")
        content = dict(section.content_json)
        nodes = [dict(row) for row in content["nodes"]]
        nodes[0]["title"] = "Chairperson with preserved spaces"
        nodes[0]["items"] = ["First child label", "Second child label"]
        content["nodes"] = nodes
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["content_json"]["nodes"][0]["title"], "Chairperson with preserved spaces")
        self.assertEqual(saved.data["content_json"]["nodes"][0]["items"][0], "First child label")

        invalid = dict(saved.data["content_json"])
        invalid["nodes"] = list(invalid["nodes"])[:-1]
        rejected = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": invalid}, format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("fixed", str(rejected.data).lower())

    def test_about_resolution_year_validation_and_optional_document(self):
        section = CMSPageSection.objects.get(page__slug="about-rdc", section_key="resolutions-archive")
        invalid = dict(section.content_json)
        invalid["years"] = [{"year": "Final Year 2026", "resolutions": []}]
        rejected = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": invalid}, format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("four-digit", str(rejected.data).lower())

        created = self.client.post("/api/admin/cms/resolutions/", {
            "stable_key": "resolution-2026-space-test",
            "resolution_number": "RDC-NCR Resolution No. 01, s. 2026",
            "title": "Resolution title with spaces",
            "description": "Description with multiple words",
            "year": 2026,
            "resolution_date": "2026-10-31",
            "external_url": "",
            "sort_order": 1,
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        resolution = CMSResolution.objects.get(stable_key="resolution-2026-space-test")
        self.assertIsNone(resolution.attachment)
        section.refresh_from_db()
        year_row = next(row for row in section.content_json["years"] if str(row["year"]) == "2026")
        mirrored = next(row for row in year_row["resolutions"] if row["id"] == resolution.stable_key)
        self.assertEqual(mirrored["title"], "Resolution title with spaces")

    def test_about_resolution_legend_and_categories_are_cms_owned(self):
        page = CMSPage.objects.get(slug="about-rdc")
        section = page.sections.get(section_key="resolutions-archive")
        self.assertTrue(section.content_json.get("legendItems"))
        self.assertTrue(section.content_json.get("categoryItems"))
        published = next(
            row for row in page.published_snapshot_json.get("sections", [])
            if row.get("sectionKey") == "resolutions-archive"
        )
        self.assertTrue(published["content"].get("legendItems"))
        self.assertTrue(published["content"].get("categoryItems"))

    def test_public_about_page_returns_every_published_resolution(self):
        section = CMSPageSection.objects.get(page__slug="about-rdc", section_key="resolutions-archive")
        content = dict(section.content_json)
        content["years"] = [{
            "year": "2026",
            "resolutions": [
                {"id": f"resolution-2026-{index}", "title": f"Resolution {index}", "description": ""}
                for index in range(1, 8)
            ],
        }]
        saved = self.client.patch(
            "/api/admin/cms/modules/about-rdc/",
            {"sections": {"resolutions-archive": content}},
            format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        published = self.client.post("/api/admin/cms/modules/about-rdc/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)

        # A stale/missing normalized mirror must not cap or remove an entry
        # that is present in the authoritative published page snapshot.
        CMSResolution.objects.filter(stable_key="resolution-2026-4").delete()

        public_page = self.client.get("/api/public/cms/pages/about-rdc/")
        self.assertEqual(public_page.status_code, 200, public_page.data)
        archive = next(
            row for row in public_page.data["sections"]
            if row["sectionKey"] == "resolutions-archive"
        )
        year = next(row for row in archive["content"]["years"] if row["year"] == "2026")
        self.assertEqual(len(year["resolutions"]), 7)
        self.assertEqual(
            [row["title"] for row in year["resolutions"]],
            [f"Resolution {index}" for index in range(7, 0, -1)],
        )

    def test_carousel_section_syncs_normalized_draft(self):
        section = CMSPageSection.objects.get(page__slug="home", section_key="hero-carousel")
        content = dict(section.content_json)
        slides = list(content.get("slides") or [])
        slides.insert(0, {
            "id": "new-fixed-slide", "title": "New fixed slide", "subtitle": "Draft copy",
            "imageKey": "photo1", "imageAlt": "Metro Manila skyline at night",
            "button1": {"text": "Read", "link": "/about"},
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
        self.assertEqual(item.image_alt_text, "Metro Manila skyline at night")
        self.assertEqual(item.published_snapshot_json, {})

    def test_clearing_carousel_image_removes_it_from_public_snapshot(self):
        page = CMSPage.objects.get(slug="home")
        section = page.sections.get(section_key="hero-carousel")
        content = dict(section.content_json)
        slides = [dict(row) for row in content.get("slides") or []]
        self.assertTrue(slides)
        slide = slides[0]
        slide["imageUrl"] = "https://example.com/old-carousel-image.jpg"
        slide["imageKey"] = ""
        slide["mediaAssetId"] = ""
        slide["imageAssetId"] = ""
        content["slides"] = slides
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)

        cleared = dict(saved.data["content_json"])
        cleared_slides = [dict(row) for row in cleared["slides"]]
        cleared_slides[0].update({
            "imageUrl": "", "imageKey": "", "mediaAssetId": "", "imageAssetId": "",
        })
        cleared["slides"] = cleared_slides
        cleared_response = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": cleared}, format="json",
        )
        self.assertEqual(cleared_response.status_code, 200, cleared_response.data)
        item = CMSCarouselItem.objects.get(stable_key=cleared_slides[0]["id"])
        self.assertIsNone(item.image)
        self.assertEqual(item.legacy_image_url, "")

        published = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        public_page = self.client.get("/api/public/cms/pages/home/")
        self.assertEqual(public_page.status_code, 200, public_page.data)
        carousel = next(
            row for row in public_page.data["sections"] if row["sectionKey"] == "hero-carousel"
        )
        public_slide = next(
            row for row in carousel["content"]["slides"] if row["id"] == cleared_slides[0]["id"]
        )
        self.assertNotIn("imageUrl", public_slide)
        self.assertNotIn("imageKey", public_slide)

    def test_new_carousel_slide_does_not_reuse_archived_title_identity(self):
        archived = CMSCarouselItem.objects.create(
            stable_key="new-carousel-slide",
            title="New carousel slide",
            status="archived",
            archived_at=timezone.now(),
        )
        section = CMSPageSection.objects.get(page__slug="home", section_key="hero-carousel")
        content = dict(section.content_json)
        slides = [dict(row) for row in content.get("slides") or []]
        slides.append({
            "title": "New carousel slide",
            "subtitle": "A genuinely new slide",
            "imageKey": "photo1",
            "button1": {"text": "Learn More", "link": "/"},
            "button2": {"text": "View Details", "link": "/"},
        })
        content["slides"] = slides

        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        created_key = saved.data["content_json"]["slides"][-1]["id"]
        self.assertNotEqual(created_key, archived.stable_key)
        self.assertTrue(CMSCarouselItem.objects.filter(stable_key=created_key, status="draft").exists())
        archived.refresh_from_db()
        self.assertEqual(archived.status, "archived")

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
        legacy_item = CMSCarouselItem.objects.create(
            stable_key="unrelated-published-carousel",
            title="Unrelated migrated item",
            status="published",
            published_at=timezone.now(),
            published_snapshot_json={"id": "unrelated-published-carousel", "title": "Unrelated migrated item"},
        )
        page = CMSPage.objects.get(slug="home")
        response = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        legacy_item.refresh_from_db()
        self.assertEqual(legacy_item.status, "published")

    def test_home_publish_uses_its_own_cards_without_publication_dependencies(self):
        page = CMSPage.objects.get(slug="home")
        section = page.sections.get(section_key="development-plans")
        content = dict(section.content_json)
        content["featuredCategoryCode"] = "missing-legacy-category"
        content["featuredCategory"] = {"title": "Legacy injected title"}
        content["title"] = "CMS-owned Home cards"
        content["items"] = [{
            "title": "CMS-owned card",
            "category": "CMS content",
            "icon": "file",
            "link": "/publications",
        }]
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)

        response = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        section.refresh_from_db()
        self.assertNotIn("featuredCategoryCode", section.content_json)
        self.assertNotIn("featuredCategory", section.content_json)
        public_page = self.client.get("/api/public/cms/pages/home/")
        public_content = next(
            row["content"] for row in public_page.data["sections"]
            if row["sectionKey"] == "development-plans"
        )
        self.assertEqual(public_content["title"], "CMS-owned Home cards")
        self.assertEqual(public_content["items"][0]["title"], "CMS-owned card")
        self.assertNotIn("featuredCategoryCode", public_content)
        self.assertNotIn("featuredCategory", public_content)

    def test_publications_publish_rebuilds_stale_normalized_rows(self):
        page = CMSPage.objects.get(slug="publications")
        section = page.sections.get(section_key="publication-catalog")
        category_row = next(row for row in section.content_json["categories"] if isinstance(row, dict))
        category_code = category_row.get("code") or category_row.get("id")
        document_keys = [
            row.get("id") for row in category_row.get("documents") or []
            if isinstance(row, dict) and row.get("id")
        ]
        CMSPublicationDocument.objects.filter(category__code=category_code).delete()
        CMSPublicationCategory.objects.filter(code=category_code).delete()

        response = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        rebuilt_category = CMSPublicationCategory.objects.get(code=category_code)
        self.assertEqual(rebuilt_category.status, "published")
        self.assertTrue(rebuilt_category.published_snapshot_json)
        for key in document_keys:
            rebuilt_document = CMSPublicationDocument.objects.get(stable_key=key)
            self.assertEqual(rebuilt_document.status, "published")
            self.assertTrue(rebuilt_document.published_snapshot_json)

    def test_publications_publish_document_covers_and_newest_categories_first(self):
        page = CMSPage.objects.get(slug="publications")
        section = page.sections.get(section_key="publication-catalog")
        content = dict(section.content_json)
        categories = [dict(row) for row in content.get("categories") or []]
        self.assertGreaterEqual(len(categories), 2)
        categories[0]["categoryNumber"] = 1
        categories[1]["categoryNumber"] = 2
        categories[0]["documents"] = [dict(row) for row in categories[0].get("documents") or []]
        self.assertTrue(categories[0]["documents"])
        cover = CMSMediaAsset.objects.create(
            file="cms/publication-cover.png",
            public_url="/media/cms/publication-cover.png",
            file_type=CMSMediaAsset.FILE_TYPE_IMAGE,
            mime_type="image/png",
            alt_text="Publication cover",
        )
        categories[0]["documents"][0].update({
            "coverAssetId": str(cover.pk),
            "coverImage": cover.public_url,
            "coverAlt": "Document cover description",
        })
        content["categories"] = categories
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/",
            {"content_json": content},
            format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        published = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)

        document_key = saved.data["content_json"]["categories"][0]["documents"][0]["id"]
        document = CMSPublicationDocument.objects.get(stable_key=document_key)
        self.assertEqual(document.cover_image_id, cover.pk)
        self.assertEqual(document.cover_alt_text, "Document cover description")

        public_page = self.client.get("/api/public/cms/pages/publications/")
        catalog = next(
            row["content"] for row in public_page.data["sections"]
            if row["sectionKey"] == "publication-catalog"
        )
        public_categories = catalog["categories"]
        self.assertGreater(public_categories[0]["categoryNumber"], public_categories[1]["categoryNumber"])
        self.assertNotIn("icon", public_categories[0])
        covered = next(row for row in public_categories if row["id"] == categories[0].get("id"))
        covered_document = next(row for row in covered["documents"] if row["id"] == document_key)
        self.assertEqual(covered_document["coverImage"], cover.public_url)
        self.assertEqual(covered_document["coverAlt"], "Document cover description")

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

    def test_published_carousel_removal_is_private_until_published(self):
        page = CMSPage.objects.get(slug="home")
        self.assertEqual(self.client.post("/api/admin/cms/modules/home/publish/").status_code, 200)
        section = page.sections.get(section_key="hero-carousel")
        content = dict(section.content_json)
        slides = [dict(row) for row in content.get("slides") or []]
        self.assertGreater(len(slides), 0)
        removed_key = slides[0].get("id") or slides[0].get("key")
        item = CMSCarouselItem.objects.get(stable_key=removed_key)
        item.created_by = self.admin
        item.save(update_fields=["created_by", "updated_at"])
        content["slides"] = slides[1:]
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        public = self.client.get("/api/public/cms/pages/home/")
        carousel = next(row for row in public.data["sections"] if row["sectionKey"] == "hero-carousel")
        self.assertIn(removed_key, {row["id"] for row in carousel["content"]["slides"]})
        self.assertEqual(self.client.post(f"/api/admin/cms/carousel-items/{item.pk}/archive/").status_code, 405)
        published = self.client.post("/api/admin/cms/modules/home/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)

    def test_carousel_collection_search_accepts_stable_key(self):
        item = CMSCarouselItem.objects.exclude(status="archived").first()
        self.assertIsNotNone(item)
        response = self.client.get("/api/admin/cms/carousel-items/", {"q": item.stable_key})
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data.get("results", response.data) if isinstance(response.data, dict) else response.data
        self.assertIn(item.stable_key, {row["stable_key"] for row in rows})

    def test_removed_migrated_carousel_is_preserved_after_publish(self):
        page = CMSPage.objects.get(slug="home")
        section = page.sections.get(section_key="hero-carousel")
        content = dict(section.content_json)
        slides = [dict(row) for row in content.get("slides") or []]
        removed_key = slides[0].get("id") or slides[0].get("key")
        item = CMSCarouselItem.objects.get(stable_key=removed_key)
        item.created_by = None
        item.save(update_fields=["created_by", "updated_at"])
        content["slides"] = slides[1:]
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)

        published = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        item.refresh_from_db()
        self.assertEqual(item.status, "published")
        public_page = self.client.get("/api/public/cms/pages/home/")
        carousel = next(row for row in public_page.data["sections"] if row["sectionKey"] == "hero-carousel")
        self.assertNotIn(removed_key, {row.get("id") for row in carousel["content"]["slides"]})

    def test_confirmed_publication_removal_preserves_migrated_records(self):
        page = CMSPage.objects.get(slug="publications")
        section = page.sections.get(section_key="publication-catalog")
        content = dict(section.content_json)
        content["removedCategoryIds"] = [row.get("code") or row["id"] for row in content["categories"]]
        content["categories"] = [{
            "title": "CMS-managed category",
            "description": "Replacement content",
            "documents": [{
                "title": "CMS-managed document",
                "year": "2026",
                "fileType": "PDF",
                "url": "https://example.com/cms-managed.pdf",
            }],
        }]
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        replacement_code = saved.data["content_json"]["categories"][0]["code"]

        published = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        self.assertEqual(CMSPublicationCategory.objects.get(code=replacement_code).status, "published")
        self.assertEqual(
            CMSPublicationCategory.objects.get(code="rdp").status,
            "published",
            "An omitted category is retained without archival.",
        )
        self.assertEqual(
            CMSPublicationCategory.objects.get(code="greenprint").status,
            "published",
            "Unlisting a migrated category preserves its record.",
        )
        public_page = self.client.get("/api/public/cms/pages/publications/")
        catalog = next(row for row in public_page.data["sections"] if row["sectionKey"] == "publication-catalog")
        self.assertEqual([row["id"] for row in catalog["content"]["categories"]], [replacement_code])
        self.assertNotIn("removedCategoryIds", catalog["content"])
        self.assertTrue(CMSPublicationDocument.objects.filter(category__code="rdp", status="published").exists())

    def test_publications_can_publish_an_empty_draft_without_archiving_content(self):
        section = CMSPageSection.objects.get(page__slug="publications", section_key="publication-catalog")
        public_url = "/api/public/cms/pages/publications/"
        publish_url = "/api/admin/cms/modules/publications/publish/"
        prior = self.client.get(public_url).data
        categories_before = list(CMSPublicationCategory.objects.order_by("pk").values_list("pk", "status", "archived_at"))
        documents_before = list(CMSPublicationDocument.objects.order_by("pk").values_list("pk", "status", "archived_at", "category_id", "attachment_id"))
        self.client.force_authenticate(self.editor)
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/",
            {"content_json": {**section.content_json, "categories": []}},
            format="json",
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(self.client.post(publish_url, {}, format="json").status_code, 403)
        self.assertEqual(self.client.get(public_url).data, prior)

        self.client.force_authenticate(self.admin)
        published = self.client.post(publish_url, {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        result = self.client.get(public_url)
        catalog = next(row["content"] for row in result.data["sections"] if row["sectionKey"] == "publication-catalog")
        self.assertEqual(catalog["categories"], [])
        self.assertEqual(list(CMSPublicationCategory.objects.order_by("pk").values_list("pk", "status", "archived_at")), categories_before)
        self.assertEqual(list(CMSPublicationDocument.objects.order_by("pk").values_list("pk", "status", "archived_at", "category_id", "attachment_id")), documents_before)

    def test_public_document_membership_changes_only_after_publish(self):
        section = CMSPageSection.objects.get(page__slug="publications", section_key="publication-catalog")
        publish_url = "/api/admin/cms/modules/publications/publish/"
        initial = self.client.post(publish_url, {}, format="json")
        self.assertEqual(initial.status_code, 200, initial.data)
        section.refresh_from_db()
        content = section.content_json
        source, target = content["categories"][:2]
        document = source["documents"].pop()
        key = document["id"]
        target["documents"].append(document)
        def public_category():
            response = self.client.get("/api/public/cms/pages/publications/")
            catalog = next(row["content"] for row in response.data["sections"] if row["sectionKey"] == "publication-catalog")
            return next(row["id"] for row in catalog["categories"] if any(item["id"] == key for item in row["documents"]))
        self.assertEqual(public_category(), source["id"])
        saved = self.client.patch(f"/api/admin/cms/sections/{section.pk}/", {"content_json": content}, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(public_category(), source["id"])
        published = self.client.post(publish_url, {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        self.assertEqual(public_category(), target["id"])

    def test_unlisting_a_publication_preserves_its_attachment_for_new_template(self):
        section = CMSPageSection.objects.get(page__slug="publications", section_key="publication-catalog")
        publish_url = "/api/admin/cms/modules/publications/publish/"
        initial = self.client.post(publish_url, {}, format="json")
        self.assertEqual(initial.status_code, 200, initial.data)
        section.refresh_from_db()
        content = section.content_json
        category = content["categories"][0]
        item = category["documents"][0]
        document = CMSPublicationDocument.objects.get(stable_key=item["id"])
        attachment = CMSMediaAsset.objects.create(
            file="cms/retained.pdf", public_url="/media/retained.pdf",
            file_type=CMSMediaAsset.FILE_TYPE_DOCUMENT, mime_type="application/pdf", size=2048,
        )
        item["mediaAssetId"] = attachment.pk
        item["fileType"] = "Legacy type"
        item["fileSize"] = "Legacy size"
        save_url = f"/api/admin/cms/sections/{section.pk}/"
        self.assertEqual(self.client.patch(save_url, {"content_json": content}, format="json").status_code, 200)
        self.assertEqual(self.client.post(publish_url, {}, format="json").status_code, 200)
        section.refresh_from_db()
        content = section.content_json
        content["categories"][0]["documents"].pop(0)
        self.assertEqual(self.client.patch(save_url, {"content_json": content}, format="json").status_code, 200)
        self.assertEqual(self.client.post(publish_url, {}, format="json").status_code, 200)
        document.refresh_from_db()
        self.assertEqual(document.attachment_id, attachment.pk)
        self.assertEqual(document.document_type, "PDF")
        self.assertEqual(document.legacy_file_size, "2 KB")
        self.assertEqual(document.status, "published")
        detail_url = f"/api/admin/cms/publication-documents/{document.pk}/"
        self.assertEqual(self.client.post(f"{detail_url}archive/").status_code, 405)
        self.assertEqual(self.client.post(f"{detail_url}restore/").status_code, 405)
        section.refresh_from_db()
        content = section.content_json
        content["categories"][0]["documents"].append({
            "title": "New template with existing file", "mediaAssetId": attachment.pk,
        })
        self.assertEqual(self.client.patch(save_url, {"content_json": content}, format="json").status_code, 200)
        self.assertEqual(self.client.post(publish_url, {}, format="json").status_code, 200)
        self.assertEqual(CMSPublicationDocument.objects.get(title="New template with existing file").attachment_id, attachment.pk)

    def test_removing_every_carousel_item_and_publishing_clears_public_home(self):
        section = CMSPageSection.objects.get(page__slug="home", section_key="hero-carousel")
        response = self.client.patch(f"/api/admin/cms/sections/{section.pk}/", {
            "content_json": {**section.content_json, "slides": []},
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        published = self.client.post("/api/admin/cms/modules/home/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200, published.data)
        public_page = self.client.get("/api/public/cms/pages/home/")
        carousel = next(row for row in public_page.data["sections"] if row["sectionKey"] == "hero-carousel")
        self.assertEqual(carousel["content"]["slides"], [])

    def test_resolution_removal_changes_public_page_only_after_publish(self):
        section = CMSPageSection.objects.get(page__slug="about-rdc", section_key="resolutions-archive")
        save = f"/api/admin/cms/sections/{section.pk}/"
        publish = "/api/admin/cms/modules/about-rdc/publish/"
        response = self.client.patch(save, {"content_json": {
            **section.content_json,
            "years": [{"year": 2025, "resolutions": [{"title": "Resolution to remove"}]}],
        }}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.post(publish).status_code, 200)
        resolution = CMSResolution.objects.get(title="Resolution to remove")
        section.refresh_from_db()
        self.client.force_authenticate(self.editor)
        response = self.client.patch(save, {"content_json": {
            **section.content_json, "years": [],
        }}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        public_url = "/api/public/cms/pages/about-rdc/"
        self.assertContains(self.client.get(public_url), "Resolution to remove")
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f"/api/admin/cms/resolutions/{resolution.pk}/archive/").status_code, 405)
        self.assertEqual(self.client.post(publish).status_code, 200)
        self.assertNotContains(self.client.get(public_url), "Resolution to remove")
        resolution.refresh_from_db()
        self.assertEqual(resolution.status, "published")

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

    def test_legacy_publication_without_draft_category_cannot_be_falsely_restored(self):
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
        doc = category.documents.get()
        doc.status = "archived"
        doc.save(update_fields=["status"])
        self.assertEqual(self.client.post(f"/api/admin/cms/publication-categories/{category.pk}/archive/").status_code, 405)
        self.assertEqual(self.client.post(f"/api/admin/cms/publication-documents/{doc.pk}/restore/").status_code, 405)
        read = self.client.get("/api/admin/cms/publication-documents/?archived=1")
        rows = read.data.get("results", []) if isinstance(read.data, dict) else read.data
        self.assertEqual(rows, [])
        doc.refresh_from_db()
        self.assertEqual(doc.status, "archived")
        self.assertEqual(doc.category, category)

    def test_archive_lists_only_supported_content_and_keeps_existing_role_permissions(self):
        media = CMSMediaAsset.objects.create(file="cms/archive-check.pdf", file_type="document")
        article = CMSArticle.objects.create(title="Article to archive", slug="article-to-archive")
        event = PublicEvent.objects.create(title="Event to archive", start_at=timezone.now(), created_by=self.editor)
        supported = [
            ("media", media, "restore"), ("articles", article, "restore"), ("events", event, "unarchive"),
        ]
        for group, item, restore_action in supported:
            with self.subTest(group=group):
                self.client.force_authenticate(self.admin)
                path = f"/api/admin/cms/{group}/{item.pk}/"
                response = self.client.post(f"{path}archive/")
                self.assertEqual(response.status_code, 200, response.data)
                self.client.force_authenticate(self.editor)
                archive_path = f"/api/admin/cms/{group}/?archived=1&view=summary"
                listed = self.client.get(archive_path)
                self.assertEqual(listed.status_code, 200, listed.data)
                rows = listed.data.get("results", []) if isinstance(listed.data, dict) else listed.data
                entry = next(row for row in rows if row["id"] == item.pk)
                self.assertTrue(entry["archived_at"])
                if group in {"media", "articles"}:
                    self.assertTrue(entry["archived_by_name"])
                self.assertEqual(self.client.post(f"{path}{restore_action}/").status_code, 403)
                self.client.force_authenticate(self.admin)
                restored = self.client.post(f"{path}{restore_action}/")
                self.assertEqual(restored.status_code, 200, restored.data)
                if group == "media":
                    self.assertFalse(restored.data["is_archived"])
                else:
                    self.assertEqual(restored.data["status"], "draft")
                after = self.client.get(archive_path)
                after_rows = after.data.get("results", []) if isinstance(after.data, dict) else after.data
                self.assertNotIn(item.pk, {row["id"] for row in after_rows})

    def test_publication_preview_is_private_read_only_and_matches_published_sections(self):
        page = CMSPage.objects.get(slug="publications")
        section = page.sections.get(section_key="publication-catalog")
        content = {**section.content_json, "title": "Preview catalog"}
        content["categories"] = [{
            "title": "Preview category",
            "documents": [{"title": "Preview document", "url": "https://example.test/preview.pdf"}],
        }]
        self.assertEqual(self.client.patch(f"/api/admin/cms/sections/{section.pk}/", {
            "content_json": content,
        }, format="json").status_code, 200)
        page.refresh_from_db()
        saved_page_updated = page.updated_at
        section.refresh_from_db()
        saved_section = section.content_json
        endpoint = f"/api/admin/cms/pages/{page.pk}/preview/"
        self.client.force_authenticate(self.editor)
        preview = self.client.get(endpoint)
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertIn("no-store", preview["Cache-Control"])
        draft = preview.data["draft"]["sections"]
        self.assertEqual(draft[0]["content"]["categories"][0]["documents"][0]["title"], "Preview document")
        self.assertNotEqual(preview.data["published"]["sections"], draft)
        page.refresh_from_db()
        section.refresh_from_db()
        self.assertEqual(page.updated_at, saved_page_updated)
        self.assertEqual(section.content_json, saved_section)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(endpoint).status_code, (401, 403))
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post("/api/admin/cms/modules/publications/publish/").status_code, 200)
        self.assertEqual(self.client.get("/api/public/cms/pages/publications/").data["sections"], draft)

    def test_public_home_snapshot_does_not_inject_legacy_publication_categories(self):
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
        self.assertNotIn("featuredCategoryCode", content)
        self.assertNotIn("featuredCategory", content)

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

