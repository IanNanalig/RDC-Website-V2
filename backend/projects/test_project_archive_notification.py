from rest_framework.test import APITestCase

from projects.models import Notification, Project, User


class ProjectArchiveNotificationTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="archive-notice-admin", email="archive-notice-admin@example.com",
            password="StrongTestPassword123!", role="admin", is_staff=True,
        )
        self.contributor = User.objects.create_user(
            username="archive-notice-contributor", email="archive-notice-contributor@example.com",
            password="StrongTestPassword123!", role="staff", agency="DENR",
        )
        self.project = Project.objects.create(
            name="DENR Watershed Project",
            implementing_agency="DENR",
            municipality="NCR",
            status="completed",
            validated=True,
            cost=200000,
            description="Watershed restoration",
            latitude=14.5,
            agency="DENR",
            budget=200000,
            created_by=self.contributor,
        )

    def test_archiving_notifies_project_contributor_and_links_to_project_list(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            f"/api/admin/projects/{self.project.pk}/archive/",
            {"confirm_archive": True, "expected_implementation_status": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        notification = Notification.objects.get(
            recipient=self.contributor,
            project=self.project,
            event_type="project_archived",
        )
        self.assertEqual(notification.title, "Project archived")
        self.assertIn(self.project.name, notification.message)
        self.assertIn("no longer shown in your active projects list", notification.message)
        self.assertEqual(notification.link_path, "/employee/projects")

        self.client.force_authenticate(self.contributor)
        inbox = self.client.get("/api/notifications/")
        self.assertEqual(inbox.status_code, 200, inbox.data)
        self.assertIn(notification.pk, {row["id"] for row in inbox.data})
