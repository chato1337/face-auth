from rest_framework import serializers

from apps.tenants.models import Application
from apps.tenants.redirect_uris import parse_redirect_uris


class RedirectUrisValidationMixin:
    def validate_redirect_uris(self, value):
        try:
            return parse_redirect_uris(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class ApplicationPublicSerializer(serializers.ModelSerializer):
    """Respuesta pública de validación de tenant (sin api_key)."""

    class Meta:
        model = Application
        fields = (
            "app_id",
            "name",
            "is_active",
            "redirect_uris",
            "liveness_threshold",
            "match_threshold",
        )
        read_only_fields = fields


class ApplicationAdminSerializer(RedirectUrisValidationMixin, serializers.ModelSerializer):
    """List/retrieve/update admin — nunca expone api_key."""

    users_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Application
        fields = (
            "id",
            "app_id",
            "name",
            "is_active",
            "redirect_uris",
            "liveness_threshold",
            "match_threshold",
            "api_key_rotated_at",
            "created_at",
            "updated_at",
            "users_count",
        )
        read_only_fields = (
            "id",
            "app_id",
            "api_key_rotated_at",
            "created_at",
            "updated_at",
            "users_count",
        )


class ApplicationAdminCreateSerializer(RedirectUrisValidationMixin, serializers.ModelSerializer):
    """Alta de tenant; la respuesta one-shot incluye api_key vía ApplicationCreatedSerializer."""

    class Meta:
        model = Application
        fields = (
            "name",
            "redirect_uris",
            "liveness_threshold",
            "match_threshold",
            "is_active",
        )


class ApplicationCreatedSerializer(serializers.ModelSerializer):
    """Respuesta de create: incluye api_key una sola vez."""

    class Meta:
        model = Application
        fields = (
            "id",
            "app_id",
            "name",
            "api_key",
            "is_active",
            "redirect_uris",
            "liveness_threshold",
            "match_threshold",
            "api_key_rotated_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ApplicationRotateApiKeySerializer(serializers.Serializer):
    app_id = serializers.CharField()
    api_key = serializers.CharField()
    api_key_rotated_at = serializers.DateTimeField()
