"""Alembic ortamı — hedef metadata `app.core.db.Base` üzerinden çözülür."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  — modeller metadata'ya kaydolsun diye import edilir
from app.core.config import get_settings
from app.core.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL çağıran tarafından verilmişse (testler, `-x url=...`) korunur; yoksa ayarlardan gelir.
if not config.get_main_option("sqlalchemy.url", default=None):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """`raw_events` partition çocuklarını autogenerate karşılaştırmasından çıkarır.

    Partition'lar modelde tanımlı değildir (migration/job tarafından açılır); aksi
    halde `alembic check` her partition'ı "fazladan tablo" sanıp drift raporlar.
    """
    if type_ == "table" and name is not None and name.startswith("raw_events_"):
        return False
    if type_ == "index":
        table_name = getattr(getattr(obj, "table", None), "name", "")
        if table_name.startswith("raw_events_"):
            return False
    return True


def run_migrations_offline() -> None:
    """SQL üretir, DB'ye bağlanmaz."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Canlı bağlantı üzerinden migration uygular."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
