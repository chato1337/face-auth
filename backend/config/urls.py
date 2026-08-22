"""URL configuration for face-auth."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.tenants.health import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # API v1
    path("api/v1/health/", HealthView.as_view(), name="health"),
    path("api/v1/", include("apps.tenants.urls")),
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/otp/", include("apps.otp.urls")),
    # Panel admin (operadores is_superuser) — no requiere X-App-Id
    path("api/v1/admin/auth/", include("apps.authentication.admin_urls")),
    path("api/v1/admin/", include("apps.tenants.admin_urls")),
    path("api/v1/admin/", include("apps.accounts.admin_urls")),
]
