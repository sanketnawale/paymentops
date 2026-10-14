"""Application authentication tests (require PostgreSQL; skipped otherwise)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from paymentops_api.db.models import Organization, UserSession
from paymentops_api.passwords import hash_password, verify_password
from paymentops_api.services import user_service
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


async def _seed_org(session, public_id: str):
    org = Organization(name=public_id, public_id=public_id)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


def test_password_hash_roundtrip():
    stored = hash_password("correct horse battery staple")
    assert stored.startswith("pbkdf2_sha256$")
    assert "correct horse battery staple" not in stored
    assert verify_password("correct horse battery staple", stored) is True
    assert verify_password("wrong", stored) is False
    assert verify_password("x", "not-a-hash") is False


async def test_authenticate_and_session_lifecycle():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "auth-lifecycle")
        user = await user_service.create_user(
            session,
            organization_id=str(org.id),
            email="Operator@Example.COM",
            display_name="Op",
            password="a-strong-password-1",
            role=user_service.UserRole.OPERATOR,
        )
        # Email is normalized.
        assert user.email == "operator@example.com"

        authed = await user_service.authenticate(
            session, "operator@example.com", "a-strong-password-1"
        )
        assert authed.id == user.id

        token, expires_at = await user_service.create_session(session, authed)
        assert expires_at > datetime.now(UTC)
        # Token is not stored in plaintext.
        rows = (await session.execute(UserSession.__table__.select())).all()
        assert all(token not in (r.token_hash or "") for r in rows)

        resolved = await user_service.resolve_session(session, token)
        assert resolved is not None and resolved.id == user.id

        await user_service.revoke_session(session, token)
        assert await user_service.resolve_session(session, token) is None
    await engine.dispose()


async def test_wrong_password_is_generic_and_disabled_is_distinct():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "auth-errors")
        await user_service.create_user(
            session,
            organization_id=str(org.id),
            email="disabled@example.com",
            display_name="Disabled",
            password="a-strong-password-1",
            role=user_service.UserRole.VIEWER,
            status=user_service.UserStatus.DISABLED,
        )
        # Unknown email and wrong password both raise the generic error.
        with pytest.raises(user_service.AuthenticationError) as e1:
            await user_service.authenticate(session, "nobody@example.com", "whatever")
        assert "invalid credentials" in str(e1.value)
        with pytest.raises(user_service.AuthenticationError) as e2:
            await user_service.authenticate(session, "disabled@example.com", "wrong-password")
        assert "invalid credentials" in str(e2.value)
        # Correct password on a disabled account reveals the disabled state.
        with pytest.raises(user_service.AccountDisabledError):
            await user_service.authenticate(session, "disabled@example.com", "a-strong-password-1")
    await engine.dispose()


async def test_lockout_after_repeated_failures():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "auth-lockout")
        await user_service.create_user(
            session,
            organization_id=str(org.id),
            email="lock@example.com",
            display_name="Lock",
            password="a-strong-password-1",
            role=user_service.UserRole.OPERATOR,
        )
        for _ in range(user_service.MAX_FAILED_LOGINS):
            with pytest.raises(user_service.AuthenticationError):
                await user_service.authenticate(session, "lock@example.com", "wrong")
        # Even the correct password is rejected while locked.
        with pytest.raises(user_service.AuthenticationError):
            await user_service.authenticate(session, "lock@example.com", "a-strong-password-1")
    await engine.dispose()


async def test_set_password_revokes_sessions_and_clears_lockout():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "auth-admin-pw")
        user = await user_service.create_user(
            session,
            organization_id=str(org.id),
            email="admin-pw@example.com",
            display_name="AdminPw",
            password="old-strong-password-1",
            role=user_service.UserRole.OPERATOR,
        )
        token, _ = await user_service.create_session(session, user)
        for _ in range(user_service.MAX_FAILED_LOGINS):
            with pytest.raises(user_service.AuthenticationError):
                await user_service.authenticate(session, user.email, "wrong")
        await session.refresh(user)
        assert user.locked_until is not None

        await user_service.set_password(session, user, "new-strong-password-1")
        await session.refresh(user)
        # Lockout cleared and all sessions revoked.
        assert user.locked_until is None and user.failed_login_count == 0
        assert await user_service.resolve_session(session, token) is None
        # New password works, old one does not.
        assert (
            await user_service.authenticate(session, user.email, "new-strong-password-1")
        ).id == user.id
        with pytest.raises(user_service.AuthenticationError):
            await user_service.authenticate(session, user.email, "old-strong-password-1")
    await engine.dispose()


async def test_disable_revokes_sessions_and_reenable_restores_login():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "auth-admin-status")
        user = await user_service.create_user(
            session,
            organization_id=str(org.id),
            email="status@example.com",
            display_name="Status",
            password="a-strong-password-1",
            role=user_service.UserRole.VIEWER,
        )
        token, _ = await user_service.create_session(session, user)

        await user_service.set_status(session, user, user_service.UserStatus.DISABLED)
        assert await user_service.resolve_session(session, token) is None
        with pytest.raises(user_service.AccountDisabledError):
            await user_service.authenticate(session, user.email, "a-strong-password-1")

        await user_service.set_status(session, user, user_service.UserStatus.ACTIVE)
        assert (
            await user_service.authenticate(session, user.email, "a-strong-password-1")
        ).id == user.id
    await engine.dispose()


async def test_set_role_updates_authorization_role():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "auth-admin-role")
        user = await user_service.create_user(
            session,
            organization_id=str(org.id),
            email="role@example.com",
            display_name="Role",
            password="a-strong-password-1",
            role=user_service.UserRole.VIEWER,
        )
        await user_service.set_role(session, user, user_service.UserRole.ADMIN)
        await session.refresh(user)
        assert user.role == user_service.UserRole.ADMIN.value
    await engine.dispose()


async def test_expired_session_is_rejected():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        org = await _seed_org(session, "auth-expiry")
        user = await user_service.create_user(
            session,
            organization_id=str(org.id),
            email="exp@example.com",
            display_name="Exp",
            password="a-strong-password-1",
            role=user_service.UserRole.OPERATOR,
        )
        token, _ = await user_service.create_session(session, user)
        row = (await session.execute(UserSession.__table__.select())).first()
        # Force expiry.
        await session.execute(
            UserSession.__table__.update()
            .where(UserSession.__table__.c.token_hash == row.token_hash)
            .values(expires_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await session.commit()
        assert await user_service.resolve_session(session, token) is None
    await engine.dispose()
