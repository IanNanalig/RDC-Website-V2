from io import BytesIO
import shutil
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from cms.models import CMSMediaAsset, CMSPage, CMSSiteSetting
from projects.models import User


def png_bytes():
    output = BytesIO()
    Image.new("RGB", (3, 2), "green").save(output, format="PNG")
    return output.getvalue()


class CMSMediaArchiveFeaturesTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="rdc-media-features-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.admin = User.objects.create_user(username="media-admin", email="media-admin@example.com", password="pass", role="admin")
        self.client.force_authenticate(self.admin)

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root)

    def test_media_metadata_editing_and_ten_item_pagination(self):
        uploaded = self.client.post("/api/admin/cms/media/", {"file": SimpleUploadedFile("cover.png", png_bytes(), content_type="image/png")}, format="multipart")
        self.assertEqual(uploaded.status_code, 201)
        self.assertEqual((uploaded.data["width"], uploaded.data["height"]), (3, 2))
        self.assertEqual(uploaded.data["original_filename"], "cover.png")
        setting = CMSSiteSetting.objects.get(key="media-categories")
        setting.value_json = {"categories": ["General", "Publications"]}
        setting.save(update_fields=["value_json"])
        edited = self.client.patch(f"/api/admin/cms/media/{uploaded.data['id']}/", {"category": "Publications", "tags": ["report"]}, format="json")
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.data["category"], "Publications")
        for index in range(11):
            CMSMediaAsset.objects.create(file=f"cms/extra-{index}.pdf", file_type="document", mime_type="application/pdf", category="General")
        first = self.client.get("/api/admin/cms/media/?view=summary")
        self.assertEqual(first.data["count"], 12)
        self.assertEqual(len(first.data["results"]), 10)
        self.assertEqual(len(self.client.get("/api/admin/cms/media/?view=summary&page=2").data["results"]), 2)
        filtered = self.client.get("/api/admin/cms/media/?view=summary&category=Publications&tag=report")
        self.assertEqual(filtered.data["count"], 1)

    def test_media_category_settings_cannot_remove_a_category_in_use(self):
        setting = CMSSiteSetting.objects.get(key="media-categories")
        setting.value_json = {"categories": ["General", "Publications"]}
        setting.save(update_fields=["value_json"])
        CMSMediaAsset.objects.create(file="cms/archived.pdf", file_type="document", mime_type="application/pdf", category="Publications", is_archived=True)
        response = self.client.patch(
            "/api/admin/cms/settings/media-categories/",
            {"value_json": {"categories": ["General"]}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        setting.refresh_from_db()
        self.assertIn("Publications", setting.value_json["categories"])

    def test_audio_probe_failure_is_clear_and_video_limit_is_enforced(self):
        with patch("cms.services.media_validation.shutil.which", return_value=None):
            audio = self.client.post("/api/admin/cms/media/", {"file": SimpleUploadedFile("tone.mp3", b"audio", content_type="audio/mpeg")}, format="multipart")
        self.assertEqual(audio.status_code, 422)
        self.assertEqual(audio.data["reason"], "probe_unavailable")
        limits = CMSSiteSetting.objects.get(key="media-upload-max-bytes")
        limits.value_json = {"image": 1000, "document": 1000, "audio": 1000, "video": 10}
        limits.save(update_fields=["value_json"])
        video = self.client.post("/api/admin/cms/media/", {"file": SimpleUploadedFile("clip.mp4", b"12345678901", content_type="video/mp4")}, format="multipart")
        self.assertEqual(video.status_code, 422)
        self.assertEqual(video.data["reason"], "file_too_large")

    def test_archived_page_is_private_until_fresh_publish(self):
        page = CMSPage.objects.create(title="Archive", slug="archive-page", status="published", published_at=timezone.now(), published_snapshot_json={"slug": "archive-page", "title": "Archive"})
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/public/cms/pages/archive-page/").status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f"/api/admin/cms/pages/{page.pk}/archive/").status_code, 200)
        self.assertEqual(self.client.get("/api/admin/cms/pages/?view=summary&q=archive-page").data["count"], 0)
        self.assertEqual(self.client.get("/api/admin/cms/pages/?view=summary&archived=1&q=archive-page").data["count"], 1)
        self.assertEqual(self.client.post(f"/api/admin/cms/pages/{page.pk}/restore/").status_code, 200)
        page.refresh_from_db()
        self.assertEqual(page.status, "draft")
        self.assertIsNone(page.published_at)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/public/cms/pages/archive-page/").status_code, 404)
