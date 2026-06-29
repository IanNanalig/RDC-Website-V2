import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.models import CMSArticle, CMSMediaAsset, CMSPage, CMSPageSection, CMSRevision
from projects.models import PublicEvent, User


class CMSWorkflowTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="rdc-cms-tests-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.admin = User.objects.create_user(
            username="cms-admin",
            email="cms-admin@example.com",
            password="StrongTestPassword123!",
            role="admin",
        )
        self.editor = User.objects.create_user(
            username="cms-editor",
            email="cms-editor@example.com",
            password="StrongTestPassword123!",
            role="content_editor",
        )

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.admin)

    def test_page_draft_is_private_and_publish_snapshot_isolated(self):
        self.authenticate()
        page_response = self.client.post(
            "/api/admin/cms/pages/",
            {"title": "Test Home", "slug": "test-home"},
            format="json",
        )
        self.assertEqual(page_response.status_code, status.HTTP_201_CREATED)
        page_id = page_response.data["id"]

        section_response = self.client.post(
            "/api/admin/cms/sections/",
            {
                "page": page_id,
                "section_key": "hero",
                "section_type": "hero",
                "order": 1,
                "content_json": {"title": "Published title"},
                "is_visible": True,
            },
            format="json",
        )
        self.assertEqual(section_response.status_code, status.HTTP_201_CREATED)
        section_id = section_response.data["id"]

        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/public/cms/pages/test-home/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.authenticate()
        publish_response = self.client.post(f"/api/admin/cms/pages/{page_id}/publish/")
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/cms/pages/test-home/")
        self.assertEqual(public_response.status_code, status.HTTP_200_OK)
        self.assertEqual(public_response.data["sections"][0]["content"]["title"], "Published title")

        self.authenticate()
        update_response = self.client.put(
            f"/api/admin/cms/sections/{section_id}/",
            {
                "page": page_id,
                "section_key": "hero",
                "section_type": "hero",
                "order": 1,
                "content_json": {"title": "Draft-only title"},
                "is_visible": True,
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertTrue(CMSPage.objects.get(pk=page_id).has_unpublished_changes)

        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/cms/pages/test-home/")
        self.assertEqual(public_response.data["sections"][0]["content"]["title"], "Published title")

        self.authenticate()
        self.client.post(f"/api/admin/cms/pages/{page_id}/publish/")
        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/cms/pages/test-home/")
        self.assertEqual(public_response.data["sections"][0]["content"]["title"], "Draft-only title")

    def test_published_page_converts_backend_media_urls_to_portable_paths(self):
        page = CMSPage.objects.create(title="Media Page", slug="media-page")
        CMSPageSection.objects.create(
            page=page,
            section_key="hero",
            section_type="hero",
            order=1,
            content_json={
                "imageUrl": "http://127.0.0.1:8000/media/cms/cover.jpg",
                "nested": [{"documentUrl": "https://backend.example/media/cms/report.pdf?download=1"}],
            },
        )
        self.authenticate()
        response = self.client.post(f"/api/admin/cms/pages/{page.pk}/publish/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.data["published_snapshot_json"]["sections"][0]["content"]
        self.assertEqual(content["imageUrl"], "/media/cms/cover.jpg")
        self.assertEqual(content["nested"][0]["documentUrl"], "/media/cms/report.pdf?download=1")

    def test_content_editor_can_edit_but_cannot_publish(self):
        self.authenticate(self.editor)
        response = self.client.post(
            "/api/admin/cms/pages/",
            {"title": "Editor Page", "slug": "editor-page"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        publish_response = self.client.post(f"/api/admin/cms/pages/{response.data['id']}/publish/")
        self.assertEqual(publish_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_article_publish_sanitizes_html_and_keeps_draft_private(self):
        self.authenticate()
        response = self.client.post(
            "/api/admin/cms/articles/",
            {
                "title": "Safe News",
                "slug": "safe-news",
                "category": "Updates",
                "summary": "A public summary",
                "body": '<p>Safe</p><script>alert("x")</script><a href="javascript:alert(1)">Bad link</a>',
                "author": "RDC-NCR",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        article_id = response.data["id"]

        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get("/api/public/cms/news/safe-news/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.authenticate()
        self.assertEqual(
            self.client.post(f"/api/admin/cms/articles/{article_id}/publish/").status_code,
            status.HTTP_200_OK,
        )
        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/cms/news/safe-news/")
        self.assertEqual(public_response.status_code, status.HTTP_200_OK)
        self.assertIn("<p>Safe</p>", public_response.data["body"])
        self.assertNotIn("<script", public_response.data["body"])
        self.assertNotIn("javascript:", public_response.data["body"])

        self.authenticate()
        self.client.patch(
            f"/api/admin/cms/articles/{article_id}/",
            {"title": "Private Draft Title"},
            format="json",
        )
        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/cms/news/safe-news/")
        self.assertEqual(public_response.data["title"], "Safe News")

    def test_section_reorder_is_atomic_and_published_order_stays_stable(self):
        page = CMSPage.objects.create(title="Order Page", slug="order-page")
        first = CMSPageSection.objects.create(
            page=page,
            section_key="first",
            section_type="text",
            order=1,
        )
        second = CMSPageSection.objects.create(
            page=page,
            section_key="second",
            section_type="text",
            order=2,
        )
        self.authenticate()
        response = self.client.post(
            f"/api/admin/cms/pages/{page.pk}/reorder_sections/",
            {"section_ids": [second.pk, first.pk]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            list(page.sections.order_by("order").values_list("id", flat=True)),
            [second.pk, first.pk],
        )

        invalid_response = self.client.post(
            f"/api/admin/cms/pages/{page.pk}/reorder_sections/",
            {"section_ids": [first.pk]},
            format="json",
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            list(page.sections.order_by("order").values_list("id", flat=True)),
            [second.pk, first.pk],
        )

    def test_section_delete_marks_page_changed_and_is_audited(self):
        page = CMSPage.objects.create(
            title="Published Page",
            slug="published-page",
            status=CMSPage.STATUS_PUBLISHED,
            has_unpublished_changes=False,
            published_snapshot_json={"slug": "published-page", "sections": []},
        )
        section = CMSPageSection.objects.create(
            page=page,
            section_key="temporary",
            section_type="text",
            order=1,
        )
        self.authenticate()
        response = self.client.delete(f"/api/admin/cms/sections/{section.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        page.refresh_from_db()
        self.assertTrue(page.has_unpublished_changes)
        revision = CMSRevision.objects.filter(
            content_type=CMSRevision.CONTENT_SECTION,
            object_id=section.pk,
        ).latest("version_number")
        self.assertTrue(revision.snapshot_json["deleted"])

    def test_pages_and_articles_cannot_be_hard_deleted(self):
        page = CMSPage.objects.create(title="Protected Page", slug="protected-page")
        article = CMSArticle.objects.create(title="Protected News", slug="protected-news")
        self.authenticate()
        self.assertEqual(
            self.client.delete(f"/api/admin/cms/pages/{page.pk}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(
            self.client.delete(f"/api/admin/cms/articles/{article.pk}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertTrue(CMSPage.objects.filter(pk=page.pk).exists())
        self.assertTrue(CMSArticle.objects.filter(pk=article.pk).exists())

    def test_media_upload_returns_url_and_used_media_cannot_be_archived(self):
        self.authenticate()
        upload = SimpleUploadedFile(
            "cover.png",
            b"\x89PNG\r\n\x1a\nCMS test image",
            content_type="image/png",
        )
        response = self.client.post(
            "/api/admin/cms/media/",
            {"file": upload, "alt_text": "Test cover", "caption": "Test"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["url"].startswith("http://testserver/media/"))
        media = CMSMediaAsset.objects.get(pk=response.data["id"])
        article = CMSArticle.objects.create(
            title="Media News",
            slug="media-news",
            thumbnail=media,
        )
        archive_response = self.client.post(f"/api/admin/cms/media/{media.pk}/archive/")
        self.assertEqual(archive_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("used_by", archive_response.data)
        self.assertEqual(archive_response.data["used_by"][0]["slug"], article.slug)

    def test_event_workflow_only_exposes_published_events(self):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=2)
        self.authenticate(self.editor)
        create_response = self.client.post(
            "/api/admin/events/",
            {
                "title": "Public Consultation",
                "description": "Consultation details",
                "event_type": "consultation",
                "start_at": start.isoformat(),
                "end_at": end.isoformat(),
                "location": "Pasig City",
                "is_virtual": False,
                "meeting_link": "",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        event_id = create_response.data["id"]

        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/events/?include_past=1")
        self.assertFalse(any(row["id"] == event_id for row in public_response.data["results"]))

        self.authenticate(self.editor)
        self.assertEqual(
            self.client.post(f"/api/admin/events/{event_id}/submit/").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(PublicEvent.objects.get(pk=event_id).status, "submitted")

        self.authenticate(self.admin)
        self.assertEqual(
            self.client.post(f"/api/admin/events/{event_id}/publish/").status_code,
            status.HTTP_200_OK,
        )
        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/events/?include_past=1")
        self.assertTrue(any(row["id"] == event_id for row in public_response.data["results"]))

        self.authenticate(self.admin)
        self.assertEqual(
            self.client.post(f"/api/admin/events/{event_id}/archive/").status_code,
            status.HTTP_200_OK,
        )
        self.client.force_authenticate(user=None)
        public_response = self.client.get("/api/public/events/?include_past=1")
        self.assertFalse(any(row["id"] == event_id for row in public_response.data["results"]))

    def test_event_rejects_end_time_before_start(self):
        start = timezone.now() + timedelta(days=1)
        self.authenticate(self.editor)
        response = self.client.post(
            "/api/admin/events/",
            {
                "title": "Invalid Schedule",
                "event_type": "meeting",
                "start_at": start.isoformat(),
                "end_at": (start - timedelta(minutes=1)).isoformat(),
                "location": "Quezon City",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
