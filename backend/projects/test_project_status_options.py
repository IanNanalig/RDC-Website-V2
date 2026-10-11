from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from rest_framework import serializers

from cms.form_schema import CURRENT_PROJECT_STATUS_VALUES, default_simplified_form_schema
from projects.models import Project
from projects.project_status import canonical_implementation_status
from projects.serializers import ProjectSerializer


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
            ["Completed", "New", "Ongoing", "Not Implemented"],
        )
        self.assertEqual(len(CURRENT_PROJECT_STATUS_VALUES), 4)

    def test_new_projects_reject_retired_statuses(self):
        serializer = ProjectSerializer()
        for retired in ("Updated", "N/A", "Discontinued", "Dropped"):
            with self.subTest(status=retired), self.assertRaises(serializers.ValidationError):
                serializer.validate_profile_data(self.profile(retired))

        for current in ("Completed", "New", "Ongoing", "Not Implemented"):
            with self.subTest(status=current):
                validated = serializer.validate_profile_data(self.profile(current))
                self.assertEqual(validated["simplified_form"]["status"], current)

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
