# Multi-stage Dockerfile: builds frontend, installs backend deps, collects static, runs Gunicorn

# Build frontend
FROM node:20-alpine as node-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --silent
COPY . .
RUN npm run build

# Final image
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# System deps for Pillow and others (if needed)
RUN apt-get update && apt-get install -y build-essential libpq-dev gcc --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy backend source
COPY backend ./backend

# Copy built frontend into backend staticfiles
COPY --from=node-build /app/dist ./backend/staticfiles

WORKDIR /app/backend
# Collect static files
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000
CMD ["gunicorn", "rdc_site.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
