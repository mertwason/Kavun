"""KVN-04: credential kasası — Fernet şifreleme ve anahtar rotasyonu (spec §3.6)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.core import crypto
from app.core.config import Settings, get_settings

SECRET = {"api_key": "AKIA-GIZLI", "api_secret": "cok-gizli-secret", "seller_id": "12345"}


@pytest.fixture
def vault_key(monkeypatch: Any) -> Iterator[str]:
    """Testler için tek anahtarlı kasa."""
    key = crypto.generate_key()
    patched = Settings(**{**get_settings().model_dump(), "kavun_encryption_key": key})
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: patched)
    yield key


def _use_keys(monkeypatch: Any, *keys: str) -> None:
    patched = Settings(**{**get_settings().model_dump(), "kavun_encryption_key": ",".join(keys)})
    monkeypatch.setattr("app.core.crypto.get_settings", lambda: patched)


def test_roundtrip_preserves_payload(vault_key: str) -> None:
    """Şifrele → çöz zinciri içeriği birebir korur."""
    assert crypto.decrypt_secret(crypto.encrypt_secret(SECRET)) == SECRET


def test_ciphertext_does_not_contain_plaintext(vault_key: str) -> None:
    """Şifreli kayıtta düz metin görünmez — DB dökümü sızıntı olmaz."""
    token = crypto.encrypt_secret(SECRET)
    assert b"AKIA-GIZLI" not in token
    assert b"cok-gizli-secret" not in token


def test_same_payload_produces_different_ciphertext(vault_key: str) -> None:
    """Fernet her şifrelemede farklı IV kullanır — aynı secret aynı kaydı üretmez."""
    assert crypto.encrypt_secret(SECRET) != crypto.encrypt_secret(SECRET)


def test_missing_key_fails_closed(monkeypatch: Any) -> None:
    """Anahtar yoksa şifreleme denenmez; sessizce düz metin yazılmaz."""
    _use_keys(monkeypatch, "")
    assert crypto.is_available() is False
    with pytest.raises(crypto.VaultUnavailableError):
        crypto.encrypt_secret(SECRET)


def test_invalid_key_fails_closed(monkeypatch: Any) -> None:
    """Geçersiz biçimli anahtar da kasayı kapatır."""
    _use_keys(monkeypatch, "bu-gecerli-bir-fernet-anahtari-degil")
    assert crypto.is_available() is False


def test_foreign_key_cannot_decrypt(monkeypatch: Any) -> None:
    """Başka anahtarla şifrelenmiş kayıt çözülemez ve hata içerik sızdırmaz."""
    _use_keys(monkeypatch, crypto.generate_key())
    token = crypto.encrypt_secret(SECRET)

    _use_keys(monkeypatch, crypto.generate_key())
    with pytest.raises(crypto.VaultDecryptionError) as exc_info:
        crypto.decrypt_secret(token)
    assert "AKIA-GIZLI" not in str(exc_info.value)


def test_key_rotation_keeps_old_records_readable(monkeypatch: Any) -> None:
    """Yeni anahtar eklenince eski kayıtlar okunmaya devam eder (spec §3.6)."""
    old_key = crypto.generate_key()
    _use_keys(monkeypatch, old_key)
    token = crypto.encrypt_secret(SECRET)

    new_key = crypto.generate_key()
    _use_keys(monkeypatch, new_key, old_key)  # ilki şifreler, tümü çözer
    assert crypto.decrypt_secret(token) == SECRET

    rotated = crypto.rotate_secret(token)
    assert rotated != token
    assert crypto.decrypt_secret(rotated) == SECRET

    # Rotasyondan sonra eski anahtar listeden çıkarılabilir.
    _use_keys(monkeypatch, new_key)
    assert crypto.decrypt_secret(rotated) == SECRET
    with pytest.raises(crypto.VaultDecryptionError):
        crypto.decrypt_secret(token)


def test_generated_keys_are_unique_and_usable() -> None:
    """Üretilen anahtar geçerli bir Fernet anahtarıdır."""
    from cryptography.fernet import Fernet

    first, second = crypto.generate_key(), crypto.generate_key()
    assert first != second
    assert Fernet(first).decrypt(Fernet(first).encrypt(b"x")) == b"x"
