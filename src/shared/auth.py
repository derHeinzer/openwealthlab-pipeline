"""Google OAuth2 – service-account JWT → access-token exchange."""

from __future__ import annotations

import time
from typing import Optional

import httpx
import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from config import settings

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/datastore"
_LIFETIME = 3600  # 1 hour

# Simple in-memory cache
_cached_token: Optional[str] = None
_cached_expiry: float = 0.0


def get_access_token() -> str:
    global _cached_token, _cached_expiry
    now = time.time()
    if _cached_token and now < _cached_expiry - 60:
        return _cached_token

    sa = settings.get_service_account_info()
    private_key = load_pem_private_key(
        sa["private_key"].encode(), password=None
    )

    now_int = int(now)
    payload = {
        "iss": sa["client_email"],
        "scope": _SCOPE,
        "aud": _TOKEN_URI,
        "iat": now_int,
        "exp": now_int + _LIFETIME,
    }
    signed_jwt = jwt.encode(payload, private_key, algorithm="RS256")

    resp = httpx.post(
        _TOKEN_URI,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    _cached_token = data["access_token"]
    _cached_expiry = now + data.get("expires_in", _LIFETIME)
    return _cached_token
