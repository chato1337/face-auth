from rest_framework import serializers

from apps.authentication.serializers import ErrorResponseSerializer

__all__ = [
    "ErrorResponseSerializer",
    "AdminLoginRequestSerializer",
    "AdminTokenPairSerializer",
    "AdminLoginResponseSerializer",
    "AdminTokenRefreshRequestSerializer",
    "AdminTokenRefreshResponseSerializer",
    "AdminMeSerializer",
]


class AdminLoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class AdminTokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class AdminLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)


class AdminTokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class AdminTokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField(required=False)


class AdminMeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    is_superuser = serializers.BooleanField()
    is_staff = serializers.BooleanField()
