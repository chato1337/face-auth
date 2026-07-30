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
- Pesos ONNX / InsightFace viven en `backend/apps/biometrics/ml_models/` y están en `.gitignore` (se descargan en fases posteriores).
- La extensión `pgvector` se habilita automáticamente en la primera migración (`apps/tenants/migrations/0001_enable_pgvector.py`).
