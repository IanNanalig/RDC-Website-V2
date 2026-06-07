# File Structure Notes

The repository is intentionally split into two application roots:

```text
backend/   Django project and API
frontend/  React + Vite client
docs/      deployment, database, API, and structure notes
scripts/   safe helper scripts and maintenance utilities
```

## Backend App Location

Django app code remains in:

```text
backend/projects
```

Do not move it to `backend/apps/projects` during deployment cleanup. Moving it can affect app labels, migrations, `AUTH_USER_MODEL`, import paths, and existing database tables. That kind of move should be a separate migration/refactor task with its own test plan.

## Environment Files

These files are local only and must never be committed:

- root `.env`
- `backend/.env`
- `frontend/.env`
- any `*.env.backup*` files

The committed templates are:

- `backend/.env.example`
- `frontend/.env.example`

Use the templates to know which variables exist, then put real values in Render, Vercel, Supabase, or local ignored `.env` files.

## Deployment Config

- `frontend/vercel.json` is the Vercel SPA routing config.
- `Dockerfile` and `docker-compose.yml` are fallback/staging tooling.
- Render is the primary backend hosting path.
- Vercel is the primary frontend hosting path.
- Supabase is the primary production database path.

## Ignored Generated Files

These are intentionally ignored and should not be tracked:

- `frontend/node_modules/`
- `frontend/dist/`
- `.venv/`
- `venv/`
- `backend/venv/`
- `backend/staticfiles/`
- `__pycache__/`
- `*.pyc`
- `*.sqlite3`
- `backend/db.sqlite3`

## Safe Cleanup Policy

It is safe to remove generated build artifacts such as:

- `frontend/dist`
- `backend/staticfiles`
- `__pycache__`

It is not safe to automatically remove:

- `.env`
- database files
- database backups
- uploaded/public assets

Local secrets and local data must be backed up and handled manually.
