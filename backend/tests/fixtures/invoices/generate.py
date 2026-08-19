"""Fixture üretici — `python tests/fixtures/invoices/generate.py`.

Türk e-arşiv faturalarının METİN DÜZENİNİ taklit eden bir PDF üretir. Gerçek bir
tedarikçi faturası DEĞİLDİR (bkz. README.md). Yalnızca fixture'ı yeniden üretmek
gerektiğinde çalıştırılır; `reportlab` dev bağımlılığıdır.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

OUT = Path(__file__).parent / "earsiv_fatura_ornek.pdf"

HEADER = [
    "KAHVE TEDARIK A.S.",
    "VKN: 1234567890  ADRES: Istanbul / Turkiye",
    "e-ARSIV FATURA",
    "Fatura No: KTA2026000000123",
    "Fatura Tarihi: 05.08.2026",
    "Sayin: MOKKA TEKNOLOJI A.S.",
    "",
    "Mal/Hizmet Aciklamasi            Miktar   Birim Fiyat   KDV %   Tutar",
    "-------------------------------------------------------------------",
]

LINES = [
    "Brezilya Cerrado Cekirdek Kahve 1kg   20 ADET   420,00   1   8.400,00",
    "Kolombiya Huila Cekirdek Kahve 1kg    10 ADET   510,00   1   5.100,00",
    "V60 Filtre Kagidi 100lu               50 ADET    45,00  20   2.250,00",
]

FOOTER = [
    "-------------------------------------------------------------------",
    "Ara Toplam: 15.750,00",
    "KDV Toplam: 585,00",
    "Genel Toplam: 15.750,00",
    "Yalniz onbesbinyediyuzelli TL",
]


def main() -> None:
    pdf = canvas.Canvas(str(OUT), pagesize=A4)
    pdf.setFont("Courier", 9)
    y = 800
    for row in [*HEADER, *LINES, *FOOTER]:
        pdf.drawString(40, y, row)
        y -= 14
    pdf.save()
    print(f"yazildi: {OUT}")


if __name__ == "__main__":
    main()
