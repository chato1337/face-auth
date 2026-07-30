# Face-Auth

Servicio de autenticación biométrica SSO multi-tenant.

> Diseño: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Plan: [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md)

## Requisitos

- Docker + Docker Compose
- [Python 3.11](https://www.python.org/) + [pipenv](https://pipenv.pypa.io/)
- [bun](https://bun.sh/) (frontend)
- En macOS/Linux local, para compilar partes del stack biométrico fuera de Docker puede hacer falta `cmake` y librerías OpenGL (`libgl`). En la imagen Docker ya están instaladas (ver `backend/Dockerfile`).

## Arranque rápido (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Servicios:

| Servicio  | URL                     |
|-----------|-------------------------|
| Frontend  | http://localhost:5173   |
| Backend   | http://localhost:8000   |
| Postgres  | localhost:5433          |

> Si ya tienes Postgres nativo en `:5432`, el compose mapea el contenedor a **5433** a propósito.

## Desarrollo local (híbrido)

### 1. Base de datos

```bash
docker compose up -d db
```

### 2. Backend

```bash
cd backend
pipenv install --dev          # crea .venv/ y usa Pipfile.lock
cp ../.env.example ../.env    # si aún no existe
pipenv run python manage.py migrate
pipenv run python manage.py runserver 0.0.0.0:8000
```

### 3. Frontend

```bash
cd frontend
bun install
bun run dev
```

## Notas

- `backend/Pipfile.lock` **sí se versiona** (builds reproducibles).
- Pesos ML viven en `backend/apps/biometrics/ml_models/` y están en `.gitignore`; se descargan con `download_ml_models`.
- La extensión `pgvector` se habilita automáticamente en la primera migración (`apps/tenants/migrations/0001_enable_pgvector.py`).
- **MediaPipe ≥ 1.0** ya no expone `mp.solutions` (Face Mesh clásico). El liveness activo usa **Face Landmarker (Tasks API)**; el archivo `face_landmarker.task` se descarga con verificación SHA-256.
- **MiniFASNetV2.onnx** puede requerir colocación manual si las URLs de descarga fallan. En ese caso usa `--mock-passive` en `demo_biometric_flow` para probar enroll/auth sin el clasificador pasivo.
- Aún **no hay endpoints HTTP** del pipeline biométrico; eso llega en la Fase 3 (OpenAPI & contratos). Hasta entonces se valida vía management commands y tests unitarios.

## Backend — Fase 2 (biometría)

```bash
cd backend
# Descargar pesos (Face Landmarker, buffalo_s, MiniFASNet si está disponible)
pipenv run python manage.py download_ml_models

# Crear tenant de prueba
pipenv run python manage.py create_application --name "Demo" \
  --redirect-uri "http://localhost:3000/callback"

# Demo enroll+auth con videos locales (usa --mock-passive si aún no hay MiniFASNetV2.onnx)
pipenv run python manage.py demo_biometric_flow \
  --app-id app_XXX \
  --enroll-video /path/enroll.mp4 \
  --auth-video /path/auth.mp4 \
  --spoof-video /path/static_photo.mp4 \
  --mock-passive

# Tests unitarios del pipeline
pipenv run pytest tests/unit/test_biometric_pipeline.py -v
```
