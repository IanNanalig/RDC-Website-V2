# Database Notes

The production database should be Supabase PostgreSQL. SQLite is only a local fallback when PostgreSQL environment variables are not configured or `FORCE_SQLITE=1` is set.

## Important Rules

- Never commit `backend/db.sqlite3`.
- Back up PostgreSQL before migrations or cleanup work.
- Prefer `DATABASE_URL` for Supabase/Render deployment.
- Use `backend/.env.example` for required database variable names.

## Common Commands

```powershell
cd backend
.\venv\Scripts\python manage.py showmigrations
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py migrate --check
```

## Supabase Connection

Set this on Render:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require
DATABASE_SSL_REQUIRE=true
```

Use Supabase dashboard backups or `pg_dump` before risky migrations.
