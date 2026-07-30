from rest_framework import serializers


class ErrorResponseSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    field = serializers.CharField(allow_null=True, required=False)


class LivenessReportSerializer(serializers.Serializer):
    passed = serializers.BooleanField()
    active_score = serializers.FloatField()
    passive_score = serializers.FloatField()
    reason = serializers.CharField(allow_null=True, required=False)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    redirect_token = serializers.CharField()
    redirect_url = serializers.URLField(allow_null=True, required=False)


class LoginRequestSerializer(serializers.Serializer):
    app_id = serializers.CharField(help_text="Identificador del tenant.")
    video = serializers.FileField(help_text="Clip biométrico (mp4/webm, 1–6 s).")
    redirect_uri = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="Debe coincidir exactamente con una URI whitelist de la Application.",
    )


class LoginResponseSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    distance = serializers.FloatField()
    liveness = LivenessReportSerializer()
    tokens = TokenPairSerializer()


class RegisterRequestSerializer(serializers.Serializer):
    app_id = serializers.CharField()
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    video = serializers.FileField()
    redirect_uri = serializers.URLField(required=False, allow_null=True)


class RegisterResponseSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    liveness = LivenessReportSerializer()
    quality_score = serializers.FloatField()
    tokens = TokenPairSerializer()


class TokenVerifyRequestSerializer(serializers.Serializer):
    app_id = serializers.CharField(help_text="Identificador del tenant que verifica.")
    token = serializers.CharField(
        help_text="redirect_token (purpose=sso_redirect) recibido en el callback SSO.",
    )


class TokenVerifyResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    user_id = serializers.UUIDField()
    app_id = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    expires_at = serializers.DateTimeField(
        help_text="Expiración del token verificado (el consumo ya quedó registrado).",
    )


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField(required=False, help_text="Presente si se rota el refresh.")
