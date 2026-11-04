"""Gunicorn lifecycle hooks for production responsiveness."""

import os
import time


# Inline Validator document analysis performs bounded extraction and a Groq
# request inside an authenticated API request. Keep the web worker alive long
# enough for the configured 30-second provider timeout plus normal database
# work. Render/Vercel proxy limits still apply independently.
timeout = max(30, int(os.environ.get("GUNICORN_TIMEOUT", "120")))
graceful_timeout = max(timeout + 15, int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", str(timeout + 15))))


def _enabled(name, default="true"):
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def post_worker_init(worker):
    """Pay the managed-Postgres connection cost before the worker accepts user traffic."""
    if not _enabled("WARM_DATABASE_ON_START"):
        return

    from django.db import connections

    for alias in connections:
        connection = connections[alias]
        started_at = time.perf_counter()
        try:
            connection.ensure_connection()
            duration_ms = (time.perf_counter() - started_at) * 1000
            worker.log.info("Database connection warmed alias=%s duration_ms=%.1f", alias, duration_ms)
        except Exception:
            # A temporary database outage must not create a permanent worker restart loop.
            connection.close()
            worker.log.exception("Database warmup failed alias=%s; the first request will retry", alias)
