from rest_framework.permissions import BasePermission


class HasValidAppId(BasePermission):
    """
    Exige que ApplicationResolverMiddleware haya resuelto request.application.
    Usar en vistas DRF multi-tenant.
    """

    message = "Se requiere un app_id válido (header X-App-Id o query param app_id)."

    def has_permission(self, request, view) -> bool:
        return getattr(request, "application", None) is not None


class IsSuperUser(BasePermission):
    """
    Gate v1 del panel admin: solo Django User con is_superuser=True.

    Evolución futura: reemplazar/ampliar por IsPlatformOperator basado en roles
    sin cambiar los paths `/api/v1/admin/`.
    """

    message = "Se requiere un usuario superuser activo."
    code = "not_superuser"

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_superuser
        )
