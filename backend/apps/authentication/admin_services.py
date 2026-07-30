"""Emisión de JWT para operadores del panel (Django User / is_superuser)."""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import authenticate
from django.contrib.auth.models import AbstractBaseUser, User
from rest_framework_simplejwt.tokens import RefreshToken


class AdminAuthError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 401):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


@dataclass(frozen=True)
class AdminTokenPair:
    access: str
    refresh: str


def issue_admin_tokens(user: AbstractBaseUser) -> AdminTokenPair:
    refresh = RefreshToken.for_user(user)
    return AdminTokenPair(access=str(refresh.access_token), refresh=str(refresh))


def authenticate_superuser(username: str, password: str) -> tuple[User, AdminTokenPair]:
    """
    Valida credenciales y exige is_superuser activo.
    Raises AdminAuthError con code invalid_credentials | inactive_user | not_superuser.
    """
    user = authenticate(username=username, password=password)
    if user is None:
        raise AdminAuthError(
            code="invalid_credentials",
            message="Usuario o contraseña incorrectos.",
            http_status=401,
        )
    if not user.is_active:
        raise AdminAuthError(
            code="inactive_user",
            message="Usuario inactivo.",
            http_status=403,
        )
    if not user.is_superuser:
        raise AdminAuthError(
            code="not_superuser",
            message="Acceso al panel restringido a superusers.",
            http_status=403,
        )
    return user, issue_admin_tokens(user)
