# RDC-NCR system refinement

## Administrator navigation

| Group | Pages |
| --- | --- |
| Overview | Dashboard |
| Operations | Project Management, Validator Tracker, Data Exports |
| Content & Configuration | Content Management, Contributor Forms, A.I. and Project Criteria |
| Administration | Users & Access, Audit Log |

The three collapsible groups remember their settings in the browser. The current route opens its group automatically, including nested project routes. The sidebar keeps the existing route paths and role checks.

## CMS

- Select an image in **Regional Profile → Geographic Coverage**, save the section, then publish the page as an Administrator. A Content Editor can save a draft. The bundled map is used when the replacement is cleared, its Media Library asset is archived, or the browser cannot load it. The section renderer accepts a Media Library image and the API rejects iframe configuration.
- Publication categories and resolution years expand independently. Collapsing a group keeps its unsaved fields and documents in the current editor. Publication attachment size and type come from the Media Library when an asset is selected, and existing metadata remains available for legacy documents.
- Home displays Latest Media Releases, the Regional Development Dashboard, and Upcoming Events using the existing News, Projects, and Events APIs. The three sections are system-managed in the Home editor. The full calendar is available from Home and at `/news#events`, and the public dashboard remains at `/projects`. Home quick links retain valid destinations, use the canonical dashboard URL, and omit placeholders.

## AI scoring and Validator review

The scorer resolves the exact form version recorded on a submission or revision. It uses applicable answers with their labels, field types, guidance, and selected option labels. Groq receives the configured outcome rubric, relevant Validator facts, and bounded citations from the existing document assessment. Explicitly legacy submissions retain their compatibility behavior. Required answers on versioned submissions, Validator facts, and document policy still apply.

The Administrator scoring workspace no longer requires a separate form-to-criterion mapping to publish a version. Form structure and catalog associations are still validated. Individual Groq explanations and evidence appear in the score table beside separately stored Validator remarks. Validator review omits the recommendations and revision-field panels. Confirmed scores and historical analyses remain tied to their original inputs and scoring version.

The workspace documents the existing score calculation. Each criterion contributes its raw score times its weight divided by 10. The base score adds PAP and RDP points and is bounded to 0–100. The regional scorecard applies when total funding requirements reach the configured cutoff. The final score is the average of the bounded base and regional scores when eligible, and the base score below the cutoff. Projects below the cutoff receive an automatic Low recommendation. A base score of 80 and a regional score of 60 yield 70 for an eligible project and 80 below the cutoff.

## Contributor forms and catalogs

The existing protections cover Project Information, Funding and Classification, Accomplishment and Remarks, and the system-managed fields that dependent workflows require. Location and Development Sector catalog administration now requires both the Administrator role and Django superuser status. The existing Agency Catalog remains available through Users & Access.

Locations and development sectors use stable codes. Catalog renames and deactivations affect future selections while published submission snapshots retain their saved labels. Committee mappings can link one committee to multiple outcome groups. SCEED keeps both Economic and Environment groups, and Validator track selection determines which group applies. Activating committee changes or scoring rules requires valid outcome associations.

For an intentional form upgrade, use the existing form migration preview for an editable project and review unresolved choices before applying it. For a project awaiting validation that genuinely needs a corrected answer, return it for revision through the existing Validator workflow.

## Verification

| Check | Result |
| --- | --- |
| Django CMS, AI engine, and project suite | 483 tests run, 2 skipped, no failures |
| Django migration check | No model changes detected |
| Vite production build | Passed |
| CMS browser tests | Publication category collapse, draft resolution editing, file uploads, public Home links, News calendar, and map fallback passed |
| Administrator and Validator browser tests | Sidebar keyboard controls and persistence, score explanations, score editing, confirmation, facts restoration, and rule history passed |
| Public project browser tests | Project history, mobile layout, and public table pagination passed |
| Validator list pagination browser script | The expected pending-validation count timed out on this branch and on the original revision `5dc0926` |
| Standalone TypeScript check | Reports existing errors in `Footer.tsx` and `SimplifiedProjectSubmission.tsx` |

Backend tests use SQLite and mocked Groq responses. Browser tests use mocked API responses. The production database, deployed storage, and live Groq scoring are outside this verification.

The Home restoration passed the 177-test CMS and location suite and 11 focused CMS and public project API checks. The browser regressions verified refreshed media releases, project totals, and event details on Home, desktop and mobile presentation, shared calendar fetching, API-backed sections, and preserved CMS and standalone dashboard navigation. The API tests exercised publishing and editing through the existing News and Events workflows and checked the Home editing restriction for both CMS roles.

## Files and deployment

| Area | Main files |
| --- | --- |
| Navigation and permissions | `frontend/src/App.tsx`, `frontend/src/components/portal/PortalLayout.tsx`, `frontend/src/components/portal/ContributorFormsManager.tsx`, `backend/cms/form_catalog_views.py`, `backend/cms/serializers.py` |
| CMS and public pages | `frontend/src/components/portal/CmsManager.tsx`, `frontend/src/components/PublicEventsCalendar.tsx`, `frontend/src/pages/Home.tsx`, `frontend/src/pages/News.tsx`, `frontend/src/pages/RegionalProfile.tsx`, `backend/cms/services/collections.py`, `backend/cms/management/commands/seed_home_cms.py` |
| Scoring and Validator review | `backend/ai_engine/groq_priority.py`, `backend/projects/priority_scoring.py`, `backend/projects/scoring_contract.py`, `backend/cms/views.py`, `backend/cms/services/publishing.py`, `frontend/src/components/portal/AIScoringManager.tsx`, `frontend/src/components/portal/PriorityAnalysisPanel.tsx`, `frontend/src/services/cmsApi.ts` |

Deploy the backend and frontend together. The frontend uses the lockfile entry for Lucide icons. This refinement adds no migration or environment setting. Environments that have yet to apply the existing catalog migration need their usual migration step. Keep the configured Groq models and credentials. The final staging checks are one published map replacement, one scoring run with the configured Groq provider, a Validator review with the original form version, and a multi-LGU project on the public dashboard.
