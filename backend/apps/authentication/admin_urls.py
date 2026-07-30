from django.urls import path

from apps.authentication.admin_views import AdminLoginView, AdminMeView, AdminTokenRefreshView

urlpatterns = [
    path("login/", AdminLoginView.as_view(), name="admin-auth-login"),
    path("token/refresh/", AdminTokenRefreshView.as_view(), name="admin-auth-token-refresh"),
    path("me/", AdminMeView.as_view(), name="admin-auth-me"),
]
