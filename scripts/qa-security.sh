#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker Desktop no está iniciado." >&2
  exit 1
fi

if [ ! -f .env.qa ]; then
  echo "ERROR: falta .env.qa. Ejecutá primero ./scripts/qa-up.sh" >&2
  exit 1
fi

docker compose -f compose.qa.yml run --rm \
  -e DJANGO_SETTINGS_MODULE=PRY_INMOB.settings_test \
  -e QA_SEED_DATA=False \
  web sh -c '
    python manage.py check &&
    bandit -q -r apps PRY_INMOB -x "*/migrations/*" &&
    pip-audit --skip-editable
  '
