"""JWT authentication for Digital Science ID (OIDC) tokens."""

import hashlib
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
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


def _masquerade_user(email: str, real_user: CurrentUser) -> CurrentUser:
    """Create a masqueraded CurrentUser from an email address.

    The user_id is a stable hash of the email so sessions and profiles
    are keyed consistently for the masqueraded identity.
    """
    user_id = hashlib.sha256(email.lower().encode()).hexdigest()[:32]
    # Derive a display name from the email local part
    local = email.split("@")[0]
    name = " ".join(part.capitalize() for part in local.replace(".", " ").replace("-", " ").split())

    logger.info(
        "Masquerade active: real_user=%s (%s) -> masquerade=%s (%s)",
        real_user.user_id, real_user.email, user_id, email,
    )
    return CurrentUser(user_id=user_id, email=email, name=name)


async def verify_token(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
) -> CurrentUser:
    """FastAPI dependency: verify OIDC JWT and return current user.

    In dev_mode, if an X-Masquerade-As header is present, the returned
    identity is swapped to the masqueraded email while the real token
    is still validated normally.
    """
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
    user = _verify_oidc_token(token)

    # Masquerade: swap identity in dev mode
    if settings.dev_mode:
        masquerade_email = request.headers.get("X-Masquerade-As")
        if masquerade_email:
            user = _masquerade_user(masquerade_email, user)

    return user


# Dependency alias for use in route signatures
AuthUser = Annotated[CurrentUser, Depends(verify_token)]
