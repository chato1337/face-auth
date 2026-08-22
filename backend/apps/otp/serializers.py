from rest_framework import serializers

from apps.otp.models import OtpChallenge


class OtpRequestSerializer(serializers.Serializer):
    app_id = serializers.CharField()
    purpose = serializers.ChoiceField(choices=OtpChallenge.Purpose.choices)
    channel = serializers.ChoiceField(
        choices=OtpChallenge.Channel.choices,
        default=OtpChallenge.Channel.EMAIL,
        required=False,
    )
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["purpose"] == OtpChallenge.Purpose.EMAIL_VERIFY:
            if not attrs.get("first_name", "").strip() or not attrs.get("last_name", "").strip():
                raise serializers.ValidationError(
                    {
                        "first_name": "Nombre y apellido son requeridos para verificar el correo.",
                    }
                )
        return attrs


class OtpRequestResponseSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    expires_in = serializers.IntegerField()
    destination_masked = serializers.CharField()
    channel = serializers.CharField()


class OtpVerifySerializer(serializers.Serializer):
    app_id = serializers.CharField()
    purpose = serializers.ChoiceField(choices=OtpChallenge.Purpose.choices)
    email = serializers.EmailField()
    code = serializers.RegexField(regex=r"^\d{6}$", error_messages={"invalid": "El código debe ser de 6 dígitos."})


class OtpVerifyResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    expires_in = serializers.IntegerField()
