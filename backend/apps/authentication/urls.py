from django.urls import path

from apps.authentication.views import LoginView, RegisterView, TokenRefreshView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
]
