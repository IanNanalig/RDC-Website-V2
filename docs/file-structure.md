# File Structure Notes

The repository is intentionally split into two application roots:

```text
backend/   Django project and API
frontend/  React + Vite client
```

Django app code remains in `backend/projects` for now. Moving it to `backend/apps/projects` is deferred because it can affect app labels, migrations, `AUTH_USER_MODEL`, and import paths.

Generated/local-only files are ignored:

- frontend build output
- Node dependencies
- Python virtual environments
- collected Django static files
- local SQLite database
- real environment files
