import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jwt.algorithms import ECAlgorithm
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
    settings = _settings().model_copy(update={"supabase_allow_legacy_hs256": True})
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    route = respx.get("https://project.supabase.co/auth/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "user-1"})
    )

    token = jwt.encode({"sub": "user-1"}, "a" * 32, algorithm="HS256")
    assert auth.get_current_user(_request(token)) == "user-1"
    assert route.called
    assert route.calls[0].request.headers["apikey"] == "sb_publishable_key"


@respx.mock
def test_rejects_legacy_token_without_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "get_settings", _settings)
    route = respx.get("https://project.supabase.co/auth/v1/user").mock(
        return_value=httpx.Response(200, json={"id": "user-1"})
    )
    token = jwt.encode({"sub": "user-1"}, "a" * 32, algorithm="HS256")

    with pytest.raises(HTTPException, match="invalid access token") as error:
        auth.get_current_user(_request(token))

    assert error.value.status_code == 401
    assert not route.called


def test_reuses_signing_keys_for_valid_and_unknown_key_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    assert settings.supabase_jwks_url is not None
    keys = auth.SigningKeys(settings.supabase_jwks_url)
    monkeypatch.setattr(auth, "_signing_keys", lambda _: keys)
    monkeypatch.setattr(auth, "get_settings", _settings)
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = ECAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    assert isinstance(public_key, dict)
    key = jwt.PyJWK({**public_key, "kid": "current", "alg": "ES256"})
    calls = []

    def get_keys(*, refresh: bool) -> list[jwt.PyJWK]:
        calls.append(refresh)
        return [key]

    monkeypatch.setattr(keys.client, "get_signing_keys", get_keys)
    claims = {
        "iss": "https://project.supabase.co/auth/v1",
        "aud": "authenticated",
        "sub": "user-1",
        "exp": 4102444800,
    }
    valid = jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": "current"})
    unknown = jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": "unknown"})

    assert auth.get_current_user(_request(valid)) == "user-1"
    with pytest.raises(HTTPException, match="invalid access token"):
        auth.get_current_user(_request(unknown))
    assert auth.get_current_user(_request(valid)) == "user-1"
    assert calls == [True]
