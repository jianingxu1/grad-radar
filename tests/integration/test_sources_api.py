from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api import routes
from app.main import create_app
from app.services import auth
from app.services.auth import get_current_user, get_source_admin
from app.sources.bootstrap import bootstrap_sources


def test_sources_list_is_public_and_create_requires_admin(
    session_factory: sessionmaker[Session], monkeypatch: Any
) -> None:
    with session_factory.begin() as session:
        bootstrap_sources(session)
    app = create_app(session_factory)
    client = TestClient(app)
    assert [source["name"] for source in client.get("/v1/sources").json()] == [
        "simplify",
        "speedyapply",
    ]
    payload = {"platform": "ashby", "board_name": "openai", "company_name": "OpenAI"}
    assert client.post("/v1/sources", json=payload).status_code == 401

    app.dependency_overrides[get_current_user] = lambda: "not-admin"
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(source_admin_ids={"admin"}))
    assert client.post("/v1/sources", json=payload).status_code == 403

    app.dependency_overrides[get_source_admin] = lambda: "admin"
    monkeypatch.setattr(routes, "fetch_board", lambda client, platform, board: [])
    created = client.post("/v1/sources", json=payload)
    assert created.status_code == 201
    assert created.json()["name"] == "ashby:openai"
    assert created.json()["filter_config"]["level_terms"]
    assert client.post("/v1/sources", json=payload).status_code == 409
    assert (
        client.post(
            "/v1/sources",
            json={"platform": "ashby", "board_name": "../bad", "company_name": "Bad"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/sources",
            json={"platform": "ashby", "board_name": "another", "company_name": "  "},
        ).status_code
        == 422
    )

    source_id = created.json()["id"]
    updated = client.patch(f"/v1/sources/{source_id}", json={"enabled": False})
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert client.patch(f"/v1/sources/{source_id}", json={"filter_config": {}}).status_code == 422
    assert client.patch(f"/v1/sources/{source_id}", json={"enabled": True}).status_code == 200


def test_source_admin_status_uses_backend_allowlist(
    session_factory: sessionmaker[Session], monkeypatch: Any
) -> None:
    app = create_app(session_factory)
    app.dependency_overrides[get_current_user] = lambda: "admin"
    monkeypatch.setattr(routes, "get_settings", lambda: SimpleNamespace(source_admin_ids={"admin"}))
    assert TestClient(app).get("/v1/me/source-admin").json() == {"is_admin": True}
