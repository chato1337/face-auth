"""
Emisión de tokens JWT para TenantUser (no ligados al User de Django).

Decisión Fase 2: tras login exitoso se emite un JWT de redirección de un solo uso
(corto TTL, claim `purpose=sso_redirect`) + access/refresh de sesión del servicio.
Un code-exchange OAuth2 completo queda como evolución futura documentada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from django.conf import settings
from rest_framework_simplejwt.tokens import Token

from apps.accounts.models import TenantUser
from apps.tenants.models import Application


class TenantAccessToken(Token):
    token_type = "access"
    lifetime = timedelta(minutes=30)


class TenantRefreshToken(Token):
    token_type = "refresh"
    lifetime = timedelta(days=7)
    access_token_class = TenantAccessToken


class SSORedirectToken(Token):
    """JWT de un solo uso para redirigir a la app cliente tras login/registro."""

    token_type = "sso_redirect"
    lifetime = timedelta(minutes=2)


def _base_claims(user: TenantUser) -> dict[str, Any]:
    return {
        "user_id": str(user.id),
        "app_id": user.application.app_id,
        "email": user.email,
        "jti": uuid4().hex,
    }


@dataclass(frozen=True)
class IssuedTokens:
    access: str
    refresh: str
    redirect_token: str
    redirect_url: str | None


class AuthenticationService:
    """Emite tokens/códigos dados un TenantUser autenticado biométricamente."""

    def issue_for_user(
        self,
        user: TenantUser,
        *,
        redirect_uri: str | None = None,
    ) -> IssuedTokens:
        application = user.application
        claims = _base_claims(user)

        access = TenantAccessToken()
        refresh = TenantRefreshToken()
        for key, value in claims.items():
            access[key] = value
            refresh[key] = value

        redirect = SSORedirectToken()
        for key, value in claims.items():
            redirect[key] = value
        redirect["purpose"] = "sso_redirect"
        redirect["nonce"] = uuid4().hex

        redirect_url = self._build_redirect_url(application, redirect_uri, str(redirect))

        user.last_login_at = datetime.now(timezone.utc)
        user.save(update_fields=["last_login_at", "updated_at"])

        return IssuedTokens(
            access=str(access),
            refresh=str(refresh),
            redirect_token=str(redirect),
            redirect_url=redirect_url,
        )

    def _build_redirect_url(
        self,
        application: Application,
        redirect_uri: str | None,
        token: str,
    ) -> str | None:
        if not redirect_uri:
            return None
        allowed = application.redirect_uris or []
        if redirect_uri not in allowed:
            return None
        separator = "&" if "?" in redirect_uri else "?"
        return f"{redirect_uri}{separator}token={token}"


# Compat: permitir RefreshToken estándar si se necesita en Fase 3
def issue_simplejwt_style(user: TenantUser) -> dict[str, str]:
    """Helper opcional usando API familiar de simplejwt (claims custom)."""
    service = AuthenticationService()
    issued = service.issue_for_user(user)
    return {
        "access": issued.access,
        "refresh": issued.refresh,
        "redirect_token": issued.redirect_token,
    }


# Asegura que simplejwt use SECRET_KEY de Django (default).
_ = settings.SECRET_KEY
