from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.db import normalize_database_url, postgres_connect_args
from backend.app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
url = os.getenv("DATABASE_URL")
if not url:
    raise RuntimeError("Set DATABASE_URL before running Alembic")
if url.startswith("sqlite"):
    raise RuntimeError("Migrations are intended for Neon/PostgreSQL; SQLite is test-only")
config.set_main_option("sqlalchemy.url", normalize_database_url(url).replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool,
                                     pool_pre_ping=True,
                                     connect_args=postgres_connect_args(url))
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
