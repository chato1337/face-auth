from django.urls import path

from apps.otp.views import OtpRequestView, OtpVerifyView

urlpatterns = [
    path("request/", OtpRequestView.as_view(), name="otp-request"),
    path("verify/", OtpVerifyView.as_view(), name="otp-verify"),
]
