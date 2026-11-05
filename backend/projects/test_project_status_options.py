from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from rest_framework import serializers

from cms.form_schema import CURRENT_PROJECT_STATUS_VALUES, default_simplified_form_schema
from cms.models import CMSContributorForm
from projects.models import Project
from projects.project_status import canonical_implementation_status
from projects.serializers import ProjectSerializer, PublicProjectSerializer
from cms.services.publishing import publish_contributor_form


class ProjectStatusOptionsTests(TestCase):
    def setUp(self):
        cache.clear()

    @staticmethod
    def profile(status):
        return {
            "form_schema": {"key": "simplified-rdip"},
            "simplified_form": {
                "startYear": "2026",
                "endYear": "2026",
                "status": status,
            },
        }

    def test_default_status_choices_only_include_current_values(self):
        schema = default_simplified_form_schema()
        status_field = next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "status"
        )
        self.assertEqual(
            [option["value"] for option in status_field["options"]],
            ["New", "Not Implemented", "Ongoing", "Completed", "On Hold", "Cancelled"],
        )
        self.assertEqual(len(CURRENT_PROJECT_STATUS_VALUES), 6)

        live_form = CMSContributorForm.objects.select_related("current_published_version").get(key="simplified-rdip")
        live_status = next(
            field for section in live_form.current_published_version.schema_json["sections"]
            for field in section["fields"] if field["key"] == "status"
        )
        self.assertEqual([option["value"] for option in live_status["options"]], [
            "New", "Not Implemented", "Ongoing", "Completed", "On Hold", "Cancelled",
        ])

    def test_new_projects_reject_retired_statuses(self):
        serializer = ProjectSerializer()
        for retired in ("Updated", "N/A", "Discontinued", "Dropped"):
            with self.subTest(status=retired), self.assertRaises(serializers.ValidationError):
                serializer.validate_profile_data(self.profile(retired))

        for current in ("Completed", "New", "Ongoing", "Not Implemented", "On Hold", "Cancelled"):
            with self.subTest(status=current):
                validated = serializer.validate_profile_data(self.profile(current))
                self.assertEqual(validated["simplified_form"]["status"], current)

        self.assertEqual(canonical_implementation_status("On hold"), "On Hold")

    def test_new_projects_accept_and_display_a_published_custom_status(self):
        """CMS status additions use stable values but must show their editable labels."""
        form = CMSContributorForm.objects.select_related("current_published_version").get(
            key="simplified-rdip"
        )
        schema = deepcopy(form.draft_schema_json)
        status_field = next(
            field for section in schema["sections"] for field in section["fields"]
            if field["key"] == "status"
        )
        status_field["options"].append({"value": "option_1", "label": "Test"})
        form.draft_schema_json = schema
        form.has_unpublished_changes = True
        form.status = CMSContributorForm.STATUS_DRAFT
        form.save(update_fields=["draft_schema_json", "has_unpublished_changes", "status", "updated_at"])
        published = publish_contributor_form(form)
        published.refresh_from_db()

        validated = ProjectSerializer().validate_profile_data(self.profile("option_1"))
        self.assertEqual(validated["simplified_form"]["status"], "option_1")
        self.assertEqual(
            validated["form_schema"]["version"],
            published.current_published_version.version_number,
        )

        project = Project.objects.create(
            name="Custom status test project",
            implementing_agency="DPWH",
            municipality="Quezon City",
            status="completed",
            cost=0,
            latitude=14.6,
            validated=True,
            profile_data=validated,
        )
        self.assertEqual(PublicProjectSerializer(project).data["implementation_status"], "Test")
        filtered = self.client.get("/api/public/projects/?status=Test")
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual([item["title"] for item in filtered.data], [project.name])

    def test_new_and_not_implemented_projects_reject_accomplishment_values(self):
        serializer = ProjectSerializer()
        for status in ("New", "Not Implemented"):
            profile = self.profile(status)
            profile["simplified_form"]["physicalAccomplishment"] = "50% complete"
            with self.subTest(status=status), self.assertRaises(serializers.ValidationError):
                serializer.validate_profile_data(profile)

    def test_existing_legacy_status_is_normalized_on_next_save(self):
        project = Project(profile_data=self.profile("Dropped"))
        serializer = ProjectSerializer(instance=project)
        unchanged = serializer.validate_profile_data(deepcopy(project.profile_data))
        self.assertEqual(unchanged["simplified_form"]["status"], "Not Implemented")
        self.assertEqual(project.profile_data["simplified_form"]["status"], "Dropped")

        changed = deepcopy(project.profile_data)
        changed["simplified_form"]["status"] = "Not Implemented"
        self.assertEqual(serializer.validate_profile_data(changed)["simplified_form"]["status"], "Not Implemented")

        changed["simplified_form"]["status"] = "Discontinued"
        with self.assertRaises(serializers.ValidationError):
            serializer.validate_profile_data(changed)

        na_project = Project(profile_data=self.profile("N/A"))
        na_value = ProjectSerializer(instance=na_project).validate_profile_data(deepcopy(na_project.profile_data))
        self.assertEqual(na_value["simplified_form"]["status"], "N/A")

    def test_backfill_updates_active_project_values_but_preserves_na(self):
        projects = {}
        for status in ("Discontinued", "Dropped", "Updated", "N/A"):
            profile = self.profile(status)
            profile["public_summary"] = {
                "text": f"Example project. Status: {status}.",
                "bullets": [f"Status: {status}", "Objective: Retain this detail"],
                "key_facts": {"status": status, "agency": "DENR"},
            }
            profile["public_summary_override"] = {"text": f"Historical override: {status}"}
            profile["revision_history"] = [{"submitted_status": status}]
            projects[status] = Project.objects.create(
                name=f"Project {status}", implementing_agency="DENR", municipality="NCR",
                status="completed", cost=0, latitude=14.6,
                profile_data=profile,
            )
        migration = import_module("projects.migrations.0033_normalize_project_implementation_status")
        migration.normalize_project_statuses(apps, SimpleNamespace(connection=connection))

        for old_status, expected in (
            ("Discontinued", "Not Implemented"),
            ("Dropped", "Not Implemented"),
            ("Updated", "Ongoing"),
            ("N/A", "N/A"),
        ):
            projects[old_status].refresh_from_db()
            self.assertEqual(projects[old_status].profile_data["simplified_form"]["status"], expected)
            summary = projects[old_status].profile_data["public_summary"]
            self.assertEqual(summary["key_facts"]["status"], expected)
            self.assertIn(f"Status: {expected}.", summary["text"])
            self.assertEqual(summary["bullets"][0], f"Status: {expected}")
            self.assertEqual(summary["bullets"][1], "Objective: Retain this detail")
            self.assertEqual(
                projects[old_status].profile_data["public_summary_override"]["text"],
                f"Historical override: {old_status}",
            )
            self.assertEqual(
                projects[old_status].profile_data["revision_history"],
                [{"submitted_status": old_status}],
            )

    def test_public_statuses_and_filters_group_legacy_values_before_backfill(self):
        for status in ("Discontinued", "Dropped", "Updated", "N/A"):
            Project.objects.create(
                name=f"Project {status}", implementing_agency="DENR", municipality="NCR",
                status="completed", cost=0, latitude=14.6, validated=True,
                profile_data=self.profile(status),
            )

        all_projects = self.client.get("/api/public/projects/?view=summary")
        self.assertEqual(all_projects.status_code, 200)
        by_title = {project["title"]: project["implementation_status"] for project in all_projects.data}
        self.assertEqual(by_title["Project Discontinued"], "Not Implemented")
        self.assertEqual(by_title["Project Dropped"], "Not Implemented")
        self.assertEqual(by_title["Project Updated"], "Ongoing")
        self.assertEqual(by_title["Project N/A"], "N/A")

        not_implemented = self.client.get("/api/public/projects/?status=Not%20Implemented&view=summary")
        self.assertEqual(len(not_implemented.data), 2)
        ongoing = self.client.get("/api/public/projects/?status=Ongoing&view=summary")
        self.assertEqual(len(ongoing.data), 1)
        stats = self.client.get("/api/public/projects/stats/")
        self.assertEqual(stats.data["by_status"], {"Not Implemented": 2, "Ongoing": 1, "N/A": 1})
        self.assertEqual(canonical_implementation_status("Dropped"), "Not Implemented")
