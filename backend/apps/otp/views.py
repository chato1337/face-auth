"""Endpoints genéricos OTP: request (emisión) y verify (UI, no consume)."""

from __future__ import annotations

from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.serializers import ErrorResponseSerializer
from apps.otp.pending import UNAUTHENTICATED_PURPOSES, lookup_subject, resolve_or_create_subject
from apps.otp.serializers import (
    OtpRequestResponseSerializer,
    OtpRequestSerializer,
    OtpVerifyResponseSerializer,
    OtpVerifySerializer,
)
from apps.otp.services import OtpService
from apps.tenants.models import Application
from core.throttling import OtpIssueRateThrottle, OtpVerifyRateThrottle

EX_OTP_RATE = OpenApiExample(
    "Rate limit de emisión",
    value={
        "code": "otp_rate_limited",
        "message": "Demasiados códigos solicitados. Intenta de nuevo en unos minutos.",
        "field": None,
    },
    response_only=True,
    status_codes=["429"],
)
EX_OTP_INVALID = OpenApiExample(
    "Código incorrecto",
    value={"code": "otp_invalid", "message": "Código incorrecto.", "field": "code"},
    response_only=True,
    status_codes=["400"],
)
EX_OTP_EXPIRED = OpenApiExample(
    "Código expirado",
    value={"code": "otp_expired", "message": "El código expiró. Solicita uno nuevo.", "field": None},
    response_only=True,
    status_codes=["400"],
)
EX_APP_NOT_FOUND = OpenApiExample(
    "Application no encontrada",
    value={"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
    response_only=True,
    status_codes=["404"],
)


def _resolve_application(app_id: str) -> Application | Response:
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
    return application


def _expires_in(challenge) -> int:
    remaining = int((challenge.expires_at - timezone.now()).total_seconds())
    return max(0, remaining)


class OtpRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, FormParser]
    throttle_classes = [OtpIssueRateThrottle]

    @extend_schema(
        tags=["otp"],
        summary="Solicitar código OTP",
        description=(
            "Emite un código de 6 dígitos al canal indicado (email en v1). "
            "Con purpose=email_verify crea un TenantUser pendiente si no existe. "
            "Cada emisión invalida el código anterior del mismo usuario y purpose. "
            "Máximo 3 códigos cada 5 minutos por usuario."
        ),
        request=OtpRequestSerializer,
        responses={
            200: OtpRequestResponseSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer, description="App inactiva / canal no soportado"),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Application no encontrada",
                examples=[EX_APP_NOT_FOUND],
            ),
            429: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Rate limit de emisión",
                examples=[EX_OTP_RATE],
            ),
            502: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Fallo de entrega del canal",
            ),
        },
    )
    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data["purpose"] not in UNAUTHENTICATED_PURPOSES:
            return Response(
                {
                    "code": "validation_error",
                    "message": "Este purpose no puede solicitarse sin autenticación.",
                    "field": "purpose",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        application = _resolve_application(data["app_id"])
        if isinstance(application, Response):
            return application

        user = resolve_or_create_subject(
            application=application,
            purpose=data["purpose"],
            email=data["email"],
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
            phone=data.get("phone") or "",
        )
        result = OtpService().issue(
            user,
            data["purpose"],
            channel=data.get("channel") or "email",
        )
        return Response(
            {
                "challenge_id": result.challenge_id,
                "expires_in": result.expires_in,
                "destination_masked": result.destination_masked,
                "channel": result.channel,
            }
        )


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, FormParser]
    throttle_classes = [OtpVerifyRateThrottle]

    @extend_schema(
        tags=["otp"],
        summary="Validar código OTP (no consume)",
        description=(
            "Comprueba el código para la UI. No lo marca como usado: "
            "el consumidor (p. ej. registro) debe enviar otp_code de nuevo y llamar consume()."
        ),
        request=OtpVerifySerializer,
        responses={
            200: OtpVerifyResponseSerializer,
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Código inválido / expirado / bloqueado / ya usado",
                examples=[EX_OTP_INVALID, EX_OTP_EXPIRED],
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Application no encontrada",
                examples=[EX_APP_NOT_FOUND],
            ),
        },
    )
    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        application = _resolve_application(data["app_id"])
        if isinstance(application, Response):
            return application

        user = lookup_subject(application=application, email=data["email"])
        challenge = OtpService().verify(user, data["purpose"], data["code"])
        return Response({"valid": True, "expires_in": _expires_in(challenge)})
