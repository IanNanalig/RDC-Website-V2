from copy import deepcopy

from django.test import TestCase
from rest_framework.test import APIClient

from cms.form_schema import FormSchemaError, default_simplified_form_schema, validate_form_schema
from cms.models import CMSContributorForm
from cms.services.locking import acquire_form_lock
from cms.services.publishing import publish_contributor_form
from projects.models import User, UserActivity


class SupportingDocumentSchemaTests(TestCase):
    def test_document_field_limits_and_single_active_field_are_enforced(self):
        schema = default_simplified_form_schema()
        document = next(
            field
            for section in schema["sections"]
            for field in section["fields"]
            if field.get("type") == "document_upload"
        )
        document["max_files"] = 11
        with self.assertRaisesMessage(FormSchemaError, "between 1 and 10"):
            validate_form_schema(schema)

        schema = default_simplified_form_schema()
        second = deepcopy(next(
            field
            for section in schema["sections"]
            for field in section["fields"]
            if field.get("type") == "document_upload"
        ))
        second["key"] = "custom_second_documents"
        schema["sections"][0]["fields"].append(second)
        with self.assertRaisesMessage(FormSchemaError, "only one active"):
            validate_form_schema(schema)

    def test_document_field_can_be_hidden_or_removed_from_a_future_version(self):
        published = default_simplified_form_schema()
        hidden = deepcopy(published)
        for section in hidden["sections"]:
            for field in section["fields"]:
                if field.get("type") == "document_upload":
                    field["visible"] = False
        validate_form_schema(hidden, published_schema=published)

        removed = deepcopy(published)
        removed["sections"] = [
            section for section in removed["sections"] if section.get("key") != "supporting_documents"
        ]
        validate_form_schema(removed, published_schema=published)


class ContributorFormControlTests(TestCase):
    def setUp(self):
        self.admin_one = User.objects.create_user(
            username="form-admin-one", email="form-admin-one@example.com", password="Password123!", role="admin"
        )
        self.admin_two = User.objects.create_user(
            username="form-admin-two", email="form-admin-two@example.com", password="Password123!", role="admin"
        )
        self.form = CMSContributorForm.objects.get(key="simplified-rdip")
        self.client = APIClient()

    def test_admin_can_confirm_lock_takeover_and_previous_owner_is_audited(self):
        acquire_form_lock(self.form.id, self.admin_one)
        self.client.force_authenticate(self.admin_two)
        blocked = self.client.post(f"/api/admin/cms/forms/{self.form.id}/lock/", {}, format="json")
        self.assertEqual(blocked.status_code, 423)
        taken = self.client.post(
            f"/api/admin/cms/forms/{self.form.id}/lock/",
            {"force": True, "confirm_takeover": True},
            format="json",
        )
        self.assertEqual(taken.status_code, 200)
        self.assertEqual(taken.data["lock_owner"], self.admin_two.id)
        activity = UserActivity.objects.filter(event="cms_form_lock_overridden").latest("created_at")
        self.assertEqual(activity.details["previous_lock_owner"], self.admin_one.id)
        self.assertEqual(activity.details["previous_lock_owner_name"], self.admin_one.username)

    def test_repeated_publish_is_rechecked_inside_transaction(self):
        self.form.has_unpublished_changes = True
        self.form.save(update_fields=["has_unpublished_changes"])
        publish_contributor_form(self.form, self.admin_one)
        with self.assertRaisesMessage(FormSchemaError, "no unpublished changes"):
            publish_contributor_form(self.form.id, self.admin_one)
