"""
Django settings base — compartidos entre entornos.
"""
from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    LIVENESS_THRESHOLD_DEFAULT=(float, 0.85),
    MATCH_THRESHOLD_DEFAULT=(float, 0.42),
)

# Lee .env desde la raíz del monorepo o desde backend/
environ.Env.read_env(BASE_DIR.parent / ".env")
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    # Local apps (modelos de dominio llegan en Fase 2)
    "apps.tenants.apps.TenantsConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.biometrics.apps.BiometricsConfig",
    "apps.authentication.apps.AuthenticationConfig",
    "apps.otp.apps.OtpConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.ApplicationResolverMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Preferir DATABASE_URL si existe; si no, armar desde POSTGRES_*.
if env("DATABASE_URL", default=None):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="faceauth"),
            "USER": env("POSTGRES_USER", default="faceauth"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="faceauth"),
            "HOST": env("POSTGRES_HOST", default="localhost"),
            "PORT": env("POSTGRES_PORT", default="5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF / OpenAPI / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "EXCEPTION_HANDLER": "core.exceptions.face_auth_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        # Login/registro biométrico: por app_id + IP (ver core.throttling).
        "biometric_auth": env("BIOMETRIC_AUTH_THROTTLE", default="30/min"),
        "otp_issue": env("OTP_IP_THROTTLE", default="10/min"),
        "otp_verify": env("OTP_VERIFY_IP_THROTTLE", default="20/min"),
    },
}

# Cache en memoria para throttling DRF (reemplazar por Redis en multi-worker prod).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "faceauth-throttle",
    }
}

# Videos ≤15 MB en memoria; no se escriben a MEDIA_ROOT.
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024

SPECTACULAR_SETTINGS = {
    "TITLE": "Face-Auth API",
    "DESCRIPTION": (
        "Servicio de autenticación biométrica SSO multi-tenant.\n\n"
        "Errores del pipeline biométrico usan el payload uniforme "
        "`{code, message, field}` (ver códigos en ARCHITECTURE §3.3)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "tenants", "description": "Validación pública de Applications."},
        {"name": "auth", "description": "Login / registro biométrico y refresh de tokens."},
        {"name": "otp", "description": "Emisión y verificación de códigos de un solo uso (ATO)."},
        {
            "name": "admin",
            "description": (
                "Panel de administración de plataforma (Fase 6). "
                "Requiere JWT de Django User con is_superuser=True."
            ),
        },
        {"name": "system", "description": "Health y utilidades."},
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "SIGNING_KEY": SECRET_KEY,
    "ALGORITHM": "HS256",
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

# Header multi-tenant enviado por el frontend (apiFetch / apiMultipart).
CORS_ALLOW_HEADERS = (
    *default_headers,
    "x-app-id",
)

# Umbrales por defecto del pipeline (sobreescritos por Application en runtime)
LIVENESS_THRESHOLD_DEFAULT = env("LIVENESS_THRESHOLD_DEFAULT")
MATCH_THRESHOLD_DEFAULT = env("MATCH_THRESHOLD_DEFAULT")

# Pesos ONNX / InsightFace (fuera de git; se descargan en build)
ML_MODELS_DIR = BASE_DIR / "apps" / "biometrics" / "ml_models"

# ---------------------------------------------------------------------------
# OTP / email
# ---------------------------------------------------------------------------
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=300)
OTP_ISSUE_MAX = env.int("OTP_ISSUE_MAX", default=3)
OTP_ISSUE_WINDOW_SECONDS = env.int("OTP_ISSUE_WINDOW_SECONDS", default=300)
OTP_VERIFY_MAX_ATTEMPTS = env.int("OTP_VERIFY_MAX_ATTEMPTS", default=5)
OTP_PEPPER = env("OTP_PEPPER", default=SECRET_KEY)

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="Face-Auth <noreply@localhost>",
)
