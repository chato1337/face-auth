from rest_framework import serializers

from apps.tenants.models import Application


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
