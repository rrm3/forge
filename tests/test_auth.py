"""Tests for backend/auth.py."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.auth import CurrentUser, _DEV_USERS, _verify_oidc_token, verify_token


class TestDevMode:
    """Tests for dev_mode bypass."""

    @pytest.mark.asyncio
    async def test_dev_mode_defaults_to_alice(self):
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = True
            user = await verify_token(authorization=None, x_dev_user_id=None)
        assert user.user_id == "alice"
        assert user.email == "alice@example.com"
        assert user.name == "Alice"

    @pytest.mark.asyncio
    async def test_dev_mode_accepts_x_dev_user_id(self):
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = True
            user = await verify_token(authorization=None, x_dev_user_id="bob")
        assert user.user_id == "bob"
        assert user.email == "bob@example.com"
        assert user.name == "Bob"

    @pytest.mark.asyncio
    async def test_dev_mode_unknown_user_falls_back_to_email(self):
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = True
            user = await verify_token(authorization=None, x_dev_user_id="unknown-user")
        assert user.user_id == "unknown-user"
        assert user.email == "unknown-user@example.com"

    @pytest.mark.asyncio
    async def test_dev_mode_ignores_bearer_token(self):
        """In dev_mode, even a real-looking token should be bypassed."""
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = True
            user = await verify_token(
                authorization="Bearer some.jwt.token", x_dev_user_id="carol"
            )
        assert user.user_id == "carol"


class TestAuthErrors:
    """Tests for auth error cases in production mode."""

    @pytest.mark.asyncio
    async def test_missing_authorization_header_raises_401(self):
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = False
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(authorization=None, x_dev_user_id=None)
        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_raises_401(self):
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = False
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(authorization="Basic dXNlcjpwYXNz", x_dev_user_id=None)
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_jwt_raises_401(self):
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.oidc_provider_url = "https://id-staging.digital-science.us"
            mock_settings.oidc_client_id = "testclient"
            with patch("backend.auth._get_jwks_client") as mock_jwks:
                mock_client = MagicMock()
                mock_client.get_signing_key_from_jwt.side_effect = Exception("key not found")
                mock_jwks.return_value = mock_client

                with pytest.raises(HTTPException) as exc_info:
                    await verify_token(
                        authorization="Bearer invalid.jwt.token", x_dev_user_id=None
                    )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        with patch("backend.auth.settings") as mock_settings:
            mock_settings.dev_mode = False
            mock_settings.oidc_provider_url = "https://id-staging.digital-science.us"
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
                            authorization="Bearer some.jwt.token", x_dev_user_id=None
                        )
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


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
        ):
            mock_settings.oidc_provider_url = "https://id-staging.digital-science.us"
            mock_settings.oidc_client_id = "client123"

            user = _verify_oidc_token("fake.jwt.token")

        assert user.user_id == "user-sub-456"
        assert user.email == "user@corp.com"
        assert user.name == "Corp User"

    def test_missing_name_defaults_to_empty(self):
        mock_payload = {
            "sub": "user-sub-789",
            "email": "user@corp.com",
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
        ):
            mock_settings.oidc_provider_url = "https://id-staging.digital-science.us"
            mock_settings.oidc_client_id = "client123"

            user = _verify_oidc_token("fake.jwt.token")

        assert user.name == ""
