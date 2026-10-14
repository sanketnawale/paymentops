"""Alembic environment for PaymentOps.

Resolves the database URL from application settings (never from this file) and uses the
SQLAlchemy 2 declarative metadata so autogenerate reflects the ORM models.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..", "..")
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from paymentops_api.db.models import Base  # noqa: E402  (needs sys.path)
from paymentops_api.settings import get_settings  # noqa: E402

target_metadata = Base.metadata


def _database_url() -> str:
    # Prefer the URL passed on the command line/tests, otherwise resolved settings.
    return config.get_main_option("sqlalchemy.url") or get_settings().sqlalchemy_dsn()


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
