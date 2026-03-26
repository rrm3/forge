"""Tests for backend/auth.py."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.datastructures import Headers

from backend.auth import CurrentUser, _DEV_USERS, _verify_oidc_token, verify_token


def _make_request(headers: dict | None = None) -> Request:
    """Build a minimal Starlette Request with the given headers."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


class TestAuthErrors:
    """Tests for auth error cases."""

    @pytest.mark.asyncio
    async def test_missing_authorization_header_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(request=request, authorization=None)
        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_raises_401(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(request=request, authorization="Basic dXNlcjpwYXNz")
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_jwt_raises_401(self):
        request = _make_request()
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.oidc_provider_url = "https://id.digitalscience.ai"
            mock_settings.oidc_client_id = "testclient"
            with patch("backend.auth._get_jwks_client") as mock_jwks:
                mock_client = MagicMock()
                mock_client.get_signing_key_from_jwt.side_effect = Exception("key not found")
                mock_jwks.return_value = mock_client

                with pytest.raises(HTTPException) as exc_info:
                    await verify_token(
                        request=request,
                        authorization="Bearer invalid.jwt.token",
                    )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        request = _make_request()
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.oidc_provider_url = "https://id.digitalscience.ai"
            mock_settings.oidc_client_id = "testclient"
            with patch("backend.auth._get_jwks_client") as mock_jwks:
                import jwt as pyjwt

                mock_signing_key = MagicMock()
                mock_signing_key.key = "fake-key"
                mock_client = MagicMock()
                mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
                mock_jwks.return_value = mock_client

                with patch("backend.auth.jwt.decode") as mock_decode:
                    mock_decode.side_effect = pyjwt.ExpiredSignatureError("expired")

                    with pytest.raises(HTTPException) as exc_info:
                        await verify_token(
                            request=request,
                            authorization="Bearer some.jwt.token",
                        )
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


class TestMasquerade:
    """Tests for dev_mode masquerade behavior."""

    @pytest.mark.asyncio
    async def test_masquerade_swaps_identity(self):
        """In dev_mode with X-Masquerade-As header, identity is swapped."""
        request = _make_request({"X-Masquerade-As": "bob@example.com"})
        mock_user = CurrentUser(user_id="real-sub", email="real@example.com", name="Real User")

        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = True
            with patch("backend.auth._verify_oidc_token", return_value=mock_user):
                user = await verify_token(
                    request=request,
                    authorization="Bearer fake.jwt.token",
                )
        assert user.email == "bob@example.com"
        assert user.user_id != "real-sub"

    @pytest.mark.asyncio
    async def test_no_masquerade_without_header(self):
        """Without X-Masquerade-As, identity stays as the real user."""
        request = _make_request()
        mock_user = CurrentUser(user_id="real-sub", email="real@example.com", name="Real User")

        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = True
            with patch("backend.auth._verify_oidc_token", return_value=mock_user):
                user = await verify_token(
                    request=request,
                    authorization="Bearer fake.jwt.token",
                )
        assert user.user_id == "real-sub"
        assert user.email == "real@example.com"

    @pytest.mark.asyncio
    async def test_masquerade_ignored_in_production(self):
        """In production mode, X-Masquerade-As is ignored."""
        request = _make_request({"X-Masquerade-As": "bob@example.com"})
        mock_user = CurrentUser(user_id="real-sub", email="real@example.com", name="Real User")

        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = False
            with patch("backend.auth._verify_oidc_token", return_value=mock_user):
                user = await verify_token(
                    request=request,
                    authorization="Bearer fake.jwt.token",
                )
        assert user.user_id == "real-sub"
        assert user.email == "real@example.com"


class TestCurrentUser:
    """Tests for the CurrentUser dataclass."""

    def test_current_user_fields(self):
        user = CurrentUser(user_id="sub-123", email="test@example.com", name="Test User")
        assert user.user_id == "sub-123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"

    def test_dev_users_map_covers_defaults(self):
        for uid in ("alice", "bob", "carol"):
            assert uid in _DEV_USERS
            email, name = _DEV_USERS[uid]
            assert "@example.com" in email
            assert len(name) > 0


class TestVerifyOidcToken:
    """Unit tests for _verify_oidc_token."""

    def test_successful_decode_returns_current_user(self):
        mock_payload = {
            "sub": "user-sub-456",
            "email": "user@corp.com",
            "name": "Corp User",
            "org_id": "allowed-org-123",
        }
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-rsa-key"
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with (
            patch("backend.auth._get_jwks_client", return_value=mock_client),
            patch("backend.auth._jwks_url", return_value="https://example.com/jwks"),
            patch("backend.auth.jwt.decode", return_value=mock_payload),
            patch("backend.auth.settings") as mock_settings,
            patch("backend.auth.is_org_allowed", return_value=True),
        ):
            mock_settings.oidc_provider_url = "https://id.digitalscience.ai"
            mock_settings.oidc_client_id = "client123"

            user = _verify_oidc_token("fake.jwt.token")

        assert user.user_id == "user-sub-456"
        assert user.email == "user@corp.com"
        assert user.name == "Corp User"

    def test_missing_name_defaults_to_empty(self):
        mock_payload = {
            "sub": "user-sub-789",
            "email": "user@corp.com",
            "org_id": "allowed-org-123",
        }
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-rsa-key"
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with (
            patch("backend.auth._get_jwks_client", return_value=mock_client),
            patch("backend.auth._jwks_url", return_value="https://example.com/jwks"),
            patch("backend.auth.jwt.decode", return_value=mock_payload),
            patch("backend.auth.settings") as mock_settings,
            patch("backend.auth.is_org_allowed", return_value=True),
        ):
            mock_settings.oidc_provider_url = "https://id.digitalscience.ai"
            mock_settings.oidc_client_id = "client123"

            user = _verify_oidc_token("fake.jwt.token")

        assert user.name == ""

    def test_disallowed_org_raises_403(self):
        mock_payload = {
            "sub": "user-sub-999",
            "email": "hacker@evil.com",
            "name": "Bad Actor",
            "org_id": "unknown-org",
        }
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-rsa-key"
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with (
            patch("backend.auth._get_jwks_client", return_value=mock_client),
            patch("backend.auth._jwks_url", return_value="https://example.com/jwks"),
            patch("backend.auth.jwt.decode", return_value=mock_payload),
            patch("backend.auth.settings") as mock_settings,
            patch("backend.auth.is_org_allowed", return_value=False),
        ):
            mock_settings.oidc_provider_url = "https://id.digitalscience.ai"
            mock_settings.oidc_client_id = "client123"

            with pytest.raises(HTTPException) as exc_info:
                _verify_oidc_token("fake.jwt.token")

        assert exc_info.value.status_code == 403
        assert "authorized organization" in exc_info.value.detail

    def test_no_org_id_raises_403(self):
        mock_payload = {
            "sub": "user-sub-000",
            "email": "personal@gmail.com",
            "name": "No Org User",
        }
        mock_signing_key = MagicMock()
        mock_signing_key.key = "fake-rsa-key"
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with (
            patch("backend.auth._get_jwks_client", return_value=mock_client),
            patch("backend.auth._jwks_url", return_value="https://example.com/jwks"),
            patch("backend.auth.jwt.decode", return_value=mock_payload),
            patch("backend.auth.settings") as mock_settings,
            patch("backend.auth.is_org_allowed", return_value=False),
        ):
            mock_settings.oidc_provider_url = "https://id.digitalscience.ai"
            mock_settings.oidc_client_id = "client123"

            with pytest.raises(HTTPException) as exc_info:
                _verify_oidc_token("fake.jwt.token")

        assert exc_info.value.status_code == 403
