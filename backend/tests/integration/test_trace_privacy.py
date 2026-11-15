"""Traces (questions + answers metadata) are private to their author; admins see all for audit."""

import pytest


async def _register(client, name):
    r = await client.post("/auth/register", json={"username": name, "email": f"{name}@example.com", "password": "secret12"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_users_only_see_their_own_traces(client, auth_headers):
    bob = await _register(client, "bob_trace")
    carol = await _register(client, "carol_trace")

    r = await client.post("/chat", headers=bob, json={"query": "bob secret question about hotel limits", "stream": False, "backend": "mock"})
    assert r.status_code == 200

    bob_traces = (await client.get("/traces", headers=bob)).json()["traces"]
    assert any("bob secret" in t["query"] for t in bob_traces)
    tid = next(t["trace_id"] for t in bob_traces if "bob secret" in t["query"])

    carol_traces = (await client.get("/traces", headers=carol)).json()["traces"]
    assert not any("bob secret" in t["query"] for t in carol_traces)
    assert (await client.get(f"/traces/{tid}", headers=carol)).status_code == 404

    admin_traces = (await client.get("/traces", headers=auth_headers)).json()["traces"]
    assert any("bob secret" in t["query"] for t in admin_traces)
    assert (await client.get(f"/traces/{tid}", headers=auth_headers)).status_code == 200
