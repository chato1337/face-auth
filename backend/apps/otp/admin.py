from django.contrib import admin

from apps.otp.models import OtpChallenge


@admin.register(OtpChallenge)
class OtpChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "application",
        "purpose",
        "channel",
        "expires_at",
        "consumed_at",
        "invalidated_at",
        "attempt_count",
        "created_at",
    )
    list_filter = ("purpose", "channel", "application")
    search_fields = ("user__email",)
    readonly_fields = (
        "id",
        "user",
        "application",
        "purpose",
        "channel",
        "destination_hash",
        "code_hash",
        "expires_at",
        "consumed_at",
        "verified_at",
        "attempt_count",
        "invalidated_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
