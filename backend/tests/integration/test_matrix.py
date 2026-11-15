"""Matrix: documents × questions, each cell checked against its own document's text."""

import pytest

from tests.integration.test_api import _upload


@pytest.mark.asyncio
async def test_matrix_found_unverified_and_not_found(client, auth_headers, fake_llm):
    doc = await _upload(client, auth_headers)
    fake_llm.responses.update({
        "Question: Hotel cap in Tier 1 cities?":
            '{"answer": "220 USD per night", "quote": "Hotel stays are capped at 220 USD per night in Tier 1 cities", "excerpt": 1}',
        "Question: Meal allowance?":
            '{"answer": "999 USD per day", "quote": "Meals are unlimited for everyone", "excerpt": 1}',
        "Question: Parental leave weeks?":
            '{"answer": "NOT_FOUND", "quote": "", "excerpt": 0}',
    })
    r = await client.post("/matrix", headers=auth_headers, json={
        "document_ids": [doc],
        "questions": ["Hotel cap in Tier 1 cities?", "Meal allowance?", "Parental leave weeks?"],
    })
    assert r.status_code == 200, r.text
    cells = {c["question"]: c for c in r.json()["cells"]}
    assert cells["Hotel cap in Tier 1 cities?"]["status"] == "found"
    assert cells["Hotel cap in Tier 1 cities?"]["answer"] == "220 USD per night"
    assert cells["Meal allowance?"]["status"] == "unverified"        # quote is not in the document
    assert cells["Parental leave weeks?"]["status"] == "not_found"


@pytest.mark.asyncio
async def test_matrix_respects_document_access(client, auth_headers):
    doc = await _upload(client, auth_headers)
    r = await client.post("/auth/register", json={"username": "outsider", "email": "outsider@example.com", "password": "secret12"})
    other = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.put(f"/documents/{doc}/sharing", headers=auth_headers, json={"visibility": "private"})
    assert r.status_code == 200, r.text
    r = await client.post("/matrix", headers=other, json={"document_ids": [doc], "questions": ["Hotel cap?"]})
    assert r.status_code == 200
    assert r.json()["cells"][0]["status"] == "not_found"
