"""Vistas de autenticación del panel admin (Django User / is_superuser)."""
from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.admin_serializers import (
    AdminLoginRequestSerializer,
    AdminLoginResponseSerializer,
    AdminMeSerializer,
    AdminTokenRefreshRequestSerializer,
    AdminTokenRefreshResponseSerializer,
    ErrorResponseSerializer,
)
from apps.authentication.admin_services import AdminAuthError, authenticate_superuser
from core.permissions import IsSuperUser

EX_INVALID_CREDENTIALS = OpenApiExample(
    "Credenciales inválidas",
    value={
        "code": "invalid_credentials",
        "message": "Usuario o contraseña incorrectos.",
        "field": None,
    },
    response_only=True,
    status_codes=["401"],
)
EX_NOT_SUPERUSER = OpenApiExample(
    "No es superuser",
    value={
        "code": "not_superuser",
        "message": "Acceso al panel restringido a superusers.",
        "field": None,
    },
    response_only=True,
    status_codes=["403"],
)
EX_INVALID_REFRESH = OpenApiExample(
    "Refresh inválido",
    value={
        "code": "invalid_token",
        "message": "Refresh token inválido o expirado.",
        "field": "refresh",
    },
    response_only=True,
    status_codes=["401"],
)


class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["admin"],
        summary="Login de operador (superuser)",
        request=AdminLoginRequestSerializer,
        responses={
            200: AdminLoginResponseSerializer,
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Credenciales inválidas",
                examples=[EX_INVALID_CREDENTIALS],
            ),
            403: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Usuario inactivo o sin is_superuser",
                examples=[EX_NOT_SUPERUSER],
            ),
        },
    )
    def post(self, request):
        serializer = AdminLoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user, tokens = authenticate_superuser(data["username"], data["password"])
        except AdminAuthError as exc:
            return Response(
                {"code": exc.code, "message": exc.message, "field": None},
                status=exc.http_status,
            )
        return Response(
            {
                "access": tokens.access,
                "refresh": tokens.refresh,
                "username": user.username,
                "email": user.email or "",
            }
        )


class AdminTokenRefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["admin"],
        summary="Refrescar access token de operador",
        request=AdminTokenRefreshRequestSerializer,
        responses={
            200: AdminTokenRefreshResponseSerializer,
            401: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Refresh inválido",
                examples=[EX_INVALID_REFRESH],
            ),
        },
    )
    def post(self, request):
        serializer = AdminTokenRefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data["refresh"]
        try:
            refresh = RefreshToken(raw)
            access = refresh.access_token
        except TokenError:
            return Response(
                {
                    "code": "invalid_token",
                    "message": "Refresh token inválido o expirado.",
                    "field": "refresh",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({"access": str(access), "refresh": str(refresh)})


class AdminMeView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        tags=["admin"],
        summary="Operador autenticado",
        responses={
            200: AdminMeSerializer,
            403: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="No es superuser",
                examples=[EX_NOT_SUPERUSER],
            ),
        },
    )
    def get(self, request):
        user = request.user
        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "email": user.email or "",
                "is_superuser": user.is_superuser,
                "is_staff": user.is_staff,
            }
        )
