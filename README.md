# RDC-NCR Website

Public RDC-NCR website plus RDC Portal for contributor submissions, validator review, admin controls, and public dashboard reporting.

## Repository Structure

```text
backend/    Django API, portal workflow, public APIs, migrations, and backend tests
frontend/   React + TypeScript + Vite public website and portal UI
scripts/    Maintenance helpers for asset optimization
docs/       Deployment, database, API, and structure notes
```

## Local Development

### Backend

```powershell
cd backend
Copy-Item .env.example .env
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py runserver
```

### Frontend

```powershell
cd frontend
Copy-Item .env.example .env
npm ci --legacy-peer-deps
npm run dev
```

The frontend expects `VITE_API_BASE_URL` to point to the Django API, usually `http://127.0.0.1:8000/api` locally.

## Verification

```powershell
cd frontend
npm run build
npm run lint

cd ..\backend
.\venv\Scripts\python manage.py check
.\venv\Scripts\python manage.py test projects
```

## Deployment Notes

See `docs/deployment.md` for Docker, CI, environment, static files, and production checklist guidance.

## Security Rules

Do not commit real `.env` files, local databases, virtual environments, `node_modules`, build output, or collected static files. Use `.env.example` files for documented configuration only.
