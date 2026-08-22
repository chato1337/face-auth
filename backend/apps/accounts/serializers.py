from rest_framework import serializers

from apps.accounts.models import BiometricProfile, TenantUser


class TenantUserAdminSerializer(serializers.ModelSerializer):
    app_id = serializers.CharField(source="application.app_id", read_only=True)
    active_profiles_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = TenantUser
        fields = (
            "id",
            "app_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "is_active",
            "email_verified_at",
            "last_login_at",
            "created_at",
            "updated_at",
            "active_profiles_count",
        )
        read_only_fields = (
            "id",
            "app_id",
            "last_login_at",
            "email_verified_at",
            "created_at",
            "updated_at",
            "active_profiles_count",
        )


class TenantUserAdminUpdateSerializer(serializers.ModelSerializer):
    """PATCH: perfil + activar/desactivar. No crea usuarios (alta = Flujo B)."""

    class Meta:
        model = TenantUser
        fields = ("first_name", "last_name", "email", "phone", "is_active")


class BiometricProfileAdminSerializer(serializers.ModelSerializer):
    """Sin vector embedding — solo metadatos operativos."""

    user_id = serializers.UUIDField(source="user.id", read_only=True)
    app_id = serializers.CharField(source="application.app_id", read_only=True)

    class Meta:
        model = BiometricProfile
        fields = (
            "id",
            "user_id",
            "app_id",
            "model_version",
            "liveness_score",
            "quality_score",
            "is_active",
            "created_at",
        )
        read_only_fields = (
            "id",
            "user_id",
            "app_id",
            "model_version",
            "liveness_score",
            "quality_score",
            "created_at",
        )


class BiometricProfileAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiometricProfile
        fields = ("is_active",)
