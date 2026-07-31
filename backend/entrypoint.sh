#!/bin/sh
# Arranque del backend: pesos ML (idempotente) → migraciones → proceso principal.
set -e

echo "[entrypoint] Descargando / verificando modelos ML…"
python manage.py download_ml_models

echo "[entrypoint] Aplicando migraciones…"
python manage.py migrate --noinput

echo "[entrypoint] Iniciando: $*"
exec "$@"
