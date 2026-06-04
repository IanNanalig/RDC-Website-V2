# Database Notes

The production database should be PostgreSQL. SQLite is only a local fallback when PostgreSQL environment variables are not configured or `FORCE_SQLITE=1` is set.

## Important Rules

- Never commit `backend/db.sqlite3`.
- Back up PostgreSQL before migrations or cleanup work.
- Use `backend/.env.example` for required database variable names.

## Common Commands

```powershell
cd backend
.\venv\Scripts\python manage.py showmigrations
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py migrate --check
```
