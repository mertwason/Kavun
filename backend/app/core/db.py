"""Veritabanı oturum yönetimi. Şema/modeller KVN-02'de gelir."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

# Alembic autogenerate'in kararlı isimler üretmesi için (KVN-02).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Tüm ORM modellerinin ortak tabanı."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: istek başına bir DB oturumu."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database() -> dict[str, Any]:
    """Sağlık kontrolü için hafif bir DB probu."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - hata yolu entegrasyon testinde
        return {"ok": False, "error": type(exc).__name__}
    return {"ok": True}
