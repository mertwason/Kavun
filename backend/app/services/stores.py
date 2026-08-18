"""Mağaza ve credential servisi (spec §3.6, §5.1).

Credential'lar `store_credentials` tablosunda Fernet ile şifreli durur. Bu tabloda
`brand_id` yoktur (mağazanın çocuğudur), bu yüzden **her erişim mağaza üzerinden
çözülür**: brand-scope guard'ı `stores` üzerinde çalışır, credential'a ancak o
markanın mağazası üzerinden ulaşılır (KVN-03 bilinen sınırının kapatılması).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret, rotate_secret
from app.core.logging import get_logger
from app.models.enums import ChannelCode
from app.models.identity import Channel, Store, StoreCredential

log = get_logger("services.stores")


class StoreNotFoundError(LookupError):
    """Mağaza bulunamadı (ya da aktif markaya ait değil)."""


class CredentialNotFoundError(LookupError):
    """Mağazanın kayıtlı credential'ı yok."""


class MissingCredentialFieldsError(ValueError):
    """Kanalın zorunlu alanları eksik."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Eksik alanlar: {', '.join(missing)}")


def get_store(session: Session, store_id: uuid.UUID) -> Store:
    """Mağazayı getirir. Brand-scope guard'ı karşı markanın mağazasını görünmez kılar."""
    store = session.scalar(select(Store).where(Store.id == store_id))
    if store is None:
        raise StoreNotFoundError(str(store_id))
    return store


def list_stores(session: Session) -> list[tuple[Store, Channel, StoreCredential | None]]:
    """Aktif markanın mağazaları + kanal + credential durumu."""
    rows = session.execute(
        select(Store, Channel, StoreCredential)
        .join(Channel, Channel.id == Store.channel_id)
        .outerjoin(StoreCredential, StoreCredential.store_id == Store.id)
        .order_by(Store.name)
    ).all()
    return [(row[0], row[1], row[2]) for row in rows]


def get_channel(session: Session, code: ChannelCode) -> Channel:
    """Kanal kaydını koda göre getirir."""
    channel = session.scalar(select(Channel).where(Channel.code == code))
    if channel is None:
        raise LookupError(f"Kanal tanımlı değil: {code}")
    return channel


def get_channel_code(session: Session, store: Store) -> ChannelCode:
    """Mağazanın kanal kodu."""
    code = session.scalar(select(Channel.code).where(Channel.id == store.channel_id))
    if code is None:
        raise LookupError(f"Mağazanın kanalı bulunamadı: {store.id}")
    return code


def _credential_for(session: Session, store: Store) -> StoreCredential | None:
    """Mağazanın credential kaydı (varsa)."""
    return session.scalar(select(StoreCredential).where(StoreCredential.store_id == store.id))


def credential_status(session: Session, store: Store) -> StoreCredential | None:
    """Credential kaydını döndürür — çağıran yalnızca varlığını/tarihlerini kullanır."""
    return _credential_for(session, store)


def save_credentials(
    session: Session,
    store: Store,
    values: dict[str, str],
    required_fields: tuple[str, ...],
) -> StoreCredential:
    """Credential'ı şifreleyip kaydeder (varsa üzerine yazar, `rotated_at` işaretlenir)."""
    missing = [field for field in required_fields if not values.get(field, "").strip()]
    if missing:
        raise MissingCredentialFieldsError(missing)

    encrypted = encrypt_secret(dict(values))
    existing = _credential_for(session, store)
    if existing is None:
        credential = StoreCredential(store_id=store.id, encrypted_payload=encrypted)
        session.add(credential)
    else:
        existing.encrypted_payload = encrypted
        existing.rotated_at = datetime.now(UTC)
        credential = existing
    session.flush()

    # Log yalnızca hangi alanların yazıldığını söyler; değerler asla yazılmaz.
    log.info(
        "store.credentials.saved",
        store_id=str(store.id),
        channel_id=str(store.channel_id),
        fields=sorted(values),
    )
    return credential


def load_credentials(session: Session, store: Store) -> dict[str, Any]:
    """Credential'ı çözer. Yalnızca connector katmanı çağırır (KVN-05)."""
    credential = _credential_for(session, store)
    if credential is None:
        raise CredentialNotFoundError(str(store.id))
    return decrypt_secret(credential.encrypted_payload)


def delete_credentials(session: Session, store: Store) -> None:
    """Credential kaydını siler."""
    credential = _credential_for(session, store)
    if credential is None:
        raise CredentialNotFoundError(str(store.id))
    session.delete(credential)
    session.flush()
    log.info("store.credentials.deleted", store_id=str(store.id))


def rotate_credentials(session: Session, store: Store) -> StoreCredential:
    """Kaydı en güncel anahtarla yeniden şifreler (anahtar rotasyonu, spec §3.6)."""
    credential = _credential_for(session, store)
    if credential is None:
        raise CredentialNotFoundError(str(store.id))
    credential.encrypted_payload = rotate_secret(credential.encrypted_payload)
    credential.rotated_at = datetime.now(UTC)
    session.flush()
    log.info("store.credentials.rotated", store_id=str(store.id))
    return credential
