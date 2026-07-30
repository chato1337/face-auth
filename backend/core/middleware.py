"""
Middleware multi-tenant: resuelve Application desde header X-App-Id o query ?app_id=.

Prioridad: header X-App-Id > query param app_id.
Rutas bajo /api/ requieren app_id válido (salvo paths públicos explícitos).
"""
from __future__ import annotations

from django.http import JsonResponse

from apps.tenants.models import Application

# Paths de API que no exigen Application resuelta (docs, health, schema).
PUBLIC_API_PREFIXES = (
    "/api/docs",
    "/api/schema",
    "/api/v1/health",
)


class ApplicationResolverMiddleware:
    """Adjunta `request.application` (Application | None) a cada request."""

    HEADER_NAME = "HTTP_X_APP_ID"
    QUERY_PARAM = "app_id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.application = None

        app_id = request.META.get(self.HEADER_NAME) or request.GET.get(self.QUERY_PARAM)
        path = request.path

        requires_app = path.startswith("/api/") and not any(
            path.startswith(prefix) for prefix in PUBLIC_API_PREFIXES
        )

        if app_id:
            try:
                application = Application.objects.get(app_id=app_id)
            except Application.DoesNotExist:
                if requires_app:
                    return JsonResponse(
                        {"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
                        status=404,
                    )
            else:
                if not application.is_active:
                    if requires_app:
                        return JsonResponse(
                            {
                                "code": "app_inactive",
                                "message": "Application inactiva.",
                                "field": "app_id",
                            },
                            status=400,
                        )
                else:
                    request.application = application
        elif requires_app:
            return JsonResponse(
                {
                    "code": "app_id_required",
                    "message": "Se requiere header X-App-Id o query param app_id.",
                    "field": "app_id",
                },
                status=400,
            )

        return self.get_response(request)
