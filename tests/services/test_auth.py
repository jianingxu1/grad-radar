import httpx
import jwt
import pytest
import respx
from fastapi import HTTPException
from starlette.requests import Request

from app.config.settings import Settings
from app.services import auth


def _request(token: str = "access-token") -> Request:
    return Request({"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]})


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "database_url": "postgresql://postgres:postgres@localhost:54322/postgres",
            "supabase_url": "https://project.supabase.co",
            "supabase_publishable_key": "sb_publishable_key",
        }
    )


@respx.mock
def test_validates_legacy_hs256_session_with_supabase_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth, "get_settings", _settings)
    monkeypatch.setattr(jwt, "PyJWKClient", lambda _: _FailingJwkClient())
    route = respx.get("https://project.supabase.co/auth/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "user-1"})
    )

    assert auth.get_current_user(_request()) == "user-1"
    assert route.called
    assert route.calls[0].request.headers["apikey"] == "sb_publishable_key"


def test_rejects_jwks_failure_without_publishable_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings().model_copy(update={"supabase_publishable_key": None})
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(jwt, "PyJWKClient", lambda _: _FailingJwkClient())

    with pytest.raises(HTTPException, match="invalid access token") as error:
        auth.get_current_user(_request())

    assert error.value.status_code == 401


class _FailingJwkClient:
    def get_signing_key_from_jwt(self, token: str) -> None:
        raise ValueError("no matching JWKS key")
