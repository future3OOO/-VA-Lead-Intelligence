from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import Settings

settings = Settings()
engine_kwargs: dict[str, Any] = {"echo": False, "future": True}
if settings.environment == "test":
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.database_url, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
