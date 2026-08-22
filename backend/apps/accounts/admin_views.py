"""Gestión admin de TenantUser y BiometricProfile."""
from __future__ import annotations

from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import BiometricProfile, TenantUser
from apps.accounts.serializers import (
    BiometricProfileAdminSerializer,
    BiometricProfileAdminUpdateSerializer,
    TenantUserAdminSerializer,
    TenantUserAdminUpdateSerializer,
)
from apps.authentication.serializers import ErrorResponseSerializer
from apps.tenants.models import Application
from core.pagination import AdminPageNumberPagination
from core.permissions import IsSuperUser

EX_USER_NOT_FOUND = OpenApiExample(
    "Usuario no encontrado",
    value={"code": "user_not_found", "message": "Usuario no encontrado.", "field": "user_id"},
    response_only=True,
    status_codes=["404"],
)
EX_APP_NOT_FOUND = OpenApiExample(
    "Application no encontrada",
    value={"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
    response_only=True,
    status_codes=["404"],
)
EX_PROFILE_NOT_FOUND = OpenApiExample(
    "Perfil no encontrado",
    value={
        "code": "profile_not_found",
        "message": "Perfil biométrico no encontrado.",
        "field": "profile_id",
    },
    response_only=True,
    status_codes=["404"],
)


def _annotate_users(qs):
    return qs.annotate(
        active_profiles_count=Count("biometric_profiles", filter=Q(biometric_profiles__is_active=True)),
    )


class AdminTenantUserListView(APIView):
    permission_classes = [IsSuperUser]
    pagination_class = AdminPageNumberPagination

    @extend_schema(
        tags=["admin"],
        summary="Listar usuarios de un tenant",
        parameters=[
            OpenApiParameter(name="email", type=str, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                name="is_active",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
            ),
            OpenApiParameter(name="q", type=str, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
            ),
        ],
        responses={
            200: TenantUserAdminSerializer(many=True),
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_APP_NOT_FOUND]),
        },
    )
    def get(self, request, app_id: str):
        if not Application.objects.filter(app_id=app_id).exists():
            return Response(
                {"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = _annotate_users(
            TenantUser.objects.filter(application__app_id=app_id).select_related("application"),
        ).order_by("-created_at")

        email = request.query_params.get("email")
        if email:
            qs = qs.filter(email__icontains=email)
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(
                Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q),
            )
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(TenantUserAdminSerializer(page, many=True).data)


class AdminTenantUserDetailView(APIView):
    permission_classes = [IsSuperUser]

    def _get_user(self, user_id) -> TenantUser | Response:
        try:
            return _annotate_users(
                TenantUser.objects.select_related("application"),
            ).get(pk=user_id)
        except (TenantUser.DoesNotExist, ValueError):
            return Response(
                {"code": "user_not_found", "message": "Usuario no encontrado.", "field": "user_id"},
                status=status.HTTP_404_NOT_FOUND,
            )

    @extend_schema(
        tags=["admin"],
        summary="Detalle de usuario tenant",
        responses={
            200: TenantUserAdminSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_USER_NOT_FOUND]),
        },
    )
    def get(self, request, user_id):
        user = self._get_user(user_id)
        if isinstance(user, Response):
            return user
        return Response(TenantUserAdminSerializer(user).data)

    @extend_schema(
        tags=["admin"],
        summary="Actualizar usuario tenant",
        request=TenantUserAdminUpdateSerializer,
        responses={
            200: TenantUserAdminSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_USER_NOT_FOUND]),
            409: OpenApiResponse(
                response=ErrorResponseSerializer,
                description="Email duplicado en el tenant",
            ),
        },
    )
    def patch(self, request, user_id):
        user = self._get_user(user_id)
        if isinstance(user, Response):
            return user
        serializer = TenantUserAdminUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data.get("email")
        if email and TenantUser.objects.filter(
            application=user.application,
            email__iexact=email,
        ).exclude(pk=user.pk).exists():
            return Response(
                {
                    "code": "email_taken",
                    "message": "Ya existe un usuario con este email en la aplicación.",
                    "field": "email",
                },
                status=status.HTTP_409_CONFLICT,
            )
        serializer.save()
        user = self._get_user(user_id)
        return Response(TenantUserAdminSerializer(user).data)

    @extend_schema(
        tags=["admin"],
        summary="Eliminar usuario y perfiles biométricos",
        description=(
            "Elimina de forma permanente el TenantUser y, por CASCADE, "
            "todos sus BiometricProfile (embeddings) y OtpChallenge."
        ),
        responses={
            204: OpenApiResponse(description="Usuario eliminado."),
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_USER_NOT_FOUND]),
        },
    )
    def delete(self, request, user_id):
        user = self._get_user(user_id)
        if isinstance(user, Response):
            return user
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminBiometricProfileListView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        tags=["admin"],
        summary="Perfiles biométricos de un usuario (sin embedding)",
        responses={
            200: BiometricProfileAdminSerializer(many=True),
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_USER_NOT_FOUND]),
        },
    )
    def get(self, request, user_id):
        if not TenantUser.objects.filter(pk=user_id).exists():
            return Response(
                {"code": "user_not_found", "message": "Usuario no encontrado.", "field": "user_id"},
                status=status.HTTP_404_NOT_FOUND,
            )
        profiles = (
            BiometricProfile.objects.filter(user_id=user_id)
            .select_related("user", "application")
            .order_by("-created_at")
        )
        return Response(BiometricProfileAdminSerializer(profiles, many=True).data)


class AdminBiometricProfileDetailView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        tags=["admin"],
        summary="Activar/desactivar perfil biométrico",
        request=BiometricProfileAdminUpdateSerializer,
        responses={
            200: BiometricProfileAdminSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_PROFILE_NOT_FOUND]),
        },
    )
    def patch(self, request, profile_id):
        try:
            profile = BiometricProfile.objects.select_related("user", "application").get(pk=profile_id)
        except (BiometricProfile.DoesNotExist, ValueError):
            return Response(
                {
                    "code": "profile_not_found",
                    "message": "Perfil biométrico no encontrado.",
                    "field": "profile_id",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = BiometricProfileAdminUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BiometricProfileAdminSerializer(profile).data)
