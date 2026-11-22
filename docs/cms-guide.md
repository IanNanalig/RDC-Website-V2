# CMS Staff Guide

This guide is for RDC-NCR staff who will manage public website content without editing code.

## Core Rule

CMS edits are safe by default:

- Saving a draft changes only the staff-side editable copy.
- Publishing is the only action that changes the public website.
- Public pages read from the latest published snapshot, not from draft fields.

If something is not ready for the public, save it as a draft and do not publish yet.

## Pages and Sections

The Pages workspace includes all seven core public pages:

- Home
- About RDC
- Region Profile
- Publications
- News
- Projects Dashboard
- Contact

Public pages are made of sections. Examples:

- Hero banner
- Dashboard teaser
- Publication catalog
- Latest news
- Contact information
- Events/calendar preview

Typical workflow:

1. Open `CMS > Pages`.
2. Choose the page you want to edit.
3. Edit the section fields.
4. Save the section draft.
5. After publishing, use `View Published` to review the public page.
6. Content editors submit the change for review; administrators publish or reject it.

Sections can be shown or hidden with `Visibility`. Hidden sections are not included in the next published public snapshot.

Opening an existing section acquires a 10-minute editing lock. The editor refreshes the lock every two minutes and releases it on save or close. If another editor owns the lock, the section opens read-only and staff can send a Request Access notification.

The News page record controls the landing-page hero and introduction. Individual news articles remain in the separate `CMS > News` workspace. The Projects Dashboard page record controls headings and explanatory copy only; totals, budgets, statuses, maps, and project updates continue to come from endorsed portal project records.

The core-page migration fills missing pages and required sections without replacing text already edited by staff. For manual local repair or reseeding, run `python manage.py seed_all_cms`.

## Publications

The Publications page can use two kinds of files:

- Built-in fallback files already bundled with the public website.
- CMS Media Library files uploaded by staff.

Recommended workflow for replacing or adding a publication file:

1. Open `CMS > Media Library`.
2. Upload the PDF document.
3. Upload the cover image if available.
4. Add clear captions, such as `RDP 2023 Full PDF` or `Greenprint Cover`.
5. Open `CMS > Pages`.
6. Edit the `Publications` page.
7. Open the `Publication Catalog` section.
8. In the document row, select the PDF from `PDF / Document from Media Library`.
9. Select the cover from `Cover Image from Media Library`.
10. Save the section draft.
11. Publish the page when ready.

If no CMS media is selected, the page keeps using the built-in fallback file connected to the document ID.

## News

Use News for public announcements and updates.

Recommended workflow:

1. Open `CMS > News`.
2. Create or edit an article.
3. Add a short summary that can fit on a public card.
4. Add the full body content with the visual formatting toolbar. Staff do not need to enter HTML.
5. Select or upload a thumbnail image when available.
6. Save as draft.
7. Publish when ready.

Published news appears on the public News page and can be linked from the Home page. Article and page slugs become read-only after their first publish so shared public links are not broken.

## Media Library

The Media Library stores reusable public website files.

Default allowed file types:

- Images: PNG, JPG, WebP (5 MB)
- Documents: PDF, DOC, DOCX, XLS, XLSX (20 MB)

Administrators can change allowed MIME types and per-category limits in `CMS > Site Settings`. Changes take effect on the next upload without a deployment. A rejected upload reports whether its type is disallowed or it exceeds the current size limit.

Good practices:

- Use descriptive captions.
- Add alt text for images when the image has public meaning.
- Avoid uploading duplicate files.
- Do not archive media that is still used by a page, section, or article.
- For large PDFs, compress them before uploading when possible.

The Media Library shows where a file is used. The Archive action is disabled while CMS content or retained historical records still reference the file. Publication templates can reuse the same file from the Media Library.

### Page removals and Archive

Remove publication templates, categories, carousel slides, and resolution entries in their page editors. Save the draft, then have an Administrator publish it. Visitors continue seeing the published page until publication. Removing a template keeps its uploaded file available in the Media Library. Move a document to another category in the editor if it should remain on the page.

The general Archive contains **News**, **Events**, and **Media**. News and events return as drafts when restored. Media files return to the active Media Library. Archive Details shows human-readable summaries and available previews. Old publication, carousel, and resolution archive records remain stored with their files and history. To display an attachment again, add a new template and select it from the Media Library.

### Draft review and preview

Use **Preview Draft** to inspect the saved draft. **Change Review** shows modified, added, and removed sections first. Unchanged sections are available in a collapsed group. **Full-Page Preview** uses the public page components, including interactive publication categories and resolution years. The Contact form is disabled in preview. Changes in an open section editor appear after you save them.

### Archive and preview implementation report

The former publication restore handler changed an item's status before checking whether its category existed in the draft. The old Archive Details printed record properties and saved JSON. Page Review compared raw serialization and rendered every section through a generic field display.

| Area | Files |
| --- | --- |
| Archive and publication lifecycle | `backend/cms/views.py`, `backend/cms/services/collections.py`, `frontend/src/components/portal/ArchivedContent.tsx`, `frontend/src/components/portal/CmsManager.tsx` |
| Saved draft preview and comparison | `backend/cms/services/snapshots.py`, `backend/cms/views.py`, `frontend/src/components/portal/CMSPageReview.tsx`, `frontend/src/services/cmsApi.ts`, and the Home, Publications, About RDC-NCR, Regional Profile, and Contact page components |
| Inventory and regression tests | `backend/cms/management/commands/audit_content_only_cms.py`, `backend/cms/tests/test_content_only_cms.py`, `frontend/scripts/cms-profile-archive-check.mjs` |

The local CMS suite, Vite production build, and desktop and mobile CMS browser checks passed. Tests covered the two CMS roles, the three supported archive and restore paths, publication template removal and reuse, carousel removal, and preview parity with the published Publications page. The standalone TypeScript check still reports two existing errors in `Footer.tsx` and `SimplifiedProjectSubmission.tsx`.

Deploy the backend and frontend together. The current schema supports this change. Run `python manage.py audit_content_only_cms --archive-inventory` against the deployment's database before release. The audit reports historical archived rows, publication templates outside the current draft categories, and missing or archived attachment references recorded in the database. It performs read-only checks. The local database had zero historical archived rows in the excluded collections. The deployed database and storage remain unverified.

Future storage note: the system is designed so media can later move to durable cloud storage such as Cloudflare R2 without changing the staff workflow.

## Review Queue and Revisions

`CMS > Review Queue` combines submitted pages, sections, news, and events. Administrators can publish or reject submitted page content from this view. Rejection remarks remain staff-only; an older published snapshot stays public while revised content is under review.

`CMS > Revision History` records create, update, submit, publish, reject, archive, reorder, and restore actions. Deleted targets are marked `(deleted)`. An administrator can restore a deleted section when its parent page still exists; if the page was also deleted, the CMS refuses to create an orphan.

## Site Settings

Global settings cover the logo, footer text, contact details, social links, office address, quick links, Home announcement banner, and media upload policy. These are presented as grouped visual forms. Only administrators can modify settings.

Raw section, article, and setting source is hidden from the CMS interface. Staff and administrators edit website content only through the visual forms.

The CMS warns before leaving or reloading with unsaved changes. Save or intentionally discard the open draft before publishing it.

## Publishing Checklist

Before clicking Publish:

- Confirm spelling, dates, links, and file names.
- Confirm uploaded PDFs open correctly.
- Confirm cover images display correctly.
- Confirm hidden sections are intentionally hidden.
- Confirm no private/internal notes are included in public text.
- Confirm the page still looks correct on mobile if possible.

## What To Do If Something Looks Wrong

- If a draft is wrong, edit it and save again.
- If public content is wrong, correct the CMS content and publish the page/article again.
- If an uploaded file is wrong, upload a corrected file and select it in the relevant section or article.
- If the public page still does not update, refresh the browser and check that the page/article was actually published.
