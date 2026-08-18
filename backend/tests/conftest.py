"""Ortak test fixture'ları.

DB testleri gerçek PostgreSQL'e karşı koşar (partition, NUMERIC hassasiyeti ve enum
davranışı SQLite'ta doğrulanamaz). Test veritabanı adı her zaman `_test` ile biter —
geliştirme veritabanının yanlışlıkla silinmesi mümkün değildir.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_database_url() -> URL:
    """Test veritabanı URL'i — adı `_test` ile bitmiyorsa bitirilir."""
    explicit = os.getenv("TEST_DATABASE_URL")
    url = make_url(explicit or get_settings().database_url)
    name = url.database or "kavun"
    if not name.endswith("_test"):
        name = f"{name}_test"
    return url.set(database=name)


def _create_database_if_missing(url: URL) -> None:
    """Test veritabanı yoksa oluşturur."""
    admin_url = url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    engine.dispose()


def _run_migrations(url: URL) -> None:
    """Şemayı migration'larla kurar — testler modelden değil migration'dan doğrulanır."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def db_url() -> URL:
    """Test veritabanı URL'i."""
    return _test_database_url()


@pytest.fixture(scope="session")
def db_engine(db_url: URL) -> Iterator[Engine]:
    """Migration'ları uygulanmış test veritabanına bağlı engine."""
    _create_database_if_missing(db_url)
    _run_migrations(db_url)
    engine = create_engine(db_url, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """İzole oturum: test sonunda her şey geri alınır (seed'lerin commit'i dahil)."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """DB'ye ihtiyaç duymayan uçlar için test istemcisi."""
    with TestClient(create_app()) as test_client:
        yield test_client
