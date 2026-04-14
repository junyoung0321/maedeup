from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel

from app.core.config import settings

# 모든 테이블 모델을 여기서 import해야 SQLModel.metadata에 등록됩니다
import app.models  # noqa: F401

_is_dev = settings.APP_ENV.lower() in {"development", "dev"}
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=_is_dev,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """DB 연결 확인. 테이블 생성은 alembic upgrade head가 담당합니다."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
