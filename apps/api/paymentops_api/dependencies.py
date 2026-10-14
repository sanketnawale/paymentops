"""Dependency health probes used by /ready.

The set of probed dependencies is driven by ``settings.ready_checks``. A dependency is
only considered "required" when it is explicitly listed, so the app can run with reduced
dependencies (dev/test) without falsely reporting errors.
"""

from __future__ import annotations

from dataclasses import dataclass

from paymentops_api.db.base import Database
from paymentops_api.logging import get_logger
from paymentops_api.settings import Settings

logger = get_logger("paymentops.dependencies")


@dataclass(frozen=True)
class Dependency:
    name: str
    ok: bool
    detail: str


class RedisProbeUnavailable(Exception):
    pass


async def _check_database(db: Database) -> Dependency:
    try:
        await db.ping()
        return Dependency("database", True, "ok")
    except Exception as exc:  # noqa: BLE001 - report status without leaking internals
        logger.warning("dependency_database_unhealthy", error_type=type(exc).__name__)
        return Dependency("database", False, "unavailable")


async def _check_redis(settings: Settings) -> Dependency:
    import redis.asyncio as aioredis

    client = aioredis.from_url(
        settings.celery_broker_url,
        password=settings.redis_password or None,
        decode_responses=True,
        socket_connect_timeout=2,
    )
    try:
        pong = await client.ping()
        return Dependency("redis", bool(pong), "ok")
    except Exception as exc:  # noqa: BLE001
        logger.warning("dependency_redis_unhealthy", error_type=type(exc).__name__)
        return Dependency("redis", False, "unavailable")
    finally:
        # redis-py 8 exposes aclose(); older typed stubs only know close().
        await client.aclose()  # type: ignore[attr-defined]


async def check_dependencies(settings: Settings, db: Database) -> list[Dependency]:
    results: list[Dependency] = []
    for name in settings.ready_checks:
        if name == "database":
            results.append(await _check_database(db))
        elif name == "redis":
            results.append(await _check_redis(settings))
        else:
            results.append(Dependency(name, True, "skipped"))
    return results


def readiness_body(deps: list[Dependency]) -> dict[str, object]:
    ready = all(d.ok for d in deps)
    return {
        "status": "ready" if ready else "not_ready",
        "checks": [{"name": d.name, "ok": d.ok, "detail": d.detail} for d in deps],
    }
