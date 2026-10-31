import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ai_engine.models import AIModelVersion
from cms.models import CMSMediaAsset, CMSPage
from projects.management.commands.beta_cleanup import _validate_backup, build_cleanup_manifest
from projects.models import Agency, Project, ProjectConcernEvidence, ProjectConcernReport, User


class BetaCleanupCommandTests(TestCase):
    def setUp(self):
        self.rdc, _ = Agency.objects.get_or_create(code="RDC-NCR", defaults={"name": "RDC-NCR"})
        self.denr, _ = Agency.objects.get_or_create(code="DENR", defaults={"name": "DENR"})
        self.preserved = User.objects.create_user(
            id=3,
            username="ian095108",
            email="ian095108@gmail.com",
            password="PreservedPassword123!",
            role="admin",
            agency=self.rdc.code,
            agency_record=self.rdc,
            is_staff=True,
        )
        self.other = User.objects.create_user(
            username="test-contributor",
            email="test-contributor@example.test",
            password="StrongPassword123!",
            role="staff",
            agency=self.denr.code,
            agency_record=self.denr,
        )
        self.project = Project.objects.create(
            name="Test project",
            implementing_agency=self.denr.code,
            municipality="Manila",
            status="proposed",
            cost=100,
            latitude=14.5,
            longitude=121.0,
            agency=self.denr.code,
            primary_agency=self.denr,
            created_by=self.other,
        )
        concern = ProjectConcernReport.objects.create(
            reference_code="PCR-TEST-CLEANUP",
            project=self.project,
            project_id_snapshot=self.project.pk,
            project_title_snapshot=self.project.name,
            project_agency_snapshot=self.denr.code,
            reporting_mode="anonymous",
            category_code="other",
            category_label_snapshot="Other",
            description="Test concern",
            abuse_fingerprint="a" * 64,
        )
        ProjectConcernEvidence.objects.create(
            report=concern,
            original_filename="evidence.pdf",
            storage_name="evidence-test.pdf",
            content_type="application/pdf",
            extension=".pdf",
            size_bytes=4,
            checksum_sha256="c" * 64,
            content=b"test",
        )
        AIModelVersion.objects.create(
            version="test-beta-model",
            feature_schema_version="test",
            dataset_version="b" * 64,
            sample_count=0,
        )
        self.page = CMSPage.objects.create(
            title="Preserved page",
            slug="preserved-page",
            created_by=self.other,
        )
        self.media = CMSMediaAsset.objects.create(
            file="cms/preserved-test.png",
            file_type="image",
            uploaded_by=self.other,
        )

    def test_preview_reports_targets_without_mutating(self):
        password_hash = self.preserved.password
        output = StringIO()
        call_command("beta_cleanup", stdout=output)
        self.assertIn("DRY RUN ONLY", output.getvalue())
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        self.preserved.refresh_from_db()
        self.assertEqual(self.preserved.password, password_hash)

    def test_manifest_fails_closed_when_preserved_account_is_not_exact(self):
        self.preserved.is_active = False
        self.preserved.account_state = User.ACCOUNT_DISABLED
        self.preserved.save(update_fields=["is_active", "account_state"])
        manifest = build_cleanup_manifest()
        self.assertTrue(manifest["blockers"])

    def test_execute_requires_matching_review_and_verified_backup_then_preserves_cms_and_admin(self):
        password_hash = self.preserved.password
        agency_count = Agency.objects.count()
        with TemporaryDirectory() as folder:
            root = Path(folder)
            manifest_path = root / "cleanup-preview.json"
            manifest = build_cleanup_manifest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            dump_path = root / "beta.dump"
            dump_path.write_bytes(b"verified-test-dump")
            backup = {
                "database": manifest["database"],
                "dump_path": str(dump_path),
                "dump_sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
                "pg_restore_list_verified": True,
                "restore_test_verified": True,
                "supabase_snapshot_verified": True,
                "backup_folder_acl_verified": True,
                "pg_dump_major_version": 17,
                "restore_postgres_major_version": 17,
                "dump_connection_mode": "direct",
                "dump_connection_port": 5432,
            }
            backup_path = root / "backup.json"
            backup_path.write_text(json.dumps(backup), encoding="utf-8")

            with self.assertRaisesMessage(CommandError, "--backup-manifest"):
                call_command(
                    "beta_cleanup",
                    execute=True,
                    manifest=str(manifest_path),
                    confirm_plan=manifest["review_fingerprint"],
                    confirm_preserved_user_id=3,
                    allow_non_postgres=True,
                    stdout=StringIO(),
                )

            with self.assertRaises(CommandError):
                call_command(
                    "beta_cleanup",
                    execute=True,
                    manifest=str(manifest_path),
                    backup_manifest=str(backup_path),
                    confirm_plan="wrong",
                    confirm_preserved_user_id=3,
                    allow_non_postgres=True,
                    stdout=StringIO(),
                )

            call_command(
                "beta_cleanup",
                execute=True,
                manifest=str(manifest_path),
                backup_manifest=str(backup_path),
                confirm_plan=manifest["review_fingerprint"],
                confirm_preserved_user_id=3,
                allow_non_postgres=True,
                stdout=StringIO(),
            )
            self.assertTrue((root / "cleanup-preview.result.json").exists())

        self.assertEqual(User.objects.count(), 1)
        self.preserved.refresh_from_db()
        self.assertEqual(self.preserved.pk, 3)
        self.assertEqual(self.preserved.password, password_hash)
        self.assertEqual(self.preserved.role, "admin")
        self.assertTrue(self.preserved.is_active)
        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(ProjectConcernReport.objects.count(), 0)
        self.assertEqual(ProjectConcernEvidence.objects.count(), 0)
        self.assertEqual(AIModelVersion.objects.count(), 0)
        self.assertEqual(Agency.objects.count(), agency_count)
        self.page.refresh_from_db()
        self.media.refresh_from_db()
        self.assertIsNone(self.page.created_by_id)
        self.assertIsNone(self.media.uploaded_by_id)

    def test_snapshot_waiver_must_be_recorded_and_explicitly_allowed(self):
        with TemporaryDirectory() as folder:
            dump_path = Path(folder) / "beta.dump"
            dump_path.write_bytes(b"verified-test-dump")
            manifest = build_cleanup_manifest()
            backup = {
                "database": manifest["database"],
                "dump_path": str(dump_path),
                "dump_sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
                "pg_restore_list_verified": True,
                "restore_test_verified": True,
                "supabase_snapshot_verified": False,
                "supabase_snapshot_waived": True,
                "backup_folder_acl_verified": True,
                "pg_dump_major_version": 17,
                "restore_postgres_major_version": 17,
                "dump_connection_mode": "session",
                "dump_connection_port": 5432,
            }

            with self.assertRaisesMessage(CommandError, "snapshot waiver"):
                _validate_backup(backup, manifest["database"])

            _validate_backup(
                backup,
                manifest["database"],
                allow_missing_supabase_snapshot=True,
            )

    def test_execution_aborts_without_deleting_when_database_changed_after_preview(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            manifest_path = root / "cleanup-preview.json"
            manifest = build_cleanup_manifest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            dump_path = root / "beta.dump"
            dump_path.write_bytes(b"verified-test-dump")
            backup_path = root / "backup.json"
            backup_path.write_text(
                json.dumps({
                    "database": manifest["database"],
                    "dump_path": str(dump_path),
                    "dump_sha256": hashlib.sha256(dump_path.read_bytes()).hexdigest(),
                    "pg_restore_list_verified": True,
                    "restore_test_verified": True,
                    "supabase_snapshot_verified": True,
                    "backup_folder_acl_verified": True,
                    "pg_dump_major_version": 17,
                    "restore_postgres_major_version": 17,
                    "dump_connection_mode": "direct",
                    "dump_connection_port": 5432,
                }),
                encoding="utf-8",
            )
            User.objects.create_user(
                username="changed-after-review",
                email="changed-after-review@example.test",
                password="StrongPassword123!",
                role="staff",
                agency="DENR",
                agency_record=self.denr,
            )
            with self.assertRaisesMessage(CommandError, "database changed"):
                call_command(
                    "beta_cleanup",
                    execute=True,
                    manifest=str(manifest_path),
                    backup_manifest=str(backup_path),
                    confirm_plan=manifest["review_fingerprint"],
                    confirm_preserved_user_id=3,
                    allow_non_postgres=True,
                    stdout=StringIO(),
                )
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        self.assertGreater(User.objects.count(), 1)
