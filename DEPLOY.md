Deployment checklist

1. Environment & Secrets

- Set these env vars in your host/CI/secret manager:
  - `SECRET_KEY` (must be set in production)
  - `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
  - `FRONTEND_BASE_URL`
  - `SENTRY_DSN` (optional)
  - `TURNSTILE_SECRET_KEY` (optional)
  - `DJANGO_ALLOWED_HOSTS` or set `ALLOWED_HOSTS` in env

2. Static assets

- We found multiple large images and documents in `src/assets` and `public`.
- Recommended actions:
  - Compress images with `jpegoptim`/`pngquant` or use a Node tool such as `imagemin`.
  - Optimize PDFs with `ghostscript`:

    gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook -dNOPAUSE -dQUIET -dBATCH -sOutputFile=out.pdf in.pdf

  - Offload large files (PDFs, high-res images) to object storage (S3) or a CDN and update links.

3. Build & container

- Use the provided `Dockerfile` (multi-stage) and `docker-compose.yml` for local production-like testing.
- CI builds and pushes images to GHCR; configure `secrets.GITHUB_TOKEN` and `secrets.DJANGO_SECRET_KEY`.

4. Monitoring

- Add Sentry integration for Django and the frontend. Configure `SENTRY_DSN`.

5. CI

- CI runs lint, frontend build, backend migrations, a smoke test, then full tests. Fixes to lint/tests will fail CI.

6. Run scans

- Use `python tools/scan_large_assets.py --min-mb 0.5` to list files >= 0.5 MB.
