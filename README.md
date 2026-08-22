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

## Requisitos e instalación (local)

Hay dos formas de correr todo en local. **Recomendado:** Docker Compose (Postgres con `pgvector` incluido). **Híbrido / full nativo:** instalar herramientas en el host.

### Resumen de tecnologías

| Componente | Qué instalar | Notas |
|------------|--------------|--------|
| Contenedores | [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2 | Suficiente para el arranque rápido completo |
| Base de datos | **PostgreSQL 16** + extensión **[pgvector](https://github.com/pgvector/pgvector)** | Compose usa la imagen `pgvector/pgvector:pg16` (extensión ya incluida) |
| Backend runtime | [Python 3.11](https://www.python.org/) + [pipenv](https://pipenv.pypa.io/) | Fijado en `backend/Pipfile` |
| Frontend | [bun](https://bun.sh/) | Vite + React |
| Build biométrico (host) | `cmake`, compilador C/C++, OpenGL/`libgl`, OpenMP | Solo si instalas el backend **fuera** de Docker |
| Pesos ML | Descarga vía `download_ml_models` | Face Landmarker, InsightFace `buffalo_s`, MiniFASNetV2 (no van en git) |
| CPU | **AES-NI** recomendado | MediaPipe (liveness activo) puede matar el proceso (`SIGILL`) en CPUs sin AES (p. ej. Celeron N2930). Comprueba: `grep -m1 -o aes /proc/cpuinfo` |

Opcional en producción / multi-worker: **Redis** (`REDIS_URL`) para rate limiting compartido.

### Opción A — Solo Docker (menos fricción)

Instala Docker Desktop (macOS/Windows) o Docker Engine + Compose (Linux). No hace falta Postgres ni Python en el host.

```bash
cp .env.example .env
docker compose up --build
```

La imagen `db` ya trae Postgres 16 + `pgvector`. El backend descarga modelos ML en el entrypoint.

### Opción B — Híbrido (Postgres en Docker, apps en el host)

#### 1. Herramientas de aplicación

```bash
# Python 3.11 (ej. pyenv / apt / Homebrew)
python3.11 --version

# pipenv
pip install pipenv
# o: brew install pipenv

# bun (frontend)
curl -fsSL https://bun.sh/install | bash
```

#### 2. Dependencias de sistema (backend nativo)

Necesarias para compilar/ejecutar OpenCV, MediaPipe, InsightFace y ONNX Runtime **en el host**:

**Debian / Ubuntu**

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  cmake \
  libgl1 \
  libglib2.0-0 \
  libgomp1 \
  curl
```

**macOS (Homebrew)**

```bash
xcode-select --install   # si aún no tienes CLT
brew install cmake
```

En la imagen Docker del backend estas librerías ya están (ver `backend/Dockerfile`).

#### 3. PostgreSQL + pgvector

**Recomendado (Compose):** no instales Postgres en el host.

```bash
docker compose up -d db
```

- Host: `localhost`
- Puerto host: `POSTGRES_PORT` (default **5433**) → contenedor interno `5432`
- Usuario / clave / DB: `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` (default `faceauth`)
- Extensión `vector`: la crea la migración `apps/tenants/migrations/0001_enable_pgvector.py`

**Postgres nativo en el host** (si no usas el servicio `db`):

1. Instala **PostgreSQL 16** (o compatible con la imagen del proyecto).
2. Instala la extensión **pgvector** para esa versión:
   - Debian/Ubuntu (paquete distro o [instrucciones oficiales](https://github.com/pgvector/pgvector#installation)):
     ```bash
     sudo apt-get install -y postgresql-16-pgvector
     # o compilar desde fuente contra tu pg_config
     ```
   - macOS: `brew install pgvector` (asócialo al Postgres de Homebrew).
3. Crea rol y base, y habilita la extensión:

```sql
CREATE USER faceauth WITH PASSWORD 'faceauth';
CREATE DATABASE faceauth OWNER faceauth;
\c faceauth
CREATE EXTENSION IF NOT EXISTS vector;
```

4. Ajusta el `.env` raíz:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432          # o el puerto de tu instancia
POSTGRES_USER=faceauth
POSTGRES_PASSWORD=faceauth
POSTGRES_DB=faceauth
```

Sin `pgvector` / `CREATE EXTENSION vector`, las migraciones y el matching facial fallan.

### Checklist antes del primer arranque híbrido

- [ ] Docker (al menos para `db`) **o** Postgres 16 + pgvector nativo
- [ ] Python 3.11 + pipenv
- [ ] bun
- [ ] `cmake` + libs de sistema (si el backend corre en el host)
- [ ] CPU con AES-NI si vas a ejercer liveness activo con MediaPipe
- [ ] `.env` copiado desde `.env.example`
- [ ] `pipenv install --dev` + `download_ml_models` + `migrate`
- [ ] `bun install` en `frontend/`

---

## Arranque rápido (Docker)

```bash
cp .env.example .env
docker compose up --build
```

El backend, al arrancar (`entrypoint.sh`), ejecuta `download_ml_models` (pesos Face Landmarker, buffalo_s, MiniFASNet) y luego las migraciones. La primera subida puede tardar varios minutos por la descarga. En build de imagen también se precargan; con bind-mount de Compose los pesos quedan en `backend/apps/biometrics/ml_models/` del host.

Puertos host (configurables en `.env`):

| Servicio  | Variable | Default | URL / endpoint |
|-----------|----------|---------|----------------|
| Frontend  | `FRONTEND_PORT` | `5173` | http://localhost:5173 |
| Backend   | `BACKEND_PORT` | `8000` | http://localhost:8000 |
| Postgres  | `POSTGRES_PORT` | `5433` | localhost:5433 |

> Default `5433` evita choque con un Postgres nativo en `:5432`. Dentro de la red Docker el backend usa siempre `db:5432` (vía `DATABASE_URL` de Compose).

API documentada: `http://localhost:${BACKEND_PORT}/api/docs/` · `/api/redoc/`

### Cambiar puertos / host del API

Todo se configura en el `.env` raíz (Vite lo lee vía `envDir` del monorepo):

```bash
BACKEND_PORT=8001
FRONTEND_PORT=5174
POSTGRES_PORT=5434                           # puerto Postgres publicado en el host
VITE_API_BASE_URL=http://192.168.1.10:8001   # host+puerto que ve el navegador
CORS_ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174,http://192.168.1.10:5174
```

En híbrido (backend en el host), `POSTGRES_HOST` + `POSTGRES_PORT` deben coincidir con el mapeo de Compose. `VITE_API_BASE_URL` es la URL completa: Compose **no** la reescribe a `localhost`. Tras cambiar `.env`, reinicia los servicios (`docker compose up` / Vite).

Si sirves el frontend Vite (`dev` / `preview`) detrás de un dominio, añade el host:

```bash
FRONTEND_ALLOWED_HOSTS=sso.tudominio.com
```

(Equivalente a `server.allowedHosts` de Vite. También actualiza `ALLOWED_HOSTS` y `CORS_ALLOWED_ORIGINS` del backend.)

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
| POST | `/api/v1/auth/register/` | Registro biométrico (`multipart`: datos + `video` + `otp_code`) |
| POST | `/api/v1/otp/request/` | Solicitar código OTP (email) |
| POST | `/api/v1/otp/verify/` | Validar OTP en UI (no consume) |
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

- Puertos: `BACKEND_PORT` / `FRONTEND_PORT` / `POSTGRES_PORT` en `.env` (Compose, `run_devserver.py`, Vite).
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
