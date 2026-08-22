from __future__ import annotations

import pytest

from apps.authentication.services import is_allowed_redirect
from apps.tenants.models import Application
from apps.tenants.redirect_uris import parse_redirect_uris


class TestParseRedirectUris:
    def test_split_newlines(self):
        assert parse_redirect_uris(
            "http://192.168.0.101:8443/auth/callback\nhttps://mobile.ineac.xyz/auth/callback"
        ) == [
            "http://192.168.0.101:8443/auth/callback",
            "https://mobile.ineac.xyz/auth/callback",
        ]

    def test_split_comma_joined_single_entry(self):
        assert parse_redirect_uris(
            ["http://192.168.0.101:8443/auth/callback,https://mobile.ineac.xyz/auth/callback"]
        ) == [
            "http://192.168.0.101:8443/auth/callback",
            "https://mobile.ineac.xyz/auth/callback",
        ]

    def test_keeps_query_commas(self):
        assert parse_redirect_uris(["https://app.example/callback?ids=1,2"]) == [
            "https://app.example/callback?ids=1,2"
        ]

    def test_dedupes(self):
        assert parse_redirect_uris(
            ["https://a.example/cb", "https://a.example/cb,https://b.example/cb"]
        ) == ["https://a.example/cb", "https://b.example/cb"]

    def test_rejects_non_list(self):
        with pytest.raises(ValueError, match="lista"):
            parse_redirect_uris({"url": "https://a.example/cb"})


@pytest.mark.django_db
class TestAllowedRedirectExpandsStored:
    def test_comma_joined_whitelist_matches_each_uri(self):
        application = Application.objects.create(
            name="Joined",
            redirect_uris=[
                "http://192.168.0.101:8443/auth/callback,https://mobile.ineac.xyz/auth/callback"
            ],
        )
        assert is_allowed_redirect(
            application, "http://192.168.0.101:8443/auth/callback"
        )
        assert is_allowed_redirect(
            application, "https://mobile.ineac.xyz/auth/callback"
        )
        assert not is_allowed_redirect(application, "https://evil.example/cb")
