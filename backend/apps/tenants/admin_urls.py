from django.urls import path

from apps.tenants.admin_views import (
    AdminApplicationDetailView,
    AdminApplicationListCreateView,
    AdminApplicationRotateApiKeyView,
)

urlpatterns = [
    path("applications/", AdminApplicationListCreateView.as_view(), name="admin-application-list"),
    path(
        "applications/<str:app_id>/",
        AdminApplicationDetailView.as_view(),
        name="admin-application-detail",
    ),
    path(
        "applications/<str:app_id>/rotate-api-key/",
        AdminApplicationRotateApiKeyView.as_view(),
        name="admin-application-rotate-api-key",
    ),
]
