#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker Desktop no esta iniciado." >&2
  exit 1
fi

if [ ! -f .env.postgres ]; then
  umask 077
  db_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  cat > .env.postgres <<EOF
POSTGRES_DB=casarent_dev
POSTGRES_USER=casarent_dev
POSTGRES_PASSWORD=${db_password}
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
EOF
  chmod 600 .env.postgres
  echo "Se creo .env.postgres con credenciales aleatorias y permisos 0600."
fi

docker compose -f compose.dev.yml up --detach

echo "Esperando PostgreSQL..."
for _ in $(seq 1 30); do
  if docker compose -f compose.dev.yml exec -T db sh -c \
    'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    echo "PostgreSQL disponible en 127.0.0.1:5432."
    exit 0
  fi
  sleep 1
done

echo "ERROR: PostgreSQL no quedo saludable." >&2
docker compose -f compose.dev.yml ps >&2
exit 1
