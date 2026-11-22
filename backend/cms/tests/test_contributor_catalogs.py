from copy import deepcopy
from datetime import timedelta
from json import dumps
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from cms.form_schema import (
    FormSchemaError, default_simplified_form_schema, prepare_catalog_schema,
    validate_draft_schema, validate_simplified_answers,
)
from cms.models import CMSContributorForm, CMSContributorFormVersion
from cms.services.publishing import publish_contributor_form
from projects.form_catalogs import location_map_keys, project_outcome_context, upgrade_catalog_answers, with_catalog_options
from projects.models import Agency, CommitteeOutcomeGroup, Project, ProjectLocation, SectoralCommittee, SystemSetting, User
from projects.priority_scoring import analyze_project
from projects.serializers import PublicProjectSerializer
from projects.views import _filter_public_payload_location, _sync_project_collaborators


@override_settings(GROQ_ENABLED=False)
class ContributorCatalogTests(APITestCase):
    endpoint = "/api/admin/contributor-form-catalogs/"

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="catalog-admin", email="catalog-admin@example.com", role="admin", is_superuser=True)
        cls.validator = User.objects.create_user(username="catalog-validator", email="catalog-validator@example.com", role="validator")
        cls.primary = Agency.objects.get_or_create(code="DOH", defaults={"name": "Department of Health"})[0]
        cls.collaborator = Agency.objects.get_or_create(code="DPWH", defaults={"name": "Department of Public Works and Highways"})[0]

    def test_core_protection_and_cosmetic_edits(self):
        schema = default_simplified_form_schema()
        core = next(section for section in schema["sections"] if section["key"] == "project_information")
        core["fields"][1]["label"] = "Project partners"
        validate_draft_schema(schema)
        case = deepcopy(schema)
        case["sections"][0]["fields"] = [field for field in core["fields"] if field["key"] != "program"]
        with self.assertRaisesRegex(FormSchemaError, "Program"):
            validate_draft_schema(case)
        case = deepcopy(schema)
        next(section for section in case["sections"] if section["key"] == "accomplishment")["visible"] = False
        with self.assertRaisesRegex(FormSchemaError, "Accomplishment"):
            validate_draft_schema(case)
        case = deepcopy(schema)
        case["sections"][0]["fields"][1]["required"] = True
        with self.assertRaisesRegex(FormSchemaError, "optional"):
            validate_draft_schema(case)
        case = deepcopy(schema)
        next(field for field in case["sections"][0]["fields"] if field["key"] == "location")["options"] = [{"value": "fake", "label": "Fake"}]
        with self.assertRaisesRegex(FormSchemaError, "managed by its catalog"):
            prepare_catalog_schema(case)

    def test_catalog_ids_and_historical_display_survive_rename_and_deactivation(self):
        schema = prepare_catalog_schema(default_simplified_form_schema())
        form = CMSContributorForm.objects.get(key="simplified-rdip")
        version = CMSContributorFormVersion.objects.create(form=form, version_number=501, schema_json=schema)
        profile = {
            "simplified_form": {
                "location": ["lgu-manila", "lgu-taguig"], "developmentSector": "sceed",
                "collaboratingAgencies": [f"agency:{self.collaborator.pk}"],
            },
        }
        saved = validate_simplified_answers(deepcopy(profile), schema_version=version)
        project = Project.objects.create(
            name="Catalog project", cost=0, latitude=14.6, longitude=121.0,
            primary_agency=self.primary, profile_data=saved,
        )
        _sync_project_collaborators(project, saved)
        ProjectLocation.objects.filter(pk="lgu-manila").update(name="Manila (updated)", is_active=False)
        self.collaborator.is_active = False
        self.collaborator.save(update_fields=["is_active"])
        retained = validate_simplified_answers(deepcopy(profile), schema_version=version, previous_profile=saved)
        _sync_project_collaborators(project, retained)
        self.assertEqual(list(project.collaborating_agencies.values_list("pk", flat=True)), [self.collaborator.pk])
        self.assertEqual(retained["catalog_selections"]["location"][0]["label"], "Manila")
        public = PublicProjectSerializer(project).data
        self.assertEqual(public["location_raw"], "Manila, Taguig")
        self.assertEqual(public["lgus"], ["Manila", "Taguig"])
        self.assertEqual(_filter_public_payload_location([public], "Taguig"), [public])
        self.assertEqual(_filter_public_payload_location([public], "Makati"), [])
        self.assertEqual(location_map_keys(["lgu-manila", "City of Manila", "lgu-taguig"]), ["Manila", "Taguig"])
        with self.assertRaisesRegex(FormSchemaError, "active catalog options"):
            validate_simplified_answers(deepcopy(profile), schema_version=version)
        public_schema = with_catalog_options(schema)
        location_field = next(field for section in public_schema["sections"] for field in section["fields"] if field["key"] == "location")
        self.assertNotIn("lgu-manila", {item["value"] for item in location_field["options"]})

    def test_explicit_legacy_migration_resolves_known_values_only(self):
        schema = prepare_catalog_schema(default_simplified_form_schema())
        profile = {"simplified_form": {"location": ["Manila", "City of Manila", "Taguig"], "developmentSector": "SCEED"}}
        migrated = upgrade_catalog_answers(profile, schema)
        self.assertEqual(migrated["simplified_form"]["location"], ["lgu-manila", "lgu-taguig"])
        self.assertEqual(migrated["simplified_form"]["developmentSector"], "sceed")
        self.assertEqual(profile["simplified_form"]["developmentSector"], "SCEED")
        with self.assertRaisesRegex(ValueError, "catalog review"):
            upgrade_catalog_answers({"simplified_form": {"location": "Unmapped district"}}, schema)

    def test_committee_activation_and_sceeed_links(self):
        self.client.force_authenticate(self.validator)
        self.assertEqual(self.client.get(self.endpoint).status_code, 403)
        regular_admin = User.objects.create_user(username="ordinary-admin", email="ordinary-admin@example.com", role="admin")
        self.client.force_authenticate(regular_admin)
        self.assertEqual(self.client.get(self.endpoint).status_code, 403)
        self.assertEqual(self.client.patch(self.endpoint + "locations/lgu-manila/", {"name": "Replacement"}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["locations"]), 17)
        self.assertEqual(self.client.patch(self.endpoint + "committees/sceed/", {"groups": ["economic"]}, format="json").status_code, 400)
        payload = {"code": "sample", "acronym": "SAMPLE", "name": "Additional committee", "is_active": True}
        self.assertEqual(self.client.post(self.endpoint + "committees/", payload, format="json").status_code, 400)
        response = self.client.post(self.endpoint + "committees/", {**payload, "is_active": False}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.patch(self.endpoint + "committees/sample/", {"is_active": True, "groups": ["social", "environment"]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(project_outcome_context({"developmentSector": "sample"})["groups"], ["environment", "social"])

    def test_catalog_backed_contributor_create_upload_submit_and_review(self):
        form = CMSContributorForm.objects.get(key="simplified-rdip")
        historic = deepcopy(form.current_published_version.schema_json)
        form.draft_schema_json = prepare_catalog_schema(default_simplified_form_schema(), repair=True)
        form.has_unpublished_changes = True
        form.save(update_fields=["draft_schema_json", "has_unpublished_changes"])
        publish_contributor_form(form, self.admin)
        contributor = User.objects.create_user(
            username="catalog-contributor", email="catalog-contributor@example.com", role="staff",
            agency=self.primary.code, agency_record=self.primary,
        )
        now = timezone.now()
        SystemSetting.objects.update_or_create(key="portal_encoding_window", defaults={"value": dumps({
            "enabled": True, "start_at": (now - timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
        })})
        self.client.force_authenticate(contributor)
        payload = self.client.get("/api/contributor-forms/simplified-rdip/current/").data
        active_field = next(field for section in payload["schema"]["sections"] for field in section["fields"] if field["key"] == "location")
        self.assertIn("lgu-manila", {option["value"] for option in active_field["options"]})
        answers = {
            "agencyName": self.primary.code, "collaboratingAgencies": [f"agency:{self.collaborator.pk}"],
            "program": "Regional Health", "projectActivity": "Diagnostic network", "location": ["lgu-manila", "lgu-taguig"],
            "description": "Install accessible diagnostic facilities.", "objective": "Improve referral access.",
            "startYear": "2027", "endYear": "2028", "fundingRequirementByYear": {"2027": 250000000},
            "fundingSource": "Agency", "pipIncluded": "No", "arnipapIncluded": "No", "ludipIncluded": "Not Applicable",
            "ifpsIncluded": "No", "pcbIncluded": "No", "rdcEndorsed": "No", "developmentSector": "scsd",
            "rdpMainChapter": "4.1 Boost Health Health & Nutrition", "status": "New",
        }
        response = self.client.post("/api/employee/projects/", {
            "agency": self.primary.code, "profile_data": {"simplified_form": {**answers, "location": ["lgu-unknown"]}},
        }, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post("/api/employee/projects/", {
            "agency": self.primary.code, "profile_data": {"simplified_form": answers},
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        project = Project.objects.get(pk=response.data["id"])
        document = self.client.post("/api/project-supporting-documents/", {
            "project": project.pk, "field_key": "custom_supporting_documents",
            "file": SimpleUploadedFile("facts.csv", b"measure,amount\nclinics,17\n", content_type="text/csv"),
        }, format="multipart")
        self.assertEqual(document.status_code, 201, document.data)
        submitted = self.client.post(f"/api/employee/projects/{project.pk}/submit/", {}, format="json")
        self.assertEqual(submitted.status_code, 200, submitted.data)
        self.client.force_authenticate(self.validator)
        reviewed = self.client.get(f"/api/validator/projects/{project.pk}/")
        self.assertEqual(reviewed.status_code, 200, reviewed.data)
        self.assertEqual(reviewed.data["profile_data"]["simplified_form"]["location"], answers["location"])
        self.assertEqual(form.versions.order_by("-version_number")[1].schema_json, historic)

    def test_sceeed_uses_only_the_validated_link_without_changing_the_rubric(self):
        snapshot = {"simplified_form": {"developmentSector": "sceed", "location": ["lgu-manila", "lgu-taguig"]}}
        project = Project.objects.create(name="SCEED project", cost=0, latitude=14.6, longitude=121.0)
        for selected, expected_key, excluded_key in (("economic", "industry_services", "climate"), ("environment", "climate", "industry_services")):
            with self.subTest(track=selected), patch("ai_engine.groq_priority.analyze_priority_with_groq", return_value=None) as provider:
                result, _ = analyze_project(project, self.validator, snapshot, {"sceeedTrack": selected}, persist=False)
                self.assertEqual(result["suggested_scores"]["rdp_track"], selected)
                self.assertEqual(result["suggested_scores"]["outcome_context"]["groups"], ["economic", "environment"])
                criteria = {row["key"] for row in provider.call_args.args[3]}
                self.assertIn(expected_key, criteria)
                self.assertNotIn(excluded_key, criteria)

    def test_changed_committee_links_generate_a_new_analysis(self):
        committee = SectoralCommittee.objects.create(code="combined", acronym="COMBINED", name="Combined Committee", is_active=True)
        link = CommitteeOutcomeGroup.objects.create(committee=committee, group="social")
        project = Project.objects.create(name="Outcome routing", cost=0, latitude=14.6, longitude=121.0)
        snapshot = {"simplified_form": {"developmentSector": committee.code}}
        original, _ = analyze_project(project, self.validator, snapshot)
        link.group = "economic"
        link.save(update_fields=["group"])
        current, reused = analyze_project(project, self.validator, snapshot)
        self.assertFalse(reused)
        self.assertNotEqual(original.pk, current.pk)
        self.assertEqual(original.suggested_scores["rdp_track"], "social")
        self.assertEqual(current.suggested_scores["rdp_track"], "economic")
