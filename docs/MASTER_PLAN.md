# Master Plan — Face-Auth (Servicio de Autenticación Biométrica SSO)

> **Propósito de este documento:** ser la guía única de estado y ruta de implementación del proyecto. Cualquier desarrollador o agente de IA que retome el trabajo debe poder leer este archivo y saber (a) qué existe, (b) qué falta, (c) en qué orden hacerlo y (d) cómo validar que cada fase está completa.
>
> **Cómo usar este documento:** cada tarea tiene un checkbox. Márcalo `[x]` solo cuando el criterio de aceptación se cumple. No avances de fase sin cerrar los criterios de aceptación de la fase anterior, salvo excepciones explícitas anotadas.
>
> Diseño de referencia: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (estructura de carpetas, modelos de datos, especificación del pipeline).

**Estado global del proyecto:** 🟡 Fase 1 implementada — pendiente revisión manual antes de Fase 2.

---

## Fase 0 — Diseño (✅ Completada)

- [x] Definición de requerimientos core (multi-tenant, anti-spoofing, API-first).
- [x] Selección del stack tecnológico (backend y frontend).
- [x] Estructura de monorepo propuesta (`docs/ARCHITECTURE.md`).
- [x] Modelos de datos iniciales (`Application`, `TenantUser`, `BiometricProfile`).
- [x] Especificación modular del pipeline biométrico (`BiometricService`).

---

## Fase 1 — Configuración e Infraestructura

**Objetivo:** repositorio bootstrapeado, entorno reproducible con Docker, base de datos con `pgvector` operativa, CI mínimo.

- [x] Inicializar repositorio git y `.gitignore` (Python, Node, entorno virtual de `pipenv` (`.venv/`), ONNX weights, `.env`). **`Pipfile.lock` no se ignora** — se versiona para builds reproducibles.
- [x] `docker-compose.yml` con servicios: `db` (postgres con imagen `pgvector/pgvector:pg16` o extensión instalada), `backend`, `frontend`.
- [x] `backend/`: proyecto Django (`config/`) con settings divididos (`base.py`, `dev.py`, `prod.py`) leyendo variables de entorno (`django-environ` o similar).
- [x] Habilitar extensión `pgvector` en la base de datos (`CREATE EXTENSION IF NOT EXISTS vector;`) vía migración de Django.
- [x] Gestión de paquetes del backend con **`pipenv`**: `backend/Pipfile` creado con `[packages]` (Django, DRF, `djangorestframework-simplejwt`, `drf-spectacular`, `psycopg[binary]`, `pgvector`, `django-environ`, `django-cors-headers`, `gunicorn` + stack biométrico: `opencv-python-headless`, `mediapipe`, `onnxruntime`, `insightface`, `numpy`) y `[dev-packages]` (`pytest`, `pytest-django`, `pytest-cov`, `factory-boy`, `ruff`, `black`, `mypy`, `django-stubs`, `ipython`); `python_version = "3.11"` fijado en `[requires]`.
- [x] Generar `backend/Pipfile.lock` (`pipenv lock` o `pipenv install`) una vez confirmado el entorno (requiere `cmake`/`libgl1` a nivel de sistema para compilar `mediapipe`/`insightface`; documentar en Dockerfile) y versionarlo.
- [x] Ajustar `docker-compose.yml`/`Dockerfile` del backend para usar `pipenv install --deploy --ignore-pipfile --system` en la imagen (sin `dev-packages`; `--system` evita que el bind-mount de `./backend` pise el venv), y comandos de management vía `python`/`gunicorn` del system site-packages.
- [x] `frontend/`: proyecto Vite + React + TypeScript inicializado con `bun`, Tailwind y `shadcn/ui` configurados.
- [x] `.env.example` documentando todas las variables necesarias (DB, `SECRET_KEY`, orígenes CORS, umbrales por defecto).
- [x] README raíz con instrucciones de arranque local (`docker compose up`, comandos de migración, comando para levantar frontend).
- [ ] (Opcional) CI básico (GitHub Actions) que corra lint + tests en cada push.

**Criterio de aceptación:** `pipenv install --dev` resuelve e instala todas las dependencias del backend sin conflictos; `docker compose up` levanta backend + db + frontend; `pipenv run python manage.py migrate` corre sin errores contra Postgres con `pgvector` habilitado; `bun run dev` sirve el frontend.

> **Nota local:** Postgres del host ya usa `:5432`; el compose publica `db` en **`localhost:5433`**. Dentro de la red Docker el backend sigue usando `db:5432`.

---

## Fase 2 — Backend Core & Biometría

**Objetivo:** modelos persistidos, pipeline biométrico funcional de punta a punta (probado vía script/test, aún sin exponer HTTP), autenticación JWT emitida internamente.

### 2.1 Modelos y multi-tenancy
- [ ] Crear app `apps/tenants` con el modelo `Application` (ver `docs/ARCHITECTURE.md §2.1`) + admin registrado + migración inicial.
- [ ] Crear app `apps/accounts` con `TenantUser` y `BiometricProfile` (ver `docs/ARCHITECTURE.md §2.2`) + migraciones (incluyendo el índice HNSW).
- [ ] Middleware `core/middleware.py`: resuelve `app_id` (query param o header `X-App-Id`, a definir) → `request.application`; responde 404/400 si no existe o está inactiva.
- [ ] Permission `core/permissions.py::HasValidAppId` reutilizable en todas las vistas.
- [ ] Comando de management `create_application` (o vía Django admin) para dar de alta tenants de prueba.

### 2.2 Pipeline biométrico (aislado, testeable sin HTTP)
- [ ] `preprocessing.FramePreprocessor`: extracción de frames con OpenCV, validación de fps/resolución/brillo/duración.
- [ ] `liveness_active.ActiveLivenessChecker`: landmarks con MediaPipe Face Mesh, cálculo de EAR (parpadeo) y variación de yaw/pitch/roll entre frames.
- [ ] `liveness_passive.PassiveLivenessClassifier`: carga de modelo ONNX MiniFASNetV2, inferencia sobre frames clave, agregación de score.
- [ ] Script/documentación de descarga de pesos (`buffalo_s` de InsightFace, `MiniFASNetV2.onnx`) fuera del control de versiones, con checksum.
- [ ] `embeddings.FaceEmbedder`: carga de InsightFace `buffalo_s`, extracción y normalización L2 del embedding de 512-d.
- [ ] `vector_matcher.VectorMatcher`: búsqueda por distancia coseno con pgvector, filtrado estricto por `application`, top-1 + umbral.
- [ ] `biometric_service.BiometricService`: orquestador con `process_enrollment()` y `process_authentication()` (ver contrato en `docs/ARCHITECTURE.md §3.2`).
- [ ] Excepciones tipadas (`apps/biometrics/exceptions.py`) para cada punto de falla del pipeline.
- [ ] Suite de tests unitarios del pipeline usando clips de video fixture (real, foto estática, pantalla LCD, poca luz) — sin pasar por HTTP.

### 2.3 Autenticación / emisión de tokens
- [ ] Configurar `django-simplejwt` para emitir tokens propios del servicio (no ligados al `User` de Django, sino a `TenantUser`); definir claims custom (`app_id`, `user_id`).
- [ ] Definir el mecanismo de "authorization code" o token de redirección hacia la app cliente tras un login exitoso (a decidir: JWT firmado de un solo uso vs. code exchange estilo OAuth2).
- [ ] Servicio `apps/authentication/services.py` que emite el token/código dado un `TenantUser` autenticado.

**Criterio de aceptación:** un script de management (`manage.py shell` o comando dedicado) puede registrar un usuario con un video de prueba, extraer y guardar su embedding, y luego autenticar con un segundo video del mismo usuario obteniendo un match exitoso; un video de una foto estática es rechazado por liveness.

---

## Fase 3 — OpenAPI & Contratos

**Objetivo:** exponer el pipeline vía API REST completamente documentada y auto-descriptiva, siguiendo metodología contract-first.

- [ ] Instalar y configurar `drf-spectacular` (`SPECTACULAR_SETTINGS`, `SchemaView` en `config/urls.py`).
- [ ] Endpoints de `apps/tenants`: `GET /api/v1/applications/{app_id}/` (validación pública de existencia, para el frontend antes de cualquier flujo).
- [ ] Endpoints de `apps/authentication` / `apps/biometrics`:
  - [ ] `POST /api/v1/auth/login/` (`multipart/form-data`: `app_id` + `video`) → `AuthResult` serializado (token/redirect_url o error descriptivo).
  - [ ] `POST /api/v1/auth/register/` (`multipart/form-data`: datos de texto + `video`) → usuario creado + token, o error descriptivo sin romper el formulario.
  - [ ] `POST /api/v1/auth/token/refresh/` (si aplica, vía `simplejwt`).
- [ ] Serializers de request/response con `@extend_schema` y ejemplos (`OpenApiExample`) para cada código de error (400/401/409/422).
- [ ] Exception handler uniforme (`core/exceptions.py`) que mapea las excepciones del pipeline a un payload de error consistente (`{code, message, field}`).
- [ ] Generar `backend/schema.json` (`python manage.py spectacular --file schema.json`) y servir Swagger UI / Redoc en `/api/docs/`.
- [ ] Validar el schema generado (`drf-spectacular` `--fail-on-warn` en CI).

**Criterio de aceptación:** `schema.json` se genera sin warnings; Swagger UI permite ejecutar manualmente `login`/`register` subiendo un video; el contrato cubre todos los códigos de error documentados en `docs/ARCHITECTURE.md §3.3`.

---

## Fase 4 — Frontend

**Objetivo:** frontend funcional que consume el API generado, implementando los Flujos A y B descritos en los requerimientos.

### 4.1 Fundación
- [ ] Generar tipos TS desde `schema.json` (`openapi-typescript` u `orval`) hacia `src/api/generated/`, con script `bun run generate:api` documentado.
- [ ] Cliente HTTP base (`src/api/client.ts`) + configuración de TanStack Query (`QueryClientProvider`).
- [ ] `TenantContext`: lee `?app_id=` de la URL, llama a `GET /applications/{app_id}/`; si no existe/inactiva → redirige a página 404 propia.
- [ ] Router (`react-router` o similar) con rutas: `/login`, `/register`, `/404`, guardadas por `TenantContext`.

### 4.2 Captura de video
- [ ] Componente `CameraCapture`: solicita permiso de cámara (`getUserMedia`), preview en vivo.
- [ ] `videoRecorder.ts`: graba clip de 2-3s con `MediaRecorder`, con guía visual (cuenta regresiva, encuadre de rostro) siguiendo un "estándar seguro" (resolución mínima, códec soportado por el backend).
- [ ] Manejo de errores de permisos de cámara (denegado, no disponible) con mensajes claros.

### 4.3 Flujo A — Login
- [ ] `LoginPage`: botón "Iniciar Sesión" → abre `CameraCapture` → al capturar, envía video vía `useLogin` (mutation de TanStack Query, `multipart/form-data`).
- [ ] Estado de carga durante el procesamiento (pipeline puede tardar unos segundos) con feedback visual.
- [ ] En éxito: redirección a la `redirect_url`/token devuelto por el backend.
- [ ] En error: mostrar motivo descriptivo (reutilizando el payload de error del contrato) y permitir reintentar captura sin recargar la página.

### 4.4 Flujo B — Registro
- [ ] `RegisterPage`: formulario tradicional (nombres, apellidos, correo, teléfono) con validación de campos (`react-hook-form` + `zod`, recomendado).
- [ ] Botón "Registro Biométrico" habilita `CameraCapture`; al capturar, envía `FormData` combinando texto + video vía `useRegister`.
- [ ] **Regla crítica de UX:** en caso de error (liveness fallido, email duplicado, etc.) el formulario **no se resetea**; solo se limpia el video capturado, permitiendo reintentar la captura conservando los datos ya ingresados.
- [ ] En éxito: guardar sesión/token y redirigir a la pantalla de inicio de la app cliente.

### 4.5 UI/UX
- [ ] Componentes `shadcn/ui` para formularios, botones, alertas de error, spinners.
- [ ] Página 404 dedicada para `app_id` inválido/ausente.
- [ ] Diseño responsive (mobile-first, ya que la cámara se usará mayormente en dispositivos móviles).

**Criterio de aceptación:** flujo completo de registro y login funcionando end-to-end contra el backend real, sin mocks; tipos TS regenerados reflejan el contrato actual sin `any` manuales.

---

## Fase 5 — Pruebas & Hardening

**Objetivo:** robustecer seguridad, rendimiento y confiabilidad antes de considerar el servicio listo para integrarse por terceros.

### 5.1 Seguridad
- [ ] Rate limiting en endpoints de login/registro (por `app_id` + IP) para mitigar fuerza bruta biométrica.
- [ ] Validación estricta de `redirect_uris` (whitelist exacta, no solo prefijo) antes de redirigir tras login.
- [ ] Revisar almacenamiento de video: **no persistir el clip crudo** más allá del tiempo de procesamiento (borrar de memoria/disco temporal inmediatamente); solo persistir el embedding.
- [ ] Rotación/gestión segura de `api_key` por `Application`.
- [ ] Revisión con subagente de seguridad (`security-review`) sobre el manejo de uploads, deserialización de video y permisos multi-tenant.

### 5.2 Pruebas de liveness / anti-spoofing
- [ ] Dataset de prueba con: rostro real, foto impresa, foto en pantalla (móvil/monitor), video pregrabado reproducido en pantalla, máscara/deepfake básico si es factible.
- [ ] Medición de FAR (False Acceptance Rate) y FRR (False Rejection Rate) del pipeline combinado (activo + pasivo) y ajuste de `liveness_threshold`/`match_threshold` por defecto.
- [ ] Pruebas de condiciones adversas: poca luz, contraluz, rostro parcialmente cubierto, múltiples rostros en cuadro.

### 5.3 Rendimiento
- [ ] Benchmark de latencia end-to-end del pipeline (objetivo: procesar un clip de 2-3s en < X segundos en CPU; definir X según hardware objetivo).
- [ ] Prueba de carga sobre la búsqueda vectorial (`VectorMatcher`) con volumen simulado de usuarios por tenant (10k, 100k) para validar el comportamiento del índice HNSW con filtrado por `application_id`.
- [ ] Pooling/reuso de sesiones ONNXRuntime e instancias de modelos (evitar recargar pesos en cada request).

### 5.4 Calidad y mantenibilidad
- [ ] Cobertura de tests backend (unit + integración de API) e informe de cobertura en CI.
- [ ] Tests de frontend (componentes clave: `CameraCapture`, flujos de login/registro) con Vitest/Testing Library.
- [ ] Documentación operativa: cómo agregar un nuevo tenant, cómo rotar modelos ONNX, runbook de incidentes comunes (falsos rechazos masivos, caída de latencia).

**Criterio de aceptación:** métricas de FAR/FRR documentadas y aceptadas, sin hallazgos críticos/altos pendientes de la revisión de seguridad, pipeline dentro del presupuesto de latencia definido.

---

## Registro de decisiones pendientes (a resolver antes/durante Fase 2-3)

- [ ] Mecanismo exacto de "authorization code" para el SSO (JWT de un solo uso vs. code-exchange estilo OAuth2) — impacta `apps/authentication`.
- [ ] Formato/códec exacto del video aceptado desde el frontend (webm/mp4, límites de tamaño) — impacta `videoRecorder.ts` y `FramePreprocessor`.
- [ ] Política exacta de qué campo identifica duplicados en registro además del biométrico (¿solo email, o también teléfono?) — impacta `TenantUser` constraints.
- [ ] Estrategia de particionamiento de `BiometricProfile` si un tenant supera cierto volumen (ver nota en `docs/ARCHITECTURE.md §2.2`).

---

## Próximo paso

Fase 1 lista para **revisión manual**. Tras tu OK, continuar con la **Fase 2 (Backend Core & Biometría)**.
