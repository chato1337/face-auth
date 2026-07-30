"""CRUD admin de Applications (panel operadores / is_superuser)."""
from __future__ import annotations

from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.serializers import ErrorResponseSerializer
from apps.tenants.models import Application
from apps.tenants.serializers import (
    ApplicationAdminCreateSerializer,
    ApplicationAdminSerializer,
    ApplicationCreatedSerializer,
    ApplicationRotateApiKeySerializer,
)
from core.pagination import AdminPageNumberPagination
from core.permissions import IsSuperUser

EX_NOT_FOUND = OpenApiExample(
    "Application no encontrada",
    value={"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
    response_only=True,
    status_codes=["404"],
)


def _get_application(app_id: str) -> Application | Response:
    try:
        return Application.objects.annotate(users_count=Count("users")).get(app_id=app_id)
    except Application.DoesNotExist:
        return Response(
            {"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
            status=status.HTTP_404_NOT_FOUND,
        )


class AdminApplicationListCreateView(APIView):
    permission_classes = [IsSuperUser]
    pagination_class = AdminPageNumberPagination

    @extend_schema(
        tags=["admin"],
        summary="Listar tenants",
        parameters=[
            OpenApiParameter(name="q", type=str, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                name="is_active",
                type=bool,
                location=OpenApiParameter.QUERY,
                required=False,
            ),
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(
                name="page_size",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
            ),
        ],
        responses={200: ApplicationAdminSerializer(many=True)},
    )
    def get(self, request):
        qs = Application.objects.annotate(users_count=Count("users")).order_by("-created_at")
        q = request.query_params.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(app_id__icontains=q))
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = ApplicationAdminSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["admin"],
        summary="Crear tenant",
        request=ApplicationAdminCreateSerializer,
        responses={
            201: ApplicationCreatedSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        serializer = ApplicationAdminCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app = serializer.save()
        return Response(
            ApplicationCreatedSerializer(app).data,
            status=status.HTTP_201_CREATED,
        )


class AdminApplicationDetailView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        tags=["admin"],
        summary="Detalle de tenant",
        responses={
            200: ApplicationAdminSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_NOT_FOUND]),
        },
    )
    def get(self, request, app_id: str):
        app = _get_application(app_id)
        if isinstance(app, Response):
            return app
        return Response(ApplicationAdminSerializer(app).data)

    @extend_schema(
        tags=["admin"],
        summary="Actualizar tenant",
        request=ApplicationAdminSerializer,
        responses={
            200: ApplicationAdminSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_NOT_FOUND]),
        },
    )
    def patch(self, request, app_id: str):
        app = _get_application(app_id)
        if isinstance(app, Response):
            return app
        serializer = ApplicationAdminSerializer(app, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Re-annotate users_count after save
        app = _get_application(app_id)
        return Response(ApplicationAdminSerializer(app).data)


class AdminApplicationRotateApiKeyView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        tags=["admin"],
        summary="Rotar api_key del tenant",
        description="Invalida la clave anterior. La nueva se devuelve **una sola vez** en claro.",
        request=None,
        responses={
            200: ApplicationRotateApiKeySerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer, examples=[EX_NOT_FOUND]),
        },
    )
    def post(self, request, app_id: str):
        try:
            app = Application.objects.get(app_id=app_id)
        except Application.DoesNotExist:
            return Response(
                {"code": "app_not_found", "message": "Application no encontrada.", "field": "app_id"},
                status=status.HTTP_404_NOT_FOUND,
            )
        new_key = app.rotate_api_key()
        return Response(
            {
                "app_id": app.app_id,
                "api_key": new_key,
                "api_key_rotated_at": app.api_key_rotated_at,
            }
        )
