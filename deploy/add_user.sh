#!/usr/bin/env sh
# Add or replace a user:  ./add_user.sh <ID> <ROLE> <PIN> "<Name>"
# Roles: Patrol (captures), SSE / ADEE / DEE / SrDEE (review and sign), Admin.
set -e
cd "$(dirname "$0")"
docker compose run --rm rvi python -m app.ohe.auth add "$@"
