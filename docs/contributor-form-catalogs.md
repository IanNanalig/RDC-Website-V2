# Contributor Forms and Catalogs

## Architecture and protected fields

Contributor projects and progress revisions use their saved form version. The form editor creates drafts and publishes a new immutable version. The catalog-backed version stores each system field's catalog reference. The API supplies choices when a client loads the form.

| Protected field | Answer | Dependencies |
| --- | --- | --- |
| Collaborating Agencies (`collaboratingAgencies`) | Optional multi-select | Agency Catalog, project collaboration records, Contributor and Validator views |
| Program (`program`) | Required text | Structured project metadata, form review |
| Project/Activity (`projectActivity`) | Required text | Project name, submission, Validator review, dashboard listing |
| Location (`location`) | Required multi-select | Project location snapshots, public map filters, distinct LGU count in PAP scoring |
| Description (`description`) | Required textarea | Project listing, review, public summary, AI input |
| Objective (`objective`) | Required textarea | Review, public summary, AI input |
| RDC-NCR Development Sector (`developmentSector`) | Required select | Committee catalog, Validator track selection, AI outcome groups |

Administrators can edit display labels, helper text, placeholders, and the order of fields in Change Form. The server protects field identities, types, requiredness for these fields, visibility, and placement in core sections. It also protects existing ownership, years, funding, and the supporting-document field. Funding and Classification and Accomplishment and Remarks are core sections. Ordinary fields in those sections still use the existing edit and conditional-display rules.

The catalog screen is available under **Contributor Forms → Manage form catalogs**. Agency choices come from **Users & Access → Agencies**. The system returns live choices for current Contributor forms and rejects new inactive selections. An existing record can retain an inactive choice on an unrelated edit.

## Identities and scoring

- Collaborating agency answers use `agency:<agency primary key>` in new form versions. Primary agency and collaborator relationships continue to use the existing Agency records. The form still excludes the primary agency and blocks duplicate collaborators.
- The Location Catalog starts with the 16 cities and one municipality already supported by the NCR map. The stable ID for Manila is `lgu-manila`, and the stable ID for Taguig is `lgu-taguig`. The public `lgu` and `lgus` fields continue returning map keys such as `Manila` and `Taguig`. Catalog names can change independently of those keys.
- The four seeded committee codes are `scid`, `scsd`, `sceed`, and `scfda`. They link to Infrastructure, Social, Economic and Environment, and Financial and Administrative respectively. Links are many-to-many. A draft committee can be incomplete while inactive. The catalog and rule activation check that every active committee and each committee-specific outcome group have valid links.
- A committee with one linked group is scored under that group. For multiple groups the Validator selects one linked track. SCEED retains its Economic and Environment choices and saved `sceeedTrack` values. The scorer combines the selected group with Common Outcomes using the existing weights and formulas. New analyses record the available groups and selected track. A change in the group links updates the key used to reuse analysis results.

## Historical data and verification

The read-only inventory found published version 19, 19 published versions, and nine collaboration links. All catalog values found in 19 simplified project profiles and 21 simplified revision profiles mapped unambiguously to the seeded catalog identities. The current draft contained no conditions using Agency, Location, or Development Sector as a source.

Existing submitted versions and confirmed Validator decisions remain readable with their original saved context. Catalog-backed saves record their display labels with the selected IDs. When an editable project is explicitly moved to a newer form, the migration maps known legacy values by exact ID, current code or label, or a supported alias. It reports unresolved choices for review before any version upgrade.

| Verification area | Expected result | Local result |
| --- | --- | --- |
| Administrator editor and API | Core elements remain protected, normal editing still works, and catalog links govern activation | API tests passed for protection, permissions, and activation. A browser smoke test passed for catalog controls and the upgrade action. |
| Contributor | Current version serves stable IDs, and create, upload, submit, and revision use the selected catalog records | Passed the catalog-backed API submission and the Contributor upload browser regression. |
| Validator and AI | Both SCEED tracks route to their respective group, and score and confirmation workflows preserve existing behavior | Passed with a mocked provider and in the Validator browser regression. Changing the linked group creates a new analysis. |
| Public dashboard | Historical location labels remain visible and Manila and Taguig continue using their canonical map keys | Passed the public serializer and LGU filter checks. A deployed map check remains pending. |
| Migration | Migration creates and seeds the new catalogs. Historical schemas and submitted answers retain their original contents | Passed on an isolated test database. The live inventory ran read-only. |

The selected backend regression suite passed 143 tests. The final catalog-specific run passed seven tests, including the additional analysis reuse check. The frontend production build passed.

## Deployment and rollback

1. Back up the database and record the current `simplified-rdip` published version. Apply the Django migrations through `projects.0061_contributor_form_catalogs` in staging before serving the new backend.
2. Deploy the compatible backend and frontend builds. In Contributor Forms, open **Update Form**, review the draft, choose **Save Catalog Upgrade**, and publish it. Confirm that the current version serves catalog-backed choices before opening the new form for project entry.
3. Smoke-test with separate Administrator, Contributor and Validator accounts. Include a two-LGU submission and each SCEED track, and verify the public map from a staged endorsed project.
4. Before any catalog-backed submissions, rollback can restore the previous published version pointer and application release while retaining the additive tables. After catalog-backed projects exist, keep a release that reads catalog IDs and historical formats during rollback. A rollback to an older reader requires reconciling those new submissions so their stable IDs and history stay accessible.

The live database was inspected read-only. Migration application, publication, and end-to-end scoring on the hosted environment require deployment verification.
