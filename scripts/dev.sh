#!/usr/bin/env bash
# Bootstrap the local PostgreSQL DB and start the development server.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example first:" >&2
  echo "  cp .env.example .env" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "ERROR: .venv not found. Create it first:" >&2
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import psycopg" >/dev/null 2>&1; then
  python -m pip install -r requirements.txt
fi

./scripts/postgres-up.sh

set -a
source .env.postgres
set +a

python manage.py migrate --noinput

python manage.py ensure_superuser

python manage.py runserver_dev 0.0.0.0:4000 "$@"
