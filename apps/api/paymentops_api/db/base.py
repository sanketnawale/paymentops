"""SQLAlchemy 2 foundation for PaymentOps.

Provides the async engine, declarative base, and a session factory. In Week 1 we keep
models minimal (organizations + application metadata) — the real domain schema arrives
in Week 2. All schema changes must be performed via Alembic migrations (ADR-011 rule).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from paymentops_api.settings import Settings
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.async_sqlalchemy_dsn(),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Database:
    """Thin wrapper around engine + session factory for FastAPI dependency injection."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine = build_engine(settings)
        self.session_factory = build_session_factory(self.engine)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def ping(self) -> bool:
        """Verify database connectivity with a lightweight round trip."""
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def dispose(self) -> None:
        await self.engine.dispose()
