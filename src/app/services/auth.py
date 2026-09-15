"""Supabase JWT validation for FastAPI's private endpoints."""

import httpx
import jwt
from fastapi import HTTPException, Request, status

from app.config.settings import Settings, get_settings


def get_current_user(request: Request) -> str:
    settings: Settings = get_settings()
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or not settings.supabase_url:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    token = header.removeprefix("Bearer ").strip()
    try:
        if not settings.supabase_jwks_url:
            raise ValueError("Supabase JWKS URL is not configured")
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
    except (jwt.PyJWTError, ValueError) as error:
        return _validate_with_supabase_auth(token, settings, error)


def _validate_with_supabase_auth(token: str, settings: Settings, original_error: Exception) -> str:
    """Validate tokens from legacy HS256 projects, which do not expose JWKS keys."""
    if not settings.supabase_publishable_key or not settings.supabase_url:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid access token"
        ) from original_error
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
