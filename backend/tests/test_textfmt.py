"""Uyarı metinlerindeki sayı biçimlendirmesi (`app/core/textfmt.py`).

Ham `Decimal`'i mesaja gömmek Türkçe okuyan için yanıltıcıydı: `-14.0000` "eksi on dört
bin" gibi okunuyordu. Bu testler o hatanın geri gelmesini engeller.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core import textfmt

D = Decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (D("14.0000"), "14"),
        (D("-14.0000"), "−14"),
        (D("1234567"), "1.234.567"),
        (D("1234.5600"), "1.234,56"),
        (D("0"), "0"),
        (D("-0.004"), "0"),  # yuvarlanınca sıfır: eksi işareti asılı kalmaz
    ],
)
def test_number_uses_turkish_separators(value: Decimal, expected: str) -> None:
    """Binlik `.`, ondalık `,`; negatifte gerçek eksi işareti."""
    assert textfmt.number(value) == expected


def test_money_keeps_two_decimals_and_leading_symbol() -> None:
    """Tutar sembol başta yazılır ve kuruş hanesi düşmez (handoff)."""
    assert textfmt.money(D("2400")) == "₺2.400,00"
    assert textfmt.money(D("-516")) == "−₺516,00"


def test_percent_puts_the_sign_before_the_symbol() -> None:
    """Türkçe'de yüzde işareti sayının başındadır; eksi onun da önünde durur."""
    assert textfmt.percent(D("12.35")) == "%12,4"
    assert textfmt.percent(D("-8.40")) == "−%8,4"


def test_negative_stock_message_is_readable() -> None:
    """Regresyon: `-14.0000` "eksi on dört bin" gibi okunuyordu."""
    assert f"stoğu {textfmt.number(D('-14.0000'))} adede düştü" == "stoğu −14 adede düştü"
