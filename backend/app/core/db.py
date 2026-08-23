import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, DateTime, types
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


class GUID(types.TypeDecorator):
    """Cross-database UUID: CHAR(36) compatible with both PostgreSQL and SQLite."""
    impl = types.CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(str(value)) if value is not None else None


# Engine setup with seamless SQLite fallback if PostgreSQL is not active
db_url = settings.POSTGRES_URL
try:
    if db_url.startswith("sqlite"):
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
        with engine.connect() as test_conn:
            pass
except Exception:
    # Seamless fallback to local SQLite database for development
    sqlite_url = "sqlite:///./ipte_dev.db"
    engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_postgres_connection() -> dict:
    # Test connection to configured POSTGRES_URL
    if settings.POSTGRES_URL.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                return {"status": "healthy", "engine": "sqlite", "url": str(engine.url)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # If POSTGRES_URL is configured, test PostgreSQL connection directly
    try:
        pg_engine = create_engine(settings.POSTGRES_URL, pool_pre_ping=True, connect_args={"connect_timeout": 2})
        with pg_engine.connect() as conn:
            return {"status": "healthy", "engine": "postgresql", "url": settings.POSTGRES_URL.split("@")[-1] if "@" in settings.POSTGRES_URL else settings.POSTGRES_URL}
    except Exception as e:
        # If engine fell back to SQLite, indicate dev fallback
        if engine.name == "sqlite":
            return {"status": "unhealthy", "engine": "sqlite_fallback", "error": f"PostgreSQL server unreachable: {str(e)}"}
        return {"status": "unhealthy", "error": str(e)}


