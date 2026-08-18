"""Uygulama ayarları — tüm konfigürasyon env'den okunur (12-factor)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Kavun servis ayarları.

    Secret'lar (DB şifresi, `KAVUN_ENCRYPTION_KEY`, store credential'ları) asla
    loglanmaz; bkz. `app.core.logging.configure_logging`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Kavun"
    environment: Literal["local", "ci", "staging", "production"] = "local"
    debug: bool = False

    database_url: str = "postgresql+psycopg://kavun:kavun@localhost:5432/kavun"
    redis_url: str = "redis://localhost:6379/0"

    # Fernet anahtarı — store_credentials şifrelemesi (spec §3.6). KVN-04'te kullanılır.
    kavun_encryption_key: str | None = Field(default=None, repr=False)

    # JWT (KVN-03)
    jwt_secret: str = Field(default="dev-only-degistir", repr=False)
    # ops.mokka SSO token'larını doğrulamak için paylaşılan secret (spec §8).
    ops_sso_secret: str | None = Field(default=None, repr=False)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Süreç ömrü boyunca tek Settings örneği."""
    return Settings()
