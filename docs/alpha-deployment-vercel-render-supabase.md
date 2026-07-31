# Alpha Deployment Guide: Vercel + Render + Supabase

This guide deploys:

- Frontend: Vercel
- Backend API: Render Web Service
- Database: Supabase PostgreSQL

Use this for alpha testing after the latest security and CI fixes are on `main`.

References:

- Vercel Git deployments: https://vercel.com/docs/git
- Vercel Vite deployments: https://vercel.com/docs/frameworks/frontend/vite
- Render Django deployments: https://render.com/docs/deploy-django
- Render environment variables: https://render.com/docs/configure-environment-variables
- Supabase Postgres connections: https://supabase.com/docs/guides/database/connecting-to-postgres

## 1. Pre-Deployment Checks

From the repository root, verify the code that will deploy:

```powershell
git remote -v
git status --short --branch
```

Expected remote:

```text
https://github.com/IanNanalig/RDC-Website-V2.git
```

Expected branch for deployment:

```text
main
```

Run local checks:

```powershell
cd frontend
npm ci --legacy-peer-deps
npm audit --audit-level=moderate
npm run lint
npm run build

cd ..\backend
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe manage.py test projects cms
```

Do not commit local-only files:

- `backend/.env`
- `frontend/.env`
- `backend/db.sqlite3`
- `backend/cms/2026/07/Sample.pdf`, unless it is intentionally part of the site content
- `frontend/dist`
- `backend/staticfiles`
- `node_modules`
- `backend/venv`

## 2. Create Supabase Database

1. Go to Supabase and create a new project.
2. Save the database password securely.
3. In the Supabase dashboard, open the database connection settings.
4. Copy a PostgreSQL connection string.
5. For Render, prefer the Supabase pooler session-mode connection if the direct database hostname is not reachable from Render.
6. Ensure the connection string includes SSL:

```text
?sslmode=require
```

Render environment value:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
DATABASE_SSL_REQUIRE=true
```

For alpha testing, use one Supabase project dedicated to alpha. Do not share the alpha database with production client data.

## 3. Deploy Backend On Render

1. Open Render Dashboard.
2. Create a new Web Service.
3. Connect GitHub repository:

```text
IanNanalig/RDC-Website-V2
```

4. Use these service settings:

```text
Name: rdc-website-v2-api-alpha
Language: Python 3
Branch: main
Root Directory: backend
Build Command: pip install -r requirements.txt && python manage.py collectstatic --noinput
Start Command: gunicorn rdc_site.wsgi:application --bind 0.0.0.0:$PORT
```

5. Add Render environment variables:

```text
SECRET_KEY=generate-a-long-random-secret-at-least-50-characters
DEBUG=False
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
DATABASE_SSL_REQUIRE=true
ALLOWED_HOSTS=rdc-website-v2-api-alpha.onrender.com
CORS_ALLOWED_ORIGINS=https://your-vercel-alpha-url.vercel.app
CSRF_TRUSTED_ORIGINS=https://your-vercel-alpha-url.vercel.app
FRONTEND_BASE_URL=https://your-vercel-alpha-url.vercel.app

SECURE_SSL_REDIRECT=true
SECURE_PROXY_SSL_HEADER=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=false
SECURE_HSTS_PRELOAD=false

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-alpha-sender@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=RDC Portal <your-alpha-sender@gmail.com>
CONTACT_RECEIVER_EMAIL=your-test-receiver@example.com

TURNSTILE_REQUIRED=false
TURNSTILE_SECRET_KEY=
SENTRY_DSN=
JWT_ACCESS_HOURS=8
JWT_REFRESH_DAYS=7
```

6. Deploy the service.
7. After the first successful deploy, run migrations from Render Shell:

```bash
python manage.py migrate --noinput
```

8. Optional but useful for alpha: create an admin account from Render Shell:

```bash
python manage.py createsuperuser
```

9. Copy the Render service URL. It should look like:

```text
https://rdc-website-v2-api-alpha.onrender.com
```

## 4. Deploy Frontend On Vercel

1. Open Vercel Dashboard.
2. Add a new project from GitHub.
3. Select repository:

```text
IanNanalig/RDC-Website-V2
```

4. Configure project settings:

```text
Framework Preset: Vite
Root Directory: frontend
Install Command: npm ci --legacy-peer-deps
Build Command: npm run build
Output Directory: dist
```

5. Add Vercel environment variable:

```text
VITE_API_BASE_URL=https://rdc-website-v2-api-alpha.onrender.com/api
```

6. Deploy the frontend.
7. Copy the Vercel deployment URL. It should look like:

```text
https://your-vercel-alpha-url.vercel.app
```

## 5. Connect Frontend And Backend

After Vercel gives you the final alpha URL, go back to Render and update:

```text
CORS_ALLOWED_ORIGINS=https://your-vercel-alpha-url.vercel.app
CSRF_TRUSTED_ORIGINS=https://your-vercel-alpha-url.vercel.app
FRONTEND_BASE_URL=https://your-vercel-alpha-url.vercel.app
```

If you later add a custom domain, include both the Vercel preview URL and the custom domain during alpha:

```text
CORS_ALLOWED_ORIGINS=https://your-vercel-alpha-url.vercel.app,https://alpha.your-domain.gov.ph
CSRF_TRUSTED_ORIGINS=https://your-vercel-alpha-url.vercel.app,https://alpha.your-domain.gov.ph
```

Save the Render environment changes and redeploy the backend.

## 6. Alpha Smoke Test

Check backend:

```text
https://rdc-website-v2-api-alpha.onrender.com/api/
```

Then test the Vercel site:

1. Home page loads.
2. Public news and CMS pages load.
3. Public projects/events load from the Render API.
4. Login page loads.
5. Admin account can sign in.
6. Dashboard pages load without CORS errors.
7. Employee/contributor project submission works.
8. Validator review workflow works.
9. Admin project controls work.
10. Password reset/setup email links open the Vercel frontend.
11. Uploaded CMS media appears after publishing.
12. Direct browser refresh works on frontend routes like `/login` and portal pages.

Browser DevTools should show no blocked CORS requests and no failed API calls caused by wrong hostnames.

## 7. Alpha Security Checklist

Before sending the alpha link to testers:

1. Confirm Render has `DEBUG=False`.
2. Confirm Render has a real `SECRET_KEY`, not a placeholder.
3. Confirm Supabase connection uses SSL.
4. Confirm Vercel `VITE_API_BASE_URL` points to Render `/api`.
5. Confirm Render CORS/CSRF origins match the actual Vercel URL.
6. Confirm `.env` files are not committed.
7. Confirm `npm audit --audit-level=moderate` reports 0 vulnerabilities.
8. Confirm `pip-audit -r backend/requirements.txt` reports no known vulnerabilities.
9. Keep `SECURE_HSTS_SECONDS=0` for first alpha unless the final HTTPS domain is stable.
10. Do not store permanent production uploads on Render's temporary filesystem.

## 8. Known Alpha Caveats

Render filesystem storage is not permanent unless a persistent disk is configured. CMS uploads may disappear across rebuilds or service resets if stored only on Render local disk.

For durable uploads before production, move media storage to one of:

- Supabase Storage
- S3-compatible object storage
- Cloudinary for image-only workflows

HSTS is intentionally disabled for alpha. Enable it only after the final production HTTPS domain is stable:

```text
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=false
```

## 9. Redeploy After Updates

For future code changes:

1. Push to `main`.
2. Wait for GitHub Actions to pass.
3. Confirm Render deploy succeeds.
4. Confirm Vercel deploy succeeds.
5. Run the smoke test again.

If deployment fails:

1. Check GitHub Actions first.
2. Check Render build logs.
3. Check Render runtime logs.
4. Check Vercel build logs.
5. Check browser DevTools network errors.

