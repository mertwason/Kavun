"""İstek bağlamı: tenant + aktif marka (spec §3.1, §3A.1).

Bağlam `contextvars` ile taşınır; böylece DB katmanı (brand-scope guard'ı) hangi
markanın evreninde çalıştığını FastAPI'ye bağımlı olmadan bilir — worker ve CLI de
aynı mekanizmayı kullanır.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # models → core.db → core.scoping → core.context döngüsünü kırmak için
    from app.models.enums import UserRole


@dataclass(frozen=True)
class RequestContext:
    """Bir isteğin (ya da job'ın) kim/hangi marka bağlamı."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    brand_slug: str | None = None
    role: UserRole | None = None
    # Markalar arası konsolide görünüm — brand filtresini bypass eder, audit'e yazılır.
    holding_view: bool = False
    # Sistem işleri (seed, replay, sync): marka filtresi aranmaz.
    system: bool = False

    @property
    def scoped(self) -> bool:
        """Marka filtresi zorunlu mu (holding/system dışındaki her durum)."""
        return not (self.holding_view or self.system)


_context: ContextVar[RequestContext | None] = ContextVar("kavun_request_context", default=None)


def current_context() -> RequestContext | None:
    """Aktif bağlam; yoksa None."""
    return _context.get()


def require_context() -> RequestContext:
    """Aktif bağlamı döndürür; yoksa hata verir."""
    context = _context.get()
    if context is None:
        raise LookupError("İstek bağlamı yok — brand-scope guard'ı bağlam olmadan çalışmaz")
    return context


@contextmanager
def use_context(context: RequestContext) -> Iterator[RequestContext]:
    """Verilen bağlamı blok boyunca aktif kılar."""
    token = _context.set(context)
    try:
        yield context
    finally:
        _context.reset(token)


@contextmanager
def brand_scope(
    tenant_id: uuid.UUID,
    brand_id: uuid.UUID,
    *,
    brand_slug: str | None = None,
    user_id: uuid.UUID | None = None,
    role: UserRole | None = None,
) -> Iterator[RequestContext]:
    """Tek markanın evreni — sorgular otomatik olarak bu markaya kısıtlanır."""
    with use_context(
        RequestContext(
            tenant_id=tenant_id,
            user_id=user_id,
            brand_id=brand_id,
            brand_slug=brand_slug,
            role=role,
        )
    ) as context:
        yield context


@contextmanager
def holding_scope(
    tenant_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> Iterator[RequestContext]:
    """Holding görünümü — markalar arası okuma (spec §3A.3). Kullanımı audit'e yazılır."""
    with use_context(
        RequestContext(tenant_id=tenant_id, user_id=user_id, holding_view=True)
    ) as context:
        yield context


@contextmanager
def system_scope(tenant_id: uuid.UUID | None = None) -> Iterator[RequestContext]:
    """Sistem işleri (seed, migration, replay, sync) — marka filtresi aranmaz.

    Kullanıcı isteklerinde ASLA kullanılmaz; yalnızca arka plan/CLI kodunda.
    """
    context = current_context()
    if context is not None:
        yield from _yield_replaced(context)
        return
    with use_context(RequestContext(tenant_id=tenant_id or uuid.UUID(int=0), system=True)) as fresh:
        yield fresh


def _yield_replaced(context: RequestContext) -> Iterator[RequestContext]:
    """Var olan bağlamı sistem moduna çevirip geri alır."""
    with use_context(replace(context, system=True)) as system_context:
        yield system_context
