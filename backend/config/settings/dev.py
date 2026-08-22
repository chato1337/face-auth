"""Settings de desarrollo local."""
from .base import *  # noqa: F401, F403

DEBUG = True

# No envía red: el código OTP se imprime en la consola de runserver.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ALLOWED_HOSTS = ["*"]

CORS_ALLOW_ALL_ORIGINS = True

# Logs del pipeline biométrico visibles en la consola de runserver.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "pipeline": {
            "format": "{asctime} {levelname} {name} | {message}",
            "style": "{",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "pipeline",
        },
    },
    "loggers": {
        "apps.biometrics": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
