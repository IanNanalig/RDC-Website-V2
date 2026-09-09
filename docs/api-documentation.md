# API Documentation Notes

The Django API is served under `/api/` from `backend/projects/urls.py`.

Important API groups:

- Authentication and password setup/reset
- Employee project submissions
- Validator review and progress revisions
- Admin user/activity/window controls
- Public projects dashboard endpoints
- Public chatbot endpoints

Public endpoints must not require JWT headers and must avoid exposing raw workflow data or private `profile_data`.

## Public CMS API

- `GET /api/public/cms/pages/:slug/` — latest approved page snapshot.
- `GET /api/public/cms/news/` and `GET /api/public/cms/news/:slug/` — approved news only.
- `GET /api/public/cms/events/` — approved events/calendar data.
- `GET /api/public/cms/site-settings/` — public global settings; upload governance is excluded.

Public page snapshots contain only sections whose status is `published` and whose visibility flag is enabled. Existing approved snapshots remain public while a replacement draft is submitted or rejected. Archived records are removed from public responses.

Public CMS, event, and project responses use stable URLs, strong `ETag` validators, and `Cache-Control: public, no-cache, must-revalidate`. Clients may send `If-None-Match`; unchanged content returns HTTP 304, while a publish or endorsed project update changes the validator on the next request.

## Lightweight Lists

- Add `?view=summary` to authenticated project or project-revision list requests to omit full form snapshots and detailed priority analysis.
- Add `?view=summary` to `GET /api/public/projects/` to omit narratives and the complete public revision timeline. Fetch `GET /api/public/projects/:id/` when details are opened.
- Add `?include_meta=1` to `GET /api/notifications/` to receive `{results, unread_count}`. Without it, the legacy array response is unchanged.

All summary options are additive. Existing list and detail response shapes remain the default for older clients.

## Staff CMS API

Authenticated administrators and content editors use:

- `/api/admin/cms/pages/`, `/sections/`, `/news/` (with `/articles/` retained as a compatibility alias), `/media/`, `/events/`, `/settings/`, and `/revisions/`.
- Workflow actions on pages, sections, and news: `submit/`, `publish/`, `reject/`, and `archive/`. Publish/reject/archive require an administrator.
- Section concurrency actions: `lock/`, `unlock/`, `heartbeat/`, and `request-access/`.
- `GET /api/admin/cms/review-queue/` for all submitted CMS content.
- `POST /api/admin/cms/revisions/:id/restore-revision/` to restore a historical snapshot.

Media policy failures return HTTP 422. The response has `reason: file_type_not_allowed` with the allowed policy, or `reason: file_too_large` with `current_limit` and the submitted size.
