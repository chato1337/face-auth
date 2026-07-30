from django.contrib import admin

from apps.tenants.models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "app_id",
        "is_active",
        "api_key_rotated_at",
        "liveness_threshold",
        "match_threshold",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "app_id")
    readonly_fields = (
        "id",
        "app_id",
        "api_key",
        "api_key_rotated_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
    # Rotación de api_key solo vía CLI (`rotate_api_key`) para mostrar el secreto una vez.
