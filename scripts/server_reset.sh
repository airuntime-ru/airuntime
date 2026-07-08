#!/usr/bin/env bash
set -euo pipefail

cd /home/airuntime

echo "==> Pull latest code"
git pull origin main

echo "==> Stop stack"
docker compose -f docker-compose.prod.yml --env-file .env down

echo "==> Drop postgres volume (fresh database)"
docker volume rm airuntime_postgres_data || true

echo "==> Rebuild and start"
docker compose -f docker-compose.prod.yml --env-file .env up -d --build --remove-orphans

echo "==> Wait for postgres"
sleep 8

echo "==> Backend alembic migrations"
docker compose -f docker-compose.prod.yml --env-file .env exec -T backend alembic upgrade head

echo "==> Django admin migrations"
docker compose -f docker-compose.prod.yml --env-file .env exec -T django-admin python manage.py migrate --noinput

echo "==> Ensure django superuser"
docker compose -f docker-compose.prod.yml --env-file .env exec -T django-admin python manage.py ensure_superuser

echo "==> Service status"
docker compose -f docker-compose.prod.yml --env-file .env ps

echo "==> Health checks"
curl -sk https://api.airuntime.ru/health || true
curl -skI https://admin.airuntime.ru/ || true
curl -skI https://airuntime.ru/ || true

echo "Done."
