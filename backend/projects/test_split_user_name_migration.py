from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SplitUserNameMigrationTests(TransactionTestCase):
    migrate_from = ("projects", "0038_regional_priority_policy")
    migrate_to = ("projects", "0039_split_user_full_name")

    def test_splits_legacy_names_and_aborts_without_truncating_oversized_parts(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        OldUser = old_apps.get_model("projects", "User")
        OldUser.objects.create(username="legacy-blank", role="staff", full_name="   ")
        OldUser.objects.create(username="legacy-single", role="staff", full_name="Cher")
        OldUser.objects.create(username="legacy-many", role="staff", full_name="  Ana María van Dyke  ")
        oversized = OldUser.objects.create(username="legacy-long", role="staff", full_name="x" * 151)

        try:
            with self.assertRaisesRegex(RuntimeError, "exceeds 150 characters"):
                MigrationExecutor(connection).migrate([self.migrate_to])

            OldUser.objects.filter(pk=oversized.pk).update(full_name="Fixed Legacy Name")
            MigrationExecutor(connection).migrate([self.migrate_to])
            new_apps = MigrationExecutor(connection).loader.project_state([self.migrate_to]).apps
            NewUser = new_apps.get_model("projects", "User")
            blank_name = NewUser.objects.get(username="legacy-blank")
            self.assertEqual((blank_name.first_name, blank_name.last_name), ("", ""))
            self.assertEqual(
                (NewUser.objects.get(username="legacy-single").first_name, NewUser.objects.get(username="legacy-single").last_name),
                ("Cher", ""),
            )
            migrated = NewUser.objects.get(username="legacy-many")
            self.assertEqual((migrated.first_name, migrated.last_name), ("Ana", "María van Dyke"))
        finally:
            MigrationExecutor(connection).migrate([self.migrate_to])
