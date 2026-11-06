#!/usr/bin/env sh
set -eu

export DJANGO_SETTINGS_MODULE=PRY_INMOB.settings_production

# Migrations and static collection belong to a single release job, not each worker.
exec gunicorn PRY_INMOB.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
