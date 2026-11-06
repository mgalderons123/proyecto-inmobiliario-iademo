#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
docker compose -f compose.qa.yml exec web python manage.py seed_qa
