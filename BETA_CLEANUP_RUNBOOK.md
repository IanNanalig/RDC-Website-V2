# Supabase Beta Cleanup Runbook

The `beta_cleanup` command is a dry run unless every execution safeguard is
provided. Do not run its execution mode against production. The approved beta
target preserves only user ID `3` (`ian095108@gmail.com`) and intentionally
invalidates every portal and Django session.

## 1. Prepare and identify the target

1. Put the beta web service and workers into maintenance mode.
2. Use a direct or session-mode Supabase connection on port `5432`. Do not use
   the transaction pooler on port `6543` for backup or restore validation.
3. Keep the connection string in a process environment variable or secret
   manager. Never save it in this repository, a command file, or the manifest.
4. Generate a read-only preview. This command does not change the database:

   ```powershell
   python manage.py beta_cleanup --manifest C:\Users\Ian\RDC-NCR-Backups\<timestamp>\cleanup-preview.json
   ```

Review the non-secret database fingerprint, blockers, target IDs, per-table
counts, preserved counts, and `review_fingerprint` in that file.

## 2. Create and prove the backup

1. Record a Supabase-managed snapshot for the same beta project.
2. With PostgreSQL 17 tools, create a custom-format dump in the timestamped
   backup folder:

   ```powershell
   pg_dump --format=custom --no-owner --no-acl --file C:\Users\Ian\RDC-NCR-Backups\<timestamp>\beta.dump $env:RDC_BETA_DIRECT_DATABASE_URL
   pg_restore --list C:\Users\Ian\RDC-NCR-Backups\<timestamp>\beta.dump
   Get-FileHash C:\Users\Ian\RDC-NCR-Backups\<timestamp>\beta.dump -Algorithm SHA256
   ```

3. Restrict the timestamped folder to the current Windows user.
4. Restore the dump into a new, disposable local PostgreSQL 17 database and
   verify the table counts, preserved Administrator ID, email, role, active
   state, and password-hash digest.
5. Create `backup-evidence.json` outside the repository using this schema:

   ```json
   {
     "database": {
       "vendor": "postgresql",
       "identity_sha256": "copy from cleanup-preview.json",
       "postgres_server_version": 170006
     },
     "dump_path": "C:\\Users\\Ian\\RDC-NCR-Backups\\<timestamp>\\beta.dump",
     "dump_sha256": "lowercase SHA-256",
     "pg_dump_major_version": 17,
     "restore_postgres_major_version": 17,
     "dump_connection_mode": "direct",
     "dump_connection_port": 5432,
     "supabase_snapshot_verified": true,
     "pg_restore_list_verified": true,
     "restore_test_verified": true,
     "backup_folder_acl_verified": true
   }
   ```

All three confirmation fields must describe checks that were actually
completed. The command streams and verifies the dump checksum again.

## 3. Apply the schema and re-preview

Apply migration `projects.0048_account_capacity` during the maintenance window.
Generate a new preview after migration. Any changed target, count, blocker, or
fingerprint invalidates the older preview and requires another review.

Automated tests must use a disposable local database, never the Supabase beta
database.

## 4. Obtain explicit approval and execute

After a reviewer explicitly approves the final `review_fingerprint`, execute
with all safeguards:

```powershell
python manage.py beta_cleanup `
  --execute `
  --manifest C:\Users\Ian\RDC-NCR-Backups\<timestamp>\cleanup-preview.json `
  --backup-manifest C:\Users\Ian\RDC-NCR-Backups\<timestamp>\backup-evidence.json `
  --confirm-plan <approved-review-fingerprint> `
  --confirm-preserved-user-id 3
```

The command locks the affected rows, recalculates the preview inside one
transaction, and aborts if the review fingerprint changed. It does not reset
database sequences. It verifies foreign-key constraints and writes a new
`cleanup-preview.result.json` after a successful commit.

## 5. Post-cleanup verification

Before ending maintenance mode, verify:

- exactly one user remains and it is the unchanged Administrator ID `3`;
- its authentication, password-hash, and full-profile digests match;
- no projects, concern reports, project-derived AI records, sessions, or
  operational audit/activity rows remain;
- all agencies, permissions, migrations, priority rules, system settings,
  CMS/public content, contributor-form versions, and all CMS media remain;
- public CMS endpoints and Administrator login work; and
- the preserved Administrator signs in again because all sessions were removed.

If any verification fails, keep services in maintenance mode and restore the
verified backup rather than attempting ad-hoc repairs.
