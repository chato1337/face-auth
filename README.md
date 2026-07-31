# Face-Auth

**SSO biométrico multi-tenant.** Face-Auth autentica personas con un clip corto de video — sin contraseñas. Las aplicaciones cliente delegan login y registro; reciben un token firmado cuando el usuario se autentica.

> Arquitectura: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · Integración: [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md) · Operaciones: [`docs/OPERATIONS.md`](docs/OPERATIONS.md)

---

## Qué resuelve

| Problema | Enfoque Face-Auth |
|----------|-------------------|
| Contraseñas olvidadas / robadas | Login con rostro + liveness (anti-spoofing activo y pasivo) |
| Integrar biometría en cada app | SSO hosted: rediriges al frontend y recibes un token en tu callback |
| Varias apps, mismos usuarios | Multi-tenant estricto: cada `app_id` aísla usuarios y embeddings |
| Fotos / pantallas / deepfakes básicos | Pipeline: MediaPipe (parpadeo/pose) + MiniFASNetV2 + matching con pgvector |

La captura en el navegador es pasiva (“dashcam”): la cámara detecta el rostro alineado y un parpadeo dispara el envío. La validación biométrica real ocurre siempre en el servidor (Zero-Trust).

---

## Cómo se usa (producto)

### Para apps cliente (integradores)

1. Un operador da de alta tu tenant (`app_id`, `api_key`, whitelist de `redirect_uris`).
2. Rediriges al usuario a Face-Auth:

```
<FACEAUTH_WEB>/login?app_id=<APP_ID>&redirect_uri=<CALLBACK>
<FACEAUTH_WEB>/register?app_id=<APP_ID>&redirect_uri=<CALLBACK>
```

3. Tras éxito, Face-Auth redirige a tu callback con un JWT de un solo uso (`token`).
4. Tu backend verifica el token con `POST /api/v1/auth/token/verify/` y el header `X-Api-Key`.

Detalle completo: [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md). También puedes llamar la API REST directa si tu app captura el video (móvil nativo, UI propia).

### Para operadores de plataforma

Panel SPA en `/admin/login` (usuario Django con `is_superuser`): alta de tenants, rotación de `api_key`, listado/edición de usuarios y soft-deactivate de perfiles biométricos. Ver [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

---

## Capacidades

- **Login y registro biométrico** con captura pasiva en el navegador (fallback manual disponible).
- **Anti-spoofing** activo (parpadeo / pose) + pasivo (ONNX MiniFASNetV2).
- **Matching facial** InsightFace `buffalo_s` (embedding 512-d) + búsqueda coseno con **pgvector** (índice HNSW), filtrada por tenant.
- **SSO** con JWT de un solo uso (`purpose=sso_redirect`, TTL ~2 min) + access/refresh de sesión.
- **API contract-first** (OpenAPI / Swagger / Redoc) y tipos TypeScript generados para el frontend.
- **Hardening**: rate limit por `app_id`+IP, whitelist exacta de `redirect_uri`, rotación de `api_key`, pool de modelos ML.
- **Panel admin** de plataforma separado del flujo SSO.

---

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Django + DRF, SimpleJWT, drf-spectacular, pipenv |
| Biometría | OpenCV, MediaPipe Face Landmarker, ONNXRuntime, InsightFace |
| Datos | PostgreSQL + pgvector |
| Frontend | Vite, React, TypeScript, TanStack Query, bun, shadcn/ui |

---

## Requisitos

- Docker + Docker Compose
- [Python 3.11](https://www.python.org/) + [pipenv](https://pipenv.pypa.io/)
- [bun](https://bun.sh/) (frontend)
- En macOS/Linux local, para compilar el stack biométrico fuera de Docker puede hacer falta `cmake` y librerías OpenGL (`libgl`). En la imagen Docker ya están instaladas (ver `backend/Dockerfile`).

---

## Arranque rápido (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Puertos por defecto (configurables en `.env` con `BACKEND_PORT` / `FRONTEND_PORT`):

| Servicio  | Variable | Default | URL |
|-----------|----------|---------|-----|
| Frontend  | `FRONTEND_PORT` | `5173` | http://localhost:5173 |
| Backend   | `BACKEND_PORT` | `8000` | http://localhost:8000 |
| Postgres  | `POSTGRES_PORT` | `5433` | localhost:5433 |

> Si ya tienes Postgres nativo en `:5432`, el compose mapea el contenedor a **5433** a propósito.

API documentada: `http://localhost:${BACKEND_PORT}/api/docs/` · `/api/redoc/`

### Cambiar puertos / host del API

Todo se configura en el `.env` raíz (Vite lo lee vía `envDir` del monorepo):

```bash
BACKEND_PORT=8001
FRONTEND_PORT=5174
VITE_API_BASE_URL=http://192.168.1.10:8001   # host+puerto que ve el navegador
CORS_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174,http://192.168.1.10:5174
```

`VITE_API_BASE_URL` es la URL completa: Compose **no** la reescribe a `localhost`. Tras cambiar `.env`, reinicia Vite (`bun run dev` / `docker compose up`).

---

## Desarrollo local (híbrido)

### 1. Base de datos

```bash
docker compose up -d db
```

### 2. Backend

```bash
cd backend
pipenv install --dev
cp ../.env.example ../.env    # si aún no existe
pipenv run python manage.py migrate
pipenv run python manage.py download_ml_models
pipenv run python run_devserver.py   # respeta BACKEND_PORT del .env
```

Crear un superuser (panel admin) y un tenant de prueba:

```bash
pipenv run python manage.py createsuperuser
pipenv run python manage.py create_application --name "Demo" \
  --redirect-uri "http://localhost:3000/callback"
```

### 3. Frontend

```bash
cd frontend
bun install
bun run dev            # FRONTEND_PORT + VITE_API_BASE_URL desde el .env raíz
```

URLs útiles (defaults; sustituye el puerto si lo cambiaste y `app_XXXX` por el `app_id`):

| Flujo | URL |
|-------|-----|
| Login SSO | http://localhost:5173/login?app_id=app_XXXX |
| Registro SSO | http://localhost:5173/register?app_id=app_XXXX |
| Panel admin | http://localhost:5173/admin/login |

Opcional: `&redirect_uri=` debe coincidir **exactamente** con una URI whitelist del tenant.

Tras cambiar el OpenAPI del backend:

```bash
cd frontend && bun run generate:api
```

---

## API (resumen)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/applications/{app_id}/` | Validar tenant (público) |
| POST | `/api/v1/auth/login/` | Login biométrico (`multipart`: `app_id`, `video`, `redirect_uri?`) |
| POST | `/api/v1/auth/register/` | Registro biométrico (`multipart`: datos + `video`) |
| POST | `/api/v1/auth/token/refresh/` | Refrescar access token |
| POST | `/api/v1/auth/token/verify/` | Verificar token SSO del callback (server-to-server, `X-Api-Key`) |
| — | `/api/v1/admin/*` | Panel de operadores (JWT Django + `is_superuser`) |
| GET | `/api/docs/` · `/api/redoc/` · `/api/schema/` | OpenAPI |

Regenerar contrato y tests:

```bash
cd backend
pipenv run python manage.py spectacular --file schema.json --format openapi-json --fail-on-warn --validate
pipenv run pytest tests/integration/test_auth_api.py -v
```

Errores del pipeline HTTP: payload uniforme `{code, message, field}` (ver `docs/ARCHITECTURE.md` §3.3).

---

## Herramientas útiles (backend)

```bash
cd backend

# Demo enroll + auth con videos locales (--mock-passive si falta MiniFASNetV2.onnx)
pipenv run python manage.py demo_biometric_flow \
  --app-id app_XXX \
  --enroll-video /path/enroll.mp4 \
  --auth-video /path/auth.mp4 \
  --spoof-video /path/static_photo.mp4 \
  --mock-passive

# Rotar api_key de un tenant
pipenv run python manage.py rotate_api_key --app-id app_XXX --yes

# Benchmarks / evaluación
pipenv run python manage.py benchmark_pipeline
pipenv run python manage.py benchmark_vector_search
pipenv run python manage.py evaluate_liveness

# Tests del pipeline
pipenv run pytest tests/unit/test_biometric_pipeline.py -v
```

---

## Notas operativas

- Puertos: `BACKEND_PORT` / `FRONTEND_PORT` en `.env` (Compose, `run_devserver.py`, Vite).
- `backend/Pipfile.lock` **sí se versiona** (builds reproducibles).
- Pesos ML en `backend/apps/biometrics/ml_models/` (gitignored); se descargan con `download_ml_models`.
- La extensión `pgvector` se habilita en la primera migración (`apps/tenants/migrations/0001_enable_pgvector.py`).
- **MediaPipe ≥ 1.0** usa Face Landmarker (Tasks API); `face_landmarker.task` se descarga con verificación SHA-256.
- **MiniFASNetV2.onnx** puede requerir colocación manual si fallan las URLs; usa `--mock-passive` en `demo_biometric_flow` para probar sin el clasificador pasivo.
- En producción, rate limiting multi-worker requiere `REDIS_URL`.
- Datasets de evaluación: [`docs/datasets/README.md`](docs/datasets/README.md).
- CI: `.github/workflows/ci.yml` (lint + tests + coverage).

---

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md) | Integrar una app cliente (SSO hosted o API) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Monorepo, modelos, pipeline biométrico, panel admin |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Alta de tenants, rotación de claves, runbooks |
| [`docs/DASHCAM-FEATURE.md`](docs/DASHCAM-FEATURE.md) | Captura pasiva por parpadeo (cliente) |
| [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) | Plan de implementación por fases (estado del proyecto) |
| [`frontend/README.md`](frontend/README.md) | Detalle del SPA |

---

## Plan de desarrollo (fases)

El trabajo de implementación se organizó por fases. El estado actual, checklists y criterios de aceptación viven en [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md). Resumen:

| Fase | Tema | Estado |
|------|------|--------|
| 0 | Diseño | Completada |
| 1 | Infraestructura (Docker, pgvector, monorepo) | Completada |
| 2 | Backend core y pipeline biométrico | Completada |
| 3 | OpenAPI y contratos HTTP | Completada |
| 4 | Frontend SSO (login / registro) | Completada |
| 5 | Hardening, benchmarks, seguridad | Completada |
| 6 | Panel de administración | Implementada — revisión manual pendiente |
| 7 | Captura pasiva “Dashcam” | Implementada — prueba con cámara real pendiente |
| 8 | Verificación server-to-server de tokens SSO | Completada |

Para retomar desarrollo o validar una fase, usa el master plan; este README describe el producto y cómo operarlo.
