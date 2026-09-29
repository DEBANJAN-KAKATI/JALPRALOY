from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def create_all() -> None:
    """Dev convenience. Use Alembic migrations once the schema settles:
    alembic init backend/app/db/migrations"""
    from app.db.models import Base

    Base.metadata.create_all(engine)
