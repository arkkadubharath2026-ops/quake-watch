#!/bin/sh
# Container entrypoint: web | worker | beat | <any command>
set -eu

case "${1:-web}" in
  web)
    python manage.py migrate --noinput
    python manage.py arango_migrate
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout 60 \
      --access-logfile - ;;
  worker)
    exec celery -A config worker --loglevel "${QW_LOG_LEVEL:-INFO}" --concurrency "${CELERY_CONCURRENCY:-2}" ;;
  beat)
    exec celery -A config beat --loglevel "${QW_LOG_LEVEL:-INFO}" --schedule /tmp/celerybeat-schedule ;;
  *)
    exec "$@" ;;
esac
