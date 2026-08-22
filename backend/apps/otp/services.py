"""Servicio de dominio OTP: issue / verify / consume. Única puerta de escritura del modelo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import TenantUser
from apps.otp.channels import get_channel
from apps.otp.codes import generate_numeric_code
from apps.otp.exceptions import (
    OtpConsumedError,
    OtpExpiredError,
    OtpInvalidError,
    OtpLockedError,
    OtpNotFoundError,
    OtpRateLimitedError,
)
from apps.otp.hashing import compare_hash, hash_code, hash_destination
from apps.otp.masking import mask_email
from apps.otp.models import OtpChallenge


@dataclass(frozen=True)
class IssueResult:
    challenge_id: UUID
    expires_in: int
    destination_masked: str
    channel: str


class OtpService:
    def issue(
        self,
        user: TenantUser,
        purpose: str,
        *,
        channel: str = OtpChallenge.Channel.EMAIL,
        context: dict | None = None,
    ) -> IssueResult:
        destination = self._destination_for(user, channel)
        channel_impl = get_channel(channel)
        self._assert_issue_rate_limit(user, purpose)

        ttl = int(settings.OTP_TTL_SECONDS)
        now = timezone.now()
        code = generate_numeric_code()

        with transaction.atomic():
            self._invalidate_active(user, purpose, now)
            challenge = OtpChallenge.objects.create(
                user=user,
                application=user.application,
                purpose=purpose,
                channel=channel,
                destination_hash=hash_destination(destination),
                code_hash=hash_code(user_id=str(user.id), purpose=purpose, code=code),
                expires_at=now + timedelta(seconds=ttl),
            )

        ttl_minutes = max(1, ttl // 60)
        send_context = {
            "ttl_minutes": ttl_minutes,
            "first_name": user.first_name,
            **(context or {}),
        }
        channel_impl.send(
            destination=destination,
            purpose=purpose,
            code=code,
            context=send_context,
        )

        return IssueResult(
            challenge_id=challenge.id,
            expires_in=ttl,
            destination_masked=self._mask(channel, destination),
            channel=channel,
        )

    def verify(self, user: TenantUser, purpose: str, code: str) -> OtpChallenge:
        with transaction.atomic():
            challenge = self._lock_latest(user, purpose)
            self._assert_usable(challenge)
            self._assert_code_matches(challenge, code)
            if challenge.verified_at is None:
                challenge.verified_at = timezone.now()
                challenge.save(update_fields=["verified_at"])
            return challenge

    def consume(self, user: TenantUser, purpose: str, code: str) -> OtpChallenge:
        with transaction.atomic():
            challenge = self._lock_latest(user, purpose)
            self._assert_usable(challenge)
            self._assert_code_matches(challenge, code)
            now = timezone.now()
            challenge.consumed_at = now
            if challenge.verified_at is None:
                challenge.verified_at = now
            challenge.save(update_fields=["consumed_at", "verified_at"])
            return challenge

    def _lock_latest(self, user: TenantUser, purpose: str) -> OtpChallenge:
        challenge = (
            OtpChallenge.objects.select_for_update()
            .filter(user=user, purpose=purpose)
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            raise OtpNotFoundError("No hay un código activo. Solicita uno nuevo.")
        return challenge

    def _assert_usable(self, challenge: OtpChallenge) -> None:
        max_attempts = int(settings.OTP_VERIFY_MAX_ATTEMPTS)
        if challenge.consumed_at is not None:
            raise OtpConsumedError("Este código ya fue utilizado.")
        if (
            challenge.invalidated_at is not None
            and challenge.attempt_count >= max_attempts
        ):
            raise OtpLockedError(
                "Demasiados intentos. Solicita un código nuevo.",
            )
        if challenge.invalidated_at is not None:
            raise OtpNotFoundError("No hay un código activo. Solicita uno nuevo.")
        if challenge.expires_at <= timezone.now():
            raise OtpExpiredError("El código expiró. Solicita uno nuevo.")

    def _assert_code_matches(self, challenge: OtpChallenge, code: str) -> None:
        expected = hash_code(
            user_id=str(challenge.user_id),
            purpose=challenge.purpose,
            code=code.strip(),
        )
        if compare_hash(challenge.code_hash, expected):
            return

        challenge.attempt_count += 1
        max_attempts = int(settings.OTP_VERIFY_MAX_ATTEMPTS)
        update = ["attempt_count"]
        if challenge.attempt_count >= max_attempts:
            challenge.invalidated_at = timezone.now()
            update.append("invalidated_at")
            challenge.save(update_fields=update)
            raise OtpLockedError(
                "Demasiados intentos. Solicita un código nuevo.",
            )
        challenge.save(update_fields=update)
        raise OtpInvalidError("Código incorrecto.", field="code")

    def _assert_issue_rate_limit(self, user: TenantUser, purpose: str) -> None:
        window = timedelta(seconds=int(settings.OTP_ISSUE_WINDOW_SECONDS))
        since = timezone.now() - window
        qs = OtpChallenge.objects.filter(
            user=user,
            purpose=purpose,
            created_at__gte=since,
        )
        issued = qs.count()
        if issued < int(settings.OTP_ISSUE_MAX):
            return
        oldest = qs.order_by("created_at").first()
        retry_after = 1
        if oldest is not None:
            remaining = oldest.created_at + window - timezone.now()
            retry_after = max(1, int(remaining.total_seconds()))
        raise OtpRateLimitedError(
            "Demasiados códigos solicitados. Intenta de nuevo en unos minutos.",
            retry_after=retry_after,
        )

    def _invalidate_active(self, user: TenantUser, purpose: str, now) -> None:
        OtpChallenge.objects.filter(
            user=user,
            purpose=purpose,
            consumed_at__isnull=True,
            invalidated_at__isnull=True,
        ).update(invalidated_at=now)

    def _destination_for(self, user: TenantUser, channel: str) -> str:
        if channel == OtpChallenge.Channel.EMAIL:
            return user.email
        if channel in (OtpChallenge.Channel.SMS, OtpChallenge.Channel.WHATSAPP):
            return user.phone
        return user.email

    def _mask(self, channel: str, destination: str) -> str:
        if channel == OtpChallenge.Channel.EMAIL:
            return mask_email(destination)
        return "***"
