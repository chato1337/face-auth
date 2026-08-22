"""Enmascara destinos para respuestas públicas (anti-enumeración / PII)."""


def mask_email(email: str) -> str:
    local, sep, domain = email.strip().partition("@")
    if not sep or not domain:
        return "***"
    visible = local[:1] if local else ""
    return f"{visible}***@{domain.lower()}"
