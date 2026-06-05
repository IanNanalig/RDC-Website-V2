# Deployment Guide

## Required Environment

Set these in the production host, CI secrets, or secret manager:

- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `FRONTEND_BASE_URL`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`
- `SENTRY_DSN` and `TURNSTILE_SECRET_KEY` when enabled

## Build Layout

- Frontend source lives in `frontend/`.
- Backend source lives in `backend/`.
- Docker builds `frontend/dist` first, then copies it into `backend/staticfiles` inside the final image.
- `backend/staticfiles` is generated output and must not be committed.

## Local Production-Like Run

```powershell
docker compose up --build
```

## Manual Checks

```powershell
cd frontend
npm ci --legacy-peer-deps
npm run build
npm run lint

cd ..\backend
.\venv\Scripts\python manage.py check
.\venv\Scripts\python manage.py migrate --check
.\venv\Scripts\python manage.py test projects
```

## Static and Assets

Large public PDFs and images currently live in `frontend/src/assets`. Before final production deployment, review whether they should stay bundled or move to object storage/CDN.

Use:

```powershell
python tools/scan_large_assets.py --min-mb 0.5
```

Asset optimization helpers default to the new frontend paths:

```bash
bash scripts/optimize_images.sh
bash scripts/optimize_pdfs.sh
```
