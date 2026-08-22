from django.contrib import admin

from apps.accounts.models import BiometricProfile, TenantUser


class BiometricProfileInline(admin.TabularInline):
    model = BiometricProfile
    extra = 0
    readonly_fields = ("id", "model_version", "liveness_score", "quality_score", "is_active", "created_at")
    fields = readonly_fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TenantUser)
class TenantUserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "application",
        "is_active",
        "email_verified_at",
        "last_login_at",
        "created_at",
    )
    list_filter = ("is_active", "application")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("id", "created_at", "updated_at", "last_login_at", "email_verified_at")
    inlines = [BiometricProfileInline]


@admin.register(BiometricProfile)
class BiometricProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "application", "model_version", "liveness_score", "is_active", "created_at")
    list_filter = ("is_active", "model_version", "application")
    readonly_fields = ("id", "application", "created_at")
    search_fields = ("user__email",)
