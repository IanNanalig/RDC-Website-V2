# Contributor update and revision document audit

## Workflow-status consolidation investigation (2026-11-10)

Baseline: `projects.tests.PortalWorkflowTests.test_needs_revision_requires_comment_unlocks_edit_and_notifies` and `projects.tests.PerformanceApiTests.test_public_project_history_only_contains_endorsed_revisions` passed on the isolated SQLite test database. The working tree already contains unrelated document, AI, form migration, and sample-kit changes; these must be preserved.

Confirmed dependencies: `Project.status` stores planning/proposed/completed, `Project.validated` controls public visibility, and `profile_data.validator_review.review_status` currently overrides the displayed workflow and is used by validator queues, document access, and migration eligibility. Progress updates instead use `ProjectRevision.state`; an endorsed revision supplies the last public snapshot while a newer revision is pending. The form's own `simplified_form.status` describes implementation progress and must remain independent of validation workflow.

Older-form detection currently includes a project only when its saved form marker resolves to an existing historical `CMSContributorFormVersion` and its version is below the published version. There is no direct validated-state filter in that list. An unresolved or missing marker is omitted before the Administrator can see the blocker. The current migration eligibility separately blocks implementation-completed projects and active reviews. Tests must reproduce these cases before changing the filter.

Implementation sequence: persist canonical submission states and backfill conservatively; replace active review-status checks with the canonical state; preserve review and audit snapshots; correct older-form listing to expose unresolved cases; verify initial submission, correction, progress revision, public snapshot, document access, and permissions. Historical revision states and unrelated rejection workflows must not be rewritten.

### Workflow-status implementation and verification

Added persisted four-value workflow status to projects and active progress revisions. Migration `0057_project_workflow_status` backfills from validation, review, and revision evidence; it aborts on ambiguous project records instead of guessing. Historical review JSON, revision states, and audit entries remain stored. New validator actions write decision metadata while project and revision workflow status drive queues, permissions, summaries, dashboards, and form-migration eligibility. The project Rejected action now fails; unrelated account and CMS rejection flows remain.

The older-form list previously dropped a project when its source form-version row could not be resolved. It now displays that project with its saved and target versions and a specific blocker. When a progress-update draft exists, its form marker is used for the list. Active reviews remain blocked; returned corrections and eligible validated projects follow their established migration paths. The public projection continues to use the last endorsed revision while an update is pending.

The first 430-test local run had one failure: a funding-dashboard fixture equated implementation status `completed` with a validated workflow project. The fixture now explicitly records validation. The full local Django rerun passed: 430 tests, 2 skipped. Two additional migration regression tests passed separately, covering status mapping and ambiguous-row rollback. Django system and migration-generation checks, frontend lint, TypeScript, and the production build pass. The build required running outside the filesystem sandbox because Vite could not read its config there. The public project history headless browser check passes, including approved milestones, empty states, and pagination. No hosted migration was run; a deployed project’s exact eligibility and public rendering remain unverified. Apply `0056` and `0057` through normal release controls only after reviewing any ambiguous-row migration error. No commit, push, deployment, or hosted-data change was performed.

## Scope and baseline

Reviewed the Contributor progress-update form, `ProjectRevision` routes, Validator revision queue, supporting-document API, and the separate correction/resubmission route. All reproduction and tests used Django's isolated local SQLite test database. No hosted records were changed. The existing uncommitted priority-analysis changes and sample kits were left in place.

## Reproduction and root causes

1. The backend `start-update` route creates a progress revision. The revision update and submit routes persist it and the Validator queue includes submitted revisions. A local API regression confirms **Start Update → submit → queue** works.
2. The frontend progress-revision branch returned immediately after saving/submitting. It skipped the queued-file upload step used by ordinary submissions. The same form disabled document changes in revision mode. Consequently, selected update evidence was never attached, even though the update could be reported as submitted.
3. Documents had only a project relationship. A new document for a pending revision therefore could not be distinguished from the validated project's effective evidence. The document list also fetched assessment status jointly with files; for a Validator opening a submitted progress revision on an ongoing project, that assessment request could be forbidden and hide the otherwise accessible file list.
4. The separate initial correction path already permits document changes only when the Validator selects that document field. It continues to use the original project submission route and is not merged with progress updates.

## Changes

- Added an optional document-to-revision relationship and a migration. Current project evidence includes original project documents and documents from endorsed revisions. Pending and rejected revision documents remain linked to their revisions but do not enter effective evidence or AI assessment inputs.
- Allowed Contributors from the primary agency to attach or remove documents on editable progress revisions, subject to the progress window, field access, file validation, count, size, and checksum rules. Validators can read documents on submitted revisions. Existing project documents remain read-only during an update.
- Preserved Validator document access after endorsement by recognizing the project's persisted revision history. A completed update no longer drops the reviewer's ability to download its supporting document.
- Changed the progress form to upload files against its revision before submitting it. A failed upload leaves the revision in draft and shows a failure message; success feedback appears only after the submit request succeeds. Document loading no longer depends on the separate AI assessment request.
- Scoped the active checksum uniqueness rules so rejected revision evidence does not prevent an identical upload in a later revision. Existing effective-document duplicate checks remain.
- Kept revision state changes as the switch that makes endorsed evidence current; no file bytes or historical project answers are rewritten at endorsement.

## Verification

- Local API test: progress revision save and submit with evidence, pending isolation, Contributor download, primary-agency restrictions, Validator queue and download, invalid file rejection, duplicate submit rejection, and endorsement visibility.
- Local API test: rejected progress evidence remains attached to its historical revision and never becomes current project evidence.
- Local API test: Validator-returned original project accepts a selected correction document and resubmits through the existing route.
- The full local `projects` suite passed: 269 tests, 2 skipped. Focused update and correction regressions passed. Frontend lint and TypeScript check passed; production build passed; existing Contributor supporting-document browser check passed.
- The separate existing Contributor correction browser check timed out waiting for an `Agency Name *` label. Its fixture uses an older form shape and label expectation; this check has not verified the current correction UI. The correction API regression passed.
- Migration generation check reported no uncommitted model changes.

## Deployment boundary

The deployed Contributor and Validator workflow, hosted database migration, browser interaction with a real update project, and hosted document download were not verified here. Apply migration `0056_revision_supporting_documents` with the normal release process, then test one Contributor update with a file and one Validator endorsement in the deployed environment. No commit, push, or deployment was performed.
