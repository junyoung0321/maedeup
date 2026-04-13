import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from alembic import context
from sqlmodel import SQLModel

# 모든 모델 import — autogenerate가 테이블 변경을 감지하려면 필수
import app.models  # noqa: F401

from app.core.config import settings

config = context.config

database_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
database_url = database_url.replace("asyncpg+postgresql://", "postgresql://", 1)

# alembic.ini의 sqlalchemy.url을 env 기반 sync URL로 덮어씀
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
