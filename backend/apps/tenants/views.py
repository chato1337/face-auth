from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.models import Application
from apps.tenants.serializers import ApplicationPublicSerializer

ERROR_APP_NOT_FOUND = OpenApiExample(
    "Application no encontrada",
    value={"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
    response_only=True,
    status_codes=["404"],
)

ERROR_APP_INACTIVE = OpenApiExample(
    "Application inactiva",
    value={"code": "app_inactive", "message": "Application inactiva.", "field": "app_id"},
    response_only=True,
    status_codes=["400"],
)


class ApplicationDetailView(APIView):
    """
    Validación pública de existencia de Application para el frontend
    antes de iniciar login/registro. No requiere header X-App-Id.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["tenants"],
        summary="Obtener Application por app_id",
        parameters=[
            OpenApiParameter(
                name="app_id",
                type=str,
                location=OpenApiParameter.PATH,
                description="Identificador público del tenant (ej. app_xxxxx).",
            ),
        ],
        responses={
            200: ApplicationPublicSerializer,
            400: OpenApiResponse(description="Application inactiva", examples=[ERROR_APP_INACTIVE]),
            404: OpenApiResponse(description="No encontrada", examples=[ERROR_APP_NOT_FOUND]),
        },
    )
    def get(self, request, app_id: str):
        try:
            application = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist:
            return Response(
                {"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not application.is_active:
            return Response(
                {"code": "app_inactive", "message": "Application inactiva.", "field": "app_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ApplicationPublicSerializer(application).data)
