# Deployment Guide

Primary target:

- Frontend: Vercel
- Backend API: Render Web Service
- Database: Supabase PostgreSQL

Docker remains supported for local production-like testing and fallback VPS deployment.

## 1. Supabase Database

Create a Supabase project and copy the PostgreSQL connection string.

Use the pooled or direct connection string required by the deployment tier, then set it on Render as:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
DATABASE_SSL_REQUIRE=true
```

Rules:

- Production must use PostgreSQL.
- SQLite is local fallback only.
- Back up Supabase before migrations.
- Do not commit database dumps or `.env` files.

## 2. Render Backend

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

Required Render environment variables:

```text
SECRET_KEY=
DEBUG=False
DATABASE_URL=
DATABASE_SSL_REQUIRE=true
ALLOWED_HOSTS=your-render-service.onrender.com
CORS_ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
CSRF_TRUSTED_ORIGINS=https://your-vercel-app.vercel.app
FRONTEND_BASE_URL=https://your-vercel-app.vercel.app
SECURE_PROXY_SSL_HEADER=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

Email variables:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=
CONTACT_RECEIVER_EMAIL=
```

Optional:

```text
SENTRY_DSN=
TURNSTILE_SECRET_KEY=
TURNSTILE_REQUIRED=false
```

After deploy, run:

```bash
python manage.py migrate --noinput
```

Health check:

```text
https://your-render-service.onrender.com/api/health/
```

## 3. Vercel Frontend

Create a Vercel project using `frontend/` as the project root.

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

Required Vercel environment variable:

```text
VITE_API_BASE_URL=https://your-render-service.onrender.com/api
```

The `frontend/vercel.json` rewrite sends direct route refreshes back to `index.html`, so routes like `/login` and `/employee/dashboard` work after deployment.

## 4. Verification Checklist

Before client testing:

```bash
npm run lint
npm run build
python manage.py check
python manage.py migrate --check
```

Manual smoke tests:

- Public home page loads.
- Public dashboard fetches data from Render API.
- RDC Portal login works.
- Django admin static files load.
- Account creation email sends.
- Password setup link opens the Vercel frontend.
- Contributor save/submit workflow works.
- Validator review workflow works.
- Public endpoints work without JWT.

## 5. Docker Fallback

For local production-like testing:

```bash
docker compose up --build
```

Docker is not the primary Render deployment path, but it should continue to build successfully for staging/fallback.

## 6. Uploads and Persistent Files

Render local disk is not permanent unless a paid persistent disk is configured.

If uploaded files become production-critical, use one of:

- Supabase Storage
- S3-compatible storage
- Cloudinary for image-only assets

Do not rely on temporary Render filesystem storage for permanent public records.
