import shutil
import tempfile
from datetime import timedelta
from importlib import import_module

from django.apps import apps as django_apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.models import CMSArticle, CMSPage, CMSPageSection, CMSRevision, CMSSiteSetting
from cms.services.snapshots import build_page_snapshot
from projects.models import PublicContent, PublicEvent, User, UserActivity


class CMSV2Tests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="rdc-cms-v2-tests-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.admin = User.objects.create_user(username="v2-admin", email="v2-admin@example.com", password="test", role="admin")
        self.editor = User.objects.create_user(username="v2-editor", email="v2-editor@example.com", password="test", role="content_editor")
        self.editor_b = User.objects.create_user(username="v2-editor-b", email="v2-editor-b@example.com", password="test", role="content_editor")

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_all_core_public_pages_are_registered_with_editable_sections(self):
        expected_sections = {
            "home": {"hero-carousel", "development-plans", "investment-programming", "monitoring-evaluation", "dashboard-teaser", "latest-media", "upcoming-events"},
            "about-rdc": {"about-hero", "legal-basis", "committees", "organization-structure", "resolutions-archive"},
            "regional-profile": {"region-hero", "regional-overview", "geographic-coverage", "lgu-directory"},
            "publications": {"publication-catalog"},
            "news": {"news-hero", "news-listing"},
            "projects-dashboard": {"projects-hero", "projects-updates", "projects-data-note"},
            "contact": {"contact-hero", "main-office", "location-map", "message-form"},
        }

        self.assertEqual(
            set(CMSPage.objects.filter(slug__in=expected_sections).values_list("slug", flat=True)),
            set(expected_sections),
        )
        for slug, section_keys in expected_sections.items():
            page = CMSPage.objects.get(slug=slug)
            self.assertTrue(section_keys.issubset(set(page.sections.values_list("section_key", flat=True))))
            self.assertEqual(self.client.get(f"/api/public/cms/pages/{slug}/").status_code, status.HTTP_200_OK)

    def test_home_rejects_a_second_active_hero_carousel(self):
        page = CMSPage.objects.get(slug="home")
        self.authenticate(self.admin)
        response = self.client.post(
            "/api/admin/cms/sections/",
            {
                "page": page.pk,
                "section_key": "second-carousel",
                "section_type": "hero_carousel",
                "order": page.sections.count() + 1,
                "content_json": {"slides": []},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only have one hero carousel", str(response.data).lower())

    def test_duplicate_home_carousel_cleanup_archives_legacy_section(self):
        page = CMSPage.objects.get(slug="home")
        legacy = CMSPageSection.objects.create(
            page=page,
            section_key="carousel",
            section_type="hero_carousel",
            order=page.sections.count() + 1,
            status="published",
            is_visible=True,
            content_json={"slides": [{"title": "Legacy duplicate"}]},
        )
        snapshot = dict(page.published_snapshot_json)
        snapshot["sections"] = [
            *snapshot.get("sections", []),
            {
                "sectionKey": "carousel",
                "sectionType": "hero_carousel",
                "order": legacy.order,
                "content": legacy.content_json,
            },
        ]
        page.published_snapshot_json = snapshot
        page.save(update_fields=["published_snapshot_json"])

        cleanup = import_module("cms.migrations.0005_archive_duplicate_home_carousels")
        cleanup.archive_duplicate_home_carousels(django_apps, None)

        legacy.refresh_from_db()
        page.refresh_from_db()
        self.assertEqual(legacy.status, "archived")
        self.assertFalse(legacy.is_visible)
        self.assertNotIn("carousel", [row["sectionKey"] for row in page.published_snapshot_json["sections"]])

    def test_section_soft_lock_blocks_other_editor_and_expires(self):
        page = CMSPage.objects.create(title="Locked page", slug="locked-page")
        section = CMSPageSection.objects.create(
            page=page, section_key="hero", section_type="hero", order=1, content_json={"title": "Original"}
        )
        self.authenticate(self.editor)
        response = self.client.post(f"/api/admin/cms/sections/{section.pk}/lock/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["locked_by_me"])

        self.authenticate(self.editor_b)
        self.assertEqual(
            self.client.post(f"/api/admin/cms/sections/{section.pk}/lock/").status_code,
            423,
        )
        blocked_update = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/", {"content_json": {"title": "Collision"}}, format="json"
        )
        self.assertEqual(blocked_update.status_code, 423)

        section.refresh_from_db()
        section.lock_acquired_at = timezone.now() - timedelta(minutes=11)
        section.save(update_fields=["lock_acquired_at"])
        acquired = self.client.post(f"/api/admin/cms/sections/{section.pk}/lock/")
        self.assertEqual(acquired.status_code, status.HTTP_200_OK)
        self.assertTrue(acquired.data["locked_by_me"])
        self.assertEqual(
            self.client.post(f"/api/admin/cms/sections/{section.pk}/heartbeat/").status_code,
            status.HTTP_200_OK,
        )

    def test_upload_policy_is_database_managed_and_returns_structured_422(self):
        self.authenticate(self.admin)
        limit = CMSSiteSetting.objects.get(key="media-upload-max-bytes")
        limit.value_json = {"image": 8, "document": 20 * 1024 * 1024}
        limit.save()
        too_large = SimpleUploadedFile("large.png", b"\x89PNG\r\n\x1a\nmore", content_type="image/png")
        response = self.client.post("/api/admin/cms/media/", {"file": too_large}, format="multipart")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["reason"], "file_too_large")
        self.assertEqual(response.data["current_limit"], 8)

        wrong_type = SimpleUploadedFile("script.txt", b"not allowed", content_type="text/plain")
        response = self.client.post("/api/admin/cms/media/", {"file": wrong_type}, format="multipart")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["reason"], "file_type_not_allowed")

        limit.value_json = {"image": 100, "document": 20 * 1024 * 1024}
        limit.save()
        accepted = SimpleUploadedFile("accepted.png", b"\x89PNG\r\n\x1a\nmore", content_type="image/png")
        self.assertEqual(
            self.client.post("/api/admin/cms/media/", {"file": accepted}, format="multipart").status_code,
            status.HTTP_201_CREATED,
        )

    def test_published_slug_is_immutable(self):
        article = CMSArticle.objects.create(title="Original", slug="permanent-slug")
        self.authenticate(self.admin)
        self.assertEqual(
            self.client.post(f"/api/admin/cms/articles/{article.pk}/publish/").status_code,
            status.HTTP_200_OK,
        )
        response = self.client.patch(
            f"/api/admin/cms/articles/{article.pk}/", {"slug": "changed-slug"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        article.refresh_from_db()
        self.assertEqual(article.slug, "permanent-slug")

    def test_news_publication_date_is_saved_and_published(self):
        self.authenticate(self.admin)
        created = self.client.post(
            "/api/admin/cms/articles/",
            {
                "title": "Dated news",
                "slug": "dated-news",
                "summary": "News with an editor-selected public date",
                "publication_date": "2026-08-15",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        article_id = created.data["id"]
        published = self.client.post(f"/api/admin/cms/articles/{article_id}/publish/")
        self.assertEqual(published.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=None)
        public = self.client.get("/api/public/cms/news/dated-news/")
        self.assertEqual(public.status_code, status.HTTP_200_OK)
        self.assertEqual(public.data["publicationDate"], "2026-08-15")

    def test_archived_event_can_be_unarchived_and_returns_to_public_calendar(self):
        event = PublicEvent.objects.create(
            title="Restored calendar event",
            start_at=timezone.now() + timedelta(days=7),
            status="archived",
            created_by=self.admin,
            reviewed_by=self.admin,
            published_at=timezone.now() - timedelta(days=1),
            archived_at=timezone.now(),
        )
        self.authenticate(self.admin)
        response = self.client.post(f"/api/admin/events/{event.pk}/unarchive/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        event.refresh_from_db()
        self.assertEqual(event.status, "published")
        self.assertIsNone(event.archived_at)
        self.assertTrue(
            UserActivity.objects.filter(event="cms_event_unarchived", details__event_id=event.pk).exists()
        )

        self.client.force_authenticate(user=None)
        public = self.client.get("/api/public/events/")
        self.assertEqual(public.status_code, status.HTTP_200_OK)
        self.assertIn(event.pk, [row["id"] for row in public.data["results"]])

    def test_review_workflow_preserves_old_public_snapshot_and_syncs_chatbot(self):
        self.authenticate(self.editor)
        created = self.client.post(
            "/api/admin/cms/articles/",
            {"title": "First public title", "slug": "workflow-news", "summary": "Approved summary", "body": "Approved body"},
            format="json",
        )
        article_id = created.data["id"]
        self.assertEqual(self.client.post(f"/api/admin/cms/articles/{article_id}/submit/").status_code, 200)
        self.authenticate(self.admin)
        self.assertEqual(self.client.post(f"/api/admin/cms/articles/{article_id}/publish/").status_code, 200)
        self.assertTrue(PublicContent.objects.filter(slug=f"cms-news-{article_id}").exists())

        self.authenticate(self.editor)
        self.client.patch(
            f"/api/admin/cms/articles/{article_id}/", {"title": "Unapproved replacement"}, format="json"
        )
        self.client.post(f"/api/admin/cms/articles/{article_id}/submit/")
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/public/cms/news/workflow-news/").data["title"],
            "First public title",
        )

        self.authenticate(self.admin)
        self.client.post(f"/api/admin/cms/articles/{article_id}/reject/", {"remarks": "Revise it"}, format="json")
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/public/cms/news/workflow-news/").data["title"],
            "First public title",
        )
        self.authenticate(self.admin)
        self.client.post(f"/api/admin/cms/articles/{article_id}/archive/")
        self.assertFalse(PublicContent.objects.filter(slug=f"cms-news-{article_id}").exists())
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/public/cms/news/workflow-news/").status_code, 404)

    def test_public_page_snapshot_enforces_section_status_and_visibility(self):
        page = CMSPage.objects.create(
            title="Truth table", slug="truth-table", status="published", published_at=timezone.now()
        )
        CMSPageSection.objects.create(
            page=page, section_key="shown", section_type="text", order=1, status="published", is_visible=True
        )
        CMSPageSection.objects.create(
            page=page, section_key="hidden", section_type="text", order=2, status="published", is_visible=False
        )
        CMSPageSection.objects.create(
            page=page, section_key="draft", section_type="text", order=3, status="draft", is_visible=True
        )
        page.published_snapshot_json = build_page_snapshot(page)
        page.save(update_fields=["published_snapshot_json"])
        response = self.client.get("/api/public/cms/pages/truth-table/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["sectionKey"] for row in response.data["sections"]], ["shown"])

    def test_publication_category_and_nested_document_can_be_saved_and_published(self):
        section = CMSPageSection.objects.get(page__slug="publications", section_key="publication-catalog")
        content = dict(section.content_json)
        categories = list(content.get("categories") or [])
        categories.insert(
            0,
            {
                "id": "new-category",
                "title": "New Publication Category",
                "description": "Added through the publication editor",
                "isVisible": True,
                "documents": [
                    {
                        "id": "new-category-document-1",
                        "title": "New Publication Document",
                        "year": "2026",
                        "fileType": "PDF",
                        "url": "",
                        "isVisible": True,
                    }
                ],
            },
        )
        content["categories"] = categories

        self.authenticate(self.admin)
        saved = self.client.patch(
            f"/api/admin/cms/sections/{section.pk}/",
            {"content_json": content},
            format="json",
        )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        published = self.client.post(f"/api/admin/cms/sections/{section.pk}/publish/")
        self.assertEqual(published.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=None)
        public = self.client.get("/api/public/cms/pages/publications/")
        catalog = next(row for row in public.data["sections"] if row["sectionKey"] == "publication-catalog")
        self.assertEqual(catalog["content"]["categories"][0]["id"], "new-category")
        self.assertEqual(
            catalog["content"]["categories"][0]["documents"][0]["title"],
            "New Publication Document",
        )

    def test_deleted_section_revision_recreates_target_and_missing_parent_is_clear(self):
        self.authenticate(self.admin)
        page = CMSPage.objects.create(title="Restore page", slug="restore-page")
        created = self.client.post(
            "/api/admin/cms/sections/",
            {"page": page.pk, "section_key": "restore-me", "section_type": "text", "order": 1, "content_json": {"title": "Return"}},
            format="json",
        )
        old_id = created.data["id"]
        revision = CMSRevision.objects.filter(content_type__model="cmspagesection", object_id=old_id).first()
        self.client.delete(f"/api/admin/cms/sections/{old_id}/")
        response = self.client.post(f"/api/admin/cms/revisions/{revision.pk}/restore-revision/")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data["object_id"], old_id)
        restored = CMSPageSection.objects.get(pk=response.data["object_id"])
        self.assertEqual(restored.page_id, page.pk)
        self.assertEqual(restored.content_json["title"], "Return")

        doomed = CMSPage.objects.create(title="Doomed", slug="doomed")
        doomed_section = CMSPageSection.objects.create(
            page=doomed, section_key="gone", section_type="text", order=1, content_json={"title": "Gone"}
        )
        from cms.services.publishing import create_section_update_revision

        doomed_revision = create_section_update_revision(doomed_section, user=self.admin)
        doomed.delete()
        response = self.client.post(f"/api/admin/cms/revisions/{doomed_revision.pk}/restore-revision/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("parent page", str(response.data["detail"]).lower())

    def test_public_site_settings_hide_upload_governance(self):
        response = self.client.get("/api/public/cms/site-settings/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("footer-text", response.data)
        self.assertNotIn("media-upload-max-bytes", response.data)
