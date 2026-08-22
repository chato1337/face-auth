import uuid

from django.db import models
from django.utils import timezone

from apps.accounts.models import TenantUser
from apps.tenants.models import Application


class OtpChallenge(models.Model):
    """
    Desafío OTP atado a un TenantUser y a un purpose.
    El código en claro nunca se persiste: solo `code_hash` (HMAC-SHA256).
    """

    class Purpose(models.TextChoices):
        EMAIL_VERIFY = "email_verify", "Verificación de email"
        STEP_UP = "step_up", "Step-up de acción sensible"
        ACCOUNT_UNLOCK = "account_unlock", "Desbloqueo de cuenta"
        EMAIL_CHANGE = "email_change", "Cambio de email"
        REENROLLMENT = "reenrollment", "Re-enrolamiento biométrico"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        TenantUser,
        on_delete=models.CASCADE,
        related_name="otp_challenges",
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="otp_challenges",
        editable=False,
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    channel = models.CharField(
        max_length=16,
        choices=Channel.choices,
        default=Channel.EMAIL,
    )
    destination_hash = models.CharField(max_length=64)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "otp_challenge"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "-created_at"]),
            models.Index(fields=["user", "purpose", "consumed_at", "invalidated_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.user_id and not self.application_id:
            self.application_id = self.user.application_id
        super().save(*args, **kwargs)

    @property
    def is_active(self) -> bool:
        return (
            self.consumed_at is None
            and self.invalidated_at is None
            and self.expires_at > timezone.now()
        )

    def __str__(self) -> str:
        return f"OtpChallenge<{self.purpose} user={self.user_id} active={self.is_active}>"
