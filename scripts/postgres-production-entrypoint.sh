#!/usr/bin/env sh
set -eu
# PostgreSQL requires its private key to be owned by the server user.
cp /run/certs/server.crt /tmp/postgres-server.crt
cp /run/certs/server.key /tmp/postgres-server.key
chown postgres:postgres /tmp/postgres-server.crt /tmp/postgres-server.key
chmod 600 /tmp/postgres-server.key
exec /usr/local/bin/docker-entrypoint.sh postgres \
  -c ssl=on \
  -c ssl_cert_file=/tmp/postgres-server.crt \
  -c ssl_key_file=/tmp/postgres-server.key
