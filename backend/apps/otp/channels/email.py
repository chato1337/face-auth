from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from apps.otp.exceptions import OtpDeliveryFailedError

logger = logging.getLogger(__name__)


class SmtpEmailChannel:
    name = "email"

    def send(
        self,
        *,
        destination: str,
        purpose: str,
        code: str,
        context: dict[str, Any],
    ) -> None:
        ctx = {
            **context,
            "code": code,
            "purpose": purpose,
        }
        subject = self._render(f"otp/{purpose}_subject.txt", "otp/code_subject.txt", ctx).strip()
        text_body = self._render(f"otp/{purpose}.txt", "otp/code.txt", ctx)
        html_body = self._render_optional(f"otp/{purpose}.html", ctx)

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destination],
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")

        try:
            message.send(fail_silently=False)
        except Exception:
            logger.exception(
                "OTP email delivery failed purpose=%s host=%s port=%s tls=%s ssl=%s timeout=%s",
                purpose,
                settings.EMAIL_HOST,
                settings.EMAIL_PORT,
                settings.EMAIL_USE_TLS,
                settings.EMAIL_USE_SSL,
                getattr(settings, "EMAIL_TIMEOUT", None),
            )
            raise OtpDeliveryFailedError(
                "No se pudo entregar el código. Intenta de nuevo en unos minutos.",
            ) from None

    def _render(self, primary: str, fallback: str, ctx: dict[str, Any]) -> str:
        try:
            return render_to_string(primary, ctx)
        except TemplateDoesNotExist:
            return render_to_string(fallback, ctx)

    def _render_optional(self, name: str, ctx: dict[str, Any]) -> str | None:
        try:
            return render_to_string(name, ctx)
        except TemplateDoesNotExist:
            return None
