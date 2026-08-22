"""Tests de dominio de OtpService: issue, verify, consume, rate limit, TTL."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import TenantUser
from apps.otp.codes import generate_numeric_code
from apps.otp.exceptions import (
    OtpConsumedError,
    OtpExpiredError,
    OtpInvalidError,
    OtpLockedError,
    OtpNotFoundError,
    OtpRateLimitedError,
)
from apps.otp.hashing import hash_code
from apps.otp.models import OtpChallenge
from apps.otp.services import OtpService
from apps.tenants.models import Application


@pytest.fixture
def application(db):
    return Application.objects.create(name="OtpCo")


@pytest.fixture
def user(application):
    return TenantUser.objects.create(
        application=application,
        first_name="Ana",
        last_name="Pérez",
        email="ana@example.com",
        is_active=False,
    )


@pytest.fixture
def locmem_email(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


def _issue_with_code(service: OtpService, user: TenantUser, code: str, purpose="email_verify"):
    with patch("apps.otp.services.generate_numeric_code", return_value=code):
        return service.issue(user, purpose)


@pytest.mark.django_db
class TestOtpServiceIssue:
    def test_persists_hash_not_plaintext(self, user, locmem_email):
        service = OtpService()
        result = _issue_with_code(service, user, "123456")
        challenge = OtpChallenge.objects.get(pk=result.challenge_id)
        assert "123456" not in challenge.code_hash
        assert challenge.code_hash == hash_code(
            user_id=str(user.id), purpose="email_verify", code="123456"
        )
        assert challenge.is_active
        assert result.destination_masked == "a***@example.com"
        assert result.channel == "email"
        assert result.expires_in == 300

    def test_new_code_invalidates_previous(self, user, locmem_email):
        service = OtpService()
        first = _issue_with_code(service, user, "111111")
        second = _issue_with_code(service, user, "222222")
        old = OtpChallenge.objects.get(pk=first.challenge_id)
        new = OtpChallenge.objects.get(pk=second.challenge_id)
        assert old.invalidated_at is not None
        assert not old.is_active
        assert new.is_active
        with pytest.raises(OtpInvalidError):
            service.verify(user, "email_verify", "111111")
        service.verify(user, "email_verify", "222222")

    def test_other_purpose_is_not_invalidated(self, user, locmem_email):
        service = OtpService()
        unlock = _issue_with_code(service, user, "333333", purpose="account_unlock")
        _issue_with_code(service, user, "444444", purpose="email_verify")
        assert OtpChallenge.objects.get(pk=unlock.challenge_id).is_active

    def test_rate_limit_fourth_issue(self, user, locmem_email, settings):
        settings.OTP_ISSUE_MAX = 3
        settings.OTP_ISSUE_WINDOW_SECONDS = 300
        service = OtpService()
        for i in range(3):
            _issue_with_code(service, user, f"10000{i}")
        with pytest.raises(OtpRateLimitedError) as exc:
            _issue_with_code(service, user, "199999")
        assert exc.value.http_status == 429
        assert exc.value.retry_after >= 1
        assert OtpChallenge.objects.filter(user=user).count() == 3


@pytest.mark.django_db
class TestOtpServiceVerifyConsume:
    def test_verify_does_not_consume(self, user, locmem_email):
        service = OtpService()
        _issue_with_code(service, user, "654321")
        challenge = service.verify(user, "email_verify", "654321")
        challenge.refresh_from_db()
        assert challenge.verified_at is not None
        assert challenge.consumed_at is None
        service.consume(user, "email_verify", "654321")
        challenge.refresh_from_db()
        assert challenge.consumed_at is not None

    def test_consume_without_prior_verify(self, user, locmem_email):
        service = OtpService()
        _issue_with_code(service, user, "777888")
        challenge = service.consume(user, "email_verify", "777888")
        assert challenge.consumed_at is not None
        assert challenge.verified_at is not None

    def test_wrong_code_then_lock_after_five(self, user, locmem_email, settings):
        settings.OTP_VERIFY_MAX_ATTEMPTS = 5
        service = OtpService()
        _issue_with_code(service, user, "121212")
        for _ in range(4):
            with pytest.raises(OtpInvalidError):
                service.verify(user, "email_verify", "000000")
        with pytest.raises(OtpLockedError):
            service.verify(user, "email_verify", "000000")
        challenge = OtpChallenge.objects.filter(user=user).latest("created_at")
        assert challenge.attempt_count == 5
        assert challenge.invalidated_at is not None
        with pytest.raises(OtpLockedError):
            service.consume(user, "email_verify", "121212")

    def test_expired_code(self, user, locmem_email):
        service = OtpService()
        result = _issue_with_code(service, user, "101010")
        OtpChallenge.objects.filter(pk=result.challenge_id).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with pytest.raises(OtpExpiredError):
            service.verify(user, "email_verify", "101010")

    def test_consume_twice_fails(self, user, locmem_email):
        service = OtpService()
        _issue_with_code(service, user, "202020")
        service.consume(user, "email_verify", "202020")
        with pytest.raises(OtpConsumedError):
            service.consume(user, "email_verify", "202020")

    def test_no_challenge(self, user):
        with pytest.raises(OtpNotFoundError):
            OtpService().verify(user, "email_verify", "000000")

    def test_code_does_not_work_for_other_user(self, user, application, locmem_email):
        other = TenantUser.objects.create(
            application=application,
            first_name="Bob",
            last_name="Lee",
            email="bob@example.com",
        )
        service = OtpService()
        _issue_with_code(service, user, "303030")
        with pytest.raises(OtpNotFoundError):
            service.verify(other, "email_verify", "303030")


def test_generate_numeric_code_is_six_digits():
    code = generate_numeric_code()
    assert len(code) == 6
    assert code.isdigit()
