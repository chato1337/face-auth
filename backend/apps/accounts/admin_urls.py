from django.urls import path

from apps.accounts.admin_views import (
    AdminBiometricProfileDetailView,
    AdminBiometricProfileListView,
    AdminTenantUserDetailView,
    AdminTenantUserListView,
)

urlpatterns = [
    path(
        "applications/<str:app_id>/users/",
        AdminTenantUserListView.as_view(),
        name="admin-tenant-user-list",
    ),
    path(
        "users/<uuid:user_id>/",
        AdminTenantUserDetailView.as_view(),
        name="admin-tenant-user-detail",
    ),
    path(
        "users/<uuid:user_id>/biometric-profiles/",
        AdminBiometricProfileListView.as_view(),
        name="admin-biometric-profile-list",
    ),
    path(
        "biometric-profiles/<uuid:profile_id>/",
        AdminBiometricProfileDetailView.as_view(),
        name="admin-biometric-profile-detail",
    ),
]
