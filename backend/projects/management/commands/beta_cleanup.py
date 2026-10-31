"""Preview and, only with reviewed safeguards, execute the beta data cleanup."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction


PRESERVED_EMAIL = "ian095108@gmail.com"
PRESERVED_USER_ID = 3


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return _sha256_bytes(payload.encode("utf-8"))


def _connection_fingerprint(connection):
    config = connection.settings_dict
    identity = "|".join(
        str(config.get(key) or "") for key in ("ENGINE", "HOST", "PORT", "NAME")
    )
    return {
        "vendor": connection.vendor,
        "identity_sha256": _sha256_bytes(identity.encode("utf-8")),
        "postgres_server_version": getattr(connection, "pg_version", None),
    }


def _authentication_digest(user):
    fields = {
        "id": user.pk,
        "username": user.username,
        "email": (user.email or "").casefold(),
        "password": user.password,
        "role": user.role,
        "account_state": user.account_state,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "group_ids": list(user.groups.order_by("pk").values_list("pk", flat=True)),
        "permission_ids": list(
            user.user_permissions.order_by("pk").values_list("pk", flat=True)
        ),
    }
    return _json_fingerprint(fields)


def _preserved_row_digest(user):
    """Fingerprint every concrete User column without exposing its values."""
    values = {
        field.attname: field.value_from_object(user)
        for field in user._meta.concrete_fields
    }
    return _json_fingerprint(values)


def _model_counts(app_label, using):
    return {
        model.__name__: model.objects.using(using).count()
        for model in apps.get_app_config(app_label).get_models()
    }


def build_cleanup_manifest(alias="default"):
    from ai_engine.models import (
        AIModelTrainingRecord,
        AIModelVersion,
        AIProjectAnalysis,
        AISimilarProject,
        AITrainingRecord,
    )
    from cms.models import CMSContributorForm, CMSMediaAsset, CMSPageSection
    from cms.services.media_usage import get_media_usage_map
    from projects.models import (
        AccessRequest,
        Agency,
        AuditTrail,
        EditRequest,
        Notification,
        PasswordResetChallenge,
        PasswordResetRequest,
        PasswordSetupToken,
        PortalSession,
        ProfileEditRequest,
        Project,
        ProjectCollaboratingAgency,
        ProjectComment,
        ProjectConcernEvidence,
        ProjectConcernReport,
        ProjectDocumentAssessment,
        ProjectPriorityAnalysis,
        ProjectPriorityConfirmation,
        ProjectRevision,
        ProjectSupportingDocument,
        SystemSetting,
        User,
        UserActivity,
        UserInvitation,
        PriorityRuleSet,
    )

    connection = connections[alias]
    matches = list(
        User.objects.using(alias)
        .filter(email__iexact=PRESERVED_EMAIL)
    )
    blockers = []
    preserved_user = matches[0] if len(matches) == 1 else None
    if len(matches) != 1:
        blockers.append("The preserved email must match exactly one existing user.")
    elif preserved_user.pk != PRESERVED_USER_ID:
        blockers.append(f"The preserved account must retain primary key {PRESERVED_USER_ID}.")
    elif (
        preserved_user.role != "admin"
        or not preserved_user.is_active
        or preserved_user.account_state != User.ACCOUNT_ACTIVE
    ):
        blockers.append("The preserved account must be an active Administrator.")
    elif preserved_user.created_by_id not in {None, PRESERVED_USER_ID}:
        blockers.append(
            "The preserved account references a creator scheduled for deletion, so its full row cannot remain unchanged."
        )

    targets = {
        "user_ids": list(
            User.objects.using(alias).exclude(pk=PRESERVED_USER_ID).order_by("pk").values_list("pk", flat=True)
        ),
        "project_ids": list(Project.objects.using(alias).order_by("pk").values_list("pk", flat=True)),
        "concern_report_ids": list(
            ProjectConcernReport.objects.using(alias).order_by("pk").values_list("pk", flat=True)
        ),
        "ai_model_version_ids": list(
            AIModelVersion.objects.using(alias).order_by("pk").values_list("pk", flat=True)
        ),
    }
    target_models = (
        AccessRequest,
        AuditTrail,
        EditRequest,
        Notification,
        PasswordResetChallenge,
        PasswordResetRequest,
        PasswordSetupToken,
        PortalSession,
        ProfileEditRequest,
        Project,
        ProjectCollaboratingAgency,
        ProjectComment,
        ProjectConcernEvidence,
        ProjectConcernReport,
        ProjectDocumentAssessment,
        ProjectPriorityAnalysis,
        ProjectPriorityConfirmation,
        ProjectRevision,
        ProjectSupportingDocument,
        UserActivity,
        UserInvitation,
        AIModelTrainingRecord,
        AIModelVersion,
        AIProjectAnalysis,
        AISimilarProject,
        AITrainingRecord,
    )
    target_counts = {model.__name__: model.objects.using(alias).count() for model in target_models}
    target_counts["UsersToDelete"] = len(targets["user_ids"])
    target_counts["DjangoSessions"] = Session.objects.using(alias).count()
    target_counts["DjangoAdminLogEntries"] = LogEntry.objects.using(alias).count()
    target_counts["CMSPageSectionLocksToClear"] = CMSPageSection.objects.using(alias).filter(
        lock_owner__isnull=False
    ).count()
    target_counts["CMSContributorFormLocksToClear"] = CMSContributorForm.objects.using(alias).filter(
        lock_owner__isnull=False
    ).count()

    assets = list(CMSMediaAsset.objects.using(alias).all())
    usage = get_media_usage_map(assets)
    unreferenced_media = [
        {
            "id": asset.pk,
            "file_name": asset.file.name,
            "original_filename": asset.original_filename,
            "file_type": asset.file_type,
        }
        for asset in assets
        if not usage.get(asset.pk)
    ]
    preserved_counts = {
        "users": 1 if preserved_user else 0,
        "agencies": Agency.objects.using(alias).count(),
        "priority_rule_sets": PriorityRuleSet.objects.using(alias).count(),
        "system_settings": SystemSetting.objects.using(alias).count(),
        "auth_permissions": Permission.objects.using(alias).count(),
        "cms": _model_counts("cms", alias),
        "cms_media_referenced": sum(1 for asset in assets if usage.get(asset.pk)),
        "cms_media_unreferenced_candidates": sum(1 for asset in assets if not usage.get(asset.pk)),
    }
    stable = {
        "database": _connection_fingerprint(connection),
        "preserved_user_id": preserved_user.pk if preserved_user else None,
        "preserved_authentication_digest": _authentication_digest(preserved_user) if preserved_user else "",
        "preserved_password_hash_digest": (
            _sha256_bytes(preserved_user.password.encode("utf-8")) if preserved_user else ""
        ),
        "preserved_profile_digest": _preserved_row_digest(preserved_user) if preserved_user else "",
        "targets": targets,
        "target_counts": target_counts,
        "preserved_counts": preserved_counts,
        "unreferenced_cms_media": unreferenced_media,
        "blockers": blockers,
    }
    return {
        "schema": "rdc-beta-cleanup-v1",
        "generated_at": datetime.now(datetime_timezone.utc).isoformat(),
        **stable,
        "review_fingerprint": _json_fingerprint(stable)[:24],
    }


def _write_new_json(path, payload):
    path = Path(path).expanduser().resolve()
    if path.exists():
        raise CommandError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path


def _load_json(path, label):
    try:
        return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommandError(f"Unable to read the {label} JSON file.") from exc


def _validate_backup(backup, expected_database, *, allow_missing_supabase_snapshot=False):
    required_true = (
        "pg_restore_list_verified",
        "restore_test_verified",
        "backup_folder_acl_verified",
    )
    if any(backup.get(key) is not True for key in required_true):
        raise CommandError(
            "Backup metadata must confirm the protected folder, pg_restore listing, and restore test."
        )
    snapshot_verified = backup.get("supabase_snapshot_verified") is True
    snapshot_waived = backup.get("supabase_snapshot_waived") is True
    if not snapshot_verified:
        if not (allow_missing_supabase_snapshot and snapshot_waived):
            raise CommandError(
                "Backup metadata must confirm a Supabase snapshot, or execution must explicitly allow "
                "the recorded snapshot waiver."
            )
    try:
        pg_dump_major = int(backup.get("pg_dump_major_version") or 0)
        restore_major = int(backup.get("restore_postgres_major_version") or 0)
        dump_port = int(backup.get("dump_connection_port") or 0)
    except (TypeError, ValueError) as exc:
        raise CommandError("Backup version and port evidence must be numeric.") from exc
    if pg_dump_major != 17:
        raise CommandError("The backup must be created with PostgreSQL 17 pg_dump.")
    if restore_major != 17:
        raise CommandError("The restore test must use a fresh PostgreSQL 17 database.")
    if backup.get("dump_connection_mode") not in {"direct", "session"}:
        raise CommandError("The backup must use a direct or session-mode connection.")
    if dump_port <= 0:
        raise CommandError("Backup metadata must record the pg_dump connection port.")
    if dump_port == 6543:
        raise CommandError("The port 6543 transaction pooler cannot be used for pg_dump.")
    if backup.get("database") != expected_database:
        raise CommandError("The backup database fingerprint does not match the cleanup target.")
    dump_path = Path(str(backup.get("dump_path") or "")).expanduser().resolve()
    if not dump_path.is_file():
        raise CommandError("The recorded database dump does not exist.")
    expected_hash = str(backup.get("dump_sha256") or "").lower()
    actual_hash = _sha256_file(dump_path)
    if not expected_hash or actual_hash != expected_hash:
        raise CommandError("The database dump checksum does not match the backup metadata.")


class Command(BaseCommand):
    help = "Dry-run by default; execute the approved full beta cleanup only with backup evidence."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default")
        parser.add_argument("--manifest", help="Write a new preview manifest, or read it during --execute")
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--confirm-plan")
        parser.add_argument("--confirm-preserved-user-id", type=int)
        parser.add_argument("--backup-manifest")
        parser.add_argument(
            "--allow-missing-supabase-snapshot",
            action="store_true",
            help="Use only when the reviewed backup evidence records an explicit snapshot waiver.",
        )
        parser.add_argument("--allow-non-postgres", action="store_true", help="Tests/local rehearsal only")

    def handle(self, *args, **options):
        alias = options["database"]
        if alias not in connections:
            raise CommandError(f"Unknown database alias: {alias}")
        if not options["execute"]:
            manifest = build_cleanup_manifest(alias)
            self.stdout.write(json.dumps(manifest, indent=2, sort_keys=True, default=str))
            if options.get("manifest"):
                path = _write_new_json(options["manifest"], manifest)
                self.stdout.write(f"Manifest written: {path}")
            self.stdout.write(self.style.WARNING("DRY RUN ONLY. No records were changed."))
            return

        connection = connections[alias]
        if connection.vendor != "postgresql" and not options["allow_non_postgres"]:
            raise CommandError("Cleanup execution requires PostgreSQL; use --allow-non-postgres only for a local rehearsal.")
        if not options.get("manifest") or not options.get("backup_manifest"):
            raise CommandError("Execution requires --manifest and --backup-manifest.")
        reviewed = _load_json(options["manifest"], "cleanup manifest")
        if reviewed.get("schema") != "rdc-beta-cleanup-v1":
            raise CommandError("The cleanup manifest schema is unsupported.")
        if reviewed.get("preserved_user_id") != PRESERVED_USER_ID:
            raise CommandError("The cleanup manifest does not identify the required preserved account.")
        if reviewed.get("blockers"):
            raise CommandError("The reviewed cleanup manifest contains blockers.")
        if options.get("confirm_plan") != reviewed.get("review_fingerprint"):
            raise CommandError("--confirm-plan must match the reviewed manifest fingerprint.")
        if options.get("confirm_preserved_user_id") != PRESERVED_USER_ID:
            raise CommandError(f"--confirm-preserved-user-id must be {PRESERVED_USER_ID}.")
        backup = _load_json(options["backup_manifest"], "backup manifest")
        _validate_backup(
            backup,
            reviewed.get("database"),
            allow_missing_supabase_snapshot=options.get("allow_missing_supabase_snapshot", False),
        )

        result = self._execute(alias, reviewed)
        result_path = Path(options["manifest"]).with_suffix(".result.json")
        _write_new_json(result_path, result)
        self.stdout.write(self.style.SUCCESS("Beta cleanup completed and verified."))
        self.stdout.write(f"Result written: {result_path}")

    def _execute(self, alias, reviewed):
        from ai_engine.models import (
            AIModelTrainingRecord,
            AIModelVersion,
            AIProjectAnalysis,
            AISimilarProject,
            AITrainingRecord,
        )
        from cms.models import CMSContributorForm, CMSPageSection
        from projects.models import (
            AccessRequest,
            AuditTrail,
            EditRequest,
            Notification,
            PasswordResetChallenge,
            PasswordResetRequest,
            PasswordSetupToken,
            PortalSession,
            ProfileEditRequest,
            Project,
            ProjectConcernReport,
            User,
            UserActivity,
            UserInvitation,
        )

        db = lambda model: model.objects.using(alias)
        with transaction.atomic(using=alias):
            # The deployment runbook stops application writers. These locks and
            # the repeated fingerprint make unexpected changes fail closed.
            list(db(User).select_for_update().values_list("pk", flat=True))
            list(db(Project).select_for_update().values_list("pk", flat=True))
            list(db(ProjectConcernReport).select_for_update().values_list("pk", flat=True))
            list(db(UserInvitation).select_for_update().values_list("pk", flat=True))
            current = build_cleanup_manifest(alias)
            if current.get("review_fingerprint") != reviewed.get("review_fingerprint"):
                raise CommandError("The database changed after preview; cleanup was cancelled.")

            preserved = db(User).get(pk=PRESERVED_USER_ID, email__iexact=PRESERVED_EMAIL)
            before_digest = _authentication_digest(preserved)
            before_profile_digest = _preserved_row_digest(preserved)

            db(CMSPageSection).filter(lock_owner__isnull=False).update(
                lock_owner=None, lock_acquired_at=None
            )
            db(CMSContributorForm).filter(lock_owner__isnull=False).update(
                lock_owner=None, lock_acquired_at=None
            )

            db(AISimilarProject).all().delete()
            db(AIProjectAnalysis).all().delete()
            db(AIModelTrainingRecord).all().delete()
            db(AITrainingRecord).all().delete()
            db(AIModelVersion).all().delete()

            db(Notification).all().delete()
            db(UserActivity).all().delete()
            db(AuditTrail).all().delete()
            db(EditRequest).all().delete()
            db(Project).all().delete()
            db(ProjectConcernReport).all().delete()

            db(ProfileEditRequest).all().delete()
            db(AccessRequest).all().delete()
            db(UserInvitation).all().delete()
            db(PasswordResetChallenge).all().delete()
            db(PasswordResetRequest).all().delete()
            db(PasswordSetupToken).all().delete()
            db(PortalSession).all().delete()
            Session.objects.using(alias).all().delete()
            LogEntry.objects.using(alias).all().delete()
            db(User).exclude(pk=PRESERVED_USER_ID).delete()

            preserved.refresh_from_db(using=alias)
            if _authentication_digest(preserved) != before_digest:
                raise CommandError("The preserved Administrator changed; the transaction was cancelled.")
            if _preserved_row_digest(preserved) != before_profile_digest:
                raise CommandError("The preserved Administrator profile changed; the transaction was cancelled.")
            if db(User).count() != 1 or db(Project).exists() or db(ProjectConcernReport).exists():
                raise CommandError("Post-cleanup verification failed; the transaction was cancelled.")
            connections[alias].check_constraints()

        after = build_cleanup_manifest(alias)
        return {
            "schema": "rdc-beta-cleanup-result-v1",
            "completed_at": datetime.now(datetime_timezone.utc).isoformat(),
            "review_fingerprint": reviewed["review_fingerprint"],
            "database": reviewed["database"],
            "preserved_user_id": PRESERVED_USER_ID,
            "preserved_authentication_digest": after["preserved_authentication_digest"],
            "preserved_password_hash_digest": after["preserved_password_hash_digest"],
            "preserved_profile_digest": after["preserved_profile_digest"],
            "remaining_users": 1,
            "remaining_projects": 0,
            "remaining_concern_reports": 0,
            "preserved_counts": after["preserved_counts"],
        }
