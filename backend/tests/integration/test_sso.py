"""OIDC sign-in: real RS256 signatures against a fake provider; every bad token is refused."""

import base64
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

ISSUER = "https://idp.example.com"
CLIENT = "assay-spa"


def _b64(n: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes((n.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()


@pytest.fixture
def idp(monkeypatch):
    from src.core import oidc
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    pub = key.public_key().public_numbers()
    jwks = {"keys": [{"kty": "RSA", "kid": "k1", "use": "sig", "alg": "RS256", "n": _b64(pub.n), "e": _b64(pub.e)}]}
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", CLIENT)
    monkeypatch.setattr(oidc, "discovery", lambda iss: {"issuer": ISSUER, "jwks_uri": f"{ISSUER}/jwks"})
    cache = oidc.JWKSCache(f"{ISSUER}/jwks")
    cache.set_keys(jwks)
    oidc._jwks[f"{ISSUER}/jwks"] = cache

    def make(email="dana@acme.com", nonce="n-123456", aud=CLIENT, verified=True, alg="RS256", secret=None):
        claims = {"iss": ISSUER, "aud": aud, "sub": "u1", "email": email, "email_verified": verified,
                  "nonce": nonce, "iat": int(time.time()), "exp": int(time.time()) + 300}
        return jwt.encode(claims, secret or pem.decode(), algorithm=alg, headers={"kid": "k1"})
    return make


async def _sso(client, token, nonce="n-123456"):
    return await client.post("/auth/sso", json={"provider": "oidc", "id_token": token, "nonce": nonce})


@pytest.mark.asyncio
async def test_valid_token_creates_and_signs_in(client, idp):
    r = await _sso(client, idp())
    assert r.status_code == 200, r.text
    me = (await client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})).json()
    assert me["email"] == "dana@acme.com" and me["role"] == "user"
    r2 = await _sso(client, idp())                      # same person again: same account
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_bad_tokens_are_refused(client, idp):
    assert (await _sso(client, idp(), nonce="n-other-999")).status_code == 401      # replay / wrong nonce
    assert (await _sso(client, idp(aud="someone-else"))).status_code == 401          # token for another app
    forged = idp(alg="HS256", secret="whatever")                                      # algorithm confusion
    assert (await _sso(client, forged)).status_code == 401
    assert (await _sso(client, idp(verified=False))).status_code == 403              # unverified email


@pytest.mark.asyncio
async def test_new_people_blocked_when_auto_create_off(client, idp, monkeypatch):
    monkeypatch.setenv("SSO_AUTO_CREATE", "false")
    assert (await _sso(client, idp(email="new@acme.com"))).status_code == 403
    monkeypatch.setenv("SSO_AUTO_CREATE", "true")
    monkeypatch.setenv("SSO_ALLOWED_DOMAINS", "partner.com")
    assert (await _sso(client, idp(email="new@acme.com"))).status_code == 403
    assert (await _sso(client, idp(email="ok@partner.com"))).status_code == 200


@pytest.mark.asyncio
async def test_not_configured(client, monkeypatch):
    monkeypatch.delenv("OIDC_ISSUER", raising=False)
    r = await client.post("/auth/sso", json={"provider": "oidc", "id_token": "x" * 40, "nonce": "n-123456"})
    assert r.status_code == 404
