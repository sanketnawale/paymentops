"""Database migration tests.

Primary path: generate the migration SQL in offline mode (no DB required) to prove the
migration script is valid and produces sensible PostgreSQL DDL. When ``TEST_DATABASE_URL``
is set, additionally run ``upgrade head`` / ``downgrade base`` against a real database.

The real domain schema arrives in Week 2; this validates the Alembic foundation itself.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "apps" / "api"
ALEMBIC_INI = API_DIR / "alembic.ini"


def _alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    # Resolve script_location to an absolute path so cwd doesn't matter.
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", "")  # env.py resolves from settings if empty
    return cfg


def test_migration_offline_sql_generates():
    """Validates the migration script compiles and emits PostgreSQL DDL offline."""
    cfg = _alembic_config()
    # command.upgrade(sql=True) runs in offline mode; no DB connection is made.
    command.upgrade(cfg, "head", sql=True)


def test_migrations_are_consistent_offline():
    """Upgrade and downgrade heads both generate SQL without error."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head", sql=True)
    # Offline downgrade requires an explicit fromrev:torev range.
    command.downgrade(cfg, "head:base", sql=True)


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set; skipping live migration run",
)
def test_migration_roundtrip_live():
    """Runs upgrade head then downgrade base against a real Postgres if available."""
    url = os.environ["TEST_DATABASE_URL"]
    # Alembic's online env uses a synchronous engine, so use the psycopg2 driver.
    sync_url = url.replace("+asyncpg", "+psycopg2")
    cfg = _alembic_config()
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    # Restore the schema so later tests in the same database still have tables.
    command.upgrade(cfg, "head")
