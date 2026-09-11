#!/bin/sh
set -e

mkdir -p /app/logs /app/sessions

if [ -d /app/app/db/migrations ] && [ -f /app/alembic.ini ]; then
  echo "Running database migrations..."
  uv run alembic upgrade head
else
  echo "No Alembic migrations directory; starting with application-managed schema initialization."
fi

exec "$@"
