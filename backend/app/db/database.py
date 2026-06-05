"""
数据库连接管理
"""
import os
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _greenlet_available() -> tuple[bool, str]:
    if _is_truthy_env("QINGCAO_DB_FORCE_SYNC"):
        return False, "QINGCAO_DB_FORCE_SYNC=1"

    try:
        from greenlet import _greenlet  # noqa: F401
    except Exception as exc:
        return False, str(exc)
    return True, ""


def _to_sync_database_url(url: str) -> str:
    """把默认 async sqlite URL 转成同步 sqlite URL，供 greenlet 不可用时兜底。"""
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def _sync_fallback_supported(url: str) -> bool:
    return url.startswith(("sqlite+aiosqlite://", "sqlite://"))


_GREENLET_READY, _GREENLET_ERROR = _greenlet_available()
_SYNC_DATABASE_URL = _to_sync_database_url(settings.DATABASE_URL)

if _GREENLET_READY:
    # 创建异步引擎
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        pool_pre_ping=True,
    )

    # 创建异步会话工厂
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    # Windows 上 greenlet 的二进制扩展损坏/缺 DLL 时，SQLAlchemy async bridge
    # 会在启动 init_db 阶段直接失败。项目默认数据库是 SQLite，这里用同步
    # SQLAlchemy 会话提供一个兼容 async 调用形态的兜底，让服务仍可启动。
    if _sync_fallback_supported(settings.DATABASE_URL):
        engine = create_engine(
            _SYNC_DATABASE_URL,
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
        )
        AsyncSessionLocal = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    else:
        engine = None
        AsyncSessionLocal = None

# 声明基类
Base = declarative_base()


class SyncSessionAdapter:
    """把同步 SQLAlchemy Session 包成项目现有代码使用的 async 形态。"""

    def __init__(self, session):
        self._session = session

    def add(self, obj):
        return self._session.add(obj)

    async def flush(self):
        self._session.flush()

    async def refresh(self, obj):
        self._session.refresh(obj)

    async def execute(self, statement, *args, **kwargs):
        return self._session.execute(statement, *args, **kwargs)

    async def delete(self, obj):
        self._session.delete(obj)

    async def commit(self):
        self._session.commit()

    async def rollback(self):
        self._session.rollback()

    async def close(self):
        self._session.close()


async def init_db():
    """初始化数据库"""
    if _GREENLET_READY:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    if not _sync_fallback_supported(settings.DATABASE_URL) or engine is None:
        raise RuntimeError(
            "SQLAlchemy async database requires greenlet, but greenlet is not usable: "
            f"{_GREENLET_ERROR}"
        )

    from loguru import logger

    logger.warning(
        "greenlet 不可用，数据库切换到 SQLite 同步兼容模式: {}",
        _GREENLET_ERROR,
    )
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)


async def close_db():
    """关闭数据库连接"""
    if _GREENLET_READY:
        await engine.dispose()
    else:
        if engine is not None:
            engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖"""
    if _GREENLET_READY:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
        return

    if AsyncSessionLocal is None:
        raise RuntimeError(
            "SQLAlchemy async database requires greenlet, but greenlet is not usable: "
            f"{_GREENLET_ERROR}"
        )

    session = SyncSessionAdapter(AsyncSessionLocal())
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
