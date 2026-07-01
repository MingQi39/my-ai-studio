#!/bin/sh
set -e

mkdir -p /app/data/uploads

echo "Running database migrations..."
alembic upgrade head

echo "Starting backend..."
exec "$@"
