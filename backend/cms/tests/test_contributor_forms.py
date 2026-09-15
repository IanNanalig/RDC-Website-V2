from copy import deepcopy
from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.form_schema import FormSchemaError, validate_simplified_answers
from cms.models import CMSContributorForm
from cms.services.locking import acquire_form_lock
from cms.services.publishing import publish_contributor_form, restore_contributor_form_version
from projects.models import Notification, Project, User
from projects.serializers import ProjectSerializer


class ContributorFormWorkflowTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="form-admin",
            email="form-admin@example.com",
            password="StrongTestPassword123!",
            role="admin",
        )
        self.editor = User.objects.create_user(
            username="form-editor",
            email="form-editor@example.com",
            password="StrongTestPassword123!",
            role="content_editor",
        )
        self.contributor = User.objects.create_user(
            username="form-contributor",
            email="form-contributor@example.com",
            password="StrongTestPassword123!",
            role="staff",
        )
        self.form = CMSContributorForm.objects.select_related("current_published_version").get(
            key="simplified-rdip"
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def _draft_with_custom_field(self, required=False):
        schema = deepcopy(self.form.draft_schema_json)
        schema["sections"][0]["fields"].append({
            "key": "custom_reference_number",
            "label": "Agency Reference Number",
            "type": "text",
            "required": required,
            "visible": True,
            "protected": False,
            "help_text": "",
            "placeholder": "",
        })
        return schema

    def _save_draft(self, schema, edit_mode="update"):
        self.form.refresh_from_db()
        self.authenticate(self.editor)
        lock = self.client.post(f"/api/admin/cms/forms/{self.form.id}/lock/", {}, format="json")
        self.assertEqual(lock.status_code, status.HTTP_200_OK)
        return self.client.patch(
            f"/api/admin/cms/forms/{self.form.id}/",
            {
                "name": schema["title"],
                "description": schema.get("description", ""),
                "draft_schema_json": schema,
                "expected_updated_at": lock.data["updated_at"],
                "edit_mode": edit_mode,
            },
            format="json",
        )

    def test_editor_can_save_and_submit_while_only_admin_publishes(self):
        saved = self._save_draft(self._draft_with_custom_field())
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertEqual(saved.data["status"], "draft")

        submitted = self.client.post(f"/api/admin/cms/forms/{self.form.id}/submit/", {}, format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        self.assertEqual(submitted.data["status"], "submitted")
        self.assertTrue(Notification.objects.filter(
            recipient=self.admin, event_type="cms_form_submitted",
        ).exists())
        self.assertEqual(
            self.client.post(f"/api/admin/cms/forms/{self.form.id}/publish/", {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.authenticate(self.admin)
        published = self.client.post(f"/api/admin/cms/forms/{self.form.id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertEqual(published.data["current_published_version_number"], 2)
        self.assertFalse(published.data["has_unpublished_changes"])
        self.assertTrue(Notification.objects.filter(
            recipient=self.editor, event_type="cms_form_published",
        ).exists())

        self.authenticate(self.contributor)
        current = self.client.get("/api/contributor-forms/simplified-rdip/current/")
        legacy = self.client.get("/api/contributor-forms/simplified-rdip/versions/1/")
        self.assertEqual(current.status_code, status.HTTP_200_OK)
        self.assertEqual(current.data["version"], 2)
        self.assertEqual(legacy.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            "custom_reference_number",
            [field["key"] for section in legacy.data["schema"]["sections"] for field in section["fields"]],
        )

    def test_form_lock_query_does_not_join_nullable_owner(self):
        with CaptureQueriesContext(connection) as queries:
            form, acquired = acquire_form_lock(self.form.id, self.editor)

        self.assertTrue(acquired)
        self.assertEqual(form.lock_owner_id, self.editor.id)
        lock_queries = [
            entry["sql"]
            for entry in queries.captured_queries
            if "SELECT" in entry["sql"].upper() and "cms_cmscontributorform" in entry["sql"]
        ]
        self.assertTrue(lock_queries)
        self.assertNotIn("JOIN", lock_queries[0].upper())

    def test_form_lock_blocks_other_editors_and_admin_can_release_it(self):
        other_editor = User.objects.create_user(
            username="other-form-editor",
            email="other-form-editor@example.com",
            password="StrongTestPassword123!",
            role="content_editor",
        )
        self.authenticate(self.editor)
        acquired = self.client.post(f"/api/admin/cms/forms/{self.form.id}/lock/", {}, format="json")
        self.assertEqual(acquired.status_code, status.HTTP_200_OK)

        self.authenticate(other_editor)
        blocked = self.client.post(f"/api/admin/cms/forms/{self.form.id}/lock/", {}, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_423_LOCKED)
        save = self.client.patch(
            f"/api/admin/cms/forms/{self.form.id}/",
            {"draft_schema_json": acquired.data["draft_schema_json"], "edit_mode": "update"},
            format="json",
        )
        self.assertEqual(save.status_code, status.HTTP_423_LOCKED)

        self.authenticate(self.admin)
        released = self.client.post(f"/api/admin/cms/forms/{self.form.id}/unlock/", {}, format="json")
        self.assertEqual(released.status_code, status.HTTP_200_OK)

    def test_expired_form_lock_can_be_taken_over(self):
        self.form.lock_owner = self.editor
        self.form.lock_acquired_at = timezone.now() - timedelta(hours=1)
        self.form.save(update_fields=["lock_owner", "lock_acquired_at", "updated_at"])
        other_editor = User.objects.create_user(
            username="stale-lock-editor",
            email="stale-lock-editor@example.com",
            password="StrongTestPassword123!",
            role="content_editor",
        )

        self.authenticate(other_editor)
        response = self.client.post(f"/api/admin/cms/forms/{self.form.id}/lock/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lock_owner"], other_editor.id)

    def test_ordinary_contributors_cannot_access_form_admin_endpoints(self):
        self.authenticate(self.contributor)
        self.assertEqual(
            self.client.get("/api/admin/cms/forms/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post(f"/api/admin/cms/forms/{self.form.id}/lock/", {}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_publish_and_restore_lock_queries_do_not_join_nullable_version(self):
        schema = self._draft_with_custom_field()
        self.form.draft_schema_json = schema
        self.form.has_unpublished_changes = True
        self.form.save(update_fields=["draft_schema_json", "has_unpublished_changes", "updated_at"])
        with CaptureQueriesContext(connection) as publish_queries:
            published = publish_contributor_form(self.form, self.admin)
        publish_form_selects = [
            entry["sql"] for entry in publish_queries.captured_queries
            if "SELECT" in entry["sql"].upper() and "cms_cmscontributorform" in entry["sql"]
        ]
        self.assertTrue(publish_form_selects)
        self.assertNotIn("JOIN", publish_form_selects[0].upper())

        version_one = published.versions.get(version_number=1)
        with CaptureQueriesContext(connection) as restore_queries:
            restored = restore_contributor_form_version(published, version_one, self.admin)
        restore_form_selects = [
            entry["sql"] for entry in restore_queries.captured_queries
            if "SELECT" in entry["sql"].upper() and "cms_cmscontributorform" in entry["sql"]
        ]
        self.assertTrue(restore_form_selects)
        self.assertNotIn("JOIN", restore_form_selects[0].upper())
        self.assertEqual(restored.status, "draft")

    def test_restore_is_a_draft_and_does_not_replace_live_version(self):
        saved = self._save_draft(self._draft_with_custom_field())
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.authenticate(self.admin)
        published = self.client.post(f"/api/admin/cms/forms/{self.form.id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, status.HTTP_200_OK)

        versions = self.client.get(f"/api/admin/cms/forms/{self.form.id}/versions/")
        version_one = next(item for item in versions.data if item["version_number"] == 1)
        restored = self.client.post(
            f"/api/admin/cms/forms/{self.form.id}/restore-version/",
            {"version_id": version_one["id"]},
            format="json",
        )
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        self.assertEqual(restored.data["status"], "draft")
        self.assertEqual(restored.data["current_published_version_number"], 2)
        self.assertTrue(restored.data["has_unpublished_changes"])

        current = self.client.get("/api/contributor-forms/simplified-rdip/current/")
        self.assertEqual(current.data["version"], 2)
        retired = [
            field
            for section in restored.data["draft_schema_json"]["sections"]
            for field in section["fields"]
            if field["key"] == "custom_reference_number"
        ]
        self.assertEqual(len(retired), 1)
        self.assertFalse(retired[0]["visible"])

    def test_update_mode_cannot_reorder_existing_fields(self):
        schema = deepcopy(self.form.draft_schema_json)
        schema["sections"][0]["fields"][0], schema["sections"][0]["fields"][1] = (
            schema["sections"][0]["fields"][1],
            schema["sections"][0]["fields"][0],
        )
        response = self._save_draft(schema, edit_mode="update")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Change Form", str(response.data))

    def test_system_managed_ai_section_cannot_be_changed_or_exposed(self):
        schema = deepcopy(self.form.draft_schema_json)
        system_section = next(section for section in schema["sections"] if section.get("admin_only"))
        system_section["title"] = "Contributor AI Questions"
        response = self._save_draft(schema, edit_mode="change")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("System-managed AI analysis", str(response.data))

        schema = deepcopy(self.form.draft_schema_json)
        system_section = next(section for section in schema["sections"] if section.get("admin_only"))
        system_section["admin_only"] = False
        response = self._save_draft(schema, edit_mode="change")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("System-managed AI analysis", str(response.data))

    def test_protected_select_options_can_be_added_reordered_and_removed(self):
        schema = deepcopy(self.form.draft_schema_json)
        sdg_field = next(
            field
            for section in schema["sections"]
            for field in section["fields"]
            if field["key"] == "sdgSelections"
        )
        original_first = sdg_field["options"][0]
        sdg_field["options"].append({"value": "option_1", "label": "Additional SDG alignment"})
        sdg_field["options"].insert(0, sdg_field["options"].pop())

        saved = self._save_draft(schema, edit_mode="change")

        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        saved_sdg = next(
            field
            for section in saved.data["draft_schema_json"]["sections"]
            for field in section["fields"]
            if field["key"] == "sdgSelections"
        )
        self.assertEqual(saved_sdg["options"][0]["value"], "option_1")

        reduced_schema = deepcopy(saved.data["draft_schema_json"])
        reduced_sdg = next(
            field
            for section in reduced_schema["sections"]
            for field in section["fields"]
            if field["key"] == "sdgSelections"
        )
        reduced_sdg["options"] = [
            option for option in reduced_sdg["options"] if option["value"] != original_first["value"]
        ]
        reduced = self._save_draft(reduced_schema, edit_mode="change")
        self.assertEqual(reduced.status_code, status.HTTP_200_OK)

    def test_option_used_by_conditional_field_cannot_be_removed(self):
        schema = deepcopy(self.form.draft_schema_json)
        pcb_field = next(
            field
            for section in schema["sections"]
            for field in section["fields"]
            if field["key"] == "pcbIncluded"
        )
        pcb_field["options"] = [option for option in pcb_field["options"] if option["value"] != "Yes"]

        rejected = self._save_draft(schema, edit_mode="change")

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("controls a conditional field", str(rejected.data))

    def test_stale_form_save_returns_conflict(self):
        self.authenticate(self.editor)
        locked = self.client.post(f"/api/admin/cms/forms/{self.form.id}/lock/", {}, format="json")
        self.assertEqual(locked.status_code, status.HTTP_200_OK)
        self.form.refresh_from_db()
        self.form.description = "Changed by another request"
        self.form.save(update_fields=["description", "updated_at"])
        response = self.client.patch(
            f"/api/admin/cms/forms/{self.form.id}/",
            {
                "draft_schema_json": locked.data["draft_schema_json"],
                "expected_updated_at": locked.data["updated_at"],
                "edit_mode": "update",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_unpublished_custom_items_can_be_removed(self):
        schema = self._draft_with_custom_field()
        schema["sections"].insert(-1, {
            "key": "custom_section_1",
            "title": "Temporary Section",
            "description": "",
            "visible": True,
            "fields": [{
                "key": "custom_temporary_value",
                "label": "Temporary Value",
                "type": "text",
                "required": False,
                "visible": True,
                "protected": False,
            }],
        })
        saved = self._save_draft(schema, edit_mode="change")
        self.assertEqual(saved.status_code, status.HTTP_200_OK)

        stripped = deepcopy(saved.data["draft_schema_json"])
        stripped["sections"][0]["fields"] = [
            field for field in stripped["sections"][0]["fields"]
            if field["key"] != "custom_reference_number"
        ]
        stripped["sections"] = [
            section for section in stripped["sections"] if section["key"] != "custom_section_1"
        ]
        removed = self._save_draft(stripped, edit_mode="change")
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        keys = [
            field["key"]
            for section in removed.data["draft_schema_json"]["sections"]
            for field in section["fields"]
        ]
        self.assertNotIn("custom_reference_number", keys)
        self.assertNotIn("custom_temporary_value", keys)

    def test_published_custom_field_is_hidden_without_changing_old_version(self):
        self.assertEqual(self._save_draft(self._draft_with_custom_field()).status_code, status.HTTP_200_OK)
        self.authenticate(self.admin)
        version_two_response = self.client.post(
            f"/api/admin/cms/forms/{self.form.id}/publish/", {}, format="json"
        )
        self.assertEqual(version_two_response.status_code, status.HTTP_200_OK)

        self.form.refresh_from_db()
        schema = deepcopy(self.form.draft_schema_json)
        custom_field = next(
            field
            for section in schema["sections"]
            for field in section["fields"]
            if field["key"] == "custom_reference_number"
        )
        custom_field["visible"] = False
        hidden = self._save_draft(schema, edit_mode="change")
        self.assertEqual(hidden.status_code, status.HTTP_200_OK)
        self.authenticate(self.admin)
        version_three_response = self.client.post(
            f"/api/admin/cms/forms/{self.form.id}/publish/", {}, format="json"
        )
        self.assertEqual(version_three_response.status_code, status.HTTP_200_OK)

        self.form.refresh_from_db()
        version_two = self.form.versions.get(version_number=2)
        version_three = self.form.versions.get(version_number=3)
        old_field = next(
            field for section in version_two.schema_json["sections"] for field in section["fields"]
            if field["key"] == "custom_reference_number"
        )
        new_field = next(
            field for section in version_three.schema_json["sections"] for field in section["fields"]
            if field["key"] == "custom_reference_number"
        )
        self.assertTrue(old_field["visible"])
        self.assertFalse(new_field["visible"])

    def test_reset_draft_to_live_version_discards_unpublished_changes(self):
        saved = self._save_draft(self._draft_with_custom_field())
        self.assertTrue(saved.data["has_unpublished_changes"])
        self.authenticate(self.admin)
        reset = self.client.post(
            f"/api/admin/cms/forms/{self.form.id}/restore-version/",
            {"version_id": self.form.current_published_version_id},
            format="json",
        )
        self.assertEqual(reset.status_code, status.HTTP_200_OK)
        self.assertEqual(reset.data["status"], "published")
        self.assertFalse(reset.data["has_unpublished_changes"])
        self.assertEqual(reset.data["draft_schema_json"], self.form.current_published_version.schema_json)

    def test_rejection_notifies_the_submitting_editor_with_notes(self):
        self.assertEqual(self._save_draft(self._draft_with_custom_field()).status_code, status.HTTP_200_OK)
        submitted = self.client.post(f"/api/admin/cms/forms/{self.form.id}/submit/", {}, format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        self.authenticate(self.admin)
        rejected = self.client.post(
            f"/api/admin/cms/forms/{self.form.id}/reject/",
            {"remarks": "Clarify the agency reference label."},
            format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_200_OK)
        notification = Notification.objects.get(recipient=self.editor, event_type="cms_form_rejected")
        self.assertIn("Clarify the agency reference label", notification.message)
        self.assertEqual(notification.link_path, "/employee/cms/forms")

    def test_current_form_uses_etag_revalidation(self):
        self.authenticate(self.contributor)
        first = self.client.get("/api/contributor-forms/simplified-rdip/current/")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertTrue(first["ETag"])
        unchanged = self.client.get(
            "/api/contributor-forms/simplified-rdip/current/",
            HTTP_IF_NONE_MATCH=first["ETag"],
        )
        self.assertEqual(unchanged.status_code, status.HTTP_304_NOT_MODIFIED)

    def test_new_projects_use_live_version_while_existing_projects_stay_pinned(self):
        self.assertEqual(self._save_draft(self._draft_with_custom_field()).status_code, status.HTTP_200_OK)
        self.authenticate(self.admin)
        published = self.client.post(f"/api/admin/cms/forms/{self.form.id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        live_version = published.data["current_published_version_number"]

        existing_profile = {
            "form_schema": {"key": "simplified-rdip", "version": 1},
            "simplified_form": {"custom_fields": {"custom_historical_note": "Keep this answer"}},
        }
        existing = Project.objects.create(
            name="Pinned form project",
            agency="MMDA",
            implementing_agency="MMDA",
            budget=0,
            cost=0,
            municipality="NCR",
            latitude=14.5,
            status="planning",
            created_by=self.contributor,
            profile_data=existing_profile,
        )
        validate_simplified_answers(existing.profile_data, require_complete=False)
        self.assertEqual(existing.profile_data["form_schema"]["version"], 1)
        self.assertEqual(
            existing.profile_data["simplified_form"]["custom_fields"]["custom_historical_note"],
            "Keep this answer",
        )

        new_profile = ProjectSerializer().validate_profile_data(
            {
                "form_schema": {"key": "simplified-rdip", "version": 1},
                "simplified_form": {
                    "startYear": "2026",
                    "endYear": "2026",
                    "fundingRequirementByYear": {},
                    "actualFundingByYear": {},
                    "custom_fields": {},
                },
            }
        )
        self.assertEqual(new_profile["form_schema"]["version"], live_version)

    def test_required_custom_field_is_checked_only_for_complete_submission(self):
        saved = self._save_draft(self._draft_with_custom_field(required=True))
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.authenticate(self.admin)
        published = self.client.post(f"/api/admin/cms/forms/{self.form.id}/publish/", {}, format="json")
        version = published.data["current_published_version_number"]
        profile = {
            "form_schema": {"key": "simplified-rdip", "version": version},
            "simplified_form": {"custom_fields": {}},
        }
        validate_simplified_answers(profile, require_complete=False)
        with self.assertRaises(FormSchemaError):
            validate_simplified_answers(profile, require_complete=True)
