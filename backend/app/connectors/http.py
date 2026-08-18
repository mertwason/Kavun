"""Connector'lar için ortak HTTP istemcisi.

İki kritik davranış burada toplanır:

1. **Para hassasiyeti:** JSON gövdesi `parse_float=Decimal` ile ayrıştırılır. `httpx`in
   varsayılan `.json()` çağrısı tutarları `float`a çevirirdi; kuruş kaybı burada başlar
   (CLAUDE.md §1).
2. **Hız sınırı ve yeniden deneme:** 429 ve 5xx'te üstel geri çekilme + jitter; `Retry-After`
   başlığı varsa ona uyulur. İstekler arasında kanalın dakikalık limitine göre pas verilir.
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from app.connectors.base import AuthenticationError, ConnectorError, RateLimitError
from app.core.logging import get_logger

log = get_logger("connectors.http")

RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def parse_json(text: str) -> Any:
    """Gövdeyi ayrıştırır; ondalıklar `Decimal` olur (para kaybı olmaz)."""
    return json.loads(text, parse_float=Decimal)


@dataclass
class RetryPolicy:
    """Yeniden deneme davranışı."""

    max_attempts: int = 5
    base_delay: Decimal = Decimal("0.5")
    max_delay: Decimal = Decimal("30")

    def delay_for(self, attempt: int, *, jitter: Decimal) -> Decimal:
        """Üstel geri çekilme + jitter (saniye)."""
        raw: Decimal = self.base_delay * Decimal(2) ** (attempt - 1)
        capped: Decimal = raw if raw < self.max_delay else self.max_delay
        return capped + jitter


class ApiClient:
    """İnce httpx sarmalayıcısı: yeniden deneme, hız sınırı ve Decimal ayrıştırma."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str],
        auth: tuple[str, str] | None = None,
        timeout: int = 30,
        requests_per_minute: int = 600,
        retry: RetryPolicy | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._retry = retry or RetryPolicy()
        self._min_interval = Decimal(60) / Decimal(max(requests_per_minute, 1))
        self._last_request_at: float | None = None  # allow-float: monotonik saat, para değil
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url, headers=headers, auth=auth, timeout=timeout
        )

    async def __aenter__(self) -> ApiClient:
        """Async context manager desteği."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """İstemciyi kapatır (dışarıdan verilmişse dokunmaz)."""
        await self.aclose()

    async def aclose(self) -> None:
        """Bağlantıları kapatır."""
        if self._owns_client:
            await self._client.aclose()

    async def _pace(self) -> None:
        """Kanalın dakikalık limitini aşmamak için istekler arasında bekler."""
        loop = asyncio.get_running_loop()
        now = loop.time()
        if self._last_request_at is not None:
            elapsed = Decimal(str(now - self._last_request_at))
            if elapsed < self._min_interval:
                wait = self._min_interval - elapsed
                await asyncio.sleep(float(wait))  # allow-float: uyku süresi, para değil
        self._last_request_at = loop.time()

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET isteği atar ve JSON gövdesini `Decimal` hassasiyetiyle döndürür."""
        attempt = 0
        while True:
            attempt += 1
            await self._pace()
            try:
                response = await self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt >= self._retry.max_attempts:
                    raise ConnectorError(f"Bağlantı kurulamadı: {type(exc).__name__}") from exc
                await self._sleep_before_retry(attempt, None)
                continue

            if response.status_code in (401, 403):
                # Credential içeriği ASLA loglanmaz/mesaja konmaz (CLAUDE.md §2).
                raise AuthenticationError(
                    f"Kanal kimlik doğrulaması başarısız (HTTP {response.status_code})"
                )

            if response.status_code in RETRY_STATUS_CODES:
                if attempt >= self._retry.max_attempts:
                    if response.status_code == 429:
                        raise RateLimitError("Hız sınırı aşıldı, denemeler tükendi")
                    raise ConnectorError(f"Kanal hatası: HTTP {response.status_code}")
                log.warning(
                    "connector.retry",
                    status=response.status_code,
                    attempt=attempt,
                    path=path,
                )
                await self._sleep_before_retry(attempt, response.headers.get("Retry-After"))
                continue

            if response.status_code >= 400:
                raise ConnectorError(f"Kanal hatası: HTTP {response.status_code}")

            return parse_json(response.text)

    async def _sleep_before_retry(self, attempt: int, retry_after: str | None) -> None:
        """`Retry-After` varsa ona, yoksa üstel geri çekilmeye uyar."""
        if retry_after:
            try:
                seconds = Decimal(retry_after)
                await asyncio.sleep(float(seconds))  # allow-float: uyku süresi, para değil
                return
            except (ValueError, ArithmeticError):
                pass
        jitter = Decimal(str(random.random())) / 2
        delay = self._retry.delay_for(attempt, jitter=jitter)
        await asyncio.sleep(float(delay))  # allow-float: asyncio.sleep saniye ister, para değil
