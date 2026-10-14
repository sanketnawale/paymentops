"""API client authentication foundation.

A secure internal API-client model (client_id + secret) that maps cleanly to OAuth2 client
credentials / mTLS later. Only a salted hash of the secret is stored; plaintext secrets are
never persisted. Authentication resolves the client's organization and allowed profiles.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paymentops_api.db.base import Database
from paymentops_api.db.models import ApiClient

_PBKDF2_ITERATIONS = 200_000


def hash_secret(secret: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_secret(secret: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def generate_client_id() -> str:
    return f"cn_{uuid.uuid4().hex[:20]}"


@dataclass(frozen=True)
class AuthenticatedClient:
    client_id: str
    organization_id: str
    allowed_profiles: list[str]
    client_id_guid: str


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    db: Database = request.app.state.db
    async for session in db.session():
        yield session


async def get_api_client(
    x_client_id: str = Header(..., alias="X-Client-Id"),
    x_client_secret: str = Header(..., alias="X-Client-Secret"),
    session: AsyncSession = Depends(get_db),
) -> AuthenticatedClient:
    """Authenticate an API client via X-Client-Id / X-Client-Secret headers."""
    result = await session.execute(select(ApiClient).where(ApiClient.client_id == x_client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid client")
    if client.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="client disabled")
    if not verify_secret(x_client_secret, client.secret_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    client.last_used_at = datetime.now(UTC)
    await session.commit()
    return AuthenticatedClient(
        client_id=client.client_id,
        organization_id=str(client.organization_id),
        allowed_profiles=client.allowed_profiles or [],
        client_id_guid=str(client.id),
    )


async def get_optional_api_client(
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
    x_client_secret: str | None = Header(default=None, alias="X-Client-Secret"),
    session: AsyncSession = Depends(get_db),
) -> AuthenticatedClient | None:
    """Return an authenticated client, or ``None`` if no credentials were supplied.

    If credentials ARE supplied but invalid, raise 401/403 (never silently ignore them).
    """
    if not x_client_id or not x_client_secret:
        return None
    return await get_api_client(
        x_client_id=x_client_id,
        x_client_secret=x_client_secret,
        session=session,
    )


async def get_actor_identity(
    x_actor_identity: str | None = Header(default=None, alias="X-Actor-Identity"),
) -> str | None:
    """Trusted, internally-generated actor identity for audit.

    The public browser cannot reach the backend directly; the Next.js web server strips any
    inbound ``X-Actor-Identity`` and sets it from the validated session. Callers must never
    trust an actor identity supplied by the browser in a request body.
    """
    if x_actor_identity is None:
        return None
    return x_actor_identity.strip()[:128] or None
