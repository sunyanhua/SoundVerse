"""
数据库会话管理
"""
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base

from config import settings

# 创建基类
Base = declarative_base()

# 创建引擎
engine: AsyncEngine = None
async_session_maker: async_sessionmaker[AsyncSession] = None


async def init_db() -> None:
    """
    初始化数据库连接
    """
    global engine, async_session_maker

    if engine is not None:
        return

    # 创建异步引擎
    engine = create_async_engine(
        settings.get_database_url(),
        echo=settings.DATABASE_ECHO,
        pool_size=settings.DATABASE_POOL_SIZE,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,
        future=True,
    )

    # 创建异步会话工厂
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # 创建表（开发环境使用）
    if settings.is_development:
        async with engine.begin() as conn:
            # 在开发环境中创建所有表
            await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话依赖
    """
    if async_session_maker is None:
        await init_db()

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """
    关闭数据库连接
    """
    global engine

    if engine is not None:
        await engine.dispose()
        engine = None