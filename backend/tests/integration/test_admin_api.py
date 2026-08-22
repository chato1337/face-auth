"""
Tests de API admin (Fase 6) — operadores is_superuser.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import BiometricProfile, TenantUser
from apps.otp.models import OtpChallenge
from apps.tenants.models import Application


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="admin-secret-123",
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staffer",
        email="staff@example.com",
        password="staff-secret-123",
        is_staff=True,
        is_superuser=False,
    )


@pytest.fixture
def application(db):
    return Application.objects.create(
        name="Acme",
        redirect_uris=["http://localhost:3000/callback"],
        liveness_threshold=0.85,
        match_threshold=0.42,
    )


@pytest.fixture
def tenant_user(application):
    return TenantUser.objects.create(
        application=application,
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
        phone="+57000",
    )


@pytest.fixture
def biometric_profile(tenant_user, application):
    embedding = np.random.randn(512).astype(np.float32)
    embedding /= np.linalg.norm(embedding)
    return BiometricProfile.objects.create(
        user=tenant_user,
        application=application,
        embedding=embedding.tolist(),
        liveness_score=0.95,
        quality_score=0.88,
    )


def _auth(api: APIClient, user: User) -> None:
    token = RefreshToken.for_user(user)
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


@pytest.mark.django_db
class TestAdminAuth:
    def test_login_superuser_ok(self, api, superuser):
        res = api.post(
            "/api/v1/admin/auth/login/",
            {"username": "admin", "password": "admin-secret-123"},
            format="json",
        )
        assert res.status_code == 200
        assert "access" in res.data
        assert "refresh" in res.data
        assert res.data["username"] == "admin"

    def test_login_staff_not_superuser_403(self, api, staff_user):
        res = api.post(
            "/api/v1/admin/auth/login/",
            {"username": "staffer", "password": "staff-secret-123"},
            format="json",
        )
        assert res.status_code == 403
        assert res.data["code"] == "not_superuser"

    def test_login_invalid_credentials(self, api, superuser):
        res = api.post(
            "/api/v1/admin/auth/login/",
            {"username": "admin", "password": "wrong"},
            format="json",
        )
        assert res.status_code == 401
        assert res.data["code"] == "invalid_credentials"

    def test_me_requires_superuser(self, api, staff_user, superuser):
        _auth(api, staff_user)
        res = api.get("/api/v1/admin/auth/me/")
        assert res.status_code == 403

        _auth(api, superuser)
        res = api.get("/api/v1/admin/auth/me/")
        assert res.status_code == 200
        assert res.data["is_superuser"] is True


@pytest.mark.django_db
class TestAdminApplications:
    def test_crud_and_rotate(self, api, superuser):
        _auth(api, superuser)

        create = api.post(
            "/api/v1/admin/applications/",
            {
                "name": "NewCo",
                "redirect_uris": ["https://newco.example/callback"],
                "liveness_threshold": 0.8,
                "match_threshold": 0.4,
            },
            format="json",
        )
        assert create.status_code == 201
        assert "api_key" in create.data
        app_id = create.data["app_id"]
        old_key = create.data["api_key"]

        listing = api.get("/api/v1/admin/applications/")
        assert listing.status_code == 200
        assert listing.data["count"] >= 1
        assert "api_key" not in listing.data["results"][0]

        detail = api.get(f"/api/v1/admin/applications/{app_id}/")
        assert detail.status_code == 200
        assert detail.data["name"] == "NewCo"
        assert "api_key" not in detail.data

        patch = api.patch(
            f"/api/v1/admin/applications/{app_id}/",
            {"is_active": False, "name": "NewCo Off"},
            format="json",
        )
        assert patch.status_code == 200
        assert patch.data["is_active"] is False
        assert patch.data["name"] == "NewCo Off"

        rotate = api.post(f"/api/v1/admin/applications/{app_id}/rotate-api-key/")
        assert rotate.status_code == 200
        assert rotate.data["api_key"] != old_key
        assert rotate.data["app_id"] == app_id

    def test_patch_splits_comma_joined_redirect_uris(self, api, superuser):
        _auth(api, superuser)
        create = api.post(
            "/api/v1/admin/applications/",
            {
                "name": "Mobile",
                "redirect_uris": [
                    "http://192.168.0.101:8443/auth/callback,"
                    "https://mobile.ineac.xyz/auth/callback"
                ],
            },
            format="json",
        )
        assert create.status_code == 201
        assert create.data["redirect_uris"] == [
            "http://192.168.0.101:8443/auth/callback",
            "https://mobile.ineac.xyz/auth/callback",
        ]

        patch = api.patch(
            f"/api/v1/admin/applications/{create.data['app_id']}/",
            {
                "redirect_uris": [
                    "http://192.168.0.101:8443/auth/callback,"
                    "https://mobile.ineac.xyz/auth/callback,"
                    "https://app.ineac.xyz/auth/callback"
                ]
            },
            format="json",
        )
        assert patch.status_code == 200
        assert patch.data["redirect_uris"] == [
            "http://192.168.0.101:8443/auth/callback",
            "https://mobile.ineac.xyz/auth/callback",
            "https://app.ineac.xyz/auth/callback",
        ]

    def test_staff_cannot_list(self, api, staff_user, application):
        _auth(api, staff_user)
        res = api.get("/api/v1/admin/applications/")
        assert res.status_code == 403


@pytest.mark.django_db
class TestAdminUsersAndProfiles:
    def test_list_users_filtered_by_app(
        self,
        api,
        superuser,
        application,
        tenant_user,
        biometric_profile,
    ):
        other = Application.objects.create(name="Other", redirect_uris=[])
        TenantUser.objects.create(
            application=other,
            first_name="Bob",
            last_name="Other",
            email="bob@example.com",
        )

        _auth(api, superuser)
        res = api.get(f"/api/v1/admin/applications/{application.app_id}/users/")
        assert res.status_code == 200
        assert res.data["count"] == 1
        assert res.data["results"][0]["email"] == "ada@example.com"
        assert "embedding" not in res.data["results"][0]

        deactivate = api.patch(
            f"/api/v1/admin/users/{tenant_user.id}/",
            {"is_active": False},
            format="json",
        )
        assert deactivate.status_code == 200
        assert deactivate.data["is_active"] is False

        profiles = api.get(f"/api/v1/admin/users/{tenant_user.id}/biometric-profiles/")
        assert profiles.status_code == 200
        assert len(profiles.data) == 1
        assert "embedding" not in profiles.data[0]

        soft = api.patch(
            f"/api/v1/admin/biometric-profiles/{biometric_profile.id}/",
            {"is_active": False},
            format="json",
        )
        assert soft.status_code == 200
        assert soft.data["is_active"] is False
        biometric_profile.refresh_from_db()
        assert biometric_profile.is_active is False

    def test_delete_user_cascades_profiles_and_otp(
        self,
        api,
        superuser,
        application,
        tenant_user,
        biometric_profile,
    ):
        OtpChallenge.objects.create(
            user=tenant_user,
            application=application,
            purpose=OtpChallenge.Purpose.EMAIL_VERIFY,
            destination_hash="a" * 64,
            code_hash="b" * 64,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        profile_id = biometric_profile.id
        user_id = tenant_user.id

        _auth(api, superuser)
        res = api.delete(f"/api/v1/admin/users/{user_id}/")
        assert res.status_code == 204
        assert not TenantUser.objects.filter(pk=user_id).exists()
        assert not BiometricProfile.objects.filter(pk=profile_id).exists()
        assert not OtpChallenge.objects.filter(user_id=user_id).exists()

        missing = api.get(f"/api/v1/admin/users/{user_id}/")
        assert missing.status_code == 404
        assert missing.data["code"] == "user_not_found"

    def test_delete_user_not_found(self, api, superuser):
        _auth(api, superuser)
        res = api.delete("/api/v1/admin/users/00000000-0000-0000-0000-000000000000/")
        assert res.status_code == 404
        assert res.data["code"] == "user_not_found"

    def test_delete_user_staff_forbidden(self, api, staff_user, tenant_user):
        _auth(api, staff_user)
        res = api.delete(f"/api/v1/admin/users/{tenant_user.id}/")
        assert res.status_code == 403
        assert TenantUser.objects.filter(pk=tenant_user.id).exists()

    def test_admin_routes_do_not_require_app_id_header(self, api, superuser):
        _auth(api, superuser)
        # Sin X-App-Id — middleware debe dejar pasar /api/v1/admin/
        res = api.get("/api/v1/admin/applications/")
        assert res.status_code == 200
