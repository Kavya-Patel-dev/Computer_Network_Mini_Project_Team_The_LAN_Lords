from __future__ import annotations

import pytest
import httpx

from backend.app.config import Settings
from backend.app.db import create_test_schema
from backend.app.main import create_app
from backend.app.models import Plan, SimulationRun, User
from backend.app.security import hash_password
from backend.app.services import frontend_flows_to_model, frontend_topology_to_model
from backend.app import config as backend_config


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app():
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        session_secret="unit-test-secret-with-adequate-randomness-123456789",
        frontend_origins=("http://localhost:5173",),
    )
    application = create_app(settings, testing=True)
    create_test_schema(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def register(client: httpx.AsyncClient, email: str = "user@example.com") -> dict:
    response = await client.post("/api/v1/auth/register", json={
        "name": "Test User", "email": email, "password": "Strong-pass-123",
        "role": "admin",
    })
    assert response.status_code == 201, response.text
    assert response.json()["user"]["role"] == "user"
    return response.json()["user"]


def csrf(client: httpx.AsyncClient) -> dict[str, str]:
    value = client.cookies.get("lanlords_csrf")
    assert value
    return {"X-CSRF-Token": value}


def add_user(app, *, user_id: str, email: str, role: str = "user") -> None:
    with app.state.session_factory() as db:
        db.add(User(id=user_id, name=email.split("@")[0], email=email,
                    password_hash=hash_password("Strong-pass-123"), role=role, status="active"))
        db.commit()


@pytest.mark.anyio
async def test_health_and_readiness_are_distinct(client: httpx.AsyncClient):
    assert (await client.get("/health")).json() == {"status": "ok"}
    response = await client.get("/ready")
    assert response.status_code == 200, response.text
    assert response.json()["database"] == "connected"
    assert response.json()["model_sha256"] == "45957597F56CF163C5AE5D69F6FE6959DDB638601C7ADE97B865A848151FFF28"


@pytest.mark.anyio
async def test_registration_login_session_and_csrf(client: httpx.AsyncClient):
    user = await register(client)
    assert user["role"] == "user"
    assert (await client.get("/api/v1/auth/me")).json()["user"]["id"] == user["id"]
    response = await client.patch("/api/v1/users/me", json={"name": "Changed"})
    assert response.status_code == 403
    response = await client.patch("/api/v1/users/me", headers=csrf(client), json={"name": "Changed"})
    assert response.status_code == 200
    assert response.json()["name"] == "Changed"
    first_sessions = await client.get("/api/v1/users/me/sessions")
    assert first_sessions.status_code == 200
    assert len(first_sessions.json()["items"]) == 1
    assert first_sessions.json()["items"][0]["current"] is True
    response = await client.post("/api/v1/auth/logout", headers=csrf(client))
    assert response.status_code == 200, response.text
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    login = await client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "Strong-pass-123"})
    assert login.status_code == 200, login.text
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    second_login = await client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "Strong-pass-123"})
    assert second_login.status_code == 200
    sessions = await client.get("/api/v1/users/me/sessions")
    assert len(sessions.json()["items"]) == 2
    revoked = await client.post("/api/v1/users/me/sessions/revoke-others", headers=csrf(client))
    assert revoked.status_code == 200
    assert revoked.json()["revoked_sessions"] == 1
    remaining = await client.get("/api/v1/users/me/sessions")
    assert len(remaining.json()["items"]) == 1


@pytest.mark.anyio
async def test_duplicate_registration_and_password_policy(client: httpx.AsyncClient):
    await register(client)
    duplicate = await client.post("/api/v1/auth/register", json={
        "name": "Other", "email": "USER@example.com", "password": "Strong-pass-123",
    })
    assert duplicate.status_code == 409
    weak = await client.post("/api/v1/auth/register", json={
        "name": "Other", "email": "other@example.com", "password": "abcdefgh",
    })
    assert weak.status_code == 422


@pytest.mark.anyio
async def test_records_require_auth_csrf_and_enforce_owner(client: httpx.AsyncClient, app):
    await register(client)
    payload = {"name": "Draft topology", "topology": {"name": "draft", "nodes": [], "links": []}}
    assert (await client.post("/api/v1/records", json=payload)).status_code == 403
    created = await client.post("/api/v1/records", headers=csrf(client), json=payload)
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    assert (await client.get(f"/api/v1/records/{record_id}")).status_code == 200
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as other:
        await register(other, "other@example.com")
        assert (await other.get(f"/api/v1/records/{record_id}")).status_code == 404
        response = await other.patch(f"/api/v1/records/{record_id}", headers=csrf(other), json={"name": "stolen"})
        assert response.status_code == 404


@pytest.mark.anyio
async def test_generated_topology_updates_the_existing_draft(client: httpx.AsyncClient):
    await register(client)
    created = await client.post("/api/v1/records", headers=csrf(client), json={
        "name": "Named draft", "topology": {"name": "empty", "nodes": [], "links": []},
    })
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]
    generated_topology = {
        "id": plan_id, "name": "Named draft", "nodes": [{"id": "R1", "type": "router"}], "links": [],
    }
    updated = await client.patch(f"/api/v1/records/{plan_id}", headers=csrf(client), json={
        "topology": generated_topology, "traffic_preset": "medium",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["id"] == plan_id
    plans = await client.get("/api/v1/records")
    assert plans.json()["total"] == 1
    assert plans.json()["items"][0]["topology"]["nodes"] == generated_topology["nodes"]


@pytest.mark.anyio
async def test_pending_plan_withdrawal_returns_to_draft_and_is_owner_only(client: httpx.AsyncClient, app):
    user = await register(client)
    with app.state.session_factory() as db:
        db.add(Plan(id="pending-plan", owner_id=user["id"], name="Pending", description="",
                    status="Pending Review", version="v1", topology={"nodes": [], "links": []},
                    traffic_preset="light", flows=[], selected_scenarios=["normal"], versions=[]))
        db.commit()
    response = await client.post("/api/v1/records/pending-plan/withdraw", headers=csrf(client))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Draft"
    assert response.json()["submitted_at"] is None
    assert response.json()["versions"][-1]["summary"] == "Withdrawn from admin review"
    conflict = await client.post("/api/v1/records/pending-plan/withdraw", headers=csrf(client))
    assert conflict.status_code == 409


@pytest.mark.anyio
async def test_results_can_be_filtered_to_one_plan(client: httpx.AsyncClient, app):
    user = await register(client)
    with app.state.session_factory() as db:
        for plan_id in ("plan-a", "plan-b"):
            db.add(Plan(id=plan_id, owner_id=user["id"], name=plan_id, description="",
                        status="Approved", version="v1", topology={"nodes": [], "links": []},
                        traffic_preset="light", flows=[], selected_scenarios=["normal"], versions=[]))
            db.add(SimulationRun(id=f"run-{plan_id}", plan_id=plan_id, owner_id=user["id"],
                                 status="completed", model_sha256="a" * 64,
                                 request={"scenarios": ["normal"]},
                                 result={"scenarios": {"normal": {"metrics": {}}}}))
        db.commit()
    response = await client.get("/api/v1/results?plan_id=plan-a&limit=100")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert [item["planId"] for item in body["items"]] == ["plan-a"]


@pytest.mark.anyio
async def test_admin_only_routes_reject_regular_users(client: httpx.AsyncClient):
    await register(client)
    assert (await client.get("/api/v1/admin/users")).status_code == 403
    assert (await client.get("/api/v1/dashboard/admin")).status_code == 403


@pytest.mark.anyio
async def test_admin_role_update_and_session_revocation_are_authorized(client: httpx.AsyncClient, app):
    await register(client)
    add_user(app, user_id="admin-1", email="admin@example.com", role="admin")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as admin_client:
        login = await admin_client.post("/api/v1/auth/login", json={
            "email": "admin@example.com", "password": "Strong-pass-123",
        })
        assert login.status_code == 200
        model = await admin_client.get("/api/v1/admin/model")
        assert model.status_code == 200
        assert model.json()["sha256"] == "45957597F56CF163C5AE5D69F6FE6959DDB638601C7ADE97B865A848151FFF28"
        analytics = await admin_client.get("/api/v1/dashboard/admin/analytics?days=30")
        assert analytics.status_code == 200
        assert analytics.json()["pending_reviews"] == 0
        changed = await admin_client.patch("/api/v1/admin/users/" + (await client.get("/api/v1/auth/me")).json()["user"]["id"],
                                           headers=csrf(admin_client), json={"role": "admin"})
        assert changed.status_code == 200
        assert changed.json()["role"] == "admin"
        revoked = await admin_client.post("/api/v1/admin/users/" + changed.json()["id"] + "/sessions/revoke",
                                          headers=csrf(admin_client))
        assert revoked.status_code == 200
        assert revoked.json()["revoked_sessions"] >= 1
        self_change = await admin_client.patch("/api/v1/admin/users/admin-1", headers=csrf(admin_client), json={"role": "user"})
        assert self_change.status_code == 409


@pytest.mark.anyio
async def test_share_link_is_owned_listed_and_revocable(client: httpx.AsyncClient, app):
    user = await register(client)
    with app.state.session_factory() as db:
        db.add(Plan(id="plan-share", owner_id=user["id"], name="Share plan", description="",
                    status="Approved", version="v1", topology={"nodes": [], "links": []},
                    traffic_preset="light", flows=[], selected_scenarios=["normal"], versions=[]))
        db.add(SimulationRun(id="run-share", plan_id="plan-share", owner_id=user["id"], status="completed",
                             model_sha256="a" * 64, request={"scenarios": ["normal"]},
                             result={"scenarios": {"normal": {"metrics": {}}}}))
        db.commit()
    created = await client.post("/api/v1/results/run-share/share", headers=csrf(client))
    assert created.status_code == 201, created.text
    token = created.json()["token"]
    listed = await client.get("/api/v1/shares")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["status"] == "active"
    public = await client.get(f"/api/v1/shares/{token}")
    assert public.status_code == 200
    revoked = await client.delete(f"/api/v1/shares/{token}", headers=csrf(client))
    assert revoked.status_code == 200
    assert (await client.get(f"/api/v1/shares/{token}")).status_code == 404


def test_frontend_adapter_maps_canvas_units_and_flow_classes():
    topology = frontend_topology_to_model({
        "name": "units", "nodes": [
            {"id": "R1", "type": "cisco_2911"}, {"id": "H1", "type": "server"},
        ], "links": [{"src": "R1", "dst": "H1", "bandwidth_mbps": 1000,
                      "latency_ms": 2.5, "loss_percent": 0.1}],
    })
    assert [node["type"] for node in topology["nodes"]] == ["router", "host"]
    assert topology["links"][0] == {"src": "R1", "dst": "H1", "bandwidth": 1000,
                                    "latency": 2.5, "loss_percent": 0.1}
    flow = frontend_flows_to_model([{"src": "H1", "dst": "R1", "demand_mbps": 1,
                                     "class": "real_time"}])[0]
    assert flow["source"] == "H1" and flow["destination"] == "R1"
    assert flow["qos_class"] == "REAL_TIME"


def test_backend_rejects_sqlite_outside_test_mode():
    settings = Settings(app_env="production", database_url="sqlite:///should-not-be-used.db",
                        session_secret="a" * 40, secure_cookies=True)
    with pytest.raises(RuntimeError, match="SQLite"):
        create_app(settings, testing=False)


def test_settings_load_backend_env_and_keep_process_environment_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=development\n"
        "DATABASE_URL=sqlite:///local.db\n"
        "SESSION_SECRET=file-secret-value-which-is-long-enough-123\n"
        "FRONTEND_ORIGINS=http://from-file.test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(backend_config, "_ENV_FILE", env_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://from-process.test")

    settings = backend_config.Settings.from_env()

    assert settings.app_env == "test"
    assert settings.database_url == "sqlite:///local.db"
    assert settings.session_secret == "file-secret-value-which-is-long-enough-123"
    assert settings.frontend_origins == ("http://from-process.test",)

