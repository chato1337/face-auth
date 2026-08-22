from __future__ import annotations

from typing import Any, Protocol


class NotificationChannel(Protocol):
    """Canal de entrega de OTP. Nuevos canales (SMS, WhatsApp) implementan este contrato."""

    name: str

    def send(
        self,
        *,
        destination: str,
        purpose: str,
        code: str,
        context: dict[str, Any],
    ) -> None: ...
