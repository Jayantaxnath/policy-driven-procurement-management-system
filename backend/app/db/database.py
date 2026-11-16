from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

# Primary sync engine (sqlite3 is built into Python, or psycopg2 for PostgreSQL)
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL_SYNC else {}
)
SyncSessionLocal = sessionmaker(sync_engine, expire_on_commit=False)

# Optional async engine if asyncpg is configured
async_engine = None
AsyncSessionLocal = None

if "postgresql+asyncpg" in settings.DATABASE_URL:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    except ImportError:
        pass

class Base(DeclarativeBase):
    pass

def get_db():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()
