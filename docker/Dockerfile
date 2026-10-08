# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ARG APP_VERSION=dev
ENV QW_APP_VERSION=${APP_VERSION}

# collectstatic needs importable settings; placeholder values are build-time only.
# /data/auth: mount point of the legacy SQLite volume (read-only) until it is retired after
# `migrate_auth_to_arango` is verified (ADR-015). Nothing at runtime reads it.
RUN QW_SECRET_KEY=build-only-secret-key-not-used-at-runtime-000000000000 \
    QW_ARANGO_PASSWORD=build-only \
    QW_ENV=development \
    python manage.py collectstatic --noinput \
 && useradd --uid 10001 --create-home quakewatch \
 && mkdir -p /data/auth && chown -R quakewatch /data /app \
 && chmod +x /app/docker/entrypoint.sh

USER quakewatch
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["web"]
