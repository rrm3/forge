"""JWT authentication for Digital Science ID (OIDC) tokens."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from backend.config import settings

logger = logging.getLogger(__name__)

_DEV_USERS = {
    "alice": ("alice@example.com", "Alice"),
    "bob": ("bob@example.com", "Bob"),
    "carol": ("carol@example.com", "Carol"),
}


@dataclass
class CurrentUser:
    user_id: str
    email: str
    name: str


@lru_cache(maxsize=1)
def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Create and cache a PyJWKClient for the given JWKS URL."""
    return PyJWKClient(jwks_url, cache_keys=True)


def _jwks_url() -> str:
    return f"{settings.oidc_provider_url}/.well-known/jwks.json"


def _verify_oidc_token(token: str) -> CurrentUser:
    """Verify an OIDC JWT and return the current user."""
    jwks_client = _get_jwks_client(_jwks_url())

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token key: {e}",
        ) from e

    try:
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_provider_url,
            options={"verify_at_hash": False},
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e

    return CurrentUser(
        user_id=payload["sub"],
        email=payload.get("email", ""),
        name=payload.get("name", ""),
    )


async def verify_token(
    authorization: str | None = Header(None, alias="Authorization"),
    x_dev_user_id: str | None = Header(None, alias="X-Dev-User-Id"),
) -> CurrentUser:
    """FastAPI dependency: verify OIDC JWT and return current user.

    In dev_mode, the X-Dev-User-Id header bypasses auth (defaults to "alice").
    """
    if settings.dev_mode:
        uid = x_dev_user_id or "alice"
        email, name = _DEV_USERS.get(uid, (f"{uid}@example.com", uid))
        return CurrentUser(user_id=uid, email=email, name=name)

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]
    return _verify_oidc_token(token)


# Dependency alias for use in route signatures
AuthUser = Annotated[CurrentUser, Depends(verify_token)]
