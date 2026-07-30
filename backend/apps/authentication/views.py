"""
Vistas de autenticación biométrica (login / register / token refresh / token verify).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone as dt_timezone

from django.core.cache import cache
from django.db import IntegrityError, transaction
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.accounts.models import TenantUser
from apps.authentication.serializers import (
    ErrorResponseSerializer,
    LoginRequestSerializer,
    LoginResponseSerializer,
    RegisterRequestSerializer,
    RegisterResponseSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    TokenVerifyRequestSerializer,
    TokenVerifyResponseSerializer,
)
from apps.authentication.services import (
    AuthenticationService,
    InvalidRedirectUriError,
    SSORedirectToken,
    TenantAccessToken,
    TenantRefreshToken,
    is_allowed_redirect,
)
from apps.biometrics.exceptions import BiometricPipelineError
from apps.biometrics.services import BiometricService
from apps.tenants.models import Application
from core.throttling import AppIdScopedRateThrottle

# ---------------------------------------------------------------------------
# OpenAPI error examples (ARCHITECTURE §3.3)
# ---------------------------------------------------------------------------
EX_INVALID_VIDEO = OpenApiExample(
    "Video inválido",
    value={"code": "invalid_video", "message": "No se pudo abrir el video.", "field": "video"},
    response_only=True,
    status_codes=["400"],
)
EX_LOW_QUALITY = OpenApiExample(
    "Captura de baja calidad",
    value={
        "code": "low_quality_capture",
        "message": "Iluminación insuficiente. Mejora la luz del entorno.",
        "field": "video",
    },
    response_only=True,
    status_codes=["422"],
)
EX_SPOOF = OpenApiExample(
    "Spoof / liveness fallido",
    value={
        "code": "spoof_detected",
        "message": "Liveness activo fallido: no se detectó parpadeo",
        "field": "video",
    },
    response_only=True,
    status_codes=["422"],
)
EX_FACE_NOT_FOUND = OpenApiExample(
    "Rostro no encontrado",
    value={
        "code": "face_not_found",
        "message": "No se detectó un rostro de forma consistente en el clip.",
        "field": "video",
    },
    response_only=True,
    status_codes=["422"],
)
EX_NO_MATCH = OpenApiExample(
    "Sin coincidencia",
    value={"code": "no_match", "message": "No se encontró coincidencia biométrica.", "field": "video"},
    response_only=True,
    status_codes=["401"],
)
EX_DUPLICATE = OpenApiExample(
    "Biometría duplicada",
    value={
        "code": "duplicate_biometric",
        "message": "Este rostro ya está registrado en esta aplicación.",
        "field": "video",
    },
    response_only=True,
    status_codes=["409"],
)
EX_EMAIL_TAKEN = OpenApiExample(
    "Email duplicado",
    value={
        "code": "email_taken",
        "message": "Ya existe un usuario con este email en la aplicación.",
        "field": "email",
    },
    response_only=True,
    status_codes=["409"],
)
EX_APP_NOT_FOUND = OpenApiExample(
    "Application no encontrada",
    value={"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
    response_only=True,
    status_codes=["404"],
)
EX_APP_INACTIVE = OpenApiExample(
    "Application inactiva",
    value={"code": "app_inactive", "message": "Application inactiva.", "field": "app_id"},
    response_only=True,
    status_codes=["400"],
)
EX_INVALID_REDIRECT = OpenApiExample(
    "Redirect URI inválida",
    value={
        "code": "invalid_redirect_uri",
        "message": "redirect_uri no está en la whitelist exacta de la Application.",
        "field": "redirect_uri",
    },
    response_only=True,
    status_codes=["400"],
)
EX_INVALID_REFRESH = OpenApiExample(
    "Refresh inválido",
    value={"code": "invalid_token", "message": "Refresh token inválido o expirado.", "field": "refresh"},
    response_only=True,
    status_codes=["401"],
)
EX_INVALID_API_KEY = OpenApiExample(
    "API key inválida",
    value={"code": "invalid_api_key", "message": "X-Api-Key ausente o incorrecta.", "field": None},
    response_only=True,
    status_codes=["401"],
)
EX_INVALID_SSO_TOKEN = OpenApiExample(
    "Token SSO inválido",
    value={"code": "invalid_token", "message": "Token inválido, expirado o de otro tenant.", "field": "token"},
    response_only=True,
    status_codes=["401"],
)
EX_TOKEN_ALREADY_USED = OpenApiExample(
    "Token ya consumido",
    value={"code": "token_already_used", "message": "El token ya fue verificado (un solo uso).", "field": "token"},
    response_only=True,
    status_codes=["401"],
)
EX_USER_INACTIVE = OpenApiExample(
    "Usuario inactivo",
    value={"code": "user_inactive", "message": "El usuario está desactivado en esta aplicación.", "field": "token"},
    response_only=True,
    status_codes=["401"],
)

ERROR_RESPONSES_COMMON = {
    400: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Request inválido / app inactiva / video inválido / redirect inválida",
        examples=[EX_INVALID_VIDEO, EX_APP_INACTIVE, EX_INVALID_REDIRECT],
    ),
    404: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Application no encontrada",
        examples=[EX_APP_NOT_FOUND],
    ),
    422: OpenApiResponse(
        response=ErrorResponseSerializer,
        description="Calidad / liveness / rostro",
        examples=[EX_LOW_QUALITY, EX_SPOOF, EX_FACE_NOT_FOUND],
    ),
    429: OpenApiResponse(
        description="Rate limit excedido (app_id + IP)",
    ),
}


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


def _read_video_bytes(uploaded) -> bytes:
    return uploaded.read()


def _reject_invalid_redirect(application: Application, redirect_uri: str | None) -> Response | None:
    """Whitelist exacta: si el cliente envía redirect_uri, debe coincidir 1:1 (normalizada)."""
    if not redirect_uri:
        return None
    if is_allowed_redirect(application, redirect_uri):
        return None
    return Response(
        {
            "code": "invalid_redirect_uri",
            "message": "redirect_uri no está en la whitelist exacta de la Application.",
            "field": "redirect_uri",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _tokens_payload(issued) -> dict:
    return {
        "access": issued.access,
        "refresh": issued.refresh,
        "redirect_token": issued.redirect_token,
        "redirect_url": issued.redirect_url,
    }


def _liveness_payload(report) -> dict:
    return {
        "passed": report.passed,
        "active_score": report.active_score,
        "passive_score": report.passive_score,
        "reason": report.reason,
    }


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [AppIdScopedRateThrottle]

    @extend_schema(
        tags=["auth"],
        summary="Login biométrico",
        description=(
            "Flujo A: procesa el video, valida liveness y busca match en el tenant. "
            "Éxito → tokens + redirect_url opcional."
        ),
        request=LoginRequestSerializer,
        responses={
            200: LoginResponseSerializer,
            **ERROR_RESPONSES_COMMON,
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Sin match biométrico",
                examples=[EX_NO_MATCH],
            ),
        },
    )
    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        application = _resolve_application(data["app_id"])
        if isinstance(application, Response):
            return application

        rejected = _reject_invalid_redirect(application, data.get("redirect_uri"))
        if rejected is not None:
            return rejected

        video_bytes = _read_video_bytes(data["video"])
        try:
            service = BiometricService(application)
            try:
                result = service.process_authentication(video_bytes)
            except BiometricPipelineError:
                raise

            user = result.matched_user
            assert user is not None
            try:
                issued = AuthenticationService().issue_for_user(
                    user,
                    redirect_uri=data.get("redirect_uri"),
                )
            except InvalidRedirectUriError:
                return Response(
                    {
                        "code": "invalid_redirect_uri",
                        "message": "redirect_uri no está en la whitelist exacta de la Application.",
                        "field": "redirect_uri",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "distance": result.distance,
                    "liveness": _liveness_payload(result.liveness),
                    "tokens": _tokens_payload(issued),
                }
            )
        finally:
            # No persistir el clip crudo más allá del procesamiento.
            del video_bytes


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [AppIdScopedRateThrottle]

    @extend_schema(
        tags=["auth"],
        summary="Registro biométrico",
        description=(
            "Flujo B: valida liveness, extrae embedding y crea TenantUser. "
            "En error el cliente debe conservar el formulario y solo reintentar el video."
        ),
        request=RegisterRequestSerializer,
        responses={
            201: RegisterResponseSerializer,
            **ERROR_RESPONSES_COMMON,
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Email o biometría duplicada",
                examples=[EX_DUPLICATE, EX_EMAIL_TAKEN],
            ),
        },
    )
    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        application = _resolve_application(data["app_id"])
        if isinstance(application, Response):
            return application

        rejected = _reject_invalid_redirect(application, data.get("redirect_uri"))
        if rejected is not None:
            return rejected

        if TenantUser.objects.filter(application=application, email__iexact=data["email"]).exists():
            return Response(
                {
                    "code": "email_taken",
                    "message": "Ya existe un usuario con este email en la aplicación.",
                    "field": "email",
                },
                status=status.HTTP_409_CONFLICT,
            )

        video_bytes = _read_video_bytes(data["video"])
        try:
            service = BiometricService(application)
            enroll = service.process_enrollment(video_bytes)

            try:
                with transaction.atomic():
                    user = TenantUser.objects.create(
                        application=application,
                        first_name=data["first_name"],
                        last_name=data["last_name"],
                        email=data["email"],
                        phone=data.get("phone") or "",
                    )
                    service.persist_enrollment(user, enroll)
            except IntegrityError:
                return Response(
                    {
                        "code": "email_taken",
                        "message": "Ya existe un usuario con este email en la aplicación.",
                        "field": "email",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            try:
                issued = AuthenticationService().issue_for_user(
                    user,
                    redirect_uri=data.get("redirect_uri"),
                )
            except InvalidRedirectUriError:
                return Response(
                    {
                        "code": "invalid_redirect_uri",
                        "message": "redirect_uri no está en la whitelist exacta de la Application.",
                        "field": "redirect_uri",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    "user_id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "liveness": _liveness_payload(enroll.liveness),
                    "quality_score": enroll.quality_score,
                    "tokens": _tokens_payload(issued),
                },
                status=status.HTTP_201_CREATED,
            )
        finally:
            del video_bytes


class TokenRefreshView(APIView):
    """Refresh de access token usando TenantRefreshToken (no User de Django)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, FormParser]

    @extend_schema(
        tags=["auth"],
        summary="Refrescar access token",
        request=TokenRefreshRequestSerializer,
        responses={
            200: TokenRefreshResponseSerializer,
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Refresh inválido",
                examples=[EX_INVALID_REFRESH],
            ),
        },
    )
    def post(self, request):
        serializer = TokenRefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data["refresh"]
        try:
            refresh = TenantRefreshToken(raw)
        except Exception:  # noqa: BLE001 — TokenError y variantes
            return Response(
                {
                    "code": "invalid_token",
                    "message": "Refresh token inválido o expirado.",
                    "field": "refresh",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access = TenantAccessToken()
        for claim in ("user_id", "app_id", "email"):
            if claim in refresh:
                access[claim] = refresh[claim]

        return Response({"access": str(access), "refresh": str(refresh)})


# TTL del registro anti-replay: mayor que la vida del SSORedirectToken (2 min).
SSO_JTI_CACHE_TTL_SECONDS = 5 * 60


def _invalid_sso_token_response() -> Response:
    return Response(
        {
            "code": "invalid_token",
            "message": "Token inválido, expirado o de otro tenant.",
            "field": "token",
        },
        status=status.HTTP_401_UNAUTHORIZED,
    )


class TokenVerifyView(APIView):
    """
    Verificación server-to-server del `redirect_token` que la app cliente
    recibe en su callback SSO (`?token=...`). Autenticada con la `api_key`
    del tenant (header `X-Api-Key`). Consumo de un solo uso: el `jti` se
    registra en cache y una segunda verificación del mismo token falla.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, FormParser]
    throttle_classes = [AppIdScopedRateThrottle]

    @extend_schema(
        tags=["auth"],
        summary="Verificar token de redirección SSO (server-to-server)",
        description=(
            "La app cliente valida en su backend el `token` recibido en el callback. "
            "Requiere la `api_key` del tenant en el header `X-Api-Key`. "
            "El token es de un solo uso: la primera verificación exitosa lo consume."
        ),
        parameters=[
            OpenApiParameter(
                name="X-Api-Key",
                type=str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="api_key del tenant (server-to-server; nunca exponer en el navegador).",
            ),
        ],
        request=TokenVerifyRequestSerializer,
        responses={
            200: TokenVerifyResponseSerializer,
            400: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Application inactiva",
                examples=[EX_APP_INACTIVE],
            ),
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="api_key o token inválidos / token ya usado / usuario inactivo",
                examples=[
                    EX_INVALID_API_KEY,
                    EX_INVALID_SSO_TOKEN,
                    EX_TOKEN_ALREADY_USED,
                    EX_USER_INACTIVE,
                ],
            ),
            404: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Application no encontrada",
                examples=[EX_APP_NOT_FOUND],
            ),
            429: OpenApiResponse(description="Rate limit excedido (app_id + IP)"),
        },
    )
    def post(self, request):
        serializer = TokenVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        application = _resolve_application(data["app_id"])
        if isinstance(application, Response):
            return application

        provided_key = request.headers.get("X-Api-Key") or ""
        if not secrets.compare_digest(application.api_key, provided_key):
            return Response(
                {"code": "invalid_api_key", "message": "X-Api-Key ausente o incorrecta.", "field": None},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            # Valida firma, expiración y token_type == "sso_redirect".
            token = SSORedirectToken(data["token"])
        except TokenError:
            return _invalid_sso_token_response()

        payload = token.payload
        if payload.get("purpose") != "sso_redirect" or payload.get("app_id") != application.app_id:
            return _invalid_sso_token_response()

        jti = payload.get("jti")
        if not jti:
            return _invalid_sso_token_response()

        try:
            user = TenantUser.objects.get(id=payload.get("user_id"), application=application)
        except (TenantUser.DoesNotExist, ValueError, TypeError):
            return _invalid_sso_token_response()

        if not user.is_active:
            return Response(
                {
                    "code": "user_inactive",
                    "message": "El usuario está desactivado en esta aplicación.",
                    "field": "token",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Consumo atómico de un solo uso: cache.add falla si el jti ya existe.
        if not cache.add(f"sso_redirect_used:{jti}", True, timeout=SSO_JTI_CACHE_TTL_SECONDS):
            return Response(
                {
                    "code": "token_already_used",
                    "message": "El token ya fue verificado (un solo uso).",
                    "field": "token",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        expires_at = datetime.fromtimestamp(payload["exp"], tz=dt_timezone.utc)
        return Response(
            {
                "valid": True,
                "user_id": user.id,
                "app_id": application.app_id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "expires_at": expires_at,
            }
        )
