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
from urllib.parse import urlencode, urlparse, urlunparse
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


class InvalidRedirectUriError(ValueError):
    """La redirect_uri no está en la whitelist exacta del tenant."""


def _base_claims(user: TenantUser) -> dict[str, Any]:
    return {
        "user_id": str(user.id),
        "app_id": user.application.app_id,
        "email": user.email,
        "jti": uuid4().hex,
    }


def normalize_redirect_uri(uri: str) -> str:
    """
    Normaliza para comparación exacta (whitelist estricta, no por prefijo).
    - Rechaza fragmentos (#...)
    - Compara scheme/netloc/path/query literales tras strip
    - No reescribe path ni query (evita que un prefijo más largo matchee)
    """
    raw = (uri or "").strip()
    if not raw:
        raise InvalidRedirectUriError("redirect_uri vacía.")
    parsed = urlparse(raw)
    if parsed.fragment:
        raise InvalidRedirectUriError("redirect_uri no puede incluir fragmento (#).")
    if parsed.scheme not in ("http", "https"):
        raise InvalidRedirectUriError("redirect_uri debe usar http o https.")
    if not parsed.netloc:
        raise InvalidRedirectUriError("redirect_uri inválida (sin host).")
    # Reconstruir canónico sin fragmento; path vacío → "/"
    path = parsed.path if parsed.path else "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def is_allowed_redirect(application: Application, redirect_uri: str) -> bool:
    allowed = application.redirect_uris or []
    try:
        candidate = normalize_redirect_uri(redirect_uri)
    except InvalidRedirectUriError:
        return False
    for entry in allowed:
        try:
            if normalize_redirect_uri(str(entry)) == candidate:
                return True
        except InvalidRedirectUriError:
            continue
    return False


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
        require_allowed_redirect: bool = True,
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

        redirect_url = self._build_redirect_url(
            application,
            redirect_uri,
            str(redirect),
            require_allowed=require_allowed_redirect,
        )

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
        *,
        require_allowed: bool = True,
    ) -> str | None:
        if not redirect_uri:
            return None
        if not is_allowed_redirect(application, redirect_uri):
            if require_allowed:
                raise InvalidRedirectUriError(
                    "redirect_uri no está en la whitelist exacta de la Application."
                )
            return None
        base = normalize_redirect_uri(redirect_uri)
        parsed = urlparse(base)
        # Añadir token sin permitir inyección vía query previa maliciosa del caller:
        # usamos la URI ya normalizada y whitelistada.
        query_items = []
        if parsed.query:
            query_items.append(parsed.query)
        query_items.append(urlencode({"token": token}))
        new_query = "&".join(query_items)
        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, "", new_query, "")
        )


def issue_simplejwt_style(user: TenantUser) -> dict[str, str]:
    """Helper opcional usando API familiar de simplejwt (claims custom)."""
    service = AuthenticationService()
    issued = service.issue_for_user(user)
    return {
        "access": issued.access,
        "refresh": issued.refresh,
        "redirect_token": issued.redirect_token,
    }


_ = settings.SECRET_KEY
