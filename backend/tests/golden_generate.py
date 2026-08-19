"""Golden dataset üreticisi — `python -m tests.golden_generate` (spec §11).

Girdiler burada elle yazılır; beklenen değerler **referans hesaptan** (motordan değil)
üretilir ve `tests/golden/orders.json` dosyasına donmuş literal olarak yazılır. Dosya
gözden geçirilip commit edilir; testler hem motoru hem referansı bu literallerle
karşılaştırır.

Bu betik testlerde koşmaz. Beklenen bir değeri değiştirmek insan kararıdır: dosyayı
yeniden üretmek, o kararı bilerek vermek demektir.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from tests.golden_reference import (
    GoldenCase,
    GoldenExchange,
    GoldenReturn,
    reference_profit,
    to_kurus,
)

D = Decimal
OUTPUT = Path(__file__).parent / "golden" / "orders.json"

# 20 satır: KDV %1 ve %20, iade (stoğa dönen/hurda), değişim, kampanya, ceza, iptal,
# maliyeti/komisyonu bilinmeyen satır, negatif marj, tek adet ve çok adetli sepetler.
CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        "GOLD-01",
        "Standart satış: 2 adet, KDV %20, komisyon %20 — dosyadaki çözümlü örnek",
        line_gross=D("2000.00"),
        qty=2,
        vat_percent=D("20"),
        unit_cost_net=D("600.00"),
        commission_rate=D("0.20"),
        cargo_cost=D("60.00"),
        service_fee=D("12.00"),
    ),
    GoldenCase(
        "GOLD-02",
        "Gıda KDV %1: kahve çekirdeği, düşük sepet",
        line_gross=D("389.00"),
        qty=1,
        vat_percent=D("1"),
        unit_cost_net=D("185.00"),
        commission_rate=D("0.145"),
        cargo_cost=D("51.25"),
        service_fee=D("8.99"),
    ),
    GoldenCase(
        "GOLD-03",
        "Negatif marj: kargo + komisyon küçük sepeti eritiyor",
        line_gross=D("69.00"),
        qty=1,
        vat_percent=D("1"),
        unit_cost_net=D("48.00"),
        commission_rate=D("0.165"),
        cargo_cost=D("51.25"),
        service_fee=D("8.99"),
    ),
    GoldenCase(
        "GOLD-04",
        "Tam iade, mal stoğa döndü: gelir de komisyon da geri çevrilir, kargo kalır",
        line_gross=D("1200.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("500.00"),
        commission_rate=D("0.21"),
        cargo_cost=D("64.50"),
        service_fee=D("8.99"),
        returns=(GoldenReturn(qty=1, return_cargo_cost=D("64.50"), restocked=True),),
    ),
    GoldenCase(
        "GOLD-05",
        "Tam iade, mal hurda: o adedin maliyeti zarar olarak kalır (§12C.4)",
        line_gross=D("1200.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("500.00"),
        commission_rate=D("0.21"),
        cargo_cost=D("64.50"),
        service_fee=D("8.99"),
        returns=(GoldenReturn(qty=1, return_cargo_cost=D("64.50"), restocked=False),),
    ),
    GoldenCase(
        "GOLD-06",
        "Kısmi iade: 3 adetten 1'i döndü",
        line_gross=D("3600.00"),
        qty=3,
        vat_percent=D("20"),
        unit_cost_net=D("500.00"),
        commission_rate=D("0.21"),
        cargo_cost=D("96.00"),
        service_fee=D("8.99"),
        returns=(GoldenReturn(qty=1, return_cargo_cost=D("64.50"), restocked=True),),
    ),
    GoldenCase(
        "GOLD-07",
        "Değişim: müşteri parayı geri almaz, iki ek kargo bacağı doğar (§6.3.2)",
        line_gross=D("2690.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("1450.00"),
        commission_rate=D("0.185"),
        cargo_cost=D("79.00"),
        service_fee=D("8.99"),
        exchanges=(
            GoldenExchange(
                qty=1,
                return_cargo_cost=D("79.00"),
                replacement_cargo_cost=D("79.00"),
                restocked=True,
            ),
        ),
    ),
    GoldenCase(
        "GOLD-08",
        "Değişim + geri gelen mal hurda: iki birim maliyet çıkar",
        line_gross=D("2690.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("1450.00"),
        commission_rate=D("0.185"),
        cargo_cost=D("79.00"),
        service_fee=D("8.99"),
        exchanges=(
            GoldenExchange(
                qty=1,
                return_cargo_cost=D("79.00"),
                replacement_cargo_cost=D("79.00"),
                restocked=False,
            ),
        ),
    ),
    GoldenCase(
        "GOLD-09",
        "Kampanya, platform desteği yok: indirimin tamamını satıcı taşır (varsayılan)",
        line_gross=D("5000.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("2980.00"),
        commission_rate=D("0.21"),
        cargo_cost=D("88.25"),
        service_fee=D("8.99"),
        campaign_discount=D("950.00"),
    ),
    GoldenCase(
        "GOLD-10",
        "Kampanya, platform payı %40: destek gelire eklenir ve satış KDV'si doğurur",
        line_gross=D("5000.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("2980.00"),
        commission_rate=D("0.21"),
        cargo_cost=D("88.25"),
        service_fee=D("8.99"),
        campaign_discount=D("950.00"),
        campaign_seller_share_rate=D("0.60"),
    ),
    GoldenCase(
        "GOLD-11",
        "Ceza/tazmin: siparişe eşleşen ceza satır gideridir (§6.3.7)",
        line_gross=D("1390.00"),
        qty=1,
        vat_percent=D("1"),
        unit_cost_net=D("690.00"),
        commission_rate=D("0.145"),
        cargo_cost=D("69.75"),
        service_fee=D("8.99"),
        penalty=D("150.00"),
    ),
    GoldenCase(
        "GOLD-12",
        "İptal sipariş: ne gelir ne maliyet (§6.3.5)",
        line_gross=D("4590.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("2450.00"),
        commission_rate=D("0.225"),
        cargo_cost=D("88.25"),
        service_fee=D("8.99"),
        cancelled=True,
    ),
    GoldenCase(
        "GOLD-13",
        "Maliyeti bilinmeyen satır: motor uydurmaz, kalem sıfır kalır",
        line_gross=D("890.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=None,
        commission_rate=D("0.185"),
        cargo_cost=D("69.75"),
        service_fee=D("8.99"),
    ),
    GoldenCase(
        "GOLD-14",
        "Komisyon oranı bilinmeyen satır: oran 0 sayılır, satır uyarı alır",
        line_gross=D("890.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("420.00"),
        commission_rate=None,
        cargo_cost=D("69.75"),
        service_fee=D("8.99"),
    ),
    GoldenCase(
        "GOLD-15",
        "Yüksek sepet, düşük komisyon: premium ekipman",
        line_gross=D("16500.00"),
        qty=1,
        vat_percent=D("20"),
        unit_cost_net=D("8900.00"),
        commission_rate=D("0.195"),
        cargo_cost=D("171.50"),
        service_fee=D("8.99"),
    ),
    GoldenCase(
        "GOLD-16",
        "Çok adetli sepet: 5 adet aynı SKU",
        line_gross=D("1945.00"),
        qty=5,
        vat_percent=D("1"),
        unit_cost_net=D("185.00"),
        commission_rate=D("0.145"),
        cargo_cost=D("88.25"),
        service_fee=D("8.99"),
    ),
    GoldenCase(
        "GOLD-17",
        "Çok adetli sepette kısmi iade + biri hurda",
        line_gross=D("1945.00"),
        qty=5,
        vat_percent=D("1"),
        unit_cost_net=D("185.00"),
        commission_rate=D("0.145"),
        cargo_cost=D("88.25"),
        service_fee=D("8.99"),
        returns=(
            GoldenReturn(qty=1, return_cargo_cost=D("51.25"), restocked=True),
            GoldenReturn(qty=1, return_cargo_cost=D("51.25"), restocked=False),
        ),
    ),
    GoldenCase(
        "GOLD-18",
        "D2B satışı: komisyon 0, pazaryeri hizmet bedeli yok (§12C.9)",
        line_gross=D("29250.00"),
        qty=6,
        vat_percent=D("20"),
        unit_cost_net=D("3450.00"),
        commission_rate=D("0"),
        cargo_cost=D("0"),
        service_fee=D("0"),
    ),
    GoldenCase(
        "GOLD-19",
        "Kuruş sınırı: 3'e bölünen tutar, yuvarlama kayması olmamalı",
        line_gross=D("100.00"),
        qty=3,
        vat_percent=D("20"),
        unit_cost_net=D("20.00"),
        commission_rate=D("0.2075"),
        cargo_cost=D("42.00"),
        service_fee=D("8.99"),
    ),
    GoldenCase(
        "GOLD-20",
        "İade + kampanya + ceza birlikte: kalemler birbirini bozmamalı",
        line_gross=D("7450.00"),
        qty=2,
        vat_percent=D("20"),
        unit_cost_net=D("1890.00"),
        commission_rate=D("0.195"),
        cargo_cost=D("129.75"),
        service_fee=D("8.99"),
        penalty=D("75.00"),
        campaign_discount=D("600.00"),
        campaign_seller_share_rate=D("0.50"),
        returns=(GoldenReturn(qty=1, return_cargo_cost=D("64.50"), restocked=True),),
    ),
)


def _as_json(case: GoldenCase) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": case.case_id,
        "note": case.note,
        "line_gross": str(case.line_gross),
        "qty": case.qty,
        "vat_percent": str(case.vat_percent),
        "unit_cost_net": None if case.unit_cost_net is None else str(case.unit_cost_net),
        "commission_rate": (None if case.commission_rate is None else str(case.commission_rate)),
        "cargo_cost": str(case.cargo_cost),
        "service_fee": str(case.service_fee),
        "penalty": str(case.penalty),
        "campaign_discount": str(case.campaign_discount),
        "campaign_seller_share_rate": str(case.campaign_seller_share_rate),
        "cancelled": case.cancelled,
    }
    if case.returns:
        payload["returns"] = [
            {
                "qty": item.qty,
                "return_cargo_cost": str(item.return_cargo_cost),
                "restocked": item.restocked,
            }
            for item in case.returns
        ]
    if case.exchanges:
        payload["exchanges"] = [
            {
                "qty": item.qty,
                "return_cargo_cost": str(item.return_cargo_cost),
                "replacement_cargo_cost": str(item.replacement_cargo_cost),
                "restocked": item.restocked,
            }
            for item in case.exchanges
        ]
    return payload


def build() -> dict[str, Any]:
    """Girdileri ve referans hesabın ürettiği beklenen değerleri toplar."""
    rows: list[dict[str, Any]] = []
    total = D("0")
    for case in CASES:
        profit = to_kurus(reference_profit(case))
        total += profit
        row = _as_json(case)
        row["expected_profit"] = str(profit)
        revenue = _revenue(case)
        row["expected_margin_pct"] = str(
            (profit / revenue * D("100")).quantize(D("0.01")) if revenue else D("0.00")
        )
        rows.append(row)
    return {
        "note": (
            "Beklenen değerler tests/golden_reference.py (bağımsız referans hesap) "
            "tarafından üretildi; testler motoru VE referansı bu literallerle karşılaştırır."
        ),
        "expected_total_profit": str(total),
        "cases": rows,
    }


def _revenue(case: GoldenCase) -> D:
    """Marj paydası: iade edilen adet çıkarıldıktan sonraki brüt gelir."""
    if case.cancelled:
        return D("0")
    returned = min(sum(item.qty for item in case.returns), case.qty)
    unit = case.line_gross / case.qty if case.qty else D("0")
    return (unit * (case.qty - returned)).quantize(D("0.01"))


def main() -> None:
    """Dosyayı üretir."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUTPUT} yazıldı ({len(CASES)} satır)")


if __name__ == "__main__":  # pragma: no cover
    main()
