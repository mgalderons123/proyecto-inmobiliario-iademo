#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ "${1:-}" != "--yes" ]; then
  read -r -p "Esto eliminará SOLO los volúmenes de Casarent QA. Continuar [y/N]? " answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *) echo "Cancelado."; exit 0 ;;
  esac
fi

docker compose -f compose.qa.yml down --volumes --remove-orphans
echo "Datos y volúmenes QA eliminados. .env.qa se conservó."
