from copy import deepcopy
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from cms.management.commands.seed_publications_cms import PUBLICATION_CATEGORIES
from cms.management.commands.sync_publication_categories import merge_publication_categories
from cms.models import CMSPage, CMSPageSection, CMSRevision


class PublicationCategoryMergeTests(TestCase):
    def setUp(self):
        self.page, _ = CMSPage.objects.update_or_create(
            slug="publications",
            defaults={
                "title": "Publications",
                "status": "published",
                "has_unpublished_changes": False,
                "published_snapshot_json": {"marker": "unchanged-public-version"},
            },
        )
        existing = CMSPageSection.objects.filter(
            page=self.page,
            section_key="publication-catalog",
        ).first()
        if existing:
            existing.content_json = self._starting_content()
            existing.status = "published"
            existing.lock_owner = None
            existing.lock_acquired_at = None
            existing.save()
            self.section = existing
        else:
            self.section = CMSPageSection.objects.create(
                page=self.page,
                section_key="publication-catalog",
                section_type="publication_catalog",
                order=1,
                status="published",
                content_json=self._starting_content(),
            )

    def _starting_content(self):
        return {
            "title": "Edited publication title",
            "unknownTopLevelField": {"keep": True},
            "categories": [
                {
                    "id": "policy-briefs",
                    "title": "Policy Briefs",
                    "customCategoryField": "keep-category",
                    "documents": [
                        {
                            "id": "uploaded-policy",
                            "title": "Uploaded policy document",
                            "url": "/media/cms/policy.pdf",
                        }
                    ],
                },
                {
                    "id": "res",
                    "title": "Edited RES title",
                    "description": "Editor-written description",
                    "documents": [
                        {
                            "id": "uploaded-res",
                            "title": "Uploaded RES document",
                            "url": "/media/cms/res.pdf",
                            "unknownDocumentField": "keep-document",
                        }
                    ],
                },
            ],
        }

    def test_merge_preserves_custom_data_and_adds_all_built_ins(self):
        starting = self._starting_content()
        merged, result = merge_publication_categories(starting)

        self.assertEqual(starting, self._starting_content(), "The merge must not mutate its input.")
        self.assertEqual(merged["title"], "Edited publication title")
        self.assertEqual(merged["unknownTopLevelField"], {"keep": True})
        self.assertEqual(len(result["added_categories"]), 7)

        categories = {category["id"]: category for category in merged["categories"]}
        self.assertTrue({category["id"] for category in PUBLICATION_CATEGORIES}.issubset(categories))
        self.assertEqual(categories["policy-briefs"]["customCategoryField"], "keep-category")
        self.assertEqual(categories["res"]["title"], "Edited RES title")
        self.assertEqual(categories["res"]["description"], "Editor-written description")
        self.assertEqual(categories["res"]["documents"][0]["url"], "/media/cms/res.pdf")
        self.assertEqual(categories["res"]["documents"][0]["unknownDocumentField"], "keep-document")
        self.assertTrue({"res1", "res2", "res4"}.issubset({doc["id"] for doc in categories["res"]["documents"]}))

    def test_command_creates_draft_revision_without_changing_published_snapshot(self):
        published_before = deepcopy(self.page.published_snapshot_json)
        output = StringIO()

        call_command("sync_publication_categories", stdout=output)

        self.section.refresh_from_db()
        self.page.refresh_from_db()
        self.assertEqual(self.section.status, "draft")
        self.assertTrue(self.page.has_unpublished_changes)
        self.assertEqual(self.page.published_snapshot_json, published_before)
        self.assertTrue(
            CMSRevision.objects.filter(
                object_id=self.section.pk,
                action=CMSRevision.ACTION_UPDATE,
            ).exists()
        )
        self.assertIn("7 categories", output.getvalue())
        self.assertIn("published Publications page remains unchanged", output.getvalue())

    def test_command_is_idempotent_and_dry_run_does_not_write(self):
        dry_run_output = StringIO()
        content_before = deepcopy(self.section.content_json)
        call_command("sync_publication_categories", dry_run=True, stdout=dry_run_output)
        self.section.refresh_from_db()
        self.assertEqual(self.section.content_json, content_before)
        self.assertIn("Dry run: 7 categories", dry_run_output.getvalue())

        call_command("sync_publication_categories", stdout=StringIO())
        revision_count = CMSRevision.objects.filter(object_id=self.section.pk).count()
        second_output = StringIO()
        call_command("sync_publication_categories", stdout=second_output)
        self.assertEqual(CMSRevision.objects.filter(object_id=self.section.pk).count(), revision_count)
        self.assertIn("No database changes are needed", second_output.getvalue())
