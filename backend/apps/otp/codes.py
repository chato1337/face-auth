"""Generación de códigos OTP numéricos."""

from __future__ import annotations

import secrets

OTP_CODE_LENGTH = 6


def generate_numeric_code(length: int = OTP_CODE_LENGTH) -> str:
    return f"{secrets.randbelow(10 ** length):0{length}d}"
