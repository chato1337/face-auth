from rest_framework.permissions import BasePermission


class HasValidAppId(BasePermission):
    """
    Exige que ApplicationResolverMiddleware haya resuelto request.application.
    Usar en vistas DRF multi-tenant.
    """

    message = "Se requiere un app_id válido (header X-App-Id o query param app_id)."

    def has_permission(self, request, view) -> bool:
        return getattr(request, "application", None) is not None
