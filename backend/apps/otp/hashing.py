"""HMAC de códigos OTP y destinos. Nunca se persiste el código en claro."""

from __future__ import annotations

import hashlib
import hmac

from django.conf import settings


def _pepper() -> bytes:
    value = getattr(settings, "OTP_PEPPER", None) or settings.SECRET_KEY
    if isinstance(value, bytes):
        return value
    return str(value).encode()


def hash_code(*, user_id: str, purpose: str, code: str) -> str:
    message = f"{user_id}:{purpose}:{code}".encode()
    return hmac.new(_pepper(), message, hashlib.sha256).hexdigest()


def hash_destination(destination: str) -> str:
    normalized = destination.strip().lower().encode()
    return hmac.new(_pepper(), normalized, hashlib.sha256).hexdigest()


def compare_hash(stored: str, computed: str) -> bool:
    return hmac.compare_digest(stored, computed)
