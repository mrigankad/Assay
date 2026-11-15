"""
OpenID Connect ID-token verification for browser sign-in (Entra ID or any OIDC provider).

The browser runs Authorization Code + PKCE against the provider and sends us the
ID token. We trust it only after checking, against the provider's published
discovery document and keys: signature (asymmetric algorithms only, never the
algorithm the token asks for), issuer, audience (our client id), expiry, and the
nonce we handed the browser.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from jose import JWTError, jwt

from src.core.auth import JWKSCache, entra_issuer
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

SAFE_ALGS = {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512"}


@dataclass
class Provider:
    name: str          # "entra" | "oidc"
    issuer: str
    client_id: str


def provider(name: str) -> Optional[Provider]:
    if name == "entra" and settings.entra_tenant_id and settings.entra_client_id:
        return Provider("entra", entra_issuer(), settings.entra_client_id)
    if name == "oidc" and os.getenv("OIDC_ISSUER") and os.getenv("OIDC_CLIENT_ID"):
        return Provider("oidc", os.environ["OIDC_ISSUER"].rstrip("/"), os.environ["OIDC_CLIENT_ID"])
    return None


_discovery: Dict[str, tuple[float, Dict[str, Any]]] = {}
_jwks: Dict[str, JWKSCache] = {}


def discovery(issuer: str) -> Dict[str, Any]:
    cached = _discovery.get(issuer)
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    r = httpx.get(issuer.rstrip("/") + "/.well-known/openid-configuration", timeout=10.0)
    r.raise_for_status()
    doc = r.json()
    _discovery[issuer] = (time.time(), doc)
    return doc


class OIDCError(Exception):
    pass


def verify_id_token(p: Provider, id_token: str, nonce: Optional[str]) -> Dict[str, Any]:
    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise OIDCError("Malformed ID token") from exc
    alg = header.get("alg")
    if alg not in SAFE_ALGS:
        raise OIDCError(f"Refusing token signed with {alg!r}")
    doc = discovery(p.issuer)
    jwks_uri = doc.get("jwks_uri")
    if not jwks_uri:
        raise OIDCError("Provider has no jwks_uri")
    cache = _jwks.setdefault(jwks_uri, JWKSCache(jwks_uri))
    key = cache.get(header.get("kid", ""))
    if key is None:
        raise OIDCError("Unknown signing key")
    expected_iss = doc.get("issuer", p.issuer)
    try:
        claims = jwt.decode(id_token, key, algorithms=[alg], audience=p.client_id, issuer=expected_iss,
                            options={"verify_at_hash": False})
    except JWTError as exc:
        raise OIDCError(f"ID token rejected: {exc}") from exc
    if not nonce or claims.get("nonce") != nonce:
        raise OIDCError("Nonce mismatch")
    return claims


def claims_email(p: Provider, claims: Dict[str, Any]) -> Optional[str]:
    """Email we can rely on. Generic OIDC must not say email_verified=false."""
    if p.name == "oidc" and claims.get("email_verified") is False:
        return None
    email = claims.get("email") or (claims.get("preferred_username") if p.name == "entra" else None)
    return email.lower() if isinstance(email, str) and "@" in email else None
