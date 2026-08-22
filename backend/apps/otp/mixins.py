"""Mixin reutilizable: el consumidor de una acción sensible llama consume() con su purpose."""

from __future__ import annotations

from apps.accounts.models import TenantUser
from apps.otp.models import OtpChallenge
from apps.otp.services import OtpService


class ConsumesOtpMixin:
    otp_purpose: str = OtpChallenge.Purpose.EMAIL_VERIFY

    def consume_otp(self, user: TenantUser, code: str) -> OtpChallenge:
        return OtpService().consume(user, self.otp_purpose, code)
