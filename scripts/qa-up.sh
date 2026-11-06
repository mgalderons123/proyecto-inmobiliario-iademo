#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker Desktop no está iniciado." >&2
  echo "Iniciá Docker Desktop y volvé a ejecutar ./scripts/qa-up.sh" >&2
  exit 1
fi

if [ ! -f .env.qa ]; then
  umask 077
  secret_key="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
  pii_key="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  jwt_key="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
  db_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  super_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  admin_a_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  admin_b_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  tenant_a_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  tenant_b_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"

  cat > .env.qa <<EOF
DJANGO_SETTINGS_MODULE=PRY_INMOB.settings_qa
DEBUG=False
SECRET_KEY=${secret_key}
PII_ENCRYPTION_KEY=${pii_key}
JWT_SIGNING_KEY=${jwt_key}
ALLOWED_HOSTS=localhost,127.0.0.1,web
CSRF_TRUSTED_ORIGINS=http://localhost:4100,http://127.0.0.1:4100
RATELIMIT_ENABLE=True
POSTGRES_DB=casarent_qa
POSTGRES_USER=casarent_qa
POSTGRES_PASSWORD=${db_password}
POSTGRES_HOST=db
POSTGRES_PORT=5432
REDIS_URL=redis://redis:6379/0
EMAIL_HOST=mailpit
EMAIL_PORT=1025
DEFAULT_FROM_EMAIL=qa@casarent.test
PUBLIC_MEDIA_ROOT=/app/data/public
PRIVATE_MEDIA_ROOT=/app/data/private
DATA_UPLOAD_MAX_MEMORY_SIZE=26214400
FILE_UPLOAD_MAX_MEMORY_SIZE=5242880
QA_SEED_DATA=True
QA_SUPERADMIN_PASSWORD=${super_password}
QA_ADMIN_A_PASSWORD=${admin_a_password}
QA_ADMIN_B_PASSWORD=${admin_b_password}
QA_TENANT_A_PASSWORD=${tenant_a_password}
QA_TENANT_B_PASSWORD=${tenant_b_password}
EOF
  chmod 600 .env.qa
  echo "Se creó .env.qa con credenciales aleatorias y permisos 0600."
fi

docker compose -f compose.qa.yml up --build --detach

echo "Esperando que Casarent QA esté saludable..."
for _ in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:4100/health/ >/dev/null; then
    echo "Casarent QA: http://localhost:4100"
    echo "Mailpit:     http://localhost:8025"
    echo "Credenciales QA: .env.qa"
    exit 0
  fi
  sleep 2
done

echo "ERROR: el servicio QA no quedó saludable." >&2
docker compose -f compose.qa.yml ps >&2
docker compose -f compose.qa.yml logs web >&2
exit 1
