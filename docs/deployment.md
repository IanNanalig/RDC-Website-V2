# Deployment Guide

Primary deployment target:

- Frontend: Vercel
- Backend API: Render Web Service
- Database: Supabase PostgreSQL

Docker remains supported for local production-like testing and fallback VPS/staging deployment. Render + Vercel + Supabase is the preferred path.

## Where Environment Values Go

- Backend values go in Render environment variables.
- Frontend values go in Vercel environment variables.
- `DATABASE_URL` comes from Supabase project settings.
- Local `.env` files stay on your machine only and must never be committed.
- Use `.env.example` files as templates only.

## Supabase Database

Create a Supabase project and copy the PostgreSQL connection string.

Use a connection string with SSL:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
DATABASE_SSL_REQUIRE=true
```

Rules:

- Production must use PostgreSQL.
- SQLite is local fallback only.
- Back up Supabase before migrations.
- Do not commit database dumps, `.env` files, or backup env files.

## Local Development Env

Place backend values in `backend/.env` or your local shell:

```text
SECRET_KEY=local-dev-only-secret-key-at-least-50-characters-long
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173
FRONTEND_BASE_URL=http://localhost:5173

# Use local SQLite fallback unless you intentionally test Postgres.
FORCE_SQLITE=1
DATABASE_URL=
DATABASE_SSL_REQUIRE=false

SECURE_SSL_REDIRECT=false
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false
SECURE_HSTS_SECONDS=0
SECURE_PROXY_SSL_HEADER=false

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-gmail-address@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=RDC Portal <your-gmail-address@gmail.com>
CONTACT_RECEIVER_EMAIL=your-receiver-email@example.com
```

Place frontend values in `frontend/.env`:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

## Render Staging Env

Use these values for the first Render staging service:

```text
SECRET_KEY=generate-a-random-secret-key-with-at-least-50-characters
DEBUG=False
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
DATABASE_SSL_REQUIRE=true
ALLOWED_HOSTS=your-staging-api.onrender.com
CORS_ALLOWED_ORIGINS=https://your-staging-frontend.vercel.app
CSRF_TRUSTED_ORIGINS=https://your-staging-frontend.vercel.app
FRONTEND_BASE_URL=https://your-staging-frontend.vercel.app

SECURE_SSL_REDIRECT=true
SECURE_PROXY_SSL_HEADER=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true

# Keep HSTS disabled for first staging deploy until the final HTTPS domain is stable.
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=false
SECURE_HSTS_PRELOAD=false

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-gmail-address@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=RDC Portal <your-gmail-address@gmail.com>
CONTACT_RECEIVER_EMAIL=your-receiver-email@example.com
```

Optional staging values:

```text
SENTRY_DSN=
TURNSTILE_SECRET_KEY=
TURNSTILE_REQUIRED=false
JWT_ACCESS_HOURS=8
JWT_REFRESH_DAYS=7
```

## Render Production Env

Use production domains and a separate production secret:

```text
SECRET_KEY=generate-a-different-random-secret-key-with-at-least-50-characters
DEBUG=False
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
DATABASE_SSL_REQUIRE=true
ALLOWED_HOSTS=api.your-production-domain.gov.ph,your-render-service.onrender.com
CORS_ALLOWED_ORIGINS=https://your-production-domain.gov.ph
CSRF_TRUSTED_ORIGINS=https://your-production-domain.gov.ph
FRONTEND_BASE_URL=https://your-production-domain.gov.ph

SECURE_SSL_REDIRECT=true
SECURE_PROXY_SSL_HEADER=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true

# Enable only after final HTTPS domain is stable.
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=false

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=client-production-sender@gmail.com
EMAIL_HOST_PASSWORD=client-google-app-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=RDC Portal <client-production-sender@gmail.com>
CONTACT_RECEIVER_EMAIL=client-receiver@example.com
```

## Render Backend Commands

Create a Render Web Service using `backend/` as the service root.

Build command:

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
```

Start command:

```bash
gunicorn rdc_site.wsgi:application --bind 0.0.0.0:$PORT
```

After deploy, run:

```bash
python manage.py migrate --noinput
```

Health check:

```text
https://your-render-service.onrender.com/api/health/
```

## Vercel Frontend Env

Create a Vercel project using `frontend/` as the project root.

Required Vercel environment variable:

```text
VITE_API_BASE_URL=https://your-render-service.onrender.com/api
```

Install command:

```bash
npm ci --legacy-peer-deps
```

Build command:

```bash
npm run build
```

Output directory:

```text
dist
```

The `frontend/vercel.json` rewrite sends direct route refreshes back to `index.html`, so routes like `/login` and `/employee/dashboard` work after deployment.

## Django Deploy Check Policy

Run this locally from the repository root to simulate staging deployment settings without using real secrets:

```powershell
$env:SECRET_KEY="deploy-check-dummy-secret-key-with-more-than-50-characters-2026"
$env:DEBUG="False"
$env:ALLOWED_HOSTS="example.com"
$env:CORS_ALLOWED_ORIGINS="https://example.com"
$env:CSRF_TRUSTED_ORIGINS="https://example.com"
$env:FRONTEND_BASE_URL="https://example.com"
$env:SECURE_SSL_REDIRECT="True"
$env:SESSION_COOKIE_SECURE="True"
$env:CSRF_COOKIE_SECURE="True"
$env:SECURE_PROXY_SSL_HEADER="True"
$env:SECURE_HSTS_SECONDS="0"
python backend/manage.py check --deploy
```

Intentional staging warning:

- `security.W004`: HSTS is disabled for first staging deploy.

Unexpected warnings should be fixed before production. For production, set `SECURE_HSTS_SECONDS=31536000` only after the final HTTPS domain is stable.

## Optional Local Artifact Cleanup

These commands remove generated local artifacts only. They must not remove `.env` files or database files.

PowerShell:

```powershell
Remove-Item -Recurse -Force frontend/dist, backend/staticfiles -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

Do not automate deletion of:

- `.env`
- `backend/.env`
- `frontend/.env`
- `*.sqlite3`
- database dumps or backups

## Verification Checklist

Before client testing:

```bash
cd frontend
npm run lint
npm run build

cd ../backend
python manage.py check
python manage.py migrate --check
python manage.py check --deploy
```

Manual smoke tests:

- Public home page loads.
- Public dashboard fetches data from Render API.
- Public endpoints work without JWT.
- RDC Portal login works.
- Django admin static files load.
- Account creation email sends.
- Password setup link opens the Vercel frontend.
- Contributor save/submit workflow works.
- Validator review workflow works.

## Docker Fallback

For local production-like testing:

```bash
docker compose up --build
```

Docker is not the primary Render deployment path, but it should continue to build successfully for staging/fallback.

## Uploads and Persistent Files

Render local disk is not permanent unless a paid persistent disk is configured.

If uploaded files become production-critical, use one of:

- Supabase Storage
- S3-compatible storage
- Cloudinary for image-only assets

Do not rely on temporary Render filesystem storage for permanent public records.
