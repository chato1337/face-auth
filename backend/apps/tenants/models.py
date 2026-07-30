import secrets
import uuid

from django.db import models
from django.utils import timezone


def generate_app_id() -> str:
    return f"app_{secrets.token_urlsafe(12)}"


def generate_api_key() -> str:
    return secrets.token_hex(32)


class Application(models.Model):
    """
    Aplicación de terceros (tenant) que consume el SSO biométrico.
    Todo TenantUser / BiometricProfile está aislado por application.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    app_id = models.CharField(
        max_length=64,
        unique=True,
        default=generate_app_id,
        editable=False,
        db_index=True,
    )
    name = models.CharField(max_length=150)
    api_key = models.CharField(
        max_length=64,
        unique=True,
        default=generate_api_key,
        editable=False,
        help_text="Secreto de integración del tenant. Rotar con `rotate_api_key`.",
    )
    api_key_rotated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Última rotación de api_key (None = clave original de creación).",
    )
    is_active = models.BooleanField(default=True)

    redirect_uris = models.JSONField(
        default=list,
        help_text="Whitelist exacta de URLs a las que se permite redirigir tras login.",
    )

    liveness_threshold = models.FloatField(
        default=0.85,
        help_text="Score mínimo (0-1) del modelo de liveness pasivo para aceptar el intento.",
    )
    match_threshold = models.FloatField(
        default=0.42,
        help_text="Distancia coseno máxima aceptada entre embedding capturado y almacenado.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants_application"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.app_id})"

    def rotate_api_key(self) -> str:
        """
        Genera una nueva api_key e invalida la anterior de inmediato.
        Retorna el valor en claro (solo visible una vez al operador).
        """
        new_key = generate_api_key()
        self.api_key = new_key
        self.api_key_rotated_at = timezone.now()
        self.save(update_fields=["api_key", "api_key_rotated_at", "updated_at"])
        return new_key
