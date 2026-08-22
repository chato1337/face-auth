"""Tests HTTP de /api/v1/otp/request/ y /verify/."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import TenantUser
from apps.otp.models import OtpChallenge
from apps.tenants.models import Application


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def application(db):
    return Application.objects.create(name="OtpApiCo")


@pytest.fixture
def locmem_email(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


def _request_payload(application, **overrides):
    data = {
        "app_id": application.app_id,
        "purpose": "email_verify",
        "email": "ana@example.com",
        "first_name": "Ana",
        "last_name": "Pérez",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestOtpRequestApi:
    def test_creates_pending_user_and_masks_email(self, api, application, locmem_email):
        with patch("apps.otp.services.generate_numeric_code", return_value="123456"):
            res = api.post("/api/v1/otp/request/", _request_payload(application), format="json")
        assert res.status_code == 200, res.data
        assert res.data["destination_masked"] == "a***@example.com"
        assert res.data["channel"] == "email"
        assert res.data["expires_in"] == 300
        user = TenantUser.objects.get(email="ana@example.com")
        assert user.is_active is False
        assert OtpChallenge.objects.filter(user=user, purpose="email_verify").count() == 1

    def test_resend_reuses_user(self, api, application, locmem_email):
        with patch("apps.otp.services.generate_numeric_code", return_value="111111"):
            api.post("/api/v1/otp/request/", _request_payload(application), format="json")
        with patch("apps.otp.services.generate_numeric_code", return_value="222222"):
            res = api.post("/api/v1/otp/request/", _request_payload(application), format="json")
        assert res.status_code == 200
        assert TenantUser.objects.filter(email="ana@example.com").count() == 1
        assert OtpChallenge.objects.filter(user__email="ana@example.com").count() == 2

    def test_rate_limited_on_fourth(self, api, application, locmem_email):
        with patch("apps.otp.services.generate_numeric_code", return_value="100000"):
            for _ in range(3):
                ok = api.post("/api/v1/otp/request/", _request_payload(application), format="json")
                assert ok.status_code == 200, ok.data
            res = api.post("/api/v1/otp/request/", _request_payload(application), format="json")
        assert res.status_code == 429
        assert res.data["code"] == "otp_rate_limited"
        assert "Retry-After" in res

    def test_purpose_unlock_rejected(self, api, application):
        res = api.post(
            "/api/v1/otp/request/",
            _request_payload(application, purpose="account_unlock"),
            format="json",
        )
        assert res.status_code == 400
        assert res.data["field"] == "purpose"

    def test_unknown_app(self, api):
        res = api.post(
            "/api/v1/otp/request/",
            {
                "app_id": "app_missing",
                "purpose": "email_verify",
                "email": "a@b.com",
                "first_name": "A",
                "last_name": "B",
            },
            format="json",
        )
        assert res.status_code == 404
        assert res.data["code"] == "app_not_found"


@pytest.mark.django_db
class TestOtpVerifyApi:
    def test_verify_ok_does_not_consume(self, api, application, locmem_email):
        with patch("apps.otp.services.generate_numeric_code", return_value="654321"):
            api.post("/api/v1/otp/request/", _request_payload(application), format="json")
        res = api.post(
            "/api/v1/otp/verify/",
            {
                "app_id": application.app_id,
                "purpose": "email_verify",
                "email": "ana@example.com",
                "code": "654321",
            },
            format="json",
        )
        assert res.status_code == 200, res.data
        assert res.data["valid"] is True
        challenge = OtpChallenge.objects.get(user__email="ana@example.com")
        assert challenge.verified_at is not None
        assert challenge.consumed_at is None

    def test_wrong_code(self, api, application, locmem_email):
        with patch("apps.otp.services.generate_numeric_code", return_value="654321"):
            api.post("/api/v1/otp/request/", _request_payload(application), format="json")
        res = api.post(
            "/api/v1/otp/verify/",
            {
                "app_id": application.app_id,
                "purpose": "email_verify",
                "email": "ana@example.com",
                "code": "000000",
            },
            format="json",
        )
        assert res.status_code == 400
        assert res.data["code"] == "otp_invalid"

    def test_code_must_be_six_digits(self, api, application):
        res = api.post(
            "/api/v1/otp/verify/",
            {
                "app_id": application.app_id,
                "purpose": "email_verify",
                "email": "ana@example.com",
                "code": "12",
            },
            format="json",
        )
        assert res.status_code == 400
        assert res.data["field"] == "code"
