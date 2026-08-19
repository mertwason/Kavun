"""Kullanıcıya gösterilen metinlerde sayı biçimlendirme (Türkçe).

Uyarı mesajları ekranda **olduğu gibi** basılıyor; içine ham `Decimal` gömmek yanıltıcı:
`-14.0000` Türkçe okuyan için "eksi on dört bin"dir, `1234.5600 TL` ise binlik ayırıcısı
olmayan bir tutar. Bu yüzden mesaja giren her sayı buradan geçer.

Yuvarlama yalnızca **gösterim** için yapılır (CLAUDE.md §1); hesaplar `Decimal` kalır.
"""

from __future__ import annotations

from decimal import Decimal

MINUS = "−"
"""Gerçek eksi işareti — tasarım handoff'u negatif sayılarda tire kullanmıyor."""


def _group(digits: str) -> str:
    """Binlik ayırıcı (nokta) ekler: `1234567` → `1.234.567`."""
    out = []
    for index, char in enumerate(reversed(digits)):
        if index and index % 3 == 0:
            out.append(".")
        out.append(char)
    return "".join(reversed(out))


def number(value: Decimal | int, *, decimals: int = 2, trim: bool = True) -> str:
    """Türkçe sayı: binlik `.`, ondalık `,`, negatifte gerçek eksi işareti.

    `trim=True` ise anlamsız sondaki sıfırlar atılır (`14,0000` → `14`); tutarlarda
    `trim=False` ile iki hane sabit tutulur.
    """
    quantized = Decimal(value).quantize(Decimal(1).scaleb(-decimals))
    negative = quantized < 0
    text = format(abs(quantized), "f")
    whole, _, fraction = text.partition(".")
    if trim:
        fraction = fraction.rstrip("0")
    formatted = _group(whole) + (f",{fraction}" if fraction else "")
    return f"{MINUS}{formatted}" if negative else formatted


def money(value: Decimal | int) -> str:
    """Tutar: `₺1.234,56` — sembol başta, negatifte gerçek eksi (`{MINUS}₺12,00`)."""
    text = number(value, decimals=2, trim=False)
    if text.startswith(MINUS):
        return f"{MINUS}₺{text[1:]}"
    return f"₺{text}"


def percent(value: Decimal | int, *, decimals: int = 1) -> str:
    """Yüzde: `%12,4` — Türkçe'de işaret sayının başında durur."""
    text = number(value, decimals=decimals, trim=True)
    if text.startswith(MINUS):
        return f"{MINUS}%{text[1:]}"
    return f"%{text}"
