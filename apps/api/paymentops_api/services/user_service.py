"""Application user + session service.

Server-side authentication baseline: local application users with hashed passwords and
revocable opaque sessions. Designed so OIDC/SSO can replace or augment local login later.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from paymentops_api.db.models import AppUser, Organization, UserSession
from paymentops_api.passwords import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
SESSION_TTL_HOURS = 8


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class AuthenticationError(Exception):
    """Generic authentication failure (never reveals whether the email exists)."""


class AccountDisabledError(AuthenticationError):
    """Raised only after correct credentials for a disabled account."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def create_user(
    session: AsyncSession,
    *,
    organization_id: str,
    email: str,
    display_name: str,
    password: str,
    role: UserRole = UserRole.VIEWER,
    status: UserStatus = UserStatus.ACTIVE,
) -> AppUser:
    row = AppUser(
        organization_id=organization_id,
        email=normalize_email(email),
        display_name=display_name,
        password_hash=hash_password(password),
        role=role.value,
        status=status.value,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_user_by_email(session: AsyncSession, email: str) -> AppUser | None:
    result = await session.execute(select(AppUser).where(AppUser.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def authenticate(session: AsyncSession, email: str, password: str) -> AppUser:
    """Verify credentials. Raises ``AuthenticationError`` on any failure (no enumeration).

    The disabled-account state is only revealed after the password has been verified, so a
    wrong password never distinguishes existing from non-existing accounts.
    """
    user = await get_user_by_email(session, email)
    now = datetime.now(UTC)
    if user is None:
        # Perform a dummy verification to reduce timing side channels.
        verify_password(password, "pbkdf2_sha256$1$00$00")
        raise AuthenticationError("invalid credentials")
    if user.locked_until is not None and user.locked_until > now:
        raise AuthenticationError("account temporarily locked")
    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_count = 0
        await session.commit()
        raise AuthenticationError("invalid credentials")
    if user.status != UserStatus.ACTIVE.value:
        raise AccountDisabledError("account disabled")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    await session.commit()
    await session.refresh(user)
    return user


async def create_session(session: AsyncSession, user: AppUser) -> tuple[str, datetime]:
    token = generate_session_token()
    expires_at = datetime.now(UTC) + timedelta(hours=SESSION_TTL_HOURS)
    session.add(
        UserSession(
            user_id=user.id,
            organization_id=user.organization_id,
            token_hash=hash_session_token(token),
            expires_at=expires_at,
            last_seen_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return token, expires_at


async def resolve_session(session: AsyncSession, token: str) -> AppUser | None:
    """Return the active user for a session token, or ``None`` if invalid/expired/revoked."""
    result = await session.execute(
        select(UserSession).where(UserSession.token_hash == hash_session_token(token))
    )
    user_session = result.scalar_one_or_none()
    if user_session is None:
        return None
    now = datetime.now(UTC)
    if user_session.revoked_at is not None or user_session.expires_at <= now:
        return None
    user = await session.get(AppUser, user_session.user_id)
    if user is None or user.status != UserStatus.ACTIVE.value:
        return None
    user_session.last_seen_at = now
    await session.commit()
    return user


async def revoke_session(session: AsyncSession, token: str) -> None:
    result = await session.execute(
        select(UserSession).where(UserSession.token_hash == hash_session_token(token))
    )
    user_session = result.scalar_one_or_none()
    if user_session is not None and user_session.revoked_at is None:
        user_session.revoked_at = datetime.now(UTC)
        await session.commit()


async def revoke_all_sessions(session: AsyncSession, user_id: str) -> int:
    result = await session.execute(
        select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    )
    count = 0
    now = datetime.now(UTC)
    for user_session in result.scalars().all():
        user_session.revoked_at = now
        count += 1
    await session.commit()
    return count


async def get_organization(session: AsyncSession, organization_id: str) -> Organization | None:
    return await session.get(Organization, organization_id)


async def list_users(session: AsyncSession, organization_id: str | None = None) -> list[AppUser]:
    stmt = select(AppUser)
    if organization_id:
        stmt = stmt.where(AppUser.organization_id == organization_id)
    result = await session.execute(stmt.order_by(AppUser.created_at))
    return list(result.scalars().all())


async def set_password(session: AsyncSession, user: AppUser, new_password: str) -> None:
    """Set a new password, clear lockout, and revoke all existing sessions."""
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    await revoke_all_sessions(session, str(user.id))
    await session.commit()


async def set_status(session: AsyncSession, user: AppUser, status: UserStatus) -> None:
    user.status = status.value
    if status == UserStatus.DISABLED:
        await revoke_all_sessions(session, str(user.id))
    await session.commit()


async def set_role(session: AsyncSession, user: AppUser, role: UserRole) -> None:
    user.role = role.value
    await session.commit()
