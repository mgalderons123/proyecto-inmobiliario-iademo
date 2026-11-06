#!/usr/bin/env sh
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ "${DJANGO_SETTINGS_MODULE:-}" = "PRY_INMOB.settings_production" ]; then
  exec /bin/sh /app/scripts/production-entrypoint.sh
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

if [ "${QA_SEED_DATA:-True}" = "True" ]; then
  python manage.py seed_qa
fi

exec gunicorn PRY_INMOB.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-60}" \
  --access-logfile - \
  --error-logfile -
