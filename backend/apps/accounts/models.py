import uuid

from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.tenants.models import Application


class TenantUser(models.Model):
    """
    Usuario final de un único Application.
    Unicidad de email por tenant (no global). No extiende AbstractUser:
    el login no usa contraseña.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="users",
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)

    is_active = models.BooleanField(default=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
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
    Embedding facial (512-d) de un TenantUser (InsightFace buffalo_s).
    Varios perfiles por usuario permiten re-enrolamiento con histórico.
    """

    class SourceModel(models.TextChoices):
        BUFFALO_S = "buffalo_s", "InsightFace buffalo_s"
        MOBILEFACENET = "mobilefacenet", "MobileFaceNet"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name="biometric_profiles",
    )
    # Denormalizado: filtra por tenant en ANN sin JOIN a TenantUser.
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="biometric_profiles",
        editable=False,
    )

    embedding = VectorField(dimensions=512)
    model_version = models.CharField(
        max_length=30,
        choices=SourceModel.choices,
        default=SourceModel.BUFFALO_S,
    )

    liveness_score = models.FloatField(
        help_text="Score de anti-spoofing pasivo al momento del enrolamiento.",
    )
    quality_score = models.FloatField(null=True, blank=True)

    is_active = models.BooleanField(
        default=True,
        help_text="Desactiva un embedding antiguo al re-enrolar sin perder histórico.",
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

    def save(self, *args, **kwargs):
        if self.user_id and not self.application_id:
            self.application_id = self.user.application_id
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"BiometricProfile<user={self.user_id}, app={self.application_id}>"
