"""Tests de la base OTP (hasher, máscara, canal email, registro de canales)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core import mail

from apps.otp.channels import ChannelRegistry, SmtpEmailChannel, get_channel
from apps.otp.exceptions import OtpChannelUnsupportedError, OtpDeliveryFailedError
from apps.otp.hashing import compare_hash, hash_code, hash_destination
from apps.otp.masking import mask_email


class TestHashing:
    def test_same_inputs_same_hash(self):
        a = hash_code(user_id="u1", purpose="email_verify", code="123456")
        b = hash_code(user_id="u1", purpose="email_verify", code="123456")
        assert a == b
        assert len(a) == 64

    def test_different_user_different_hash(self):
        a = hash_code(user_id="u1", purpose="email_verify", code="123456")
        b = hash_code(user_id="u2", purpose="email_verify", code="123456")
        assert a != b

    def test_different_purpose_different_hash(self):
        a = hash_code(user_id="u1", purpose="email_verify", code="123456")
        b = hash_code(user_id="u1", purpose="account_unlock", code="123456")
        assert a != b

    def test_compare_hash_is_constant_time_equal(self):
        digest = hash_code(user_id="u1", purpose="email_verify", code="000000")
        assert compare_hash(digest, digest)
        assert not compare_hash(digest, "0" * 64)

    def test_destination_normalized_case(self):
        assert hash_destination("Ana@Example.com") == hash_destination("ana@example.com")


class TestMaskEmail:
    def test_masks_local_part(self):
        assert mask_email("user@example.com") == "u***@example.com"

    def test_single_char_local(self):
        assert mask_email("a@x.co") == "a***@x.co"

    def test_invalid_falls_back(self):
        assert mask_email("not-an-email") == "***"


class TestChannelRegistry:
    def test_email_is_registered(self):
        channel = get_channel("email")
        assert isinstance(channel, SmtpEmailChannel)

    def test_unknown_channel_raises(self):
        with pytest.raises(OtpChannelUnsupportedError) as exc:
            ChannelRegistry.get("sms")
        assert exc.value.code == "otp_channel_unsupported"


class TestSmtpEmailChannel:
    @pytest.fixture(autouse=True)
    def _locmem_email(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        mail.outbox.clear()

    def test_sends_html_and_text_with_code(self):
        SmtpEmailChannel().send(
            destination="ana@example.com",
            purpose="email_verify",
            code="654321",
            context={"first_name": "Ana", "ttl_minutes": 5},
        )
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["ana@example.com"]
        assert "654321" in message.body
        assert "Ana" in message.body
        html = message.alternatives[0][0]
        assert "654321" in html

    def test_unknown_purpose_uses_generic_template(self):
        SmtpEmailChannel().send(
            destination="ana@example.com",
            purpose="account_unlock",
            code="111222",
            context={"ttl_minutes": 5},
        )
        assert "111222" in mail.outbox[0].body

    def test_delivery_failure_does_not_leak_details(self):
        with patch(
            "apps.otp.channels.email.EmailMultiAlternatives.send",
            side_effect=OSError("connection refused"),
        ), pytest.raises(OtpDeliveryFailedError) as exc:
            SmtpEmailChannel().send(
                destination="ana@example.com",
                purpose="email_verify",
                code="123456",
                context={"ttl_minutes": 5},
            )
        assert exc.value.http_status == 502
        assert "123456" not in exc.value.message
        assert "SMTP" not in exc.value.message
        assert "connection refused" not in exc.value.message
