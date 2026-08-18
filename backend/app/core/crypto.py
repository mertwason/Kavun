"""Credential kasası — Fernet ile şifreleme (spec §3.6).

Anahtar `KAVUN_ENCRYPTION_KEY` ortam değişkeninden gelir. Anahtar rotasyonu için
virgülle ayrılmış birden fazla anahtar verilebilir: **ilki** şifrelemede kullanılır,
tümü çözmede denenir. Böylece yeni anahtar eklendiğinde eski kayıtlar okunmaya devam
eder ve `rotate_secret` ile kademeli olarak yeni anahtara taşınır.

Kural: çözülmüş credential asla loglanmaz, asla API yanıtına konmaz (CLAUDE.md §2).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings


class VaultUnavailableError(RuntimeError):
    """Şifreleme anahtarı tanımlı değil — credential yazılamaz/okunamaz."""

    def __init__(self) -> None:
        super().__init__(
            "KAVUN_ENCRYPTION_KEY tanımlı değil; credential kasası kullanılamaz. "
            "Anahtar üret: python -m app.cli generate-key"
        )


class VaultDecryptionError(RuntimeError):
    """Şifreli içerik mevcut anahtarların hiçbiriyle çözülemedi."""

    def __init__(self) -> None:
        super().__init__(
            "Credential çözülemedi: anahtar değişmiş ya da kayıt bozulmuş olabilir. "
            "Eski anahtarı KAVUN_ENCRYPTION_KEY listesine ekleyin."
        )


def generate_key() -> str:
    """Yeni bir Fernet anahtarı üretir (base64, 32 bayt)."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def _fernet() -> MultiFernet:
    """Yapılandırılmış anahtarlardan MultiFernet kurar."""
    raw = (get_settings().kavun_encryption_key or "").strip()
    if not raw:
        raise VaultUnavailableError()
    keys = [part.strip() for part in raw.split(",") if part.strip()]
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except (ValueError, TypeError) as exc:
        raise VaultUnavailableError() from exc


def is_available() -> bool:
    """Kasa kullanılabilir mi (anahtar tanımlı ve geçerli mi)."""
    try:
        _fernet()
    except VaultUnavailableError:
        return False
    return True


def encrypt_secret(payload: dict[str, Any]) -> bytes:
    """Credential sözlüğünü şifreler."""
    plaintext = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return bytes(_fernet().encrypt(plaintext))


def decrypt_secret(token: bytes) -> dict[str, Any]:
    """Şifreli credential'ı çözer. Hata mesajı içeriği ASLA sızdırmaz."""
    try:
        plaintext = _fernet().decrypt(bytes(token))
    except InvalidToken as exc:
        raise VaultDecryptionError() from exc
    decoded: dict[str, Any] = json.loads(plaintext)
    return decoded


def rotate_secret(token: bytes) -> bytes:
    """Kaydı en güncel anahtarla yeniden şifreler (içerik değişmez)."""
    try:
        return bytes(_fernet().rotate(bytes(token)))
    except InvalidToken as exc:
        raise VaultDecryptionError() from exc
