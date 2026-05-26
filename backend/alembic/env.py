import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from sqlmodel import SQLModel
import app.models  # noqa
target_metadata = SQLModel.metadata


def normalize_database_url(url: str | None, *, async_mode: bool) -> str | None:
    if not url:
        return url
    if async_mode:
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql+psycopg2://"):
            return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    else:
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("postgresql+psycopg2://"):
            return url.replace("postgresql+psycopg2://", "postgresql://", 1)
    return url


def _is_sqlite_url(url: str | None) -> bool:
    """sqlite는 async driver(aiosqlite)가 없으면 동기로 처리해야 한다.

    test_user_consent_default.py 등 sqlite 파일 기반 테스트는 `sqlite:///...`
    URL을 그대로 넘기는데, 이 경우 create_async_engine은 pysqlite를 async로 쓰지
    못해 InvalidRequestError를 던진다. 동기 경로로 분기한다.
    """
    if not url:
        return False
    return url.startswith("sqlite://") or url.startswith("sqlite+pysqlite://")


def get_url(*, async_mode: bool):
    url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    return normalize_database_url(url, async_mode=async_mode)


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = create_async_engine(get_url(async_mode=True), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_sync_migrations() -> None:
    """sqlite(pysqlite) 등 비동기 드라이버가 없는 환경을 위한 동기 경로."""
    connectable = create_engine(get_url(async_mode=False), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


def run_migrations_offline():
    url = get_url(async_mode=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # postgres(asyncpg) → 비동기 엔진, sqlite/기타 동기 드라이버 → 동기 엔진.
    sync_url = get_url(async_mode=False)
    if _is_sqlite_url(sync_url):
        run_sync_migrations()
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
