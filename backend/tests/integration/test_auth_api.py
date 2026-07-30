"""
Tests de API (Fase 3) — contratos HTTP sin depender de pesos ML.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import TenantUser
from apps.authentication.services import AuthenticationService
from apps.biometrics.exceptions import NoMatchFoundError, SpoofDetectedError
from apps.biometrics.services.biometric_service import AuthResult, EnrollResult, LivenessReport
from apps.tenants.models import Application


def _video_upload(name: str = "clip.mp4") -> SimpleUploadedFile:
    frames = []
    for _ in range(30):
        frame = np.full((480, 640, 3), 140, dtype=np.uint8)
        frames.append(frame)
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        path = Path(tmp.name)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (640, 480))
    for f in frames:
        writer.write(f)
    writer.release()
    data = path.read_bytes()
    path.unlink(missing_ok=True)
    return SimpleUploadedFile(name, data, content_type="video/mp4")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def application(db):
    return Application.objects.create(
        name="Acme",
        redirect_uris=["http://localhost:3000/callback"],
        liveness_threshold=0.5,
        match_threshold=0.5,
    )


@pytest.mark.django_db
class TestApplicationEndpoint:
    def test_get_ok(self, api, application):
        res = api.get(f"/api/v1/applications/{application.app_id}/")
        assert res.status_code == 200
        assert res.data["app_id"] == application.app_id
        assert "api_key" not in res.data

    def test_get_not_found(self, api):
        res = api.get("/api/v1/applications/app_does_not_exist/")
        assert res.status_code == 404
        assert res.data["code"] == "app_not_found"

    def test_get_inactive(self, api, application):
        application.is_active = False
        application.save(update_fields=["is_active"])
        res = api.get(f"/api/v1/applications/{application.app_id}/")
        assert res.status_code == 400
        assert res.data["code"] == "app_inactive"


@pytest.mark.django_db
class TestRegisterLogin:
    def test_register_success(self, api, application):
        embedding = np.random.randn(512).astype(np.float32)
        embedding /= np.linalg.norm(embedding)
        enroll = EnrollResult(
            embedding=embedding,
            liveness=LivenessReport(passed=True, active_score=0.9, passive_score=0.95),
            quality_score=0.88,
        )

        with patch("apps.authentication.views.BiometricService") as svc_cls:
            svc = svc_cls.return_value
            svc.process_enrollment.return_value = enroll
            svc.persist_enrollment.side_effect = lambda user, result, **kw: MagicMock(id="profile")

            res = api.post(
                "/api/v1/auth/register/",
                {
                    "app_id": application.app_id,
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "email": "ada@example.com",
                    "video": _video_upload(),
                    "redirect_uri": "http://localhost:3000/callback",
                },
                format="multipart",
            )

        assert res.status_code == 201, res.data
        assert res.data["email"] == "ada@example.com"
        assert "access" in res.data["tokens"]
        assert res.data["tokens"]["redirect_url"].startswith("http://localhost:3000/callback")
        assert TenantUser.objects.filter(email="ada@example.com").exists()

    def test_register_email_taken(self, api, application):
        TenantUser.objects.create(
            application=application,
            first_name="A",
            last_name="B",
            email="ada@example.com",
        )
        res = api.post(
            "/api/v1/auth/register/",
            {
                "app_id": application.app_id,
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "video": _video_upload(),
            },
            format="multipart",
        )
        assert res.status_code == 409
        assert res.data["code"] == "email_taken"
        assert res.data["field"] == "email"

    def test_login_success(self, api, application):
        user = TenantUser.objects.create(
            application=application,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
        auth = AuthResult(
            matched_user=user,
            distance=0.12,
            liveness=LivenessReport(passed=True, active_score=0.9, passive_score=0.95),
        )
        with patch("apps.authentication.views.BiometricService") as svc_cls:
            svc_cls.return_value.process_authentication.return_value = auth
            res = api.post(
                "/api/v1/auth/login/",
                {
                    "app_id": application.app_id,
                    "video": _video_upload(),
                    "redirect_uri": "http://localhost:3000/callback",
                },
                format="multipart",
            )
        assert res.status_code == 200, res.data
        assert res.data["user_id"] == str(user.id) or res.data["user_id"] == user.id
        assert res.data["distance"] == 0.12
        assert "refresh" in res.data["tokens"]

    def test_login_no_match_maps_to_401(self, api, application):
        with patch("apps.authentication.views.BiometricService") as svc_cls:
            svc_cls.return_value.process_authentication.side_effect = NoMatchFoundError(
                "No se encontró coincidencia biométrica.",
                field="video",
            )
            res = api.post(
                "/api/v1/auth/login/",
                {"app_id": application.app_id, "video": _video_upload()},
                format="multipart",
            )
        assert res.status_code == 401
        assert res.data["code"] == "no_match"

    def test_login_spoof_maps_to_422(self, api, application):
        with patch("apps.authentication.views.BiometricService") as svc_cls:
            svc_cls.return_value.process_authentication.side_effect = SpoofDetectedError(
                "Liveness fallido",
                field="video",
            )
            res = api.post(
                "/api/v1/auth/login/",
                {"app_id": application.app_id, "video": _video_upload()},
                format="multipart",
            )
        assert res.status_code == 422
        assert res.data["code"] == "spoof_detected"


@pytest.mark.django_db
class TestTokenRefresh:
    def test_refresh_ok(self, api, application):
        user = TenantUser.objects.create(
            application=application,
            first_name="A",
            last_name="B",
            email="a@example.com",
        )
        issued = AuthenticationService().issue_for_user(user)
        res = api.post("/api/v1/auth/token/refresh/", {"refresh": issued.refresh}, format="json")
        assert res.status_code == 200
        assert "access" in res.data

    def test_refresh_invalid(self, api):
        res = api.post("/api/v1/auth/token/refresh/", {"refresh": "not-a-token"}, format="json")
        assert res.status_code == 401
        assert res.data["code"] == "invalid_token"


@pytest.mark.django_db
class TestTokenVerify:
    VERIFY_URL = "/api/v1/auth/token/verify/"

    @pytest.fixture
    def user(self, application):
        return TenantUser.objects.create(
            application=application,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )

    def _verify(self, api, application, token, api_key=None):
        return api.post(
            self.VERIFY_URL,
            {"app_id": application.app_id, "token": token},
            format="json",
            HTTP_X_API_KEY=api_key if api_key is not None else application.api_key,
        )

    def test_verify_ok_and_single_use(self, api, application, user):
        issued = AuthenticationService().issue_for_user(user)

        res = self._verify(api, application, issued.redirect_token)
        assert res.status_code == 200, res.data
        assert res.data["valid"] is True
        assert str(res.data["user_id"]) == str(user.id)
        assert res.data["email"] == user.email
        assert res.data["app_id"] == application.app_id

        # Replay: el mismo token no puede verificarse dos veces.
        res2 = self._verify(api, application, issued.redirect_token)
        assert res2.status_code == 401
        assert res2.data["code"] == "token_already_used"

    def test_verify_wrong_api_key(self, api, application, user):
        issued = AuthenticationService().issue_for_user(user)
        res = self._verify(api, application, issued.redirect_token, api_key="wrong-key")
        assert res.status_code == 401
        assert res.data["code"] == "invalid_api_key"

    def test_verify_missing_api_key(self, api, application, user):
        issued = AuthenticationService().issue_for_user(user)
        res = api.post(
            self.VERIFY_URL,
            {"app_id": application.app_id, "token": issued.redirect_token},
            format="json",
        )
        assert res.status_code == 401
        assert res.data["code"] == "invalid_api_key"

    def test_verify_rejects_access_token(self, api, application, user):
        """Un access token no sirve como token de callback (token_type distinto)."""
        issued = AuthenticationService().issue_for_user(user)
        res = self._verify(api, application, issued.access)
        assert res.status_code == 401
        assert res.data["code"] == "invalid_token"

    def test_verify_rejects_token_of_other_tenant(self, api, application, user):
        other = Application.objects.create(name="Other", redirect_uris=[])
        issued = AuthenticationService().issue_for_user(user)
        res = self._verify(api, other, issued.redirect_token, api_key=other.api_key)
        assert res.status_code == 401
        assert res.data["code"] == "invalid_token"

    def test_verify_expired_token(self, api, application, user):
        from datetime import timedelta
        from uuid import uuid4

        from rest_framework_simplejwt.utils import aware_utcnow, datetime_to_epoch

        from apps.authentication.services import SSORedirectToken

        token = SSORedirectToken()
        token["user_id"] = str(user.id)
        token["app_id"] = application.app_id
        token["email"] = user.email
        token["jti"] = uuid4().hex
        token["purpose"] = "sso_redirect"
        token.payload["exp"] = datetime_to_epoch(aware_utcnow() - timedelta(minutes=1))

        res = self._verify(api, application, str(token))
        assert res.status_code == 401
        assert res.data["code"] == "invalid_token"

    def test_verify_inactive_user(self, api, application, user):
        issued = AuthenticationService().issue_for_user(user)
        user.is_active = False
        user.save(update_fields=["is_active"])

        res = self._verify(api, application, issued.redirect_token)
        assert res.status_code == 401
        assert res.data["code"] == "user_inactive"

    def test_verify_app_not_found(self, api, application, user):
        issued = AuthenticationService().issue_for_user(user)
        res = api.post(
            self.VERIFY_URL,
            {"app_id": "app_nope", "token": issued.redirect_token},
            format="json",
            HTTP_X_API_KEY=application.api_key,
        )
        assert res.status_code == 404
        assert res.data["code"] == "app_not_found"


@pytest.mark.django_db
class TestDocsAndHealth:
    def test_health(self, api):
        assert api.get("/api/v1/health/").status_code == 200

    def test_schema_available(self, api):
        res = api.get("/api/schema/")
        assert res.status_code == 200
