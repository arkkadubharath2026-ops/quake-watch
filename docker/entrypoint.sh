#!/bin/sh
# Container entrypoint: web | worker | scheduler | <any command>
# worker/scheduler replace Celery worker/beat: jobs and schedules live in ArangoDB (apps.jobs).
set -eu

case "${1:-web}" in
  web)
    python manage.py arango_migrate
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout 60 \
      --access-logfile - ;;
  worker)
    exec python manage.py run_worker --concurrency "${QW_WORKER_CONCURRENCY:-2}" ;;
  scheduler|beat)
    exec python manage.py run_scheduler ;;
  *)
    exec "$@" ;;
esac
