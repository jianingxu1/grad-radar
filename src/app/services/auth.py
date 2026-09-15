"""Supabase JWT validation for FastAPI's private endpoints."""

from functools import lru_cache
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request, status

from app.config.settings import Settings, get_settings


@lru_cache(maxsize=1)
def _jwks(url: str) -> dict[str, Any]:
    response = httpx.get(url, timeout=5)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise ValueError("invalid Supabase JWKS response")
    return payload


def current_user(request: Request) -> str:
    settings: Settings = get_settings()
    header = request.headers.get("Authorization", "")
    if (
        not header.startswith("Bearer ")
        or not settings.supabase_url
        or not settings.supabase_jwks_url
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    token = header.removeprefix("Bearer ").strip()
    try:
        signing_key = jwt.PyJWKClient(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=[signing_key.algorithm_name],
            audience=settings.supabase_jwt_audience,
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
        )
        subject = claims.get("sub")
        if not isinstance(subject, str):
            raise ValueError("missing subject")
        return subject
    except (jwt.PyJWTError, ValueError, httpx.HTTPError) as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid access token") from error
