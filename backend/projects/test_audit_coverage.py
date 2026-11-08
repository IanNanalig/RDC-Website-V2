from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cms.models import CMSContributorForm
from .audit_presentation import EVENT_SPECS
from .models import AuditTrail, PasswordSetupToken, Project, User, UserActivity


class AuditCoverageTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="audit-admin", email="audit-admin@example.com",
            password="StrongTestPassword123!", role="admin", must_change_password=False,
        )
        self.validator = User.objects.create_user(
            username="audit-validator", email="audit-validator@example.com",
            password="StrongTestPassword123!", role="validator", must_change_password=False,
        )
        self.editor = User.objects.create_user(
            username="audit-editor", email="audit-editor@example.com",
            password="StrongTestPassword123!", role="content_editor", must_change_password=False,
            agency="RDC-NCR",
        )
        self.contributor = User.objects.create_user(
            username="audit-contributor", email="audit-contributor@example.com",
            password="StrongTestPassword123!", role="staff", must_change_password=False,
            agency="MMDA",
        )

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def test_declared_events_have_central_human_readable_mappings(self):
        declared = {value for value, _label in UserActivity.EVENT_CHOICES}
        self.assertEqual(declared - {"api_action", "api_action_failed"} - set(EVENT_SPECS), set())
        emitted_outside_choices = {
            "project_unarchive", "profile_updated", "profile_edit_requested",
            "profile_edit_approved", "profile_edit_rejected", "chat_knowledge_approved",
            "chat_knowledge_rejected", "chat_content_updated",
        }
        self.assertEqual(emitted_outside_choices - set(EVENT_SPECS), set())

    def test_activity_list_uses_readable_projection_without_technical_details(self):
        original_details = {
            "action": "agency_created", "agency_code": "TEST-AGENCY",
            "password": "do-not-return", "nested": {"token_digest": "do-not-return"},
        }
        activity = UserActivity.objects.create(
            user=self.admin, role="admin", event="api_action", ip_address="127.0.0.1",
            details=original_details,
        )
        self.as_user(self.admin)
        response = self.client.get("/api/admin/activity/?include_meta=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        row = next(item for item in response.data["results"] if item["id"] == activity.id)
        self.assertEqual(row["category"], "agencies")
        self.assertEqual(row["category_label"], "Agencies")
        self.assertEqual(row["action_label"], "Created an agency")
        self.assertEqual(row["result"], "completed")
        self.assertEqual(row["target_label"], "TEST-AGENCY")
        self.assertIn("audit-admin", row["description"])
        self.assertNotIn("details", row)
        self.assertNotIn("ip_address", row)
        activity.refresh_from_db()
        self.assertEqual(activity.details, original_details)

    def test_readable_category_result_and_activity_search_filters(self):
        agency = UserActivity.objects.create(
            user=self.admin, role="admin", event="api_action",
            details={"action": "agency_created", "agency_code": "SEARCH-AGENCY"},
        )
        failed = UserActivity.objects.create(
            actor_username="Unauthenticated", actor_full_name="Unauthenticated", role="unauthenticated",
            event="login_failed", details={"attempted_email": "failed@example.test"},
        )
        blocked = UserActivity.objects.create(
            user=self.admin, role="admin", event="api_action_failed",
            details={"route": "admin-users-set-active", "status_code": 403},
        )
        unknown_generic = UserActivity.objects.create(
            user=self.admin, role="admin", event="api_action",
            details={"route": "future-admin-route", "status_code": 200},
        )
        project = UserActivity.objects.create(
            user=self.admin, role="admin", event="project_update",
            project_title_snapshot="Readable Search Project",
        )
        self.as_user(self.admin)

        by_category = self.client.get("/api/admin/activity/?category=agencies&include_meta=1")
        self.assertEqual([item["id"] for item in by_category.data["results"]], [agency.id])
        by_result = self.client.get("/api/admin/activity/?result=failed&include_meta=1")
        failed_row = next(item for item in by_result.data["results"] if item["id"] == failed.id)
        self.assertEqual(failed_row["display_name"], "Unauthenticated user")
        self.assertIn(failed.id, [item["id"] for item in by_result.data["results"]])
        self.assertNotIn(blocked.id, [item["id"] for item in by_result.data["results"]])
        blocked_result = self.client.get("/api/admin/activity/?result=blocked&include_meta=1")
        self.assertIn(blocked.id, [item["id"] for item in blocked_result.data["results"]])
        self.assertEqual(
            next(item for item in blocked_result.data["results"] if item["id"] == blocked.id)["result"],
            "blocked",
        )
        administration = self.client.get(
            "/api/admin/activity/?category=administration_security&result=completed&include_meta=1"
        )
        self.assertIn(unknown_generic.id, [item["id"] for item in administration.data["results"]])
        by_action = self.client.get("/api/admin/activity/?search=created%20an%20agency&include_meta=1")
        self.assertEqual([item["id"] for item in by_action.data["results"]], [agency.id])
        by_target = self.client.get("/api/admin/activity/?search=Readable%20Search%20Project&include_meta=1")
        self.assertEqual([item["id"] for item in by_target.data["results"]], [project.id])

    def test_generic_fallback_uses_actor_role_and_never_shows_one_character_action(self):
        from .audit_presentation import presentation_for

        editor = UserActivity.objects.create(
            role="content_editor", event="api_action", details={"route": "unknown-route", "target_label": "Homepage"},
        )
        contributor = UserActivity.objects.create(role="staff", event="api_action", details={"action": "x"})
        editor_label = presentation_for(editor)
        contributor_label = presentation_for(contributor)
        self.assertEqual(editor_label["category"], "website_content")
        self.assertEqual(editor_label["target_label"], "Homepage")
        self.assertNotEqual(contributor_label["action_label"], "x")
        self.assertEqual(contributor_label["category"], "projects")

    def test_activity_detail_is_admin_only_and_recursively_sanitized(self):
        activity = UserActivity.objects.create(
            user=self.admin, role="admin", event="project_update", project_title_snapshot="Safe Project",
            ip_address="127.0.0.1", location_hint="Test location",
            details={
                "method": "PATCH", "route": "admin-projects-detail", "status_code": 200,
                "password": "do-not-return", "nested": {"access_token": "do-not-return"},
                "changes": [
                    {"field": "title", "before": "Old", "after": "New"},
                    {"field": "password", "before": "old-secret", "after": "new-secret"},
                ],
            },
        )
        self.as_user(self.contributor)
        self.assertEqual(self.client.get(f"/api/admin/activity/{activity.id}/").status_code, 403)

        self.as_user(self.admin)
        response = self.client.get(f"/api/admin/activity/{activity.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertNotIn("details", response.data)
        self.assertNotIn("ip_address", response.data)
        self.assertNotIn("technical_details", response.data)
        self.assertNotIn("event", response.data)
        self.assertEqual(response.data["changes"], [{"field": "Project title", "before": "Old", "after": "New"}])
        response = self.client.get(f"/api/admin/activity/{activity.id}/?include_technical=1")
        self.assertEqual(response.data["ip_address"], "127.0.0.1")
        technical = response.data["technical_details"]
        self.assertEqual(technical["password"], "[redacted]")
        self.assertEqual(technical["nested"]["access_token"], "[redacted]")
        self.assertEqual(technical["changes"][0]["after"], "New")
        self.assertEqual(technical["changes"][1]["before"], "[redacted]")
        self.assertNotIn("old-secret", str(response.data))
        self.assertNotIn("new-secret", str(response.data))

    def test_routine_session_activity_is_hidden_by_default_without_changing_history(self):
        routine = UserActivity.objects.create(user=self.admin, role="admin", event="api_action", details={"route": "auth-activity", "status_code": 200})
        failed = UserActivity.objects.create(user=self.admin, role="admin", event="api_action_failed", details={"route": "auth-activity", "status_code": 403})
        login = UserActivity.objects.create(user=self.admin, role="admin", event="login")
        logout = UserActivity.objects.create(user=self.admin, role="admin", event="logout")
        self.as_user(self.admin)
        default = self.client.get("/api/admin/activity/?include_meta=1")
        ids = {row["id"] for row in default.data["results"]}
        self.assertNotIn(routine.id, ids)
        self.assertIn(failed.id, ids)
        for activity in (login, logout):
            self.assertEqual(self.client.get(f"/api/admin/activity/{activity.id}/").data["target_label"], "")
        included = self.client.get("/api/admin/activity/?include_meta=1&include_routine=1")
        self.assertIn(routine.id, {row["id"] for row in included.data["results"]})
        self.assertEqual(included.data["count"], default.data["count"] + 1)
        self.assertTrue(UserActivity.objects.filter(pk=routine.id).exists())

    def test_fallback_covers_all_four_roles_without_body_or_passive_gets(self):
        for user in (self.admin, self.validator, self.editor, self.contributor):
            self.as_user(user)
            before = UserActivity.objects.filter(user=user).count()
            self.assertEqual(self.client.get("/api/notifications/unread-count/").status_code, 200)
            self.assertEqual(UserActivity.objects.filter(user=user).count(), before)
            response = self.client.post("/api/notifications/mark-all-read/", {"secret": "do-not-copy"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            activity = UserActivity.objects.get(user=user, event="api_action")
            self.assertEqual(activity.role, user.role)
            self.assertEqual(activity.details["method"], "POST")
            self.assertEqual(activity.details["status_code"], 200)
            self.assertNotIn("secret", str(activity.details))

    def test_failed_action_is_audited_without_request_body(self):
        self.as_user(self.admin)
        response = self.client.post(
            f"/api/admin/users/{self.admin.id}/set_active/?token=do-not-copy",
            {"active": False, "password": "do-not-copy"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        activity = UserActivity.objects.get(user=self.admin, event="api_action_failed")
        self.assertEqual(activity.details["status_code"], 400)
        self.assertEqual(activity.details["route_parameters"].get("pk"), str(self.admin.id))
        self.assertNotIn("password", str(activity.details))
        self.assertNotIn("token", str(activity.details))

    def test_account_changes_and_deleted_actor_history_remain_visible(self):
        self.as_user(self.admin)
        edited = self.client.patch(
            f"/api/admin/users/{self.contributor.id}/",
            {"role": "validator", "password": "NewStrongPassword123_"}, format="json",
        )
        self.assertEqual(edited.status_code, 403)
        edited = self.client.patch(
            f"/api/admin/users/{self.contributor.id}/", {"role": "validator"}, format="json",
        )
        self.assertEqual(edited.status_code, 200)
        edit_activity = UserActivity.objects.get(user=self.admin, event="user_update")
        self.assertFalse(edit_activity.details["password_changed"])
        self.assertNotIn("NewStrongPassword123_", str(edit_activity.details))
        status_response = self.client.post(
            f"/api/admin/users/{self.contributor.id}/set_active/", {"active": False}, format="json"
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(
            user=self.admin, event="user_status_changed", details__target_user_id=self.contributor.id
        ).exists())

        prior = UserActivity.objects.create(
            user=self.contributor, role="staff", event="project_submit", details={"source": "test"}
        )
        contributor_id = self.contributor.id
        deleted = self.client.delete(f"/api/admin/users/{contributor_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        prior.refresh_from_db()
        self.assertIsNone(prior.user_id)
        self.assertEqual(prior.actor_username, "audit-contributor")
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="user_delete").exists())
        audit_list = self.client.get("/api/admin/activity/?user=audit-contributor&include_meta=1")
        self.assertEqual(audit_list.status_code, 200)
        self.assertTrue(any(row["id"] == prior.id and row["username"] == "audit-contributor"
                            for row in audit_list.data["results"]))

    def test_project_delete_retains_snapshot_and_project_saves_use_actual_actor(self):
        project = Project.objects.create(
            name="Audit Project", implementing_agency="MMDA", municipality="NCR",
            status="planning", cost=1000, latitude=14.5, agency="MMDA", budget=1000,
            created_by=self.contributor,
        )
        self.as_user(self.admin)
        updated = self.client.patch(
            f"/api/admin/projects/{project.id}/", {"title": "Audit Project Updated"}, format="json"
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(AuditTrail.objects.filter(project=project).latest("timestamp").actor_id, self.admin.id)
        self.assertTrue(UserActivity.objects.filter(user=self.admin, project=project, event="project_update").exists())

        deleted = self.client.delete(f"/api/admin/projects/{project.id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        activity = UserActivity.objects.get(user=self.admin, event="project_delete")
        self.assertIsNone(activity.project_id)
        self.assertEqual(activity.project_id_snapshot, project.id)
        self.assertEqual(activity.project_title_snapshot, "Audit Project Updated")
        audit_list = self.client.get("/api/admin/activity/?event=project_delete")
        self.assertEqual(audit_list.data[0]["project_title"], "Audit Project Updated")

    def test_admin_activity_sorting_orders_filtered_records_before_pagination(self):
        now = timezone.now()
        targets = ["Zulu target", "Alpha target", "Beta target"]
        rows = [
            UserActivity.objects.create(
                user=self.admin,
                actor_username=self.admin.username,
                actor_full_name=self.admin.get_full_name(),
                role="admin",
                event="project_update",
                project_title_snapshot=target,
                created_at=now + timedelta(seconds=index),
            )
            for index, target in enumerate(targets)
        ]
        self.as_user(self.admin)

        first_page = self.client.get(
            "/api/admin/activity/?event=project_update&sort_by=target&sort_direction=asc&limit=1&offset=0&include_meta=1"
        )
        second_page = self.client.get(
            "/api/admin/activity/?event=project_update&sort_by=target&sort_direction=asc&limit=1&offset=1&include_meta=1"
        )
        self.assertEqual(first_page.status_code, status.HTTP_200_OK, first_page.data)
        self.assertEqual(second_page.status_code, status.HTTP_200_OK, second_page.data)
        self.assertEqual(first_page.data["results"][0]["target_label"], "Alpha target")
        self.assertEqual(second_page.data["results"][0]["target_label"], "Beta target")
        self.assertEqual(first_page.data["count"], len(rows))

        descending = self.client.get(
            "/api/admin/activity/?event=project_update&sort_by=target&sort_direction=desc&limit=1&include_meta=1"
        )
        self.assertEqual(descending.status_code, status.HTTP_200_OK, descending.data)
        self.assertEqual(descending.data["results"][0]["target_label"], "Zulu target")

    def test_form_lock_actions_follow_cms_roles_and_are_audited(self):
        form = CMSContributorForm.objects.get(key="simplified-rdip")

        # Ordinary contributors cannot enter the CMS editing workflow.
        self.as_user(self.contributor)
        for action in ("lock", "heartbeat", "unlock"):
            with self.subTest(role="contributor", action=action):
                denied = self.client.post(
                    f"/api/admin/cms/forms/{form.id}/{action}/", {}, format="json"
                )
                self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        # Contributor Form configuration is Administrator-only.
        self.as_user(self.editor)
        editor_lock = self.client.post(f"/api/admin/cms/forms/{form.id}/lock/", {}, format="json")
        self.assertEqual(editor_lock.status_code, status.HTTP_403_FORBIDDEN)

        self.as_user(self.admin)
        admin_lock = self.client.post(f"/api/admin/cms/forms/{form.id}/lock/", {}, format="json")
        self.assertEqual(admin_lock.status_code, status.HTTP_200_OK)
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="cms_form_lock_acquired").exists())
        self.assertEqual(
            self.client.post(f"/api/admin/cms/forms/{form.id}/heartbeat/", {}, format="json").status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(f"/api/admin/cms/forms/{form.id}/unlock/", {}, format="json").status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="cms_form_lock_released").exists())

        self.as_user(self.admin)
        locked = self.client.post(f"/api/admin/cms/forms/{form.id}/lock/", {}, format="json")
        self.assertEqual(locked.status_code, status.HTTP_200_OK)
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="cms_form_lock_acquired").exists())

        other_admin = User.objects.create_user(
            username="second-audit-admin", email="second-audit-admin@example.com",
            password="StrongTestPassword123!", role="admin", must_change_password=False,
        )
        self.as_user(other_admin)
        blocked = self.client.post(f"/api/admin/cms/forms/{form.id}/lock/", {}, format="json")
        self.assertEqual(blocked.status_code, 423)
        self.assertTrue(UserActivity.objects.filter(user=other_admin, event="cms_form_lock_blocked").exists())
        access = self.client.post(f"/api/admin/cms/forms/{form.id}/request-access/", {}, format="json")
        self.assertEqual(access.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(user=other_admin, event="cms_form_access_requested").exists())

        self.as_user(self.admin)
        heartbeat = self.client.post(f"/api/admin/cms/forms/{form.id}/heartbeat/", {}, format="json")
        self.assertEqual(heartbeat.status_code, 200)
        unlocked = self.client.post(f"/api/admin/cms/forms/{form.id}/unlock/", {}, format="json")
        self.assertEqual(unlocked.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(user=self.admin, event="cms_form_lock_released").exists())

    @override_settings(TURNSTILE_REQUIRED=False)
    def test_anonymous_password_reset_attempt_is_not_attributed_to_target_user(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/auth/password-reset/request/", {"email": self.contributor.email}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        activity = UserActivity.objects.get(event="auth_reset_request")
        self.assertIsNone(activity.user_id)
        self.assertEqual(activity.role, "unauthenticated")
        self.assertEqual(activity.details["target_user_id"], self.contributor.id)
        self.assertNotIn(self.contributor.email, str(activity.details))
        self.as_user(self.admin)
        audit_list = self.client.get("/api/admin/activity/?event=auth_reset_request")
        self.assertEqual(audit_list.status_code, 200)
        self.assertEqual(audit_list.data[0]["id"], activity.id)

    def test_login_attempt_password_setup_and_logout_are_audited(self):
        self.client.force_authenticate(user=None)
        failed = self.client.post(
            "/api/auth/login/", {"email": self.contributor.email, "password": "incorrect"}, format="json"
        )
        self.assertEqual(failed.status_code, 401)
        failure = UserActivity.objects.get(event="login_failed")
        self.assertIsNone(failure.user_id)
        self.assertNotIn("incorrect", str(failure.details))

        login = self.client.post(
            "/api/auth/login/",
            {"email": self.contributor.email, "password": "StrongTestPassword123!"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(UserActivity.objects.filter(user=self.contributor, event="login").exists())

        self.as_user(self.validator)
        old_version = self.validator.session_version
        logout = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(logout.status_code, 200)
        self.validator.refresh_from_db()
        self.assertGreater(self.validator.session_version, old_version)
        self.assertTrue(UserActivity.objects.filter(user=self.validator, event="logout").exists())

        token = PasswordSetupToken.objects.create(
            user=self.editor, token="audit-test-setup-token",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.client.force_authenticate(user=None)
        setup = self.client.post(
            "/api/auth/setup-password/",
            {
                "token": token.token, "new_password": "NewStrongPassword123_",
                "first_name": "Audit", "last_name": "Editor", "agency": "RDC-NCR",
                "office": "Office", "division": "Division", "position": "Editor",
                "contact_number": "0212345678", "phone_number": "09170000000",
            },
            format="json",
        )
        self.assertEqual(setup.status_code, 200, setup.data)
        self.assertTrue(UserActivity.objects.filter(user=self.editor, event="auth_password_setup").exists())
