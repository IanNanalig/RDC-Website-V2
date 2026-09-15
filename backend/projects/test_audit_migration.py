from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AuditSnapshotMigrationTests(TransactionTestCase):
    migrate_from = ("projects", "0029_useractivity_cms_event_unarchived")
    migrate_to = ("projects", "0030_useractivity_actor_full_name_and_more")

    def test_existing_activity_backfills_actor_and_project_before_nullable_fk(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        OldUser = old_apps.get_model("projects", "User")
        OldProject = old_apps.get_model("projects", "Project")
        OldActivity = old_apps.get_model("projects", "UserActivity")
        actor = OldUser.objects.create(
            username="historical-contributor", full_name="Historical Contributor",
            email="historical-contributor@example.com", role="staff",
        )
        project = OldProject.objects.create(
            name="Historical Project", implementing_agency="MMDA", municipality="NCR",
            status="planning", cost=1000, latitude=14.5, created_by=actor,
        )
        activity = OldActivity.objects.create(
            user=actor, role="staff", event="project_submit", project=project,
        )

        executor = MigrationExecutor(connection)
        try:
            executor.migrate([self.migrate_to])
            new_apps = executor.loader.project_state([self.migrate_to]).apps
            NewActivity = new_apps.get_model("projects", "UserActivity")
            migrated = NewActivity.objects.get(pk=activity.pk)
            self.assertEqual(migrated.actor_username, "historical-contributor")
            self.assertEqual(migrated.actor_full_name, "Historical Contributor")
            self.assertEqual(migrated.project_id_snapshot, project.pk)
            self.assertEqual(migrated.project_title_snapshot, "Historical Project")
        finally:
            MigrationExecutor(connection).migrate([self.migrate_to])
