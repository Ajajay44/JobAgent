"""
Async SQLAlchemy database session for the agent service.

Why async?
FastAPI runs on an async event loop. If we used synchronous SQLAlchemy,
every DB call would block the entire event loop — meaning no other requests
could be handled while we wait for the database. Async SQLAlchemy with
asyncpg keeps the event loop free during I/O.
"""
import logging
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from config import settings

logger = logging.getLogger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.async_database_url,
    echo=False,          # set to True to see all SQL in logs (dev only)
    pool_pre_ping=True,  # test connection before using it from the pool
    pool_size=5,         # max persistent connections
    max_overflow=10,     # max temporary connections above pool_size
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base class for ORM models ─────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db():
    """
    Yields an async database session.
    Use as a FastAPI dependency: `db: AsyncSession = Depends(get_db)`
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Health check ──────────────────────────────────────────────────────────────
async def check_db_connection() -> bool:
    """
    Verify database connectivity.
    Used by the /health endpoint.
    """
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        return False
