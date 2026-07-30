"""
Rate limiting por `app_id` + IP para endpoints biométricos (Fase 5).
"""
from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class AppIdScopedRateThrottle(SimpleRateThrottle):
    """
    Limita intentos de login/registro combinando IP del cliente y `app_id`.
    Mitiga fuerza bruta biométrica sin bloquear otros tenants en la misma IP.
    """

    scope = "biometric_auth"

    def get_cache_key(self, request, view):
        app_id = self._extract_app_id(request)
        if not app_id:
            # Sin app_id el serializer fallará después; throttlear por IP sola.
            app_id = "unknown"
        ident = self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{ident}:{app_id}",
        }

    def _extract_app_id(self, request) -> str | None:
        data = getattr(request, "data", None)
        if data is not None:
            value = data.get("app_id")
            if value:
                return str(value).strip()
        query = request.query_params.get("app_id")
        if query:
            return str(query).strip()
        header = request.headers.get("X-App-Id")
        if header:
            return str(header).strip()
        return None
