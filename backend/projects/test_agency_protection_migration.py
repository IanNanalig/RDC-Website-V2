from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ProtectedAgencyMigrationTests(TransactionTestCase):
    migrate_from = ("projects", "0048_account_capacity")
    migrate_to = ("projects", "0049_protected_system_agency")

    def test_existing_rdc_row_receives_stable_identity_without_recreation(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        OldAgency = old_apps.get_model("projects", "Agency")
        original = OldAgency.objects.get(code="RDC-NCR")
        original_id = original.pk

        try:
            executor = MigrationExecutor(connection)
            executor.migrate([self.migrate_to])
            new_apps = executor.loader.project_state([self.migrate_to]).apps
            NewAgency = new_apps.get_model("projects", "Agency")
            protected = NewAgency.objects.get(system_key="rdc-ncr-primary")
            self.assertEqual(protected.pk, original_id)
            self.assertEqual(protected.code, "RDC-NCR")
            self.assertTrue(protected.is_active)
        finally:
            MigrationExecutor(connection).migrate([self.migrate_to])
