"""Sign-up closes after the first account unless ALLOW_SIGNUP; first account is admin; email works as login."""

import pytest
from sqlalchemy import delete

from src.infrastructure.database import User
from src.infrastructure.database.session_manager import session_scope


@pytest.mark.asyncio
async def test_first_user_admin_then_signup_closed(client, monkeypatch):
    monkeypatch.setenv("ALLOW_SIGNUP", "false")
    async with session_scope() as s:          # simulate a fresh install (fixture seeds an admin)
        await s.execute(delete(User))

    m = (await client.get("/auth/methods")).json()
    assert m["first_run"] is True and m["signup_open"] is True and m["password"] is True

    r = await client.post("/auth/register", json={"username": "owner", "email": "Owner@Example.com", "password": "secret12"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    me = (await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})).json()
    assert me["role"] == "admin"

    m = (await client.get("/auth/methods")).json()
    assert m["first_run"] is False and m["signup_open"] is False

    r = await client.post("/auth/register", json={"username": "second", "email": "s@example.com", "password": "secret12"})
    assert r.status_code == 403

    r = await client.post("/auth/login", json={"username": "owner@example.com", "password": "secret12"})
    assert r.status_code == 200
