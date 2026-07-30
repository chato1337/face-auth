# Face-Auth — Documento de Arquitectura

> Estado: **Fase 6 (Panel de Administración) implementada — pendiente revisión manual.**
> Este documento es la fuente de verdad sobre la estructura y el diseño de datos del sistema. Debe mantenerse actualizado a medida que el proyecto evoluciona. Ver [`MASTER_PLAN.md`](MASTER_PLAN.md) para el plan de ejecución por fases. Operaciones: [`OPERATIONS.md`](OPERATIONS.md).

## 1. Estructura del Monorepo

```
face-auth/
├── MASTER_PLAN.md
├── docs/
│   └── ARCHITECTURE.md
├── docker-compose.yml            # postgres(+pgvector), backend, frontend
├── .env.example
├── .gitignore
├── README.md
│
├── backend/
│   ├── manage.py
│   ├── Pipfile                   # gestión de paquetes con pipenv (packages + dev-packages)
│   ├── Pipfile.lock               # generado por `pipenv lock`, sí se versiona
│   │
│   ├── config/                   # proyecto Django (settings/urls/wsgi/asgi)
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── dev.py
│   │   │   └── prod.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── apps/
│   │   ├── tenants/                       # Application (app_id) — límites del multi-tenant
│   │   │   ├── models.py
│   │   │   ├── admin.py                   # Django Admin (escape hatch)
│   │   │   ├── serializers.py             # públicos + admin
│   │   │   ├── views.py                   # GET público por app_id
│   │   │   ├── admin_views.py             # CRUD admin (Fase 6)
│   │   │   ├── urls.py
│   │   │   ├── admin_urls.py
│   │   │   └── migrations/
│   │   │
│   │   ├── accounts/                      # TenantUser + BiometricProfile
│   │   │   ├── models.py
│   │   │   ├── admin.py
│   │   │   ├── serializers.py             # serializers admin (Fase 6)
│   │   │   ├── admin_views.py             # list/patch users + biometric profiles
│   │   │   ├── admin_urls.py
│   │   │   └── migrations/
│   │   │
│   │   ├── biometrics/                    # Pipeline de reconocimiento/liveness
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── biometric_service.py   # Orquestador (fachada pública)
│   │   │   │   ├── preprocessing.py       # OpenCV: brillo, dimensiones, fps, encuadre
│   │   │   │   ├── liveness_active.py     # MediaPipe Face Mesh: EAR + pose 3D
│   │   │   │   ├── liveness_passive.py    # ONNXRuntime: MiniFASNetV2
│   │   │   │   ├── embeddings.py          # InsightFace buffalo_s (512-d)
│   │   │   │   └── vector_matcher.py      # pgvector: búsqueda por coseno
│   │   │   ├── ml_models/                 # pesos .onnx (gitignored, se descargan en build)
│   │   │   ├── exceptions.py              # LivenessError, SpoofDetectedError, LowQualityError...
│   │   │   ├── serializers.py
│   │   │   ├── views.py
│   │   │   └── urls.py
│   │   │
│   │   └── authentication/                # Emisión de JWT SSO (TenantUser) + auth admin (Django User)
│   │       ├── services.py                # tokens TenantUser / SSO redirect
│   │       ├── admin_services.py          # login/refresh para operadores (is_superuser)
│   │       ├── serializers.py
│   │       ├── admin_serializers.py
│   │       ├── views.py
│   │       ├── admin_views.py
│   │       ├── urls.py
│   │       └── admin_urls.py
│   │
│   ├── core/                     # utilidades transversales
│   │   ├── permissions.py        # HasValidAppId, IsSuperUser (admin v1)
│   │   ├── middleware.py         # resuelve `request.application`; excluye `/api/v1/admin/`
│   │   ├── pagination.py         # page size default para listados admin
│   │   └── exceptions.py         # exception handler DRF uniforme
│   │
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/          # incluye tests de API admin
│   │
│   └── schema.json                # generado por drf-spectacular (contract-first; tag `admin`)
│
└── frontend/
    ├── package.json               # gestionado con bun
    ├── bun.lockb
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── tsconfig.json
    ├── index.html
    ├── public/
    ├── .env.example
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   ├── client.ts           # fetch wrapper (SSO + Bearer admin)
        │   ├── generated/
        │   │   └── schema.d.ts     # salida de openapi-typescript sobre schema.json
        │   └── hooks/
        │       ├── useLogin.ts
        │       ├── useRegister.ts
        │       ├── useApplication.ts
        │       └── admin/          # hooks del panel (auth, applications, users)
        ├── components/
        │   ├── ui/                 # primitivos shadcn/ui
        │   ├── camera/
        │   │   ├── CameraCapture.tsx
        │   │   └── videoRecorder.ts # MediaRecorder wrapper (clip 2-3s, códec, límites)
        │   └── layout/
        │       ├── AuthShell.tsx   # shell SSO
        │       └── AdminShell.tsx  # shell panel operadores
        ├── features/
        │   ├── login/LoginPage.tsx
        │   ├── register/RegisterPage.tsx
        │   ├── not-found/NotFoundPage.tsx
        │   └── admin/              # panel de administración (Fase 6)
        │       ├── AdminLoginPage.tsx
        │       ├── applications/
        │       └── users/
        ├── context/
        │   ├── TenantContext.tsx   # valida `?app_id=` (solo flujos SSO)
        │   └── AdminAuthContext.tsx
        ├── router/routes.tsx       # `/login|register` + `/admin/*`
        ├── lib/
        │   ├── utils.ts
        │   ├── session.ts         # tokens TenantUser (SSO)
        │   └── adminSession.ts    # tokens operador (Django User)
        └── styles/globals.css
```

**Decisiones clave de la estructura:**
- `apps/tenants` está desacoplada de `apps/accounts` para que el límite del multi-tenant (qué es una `Application`) sea explícito y auditable por separado del modelo de usuario.
- `apps/biometrics/services/` concentra **todo** el pipeline de IA como servicios de Python puros (sin dependencias de Django REST más allá de excepciones), de forma que sean testeables de forma aislada y reemplazables (p. ej. cambiar `buffalo_s` por otro backbone sin tocar las vistas).
- `core/middleware.py` centraliza la resolución de `app_id` → `Application` una sola vez por request, evitando repetir lookups en cada vista. El prefijo `/api/v1/admin/` queda excluido: el panel opera a nivel de plataforma, no de tenant header.
- El panel admin reutiliza el mismo frontend SPA bajo `/admin/*`, separado del SSO por contexto de auth (`AdminAuthContext` vs `TenantContext`) y almacén de sesión (`adminSession` vs `session`).
- **Gestión de paquetes con `pipenv`** (en vez de `requirements/*.txt` planos): un único `Pipfile` declara runtime (`[packages]`, incluye Django, DRF y todo el stack biométrico) y herramientas de desarrollo (`[dev-packages]`: pytest, ruff, black, mypy). `Pipfile.lock` sí se versiona para builds reproducibles; producción se instala con `pipenv install --deploy --ignore-pipfile` (solo runtime, sin dev-packages).

---

## 2. Modelos de Base de Datos Iniciales

Requiere la extensión `pgvector` habilitada en PostgreSQL (`CREATE EXTENSION vector;`) y el paquete `pgvector` (con soporte Django) instalado.

### 2.1 `apps/tenants/models.py`

```python
import secrets
import uuid

from django.db import models


def generate_app_id() -> str:
    return f"app_{secrets.token_urlsafe(12)}"


def generate_api_key() -> str:
    return secrets.token_hex(32)


class Application(models.Model):
    """
    Representa una aplicación de terceros (tenant) que consume el servicio de
    SSO biométrico. Todo `TenantUser` y `BiometricProfile` está aislado
    lógicamente por `application`, garantizando que una búsqueda vectorial o
    un login nunca crucen los límites de un `app_id` distinto.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_id = models.CharField(
        max_length=64, unique=True, default=generate_app_id,
        editable=False, db_index=True,
    )
    name = models.CharField(max_length=150)
    api_key = models.CharField(max_length=64, unique=True, default=generate_api_key, editable=False)
    is_active = models.BooleanField(default=True)

    redirect_uris = models.JSONField(
        default=list,
        help_text="Whitelist de URLs a las que se permite redirigir tras un login exitoso.",
    )

    # Umbrales configurables por tenant (cada app puede exigir distinto rigor).
    liveness_threshold = models.FloatField(
        default=0.85,
        help_text="Score mínimo (0-1) del modelo de liveness pasivo (MiniFASNetV2) para aceptar el intento.",
    )
    match_threshold = models.FloatField(
        default=0.42,
        help_text="Distancia coseno máxima aceptada entre el embedding capturado y el almacenado.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants_application"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.app_id})"
```

### 2.2 `apps/accounts/models.py`

```python
import uuid

from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.tenants.models import Application


class TenantUser(models.Model):
    """
    Usuario final perteneciente a un único `Application`. La unicidad de
    email/teléfono se valida por tenant (no global): la misma persona puede
    registrarse de forma independiente en dos apps distintas.

    Deliberadamente NO extiende `AbstractUser`/`AbstractBaseUser` de Django:
    el login no usa contraseña, por lo que el modelo de auth estándar no aporta
    valor y complicaría la unicidad global de `username`/`email`.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="users",
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)

    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_tenant_user"
        constraints = [
            models.UniqueConstraint(fields=["application", "email"], name="uniq_email_per_app"),
        ]
        indexes = [
            models.Index(fields=["application", "email"]),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} <{self.email}> @ {self.application.app_id}"


class BiometricProfile(models.Model):
    """
    Almacena el embedding facial (512-d) de un `TenantUser`, generado por
    InsightFace (buffalo_s). Se permite más de un perfil por usuario para
    soportar re-enrolamiento sin perder histórico (soft-deprecation vía
    `is_active`), útil para auditoría y para "múltiples ángulos" a futuro.
    """

    class SourceModel(models.TextChoices):
        BUFFALO_S = "buffalo_s", "InsightFace buffalo_s"
        MOBILEFACENET = "mobilefacenet", "MobileFaceNet"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(TenantUser, on_delete=models.CASCADE, related_name="biometric_profiles")

    # Denormalizado a propósito: permite filtrar por tenant en el WHERE de la
    # búsqueda ANN sin necesidad de un JOIN contra `accounts_tenant_user`.
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE,
        related_name="biometric_profiles", editable=False,
    )

    embedding = VectorField(dimensions=512)
    model_version = models.CharField(max_length=30, choices=SourceModel.choices, default=SourceModel.BUFFALO_S)

    liveness_score = models.FloatField(help_text="Score de anti-spoofing pasivo registrado al momento del enrolamiento.")
    quality_score = models.FloatField(null=True, blank=True)

    is_active = models.BooleanField(
        default=True,
        help_text="Permite desactivar un embedding antiguo al re-enrolar sin perder el histórico.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_biometric_profile"
        indexes = [
            HnswIndex(
                name="biometric_embedding_hnsw_idx",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
            models.Index(fields=["application", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"BiometricProfile<user={self.user_id}, app={self.application_id}>"
```

> **Nota sobre el filtrado por tenant en la búsqueda ANN:** el índice HNSW de pgvector no soporta un índice compuesto `(application_id, embedding)`. La estrategia práctica es: `BiometricProfile.objects.filter(application=app, is_active=True).order_by(CosineDistance("embedding", query_vector))[:k]`. Con pgvector ≥ 0.7 el *iterative index scan* permite que el filtro `WHERE application_id = ...` conviva eficientemente con el índice HNSW; esto se validará con datos reales en la Fase 5 (pruebas de carga) y, si el volumen por tenant lo justifica, se evaluará particionar la tabla por `application_id`.

---

## 3. Especificación del Pipeline Biométrico — `BiometricService`

`BiometricService` es la única fachada pública que las vistas de DRF invocan. Internamente delega en cinco colaboradores desacoplados y componibles, cada uno con una única responsabilidad y una interfaz de entrada/salida simple (arrays de `numpy`/`bytes`, nunca objetos de Django). Esto permite testear cada etapa de forma aislada (con fixtures de video) y reemplazar cualquier modelo sin tocar las demás.

```
                         ┌─────────────────────────┐
  video_bytes (mp4/webm) │      BiometricService     │  → EnrollResult | AuthResult
 ───────────────────────►│         (fachada)          │
                         └────────────┬────────────┘
                                      │ orquesta en secuencia, corta temprano (fail-fast)
        ┌─────────────────────┬──────┴───────┬─────────────────────┬────────────────────┐
        ▼                     ▼              ▼                     ▼                    ▼
 1. FramePreprocessor  2. ActiveLiveness  3. PassiveLiveness   4. FaceEmbedder     5. VectorMatcher
   (OpenCV)              (MediaPipe)        (ONNX MiniFASNetV2)  (InsightFace)       (pgvector)
```

### 3.1 Responsabilidades de cada módulo

| # | Módulo | Librería | Entrada | Salida | Falla rápido si... |
|---|--------|----------|---------|--------|---------------------|
| 1 | `preprocessing.FramePreprocessor` | OpenCV | bytes de video | `list[np.ndarray]` (frames muestreados) + metadata (fps, resolución, brillo medio) | video corrupto, < N fps, resolución insuficiente, brillo fuera de rango, rostro no detectado en el encuadre |
| 2 | `liveness_active.ActiveLivenessChecker` | MediaPipe Face Landmarker (Tasks API) | frames + landmarks por frame | `bool` + `ActiveLivenessMetrics` (EAR mínimo/parpadeos detectados, delta de yaw/pitch) | no hay parpadeo detectado, cabeza completamente estática (posible foto/pantalla) |
| 3 | `liveness_passive.PassiveLivenessClassifier` | ONNXRuntime + MiniFASNetV2 | 1-3 frames clave (crop de rostro) | score de "real" por frame + score agregado | score agregado < `application.liveness_threshold` |
| 4 | `embeddings.FaceEmbedder` | InsightFace (`buffalo_s`) | mejor frame (el de mayor nitidez/score) | vector `float32[512]` normalizado (L2) | no se puede alinear/extraer el rostro con confianza suficiente |
| 5 | `vector_matcher.VectorMatcher` | pgvector (Django ORM) | embedding + `application` | `TenantUser` candidato + distancia coseno, o `None` | distancia > `application.match_threshold` (solo aplica en login) |

### 3.2 Contrato de la fachada

```python
# apps/biometrics/services/biometric_service.py  (firma de referencia, no implementación final)

from dataclasses import dataclass
import numpy as np

from apps.tenants.models import Application
from apps.accounts.models import TenantUser


@dataclass
class LivenessReport:
    passed: bool
    active_score: float       # agregación de métricas EAR + pose
    passive_score: float      # score MiniFASNetV2
    reason: str | None = None  # motivo descriptivo si passed=False


@dataclass
class EnrollResult:
    embedding: np.ndarray          # float32[512]
    liveness: LivenessReport
    quality_score: float


@dataclass
class AuthResult:
    matched_user: TenantUser | None
    distance: float | None
    liveness: LivenessReport


class BiometricService:
    """Orquesta el pipeline completo. Sin estado entre llamadas (stateless)."""

    def __init__(self, application: Application):
        self.application = application
        self._preprocessor = FramePreprocessor()
        self._active_liveness = ActiveLivenessChecker()
        self._passive_liveness = PassiveLivenessClassifier()
        self._embedder = FaceEmbedder()
        self._matcher = VectorMatcher(application=application)

    def process_enrollment(self, video_bytes: bytes) -> EnrollResult:
        """Usado en el Flujo B (Registro). No compara contra la BD, solo extrae y valida."""
        ...

    def process_authentication(self, video_bytes: bytes) -> AuthResult:
        """Usado en el Flujo A (Login). Extrae, valida liveness y compara contra la BD del tenant."""
        ...
```

### 3.3 Manejo de errores

Cada etapa lanza una excepción propia y descriptiva (definidas en `apps/biometrics/exceptions.py`), que la vista traduce a un código/mensaje HTTP consistente vía el exception handler de DRF (`core/exceptions.py`):

- `InvalidVideoError` (formato/corrupción) → 400
- `LowQualityCaptureError` (brillo, encuadre, fps) → 422 con motivo específico (para que el frontend no resetee el formulario y guíe al usuario, ej. "mejora la iluminación")
- `SpoofDetectedError` (liveness activo o pasivo falla) → 422
- `FaceNotFoundError` → 422
- `NoMatchFoundError` (solo en login) → 401
- `DuplicateBiometricError` (el rostro ya está enrolado en ese `app_id`, en registro) → 409

---

## 4. Panel de Administración (Fase 6)

El panel es la UI operativa de plataforma. **No** forma parte del flujo SSO biométrico: los operadores son `django.contrib.auth.User`, los usuarios finales son `TenantUser`.

### 4.1 Modelo de acceso (v1 → evolución)

| Versión | Quién entra | Cómo | Gate |
|---------|-------------|------|------|
| **v1 (actual)** | Operadores internos | `POST /api/v1/admin/auth/login/` con username/password → JWT SimpleJWT de Django User | `user.is_active and user.is_superuser` (`IsSuperUser`) |
| Futuro | Roles (`platform_admin`, `tenant_operator`, …) | Mismo contrato de tokens; claims/roles ampliados | Permission plug-in reemplazando/ampliando `IsSuperUser` sin cambiar paths |

Django Admin (`/admin/`) permanece como escape hatch. CLI (`create_application`, `rotate_api_key`) sigue válido para automatización.

### 4.2 Superficie HTTP

Prefijo: `/api/v1/admin/`. Tag OpenAPI: `admin`. Auth: `Authorization: Bearer <access>` (SimpleJWT / Django User).

| Método | Path | Rol |
|--------|------|-----|
| POST | `/auth/login/` | Emitir access/refresh si `is_superuser` |
| POST | `/auth/token/refresh/` | Renovar access |
| GET | `/auth/me/` | Datos del operador autenticado |
| GET/POST | `/applications/` | Listar / crear tenants |
| GET/PATCH | `/applications/{app_id}/` | Detalle / editar (name, active, redirect_uris, umbrales) |
| POST | `/applications/{app_id}/rotate-api-key/` | Rotar clave; plaintext **one-shot** en la respuesta |
| GET | `/applications/{app_id}/users/` | Usuarios del tenant (filtros + paginación) |
| GET/PATCH | `/users/{user_id}/` | Detalle / activar-desactivar / editar perfil |
| GET | `/users/{user_id}/biometric-profiles/` | Perfiles del usuario (**sin** vector embedding) |
| PATCH | `/biometric-profiles/{profile_id}/` | Solo `is_active` (soft-deactivate) |

Reglas de seguridad de datos:
- `api_key` **no** se incluye en list/retrieve; solo en la respuesta de create (si aplica política one-shot) y `rotate-api-key`.
- El embedding 512-d **nunca** se serializa hacia el panel.
- El alta de `TenantUser` sigue siendo el Flujo B biométrico; el panel no crea usuarios con video en v1.

### 4.3 Frontend

Rutas bajo `/admin/*` (sin `TenantProvider`):

- `/admin/login` — credenciales Django
- `/admin/applications` — listado + alta
- `/admin/applications/:appId` — detalle, edición, rotar key
- `/admin/applications/:appId/users` — usuarios del tenant
- `/admin/users/:userId` — detalle usuario + perfiles biométricos

Guard: redirige a `/admin/login` si no hay sesión de operador válida.

---

Ver el plan de ejecución detallado en [`MASTER_PLAN.md`](MASTER_PLAN.md).
