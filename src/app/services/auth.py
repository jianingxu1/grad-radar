"""Supabase JWT validation for FastAPI's private endpoints."""

from functools import lru_cache
from threading import BoundedSemaphore, Lock
from time import monotonic
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status

from app.config.settings import Settings, get_settings


class SigningKeys:
    def __init__(self, url: str) -> None:
        self.client = jwt.PyJWKClient(url, timeout=3)
        self.keys: dict[str, jwt.PyJWK] = {}
        self.refresh_after = 0.0
        self.lock = Lock()

    def get(self, key_id: str) -> jwt.PyJWK | None:
        now = monotonic()
        if now >= self.refresh_after and self.lock.acquire(blocking=False):
            try:
                if now >= self.refresh_after:
                    self.refresh_after = float("inf")
                    try:
                        self.keys = {
                            key.key_id: key
                            for key in self.client.get_signing_keys(refresh=True)
                            if isinstance(key.key_id, str)
                        }
                    except (jwt.PyJWTError, ValueError):
                        self.keys = {}
                        raise
                    finally:
                        self.refresh_after = monotonic() + (60 if self.keys else 5)
            finally:
                self.lock.release()
        if not self.keys and self.lock.locked():
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "signing keys unavailable")
        return self.keys.get(key_id)


@lru_cache(maxsize=4)
def _signing_keys(url: str) -> SigningKeys:
    return SigningKeys(url)


_legacy_auth_slots = BoundedSemaphore(4)


def get_current_user(request: Request) -> str:
    settings: Settings = get_settings()
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or not settings.supabase_url:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    token = header.removeprefix("Bearer ").strip()
    try:
        if len(token) > 8192:
            raise ValueError("access token is too large")
        metadata = jwt.get_unverified_header(token)
        algorithm = metadata.get("alg")
        if algorithm == "HS256" and settings.supabase_allow_legacy_hs256:
            return _validate_with_supabase_auth(token, settings)
        key_id = metadata.get("kid")
        if algorithm not in ("ES256", "RS256", "EdDSA") or not isinstance(key_id, str):
            raise ValueError("invalid signing key metadata")
        jwks_url = settings.supabase_jwks_url
        if not jwks_url:
            raise ValueError("Supabase JWKS URL is not configured")
        signing_key = _signing_keys(jwks_url).get(key_id)
        if signing_key is None or signing_key.algorithm_name != algorithm:
            raise ValueError("unknown signing key")
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            audience=settings.supabase_jwt_audience,
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
            options={"require": ["exp", "sub"]},
        )
        subject = claims.get("sub")
        if not isinstance(subject, str):
            raise ValueError("missing subject")
        return subject
    except (jwt.PyJWTError, ValueError) as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid access token") from error


def get_source_admin(user_id: Annotated[str, Depends(get_current_user)]) -> str:
    if user_id not in get_settings().source_admin_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "source admin required")
    return user_id


def _validate_with_supabase_auth(token: str, settings: Settings) -> str:
    """Validate tokens from legacy HS256 projects, which do not expose JWKS keys."""
    if not settings.supabase_publishable_key or not settings.supabase_url:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid access token")
    if not _legacy_auth_slots.acquire(blocking=False):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "authentication busy")
    try:
        response = httpx.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=5.0,
        )
        response.raise_for_status()
        subject = response.json().get("id")
        if not isinstance(subject, str):
            raise ValueError("missing user id")
        return subject
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid access token") from error
    finally:
        _legacy_auth_slots.release()
