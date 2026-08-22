# Master Plan — Face-Auth (Servicio de Autenticación Biométrica SSO)

> **Propósito de este documento:** ser la guía única de estado y ruta de implementación del proyecto. Cualquier desarrollador o agente de IA que retome el trabajo debe poder leer este archivo y saber (a) qué existe, (b) qué falta, (c) en qué orden hacerlo y (d) cómo validar que cada fase está completa.
>
> **Cómo usar este documento:** cada tarea tiene un checkbox. Márcalo `[x]` solo cuando el criterio de aceptación se cumple. No avances de fase sin cerrar los criterios de aceptación de la fase anterior, salvo excepciones explícitas anotadas.
>
> Diseño de referencia: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) (estructura de carpetas, modelos de datos, especificación del pipeline).

**Estado global del proyecto:** 🟡 Fases 6–8 y **Fase 9 (OTP)** implementadas — pendiente `migrate` local, revisión manual del panel admin y prueba del registro con correo (console backend en dev).

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
- [x] (Opcional) CI básico (GitHub Actions) que corra lint + tests en cada push.

**Criterio de aceptación:** `pipenv install --dev` resuelve e instala todas las dependencias del backend sin conflictos; `docker compose up` levanta backend + db + frontend; `pipenv run python manage.py migrate` corre sin errores contra Postgres con `pgvector` habilitado; `bun run dev` sirve el frontend.

> **Nota local:** Postgres del host ya usa `:5432`; el compose publica `db` en **`localhost:5433`**. Dentro de la red Docker el backend sigue usando `db:5432`.

---

## Fase 2 — Backend Core & Biometría

**Objetivo:** modelos persistidos, pipeline biométrico funcional de punta a punta (probado vía script/test, aún sin exponer HTTP), autenticación JWT emitida internamente.

### 2.1 Modelos y multi-tenancy
- [x] Crear app `apps/tenants` con el modelo `Application` (ver `docs/ARCHITECTURE.md §2.1`) + admin registrado + migración inicial.
- [x] Crear app `apps/accounts` con `TenantUser` y `BiometricProfile` (ver `docs/ARCHITECTURE.md §2.2`) + migraciones (incluyendo el índice HNSW).
- [x] Middleware `core/middleware.py`: resuelve `app_id` (prioridad: header `X-App-Id`, luego query `?app_id=`) → `request.application`; responde 404/400 si no existe o está inactiva.
- [x] Permission `core/permissions.py::HasValidAppId` reutilizable en todas las vistas.
- [x] Comando de management `create_application` (o vía Django admin) para dar de alta tenants de prueba.

### 2.2 Pipeline biométrico (aislado, testeable sin HTTP)
- [x] `preprocessing.FramePreprocessor`: extracción de frames con OpenCV, validación de fps/resolución/brillo/duración.
- [x] `liveness_active.ActiveLivenessChecker`: landmarks con MediaPipe **Face Landmarker (Tasks API, mediapipe≥1.0)**, cálculo de EAR (parpadeo) y variación de yaw/pitch/roll entre frames.
- [x] `liveness_passive.PassiveLivenessClassifier`: carga de modelo ONNX MiniFASNetV2, inferencia sobre frames clave, agregación de score.
- [x] Script/documentación de descarga de pesos (`download_ml_models`: Face Landmarker `.task`, `buffalo_s` InsightFace, `MiniFASNetV2.onnx`) fuera del control de versiones, con checksum.
- [x] `embeddings.FaceEmbedder`: carga de InsightFace `buffalo_s`, extracción y normalización L2 del embedding de 512-d.
- [x] `vector_matcher.VectorMatcher`: búsqueda por distancia coseno con pgvector, filtrado estricto por `application`, top-1 + umbral.
- [x] `biometric_service.BiometricService`: orquestador con `process_enrollment()` y `process_authentication()` (ver contrato en `docs/ARCHITECTURE.md §3.2`).
- [x] Excepciones tipadas (`apps/biometrics/exceptions.py`) para cada punto de falla del pipeline.
- [x] Suite de tests unitarios del pipeline usando clips sintéticos + fakes de modelos (real E2E con videos vía `demo_biometric_flow`) — sin pasar por HTTP.

### 2.3 Autenticación / emisión de tokens
- [x] Configurar `djangorestframework-simplejwt` para emitir tokens propios del servicio (no ligados al `User` de Django, sino a `TenantUser`); claims custom (`app_id`, `user_id`, `email`).
- [x] Mecanismo de redirección SSO: **JWT firmado de un solo uso** (`purpose=sso_redirect`, TTL ~2 min) + access/refresh de sesión. Code-exchange OAuth2 queda como evolución futura.
- [x] Servicio `apps/authentication/services.py` que emite el token/código dado un `TenantUser` autenticado.

**Criterio de aceptación:** un script de management (`demo_biometric_flow`) puede registrar un usuario con un video de prueba, extraer y guardar su embedding, y luego autenticar con un segundo video del mismo usuario obteniendo un match exitoso; un video de una foto estática es rechazado por liveness. Cubierto además por tests unitarios con fakes (`pytest tests/unit/test_biometric_pipeline.py`).

---

## Fase 3 — OpenAPI & Contratos

**Objetivo:** exponer el pipeline vía API REST completamente documentada y auto-descriptiva, siguiendo metodología contract-first.

- [x] Instalar y configurar `drf-spectacular` (`SPECTACULAR_SETTINGS`, `SchemaView` en `config/urls.py`).
- [x] Endpoints de `apps/tenants`: `GET /api/v1/applications/{app_id}/` (validación pública de existencia, para el frontend antes de cualquier flujo).
- [x] Endpoints de `apps/authentication` / `apps/biometrics`:
  - [x] `POST /api/v1/auth/login/` (`multipart/form-data`: `app_id` + `video`) → `AuthResult` serializado (token/redirect_url o error descriptivo).
  - [x] `POST /api/v1/auth/register/` (`multipart/form-data`: datos de texto + `video`) → usuario creado + token, o error descriptivo sin romper el formulario.
  - [x] `POST /api/v1/auth/token/refresh/` (vía tokens propios `TenantRefreshToken`).
- [x] Serializers de request/response con `@extend_schema` y ejemplos (`OpenApiExample`) para cada código de error (400/401/409/422).
- [x] Exception handler uniforme (`core/exceptions.py`) que mapea las excepciones del pipeline a un payload de error consistente (`{code, message, field}`).
- [x] Generar `backend/schema.json` (`python manage.py spectacular --file schema.json --format openapi-json`) y servir Swagger UI / Redoc en `/api/docs/` y `/api/redoc/`.
- [x] Validar el schema generado (`drf-spectacular --fail-on-warn --validate`).

**Criterio de aceptación:** `schema.json` se genera sin warnings; Swagger UI permite ejecutar manualmente `login`/`register` subiendo un video; el contrato cubre todos los códigos de error documentados en `docs/ARCHITECTURE.md §3.3`.

---

## Fase 4 — Frontend

**Objetivo:** frontend funcional que consume el API generado, implementando los Flujos A y B descritos en los requerimientos.

### 4.1 Fundación
- [x] Generar tipos TS desde `schema.json` (`openapi-typescript` u `orval`) hacia `src/api/generated/`, con script `bun run generate:api` documentado.
- [x] Cliente HTTP base (`src/api/client.ts`) + configuración de TanStack Query (`QueryClientProvider`).
- [x] `TenantContext`: lee `?app_id=` de la URL, llama a `GET /applications/{app_id}/`; si no existe/inactiva → redirige a página 404 propia.
- [x] Router (`react-router` o similar) con rutas: `/login`, `/register`, `/404`, guardadas por `TenantContext`.

### 4.2 Captura de video
- [x] Componente `CameraCapture`: solicita permiso de cámara (`getUserMedia`), preview en vivo.
- [x] `videoRecorder.ts`: graba clip de 2-3s con `MediaRecorder`, con guía visual (cuenta regresiva, encuadre de rostro) siguiendo un "estándar seguro" (resolución mínima, códec soportado por el backend).
- [x] Manejo de errores de permisos de cámara (denegado, no disponible) con mensajes claros.

### 4.3 Flujo A — Login
- [x] `LoginPage`: botón "Iniciar Sesión" → abre `CameraCapture` → al capturar, envía video vía `useLogin` (mutation de TanStack Query, `multipart/form-data`).
- [x] Estado de carga durante el procesamiento (pipeline puede tardar unos segundos) con feedback visual.
- [x] En éxito: redirección a la `redirect_url`/token devuelto por el backend.
- [x] En error: mostrar motivo descriptivo (reutilizando el payload de error del contrato) y permitir reintentar captura sin recargar la página.

### 4.4 Flujo B — Registro
- [x] `RegisterPage`: formulario tradicional (nombres, apellidos, correo, teléfono) con validación de campos (`react-hook-form` + `zod`, recomendado).
- [x] Botón "Registro Biométrico" habilita `CameraCapture`; al capturar, envía `FormData` combinando texto + video vía `useRegister`.
- [x] **Regla crítica de UX:** en caso de error (liveness fallido, email duplicado, etc.) el formulario **no se resetea**; solo se limpia el video capturado, permitiendo reintentar la captura conservando los datos ya ingresados.
- [x] En éxito: guardar sesión/token y redirigir a la pantalla de inicio de la app cliente.

### 4.5 UI/UX
- [x] Componentes `shadcn/ui` para formularios, botones, alertas de error, spinners.
- [x] Página 404 dedicada para `app_id` inválido/ausente.
- [x] Diseño responsive (mobile-first, ya que la cámara se usará mayormente en dispositivos móviles).

**Criterio de aceptación:** flujo completo de registro y login funcionando end-to-end contra el backend real, sin mocks; tipos TS regenerados reflejan el contrato actual sin `any` manuales.

---

## Fase 5 — Pruebas & Hardening

**Objetivo:** robustecer seguridad, rendimiento y confiabilidad antes de considerar el servicio listo para integrarse por terceros.

### 5.1 Seguridad
- [x] Rate limiting en endpoints de login/registro (por `app_id` + IP) para mitigar fuerza bruta biométrica.
- [x] Validación estricta de `redirect_uris` (whitelist exacta, no solo prefijo) antes de redirigir tras login.
- [x] Revisar almacenamiento de video: **no persistir el clip crudo** más allá del tiempo de procesamiento (borrar de memoria/disco temporal inmediatamente); solo persistir el embedding.
- [x] Rotación/gestión segura de `api_key` por `Application`.
- [x] Revisión con subagente de seguridad (`security-review`) sobre el manejo de uploads, deserialización de video y permisos multi-tenant.

### 5.2 Pruebas de liveness / anti-spoofing
- [x] Dataset de prueba con: rostro real, foto impresa, foto en pantalla (móvil/monitor), video pregrabado reproducido en pantalla, máscara/deepfake básico si es factible.
- [x] Medición de FAR (False Acceptance Rate) y FRR (False Rejection Rate) del pipeline combinado (activo + pasivo) y ajuste de `liveness_threshold`/`match_threshold` por defecto.
- [x] Pruebas de condiciones adversas: poca luz, contraluz, rostro parcialmente cubierto, múltiples rostros en cuadro.

### 5.3 Rendimiento
- [x] Benchmark de latencia end-to-end del pipeline (objetivo: procesar un clip de 2-3s en < X segundos en CPU; definir X según hardware objetivo).
- [x] Prueba de carga sobre la búsqueda vectorial (`VectorMatcher`) con volumen simulado de usuarios por tenant (10k, 100k) para validar el comportamiento del índice HNSW con filtrado por `application_id`.
- [x] Pooling/reuso de sesiones ONNXRuntime e instancias de modelos (evitar recargar pesos en cada request).

### 5.4 Calidad y mantenibilidad
- [x] Cobertura de tests backend (unit + integración de API) e informe de cobertura en CI.
- [x] Tests de frontend (componentes clave: `CameraCapture`, flujos de login/registro) con Vitest/Testing Library.
- [x] Documentación operativa: cómo agregar un nuevo tenant, cómo rotar modelos ONNX, runbook de incidentes comunes (falsos rechazos masivos, caída de latencia).

**Criterio de aceptación:** métricas de FAR/FRR documentadas y aceptadas, sin hallazgos críticos/altos pendientes de la revisión de seguridad, pipeline dentro del presupuesto de latencia definido.

> **Notas de cierre Fase 5:** presupuesto latencia documentado en **≤ 8 s p50 (CPU laptop)** (`benchmark_pipeline`). Objetivos FAR ≤ 0.05 / FRR ≤ 0.10 en `docs/datasets/README.md` (requieren dataset local no versionado). Security-review: sin críticos/altos; 2 medium mitigados (Redis en prod para throttle multi-worker; admin ya no expone `api_key` en flash).

---

## Fase 6 — Panel de Administración

**Objetivo:** exponer un panel web (SPA) para que operadores de plataforma administren tenants (`Application`), usuarios (`TenantUser`) y perfiles biométricos asociados, sin depender del Django Admin como UI principal. El acceso inicial se restringe a usuarios Django con `is_superuser=True`; el diseño de permisos debe permitir evolucionar a roles (p. ej. `staff` por tenant) sin reescribir el contrato.

> **Alcance de autenticación (v1):** el panel **no** usa `TenantUser` ni el flujo biométrico. Los operadores inician sesión con credenciales de `django.contrib.auth.User`. Solo se admite `is_superuser`. Django Admin (`/admin/`) permanece como escape hatch.

### 6.1 Backend — API Admin (`/api/v1/admin/`)
- [x] Permission `core/permissions.py::IsSuperUser` (y alias/documentación para futura `IsPlatformOperator` basada en roles).
- [x] Excluir el prefijo `/api/v1/admin/` del `ApplicationResolverMiddleware` (las rutas admin no dependen de `X-App-Id`; el tenant se filtra por path/query).
- [x] Auth de operadores: `POST /api/v1/admin/auth/login/` (username + password → access/refresh JWT de Django User) + `POST /api/v1/admin/auth/token/refresh/` + `GET /api/v1/admin/auth/me/`.
- [x] Rechazar login si el usuario no es `is_active` o no es `is_superuser` (403 con código estable, p. ej. `not_superuser`).
- [x] CRUD de tenants:
  - [x] `GET|POST /api/v1/admin/applications/`
  - [x] `GET|PATCH /api/v1/admin/applications/{app_id}/` (activar/desactivar, editar `name`, `redirect_uris`, umbrales).
  - [x] `POST /api/v1/admin/applications/{app_id}/rotate-api-key/` (devuelve la nueva clave **una sola vez**; no exponer `api_key` en list/retrieve habitual).
- [x] Gestión de usuarios por tenant:
  - [x] `GET /api/v1/admin/applications/{app_id}/users/` (filtros: email, `is_active`; paginación).
  - [x] `GET|PATCH|DELETE /api/v1/admin/users/{user_id}/` (activar/desactivar, editar datos de perfil, o eliminar con CASCADE de perfiles biométricos y OTP; **sin** crear usuarios por formulario admin en v1 — el alta biométrica sigue siendo el Flujo B).
- [x] Perfiles biométricos (solo lectura + soft-deactivate):
  - [x] `GET /api/v1/admin/users/{user_id}/biometric-profiles/`
  - [x] `PATCH /api/v1/admin/biometric-profiles/{profile_id}/` (`is_active` únicamente; nunca devolver el vector `embedding` completo en listados).
- [x] Serializers admin tipados + `@extend_schema` (tag OpenAPI `admin`) + regenerar `backend/schema.json`.
- [x] Paginación DRF operativa en `core/pagination.py` (page size razonable, p. ej. 25).
- [x] Suite de tests de integración: login superuser OK / staff no-superuser 403 / CRUD tenant aislado / rotación de `api_key` / listado de users filtrado por `app_id`.

### 6.2 Frontend — Panel SPA (`/admin/*`)
- [x] Rutas admin **fuera** de `TenantProvider` (no requieren `?app_id=`): `/admin/login`, `/admin/applications`, `/admin/applications/:appId`, `/admin/applications/:appId/users`, `/admin/users/:userId`.
- [x] `AdminAuthContext` + guard de rutas: sesión de operador (JWT staff) separada de la sesión SSO de `TenantUser` (`session.ts` vs `adminSession.ts`).
- [x] Extender `api/client.ts` para adjuntar `Authorization: Bearer <admin_access>` en llamadas `/api/v1/admin/*` y refrescar token ante 401.
- [x] Regenerar tipos (`bun run generate:api`) y hooks TanStack Query en `src/api/hooks/admin/`.
- [x] `AdminLoginPage`: formulario username/password → login admin; mensaje claro si no es superuser.
- [x] `AdminShell`: layout con navegación (Applications, logout); sin cards innecesarias — UI operativa clara.
- [x] `ApplicationsListPage` + create/edit: alta de tenant, toggle `is_active`, edición de `redirect_uris` y umbrales.
- [x] `ApplicationDetailPage`: resumen del tenant + acción "Rotar API key" con confirmación y visualización one-shot de la clave.
- [x] `TenantUsersListPage` / `TenantUserDetailPage`: listado filtrable, activar/desactivar o eliminar usuario (CASCADE de embeddings), ver perfiles biométricos y desactivar embeddings.
- [x] Página / estado 403-friendly si el token deja de ser válido o el usuario pierde privilegios.

### 6.3 Documentación y cierre
- [x] Actualizar `docs/OPERATIONS.md`: flujo preferido vía panel SPA; Django Admin y CLI como alternativas.
- [x] Actualizar árbol y sección de permisos en `docs/ARCHITECTURE.md` (§1 y nueva §4 Panel Admin).
- [x] README: enlace al panel (`/admin/login`) y nota de que requiere `createsuperuser`.

**Criterio de aceptación:** un superuser creado con `createsuperuser` puede iniciar sesión en `/admin/login`, crear un tenant, rotar su `api_key`, listar/desactivar usuarios de ese tenant y desactivar un perfil biométrico; un usuario Django `is_staff=True` pero `is_superuser=False` recibe 403 en toda la API admin; el schema OpenAPI incluye el tag `admin` sin warnings; los flujos SSO (`/login`, `/register`) no se ven afectados.

> **Evolución futura (fuera de v1):** roles granulares (`platform_admin`, `tenant_operator`), scoping por `Application`, auditoría de acciones admin, creación asistida de usuarios sin video, hashing de `api_key` en reposo.

---

## Fase 7 — Captura pasiva "Dashcam" (frontend)

**Objetivo:** reemplazar el botón manual de "Grabar" por captura pasiva disparada por parpadeo (ver [`docs/dashcam-feat.md`](dashcam-feat.md)). MediaPipe en el cliente actúa **solo** como trigger de UX; el backend sigue haciendo la validación biométrica real (Zero-Trust, sin cambios de contrato).

### 7.1 Piezas base
- [x] Dependencia `@mediapipe/tasks-vision` (WASM vía CDN pinneado; modelo `.task` oficial de Google).
- [x] `src/components/camera/faceMetrics.ts`: cálculo de EAR sobre landmarks (con corrección de aspect ratio) + `createBlinkDetector` (máquina de estados con histéresis y filtro de jitter) + tests unitarios (`faceMetrics.test.ts`).
- [x] `src/components/camera/useFaceLandmarker.ts`: hook que inicializa Face Landmarker (runningMode `VIDEO`, 1 rostro, sin blendshapes) como singleton de sesión, con fallback GPU→CPU y `retry()`.
- [x] `src/components/camera/useDashcamRecorder.ts`: hook cámara + `MediaRecorder` con **segmentos rotativos** (rota cada 4 s, espera mínimo 2 s al cortar) para que el clip final quede siempre en 2–4 s (dentro del rango 1–6 s del backend) e incluya el parpadeo.

### 7.2 Integración
- [x] `evaluateFaceAlignment` en `faceMetrics.ts`: bounding box de los landmarks centrada y a buena distancia (rangos tolerantes; el encuadre fino lo valida el backend) con hints de UI (`off_center`/`too_far`/`too_close`).
- [x] Componente `DashcamCapture`: loop de `requestAnimationFrame` con `detectForVideo`, rostro alineado estable (6 frames) arma la grabación, estados de UI ("Rostro detectado. Parpadee para confirmar"), parpadeo dispara `stopAndCollect` y auto-envío del Blob; si el rostro se pierde 12 frames se desarma y vuelve a detectar.
- [x] Reemplazo de `CameraCapture` por `DashcamCapture` en `LoginPage` y `RegisterPage` (mutaciones `useLogin`/`useRegister` intactas, sin cambios de contrato). `CameraCapture` se conserva como fallback manual.
- [x] Manejo de rechazo del backend: la página muestra la alerta con el motivo y, al terminar la mutación, `DashcamCapture` se re-monta y reinicia la detección sin recargar la página (el formulario de registro no se resetea; email duplicado sigue regresando al formulario).
- [x] Tests de componente (Vitest/Testing Library) con fakes de MediaPipe (`detectForVideo` con guion de frames) y `MediaRecorder`: error de cámara, carga del detector y flujo completo alineación → parpadeo → captura → cámara apagada.
- [x] Code-splitting: `@mediapipe/tasks-vision` se importa dinámicamente (chunk lazy de ~153 kB; el bundle principal no crece para el panel admin ni la carga inicial).

**Criterio de aceptación:** login y registro completan el flujo sin presionar "Grabar": la cámara enciende, detecta rostro alineado, el parpadeo dispara el corte y el video se envía solo; un rechazo del backend reinicia la detección automáticamente.

> **Notas de cierre Fase 7 (conclusiones de implementación):**
> - **Trigger en cliente, validación en servidor:** MediaPipe en el navegador decide únicamente *cuándo* cortar el clip (conveniencia UX). El contrato Zero-Trust no cambió: el backend sigue validando liveness activo/pasivo, embedding y matching sobre el video recibido.
> - **Duración del clip:** como un Blob de `MediaRecorder` no se puede recortar de forma fiable en el cliente, `useDashcamRecorder` graba en **segmentos rotativos** (rota cada 4 s, espera mínimo 2 s al cortar) → clips siempre de 2–4 s, dentro del rango 1–6 s de `FramePreprocessor`. Caso borde conocido: si el parpadeo cae justo en la rotación de segmento, el clip puede no contener el ciclo completo y el backend lo rechazará por liveness; el flujo se reinicia solo, por lo que el costo es un reintento.
> - **Parpadeo:** EAR clásico (índices 33/133/160/144/158/153 y 362/263/385/380/387/373 de la malla de 478 puntos) con corrección de aspect ratio, e histéresis 0.20/0.25 + mínimo 2 frames cerrados para filtrar jitter. El detector dispara al **reabrir** los ojos para que el clip contenga el ciclo completo (lo que busca `ActiveLivenessChecker`).
> - **Rendimiento:** una inferencia síncrona por frame pintado vía `requestAnimationFrame` (sin Web Worker; el Face Landmarker corre en WASM/GPU y las pruebas no mostraron bloqueo del hilo). El landmarker es un **singleton de sesión** (no se paga re-init en cada reintento) con fallback GPU→CPU y assets desde CDN pinneado a la versión instalada.
> - **Pendiente de verificación manual (requiere cámara real):** calibración de umbrales de EAR/alineación con distintos rostros/luz, y comportamiento en Safari/iOS (códecs de `MediaRecorder`). Los umbrales viven como opciones en `faceMetrics.ts`/`DashcamCapture.tsx` para ajustarse sin refactor.

---

## Fase 8 — Verificación server-to-server de tokens SSO

**Objetivo:** cerrar la brecha de la guía de integración ([`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md)): las apps cliente no podían verificar la firma del `redirect_token` (HS256 con clave del servicio, sin JWKS). Ahora la `api_key` del tenant tiene uso real en el flujo público.

- [x] `POST /api/v1/auth/token/verify/` (`apps/authentication/views.py::TokenVerifyView`): body JSON `{app_id, token}` + header `X-Api-Key` (comparación en tiempo constante con `secrets.compare_digest`).
- [x] Validaciones: firma/expiración/`token_type` (vía `SSORedirectToken`), `purpose == sso_redirect`, `app_id` del token == tenant que verifica, usuario existente y activo.
- [x] **Consumo de un solo uso:** el `jti` se registra con `cache.add` atómico (TTL 5 min > TTL del token); replay → `401 token_already_used`. En prod multi-worker requiere el cache Redis ya previsto en `prod.py`.
- [x] Respuesta con datos del usuario (`user_id`, `email`, nombres, `expires_at`) para que el cliente no necesite otra llamada.
- [x] Rate limiting reutilizando `AppIdScopedRateThrottle` + errores nuevos (`invalid_api_key`, `token_already_used`, `user_inactive`) documentados con ejemplos OpenAPI; `schema.json` regenerado sin warnings y tipos TS del frontend re-generados.
- [x] Tests de integración (8): éxito + replay, api_key incorrecta/ausente, access token rechazado, token de otro tenant, token expirado, usuario inactivo, app inexistente.
- [x] `INTEGRATION_GUIDE.md` §3.3 actualizada: el cliente ya no implementa anti-replay propio; code-exchange OAuth2 sigue como evolución futura.

**Criterio de aceptación:** una app cliente puede validar el `token` de su callback con una sola llamada autenticada por `api_key`; el mismo token verificado dos veces devuelve 401; un access/refresh token o un token de otro tenant se rechaza.

---

## Fase 9 — Capa OTP (prevención de account takeover)

**Objetivo:** verificar posesión del email antes de persistir el enrolamiento biométrico. Diseño: [`docs/OTP_VALIDATION.md`](docs/OTP_VALIDATION.md). Guía para features futuros: [`docs/OTP_FEATURE_GUIDE.md`](docs/OTP_FEATURE_GUIDE.md). Conclusiones por fase: [`docs/OTP_IMPLEMENTATION.md`](docs/OTP_IMPLEMENTATION.md).

- [x] App `apps.otp`: `OtpChallenge`, hasher HMAC, `SmtpEmailChannel`, registry de canales, settings `OTP_*` / `EMAIL_*` (console en dev).
- [x] `OtpService.issue/verify/consume`: 6 dígitos, TTL 5 min, 3 emisiones / 5 min, 5 intentos de verify, invalidación del código anterior, `verify` no consume.
- [x] `POST /api/v1/otp/request/` y `POST /api/v1/otp/verify/`; `email_verify` crea `TenantUser` pendiente (`is_active=False`).
- [x] Registro exige `otp_code`; consume **después** del pipeline biométrico OK; setea `email_verified_at` y activa el usuario.
- [x] Frontend: paso OTP reutilizable (`OtpChallengeForm`) entre formulario y dashcam; `otp_code` en el `FormData` de register.
- [x] OpenAPI tag `otp`, `schema.json` y tipos TS regenerados.

**Criterio de aceptación:** no se puede completar `POST /auth/register/` sin un OTP vigente del mismo email; un video rechazado por liveness no quema el código; un cuarto `request` en 5 min responde 429.

**Fuera de alcance:** bloqueo por suplantación (`purpose=account_unlock`), SMS/WhatsApp, OTP de operadores admin.

---

## Registro de decisiones pendientes (a resolver antes/durante Fase 2-3)

- [x] Mecanismo exacto de "authorization code" para el SSO → **JWT de un solo uso** (`SSORedirectToken`, `purpose=sso_redirect`) + access/refresh. OAuth2 code-exchange como evolución.
- [x] Formato/códec del video → mp4/webm vía OpenCV; máx. 15 MB; duración 1–6 s; resolución mín. 320×240 (ajustable en `FramePreprocessor`).
- [x] Duplicados en registro → unicidad de **email por `application`** (+ detección biométrica `DuplicateBiometricError`). Teléfono no es clave única por ahora.
- [ ] Estrategia de particionamiento de `BiometricProfile` si un tenant supera cierto volumen (ver nota en `docs/ARCHITECTURE.md §2.2`).
- [x] Auth del panel admin (Fase 6) → JWT de `django.contrib.auth.User` + gate `is_superuser` (roles diferidos).

---

## Próximo paso

Aplicar migraciones `otp.0001_initial` y `accounts.0002_add_email_verified_at` (`pipenv run python manage.py migrate`) con Postgres arriba. Probar el registro: el código OTP sale en la consola del backend (`EMAIL_BACKEND` console en dev). Fase 7 sigue pendiente de prueba manual con cámara real.
