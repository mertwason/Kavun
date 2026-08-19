"""Demo katalog verisi — marka kimliğine uygun ürün listeleri.

Gerçek API'ye bağlanmadan önce tüm ekranların dolu gezilebilmesi için (CLAUDE.md §6).
Fiyat/maliyetler gerçekçi büyüklüktedir; birkaç SKU bilinçli olarak negatif marj üretir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DemoProduct:
    """Demo ürün tanımı — tüm parasal alanlar `Decimal`."""

    sku: str
    name: str
    category: str
    vat_rate: Decimal
    unit_cost: Decimal
    sale_price: Decimal
    desi: Decimal
    msrp: Decimal | None = None
    opening_qty: int = 0


_D = Decimal

# fmt: off
# Alessi: premium İtalyan tasarım, ithalat, KDV %20, MSRP disiplini var.
ALESSI_PRODUCTS: tuple[DemoProduct, ...] = (
    DemoProduct("ALS-9090-3", "Alessi 9090 Espresso Makinesi 3 Cup", "Mutfak/Kahve", _D("20"), _D("3450.00"), _D("6890.00"), _D("3.5"), _D("7290.00"), 136),
    DemoProduct("ALS-9090-6", "Alessi 9090 Espresso Makinesi 6 Cup", "Mutfak/Kahve", _D("20"), _D("4180.00"), _D("8250.00"), _D("4.0"), _D("8590.00"), 72),
    DemoProduct("ALS-PSJS", "Juicy Salif Narenciye Sıkacağı", "Mutfak/Aksesuar", _D("20"), _D("2980.00"), _D("5950.00"), _D("2.5"), _D("6190.00"), 88),
    DemoProduct("ALS-AM01", "Anna G. Tirbuşon", "Mutfak/Aksesuar", _D("20"), _D("1840.00"), _D("3690.00"), _D("1.5"), _D("3890.00"), 164),
    DemoProduct("ALS-AM23", "Alessandro M. Tirbuşon", "Mutfak/Aksesuar", _D("20"), _D("1920.00"), _D("3790.00"), _D("1.5"), _D("3990.00"), 108),
    DemoProduct("ALS-MG32", "Mami Tencere 24 cm", "Mutfak/Pişirme", _D("20"), _D("4650.00"), _D("8900.00"), _D("6.0"), _D("9290.00"), 48),
    DemoProduct("ALS-MG33", "Mami Tava 28 cm", "Mutfak/Pişirme", _D("20"), _D("3890.00"), _D("7450.00"), _D("5.5"), _D("7790.00"), 60),
    DemoProduct("ALS-KTL-01", "Il Conico Su Isıtıcısı", "Mutfak/Pişirme", _D("20"), _D("8900.00"), _D("16500.00"), _D("7.0"), _D("17290.00"), 24),
    DemoProduct("ALS-BOMB", "Bombé Çay Seti", "Sofra/Servis", _D("20"), _D("5200.00"), _D("9800.00"), _D("8.0"), _D("10290.00"), 36),
    DemoProduct("ALS-CIRC-T", "Circus Kurabiye Kutusu", "Sofra/Servis", _D("20"), _D("1450.00"), _D("2890.00"), _D("2.0"), _D("2990.00"), 132),
    DemoProduct("ALS-CIRC-M", "Circus Müzik Kutusu", "Dekorasyon", _D("20"), _D("2650.00"), _D("4950.00"), _D("2.5"), _D("5190.00"), 56),
    DemoProduct("ALS-BLOW", "Blow Up Meyve Sepeti", "Sofra/Servis", _D("20"), _D("3100.00"), _D("5890.00"), _D("4.0"), _D("6190.00"), 76),
    DemoProduct("ALS-DRSS", "Dressed Yemek Tabağı Seti 4'lü", "Sofra/Tabak", _D("20"), _D("2890.00"), _D("5290.00"), _D("5.0"), _D("5590.00"), 96),
    DemoProduct("ALS-COL-B", "Colombina Kase Seti", "Sofra/Tabak", _D("20"), _D("2340.00"), _D("4290.00"), _D("4.5"), _D("4490.00"), 84),
    DemoProduct("ALS-GIRO", "Girotondo Servis Tepsisi", "Sofra/Servis", _D("20"), _D("1980.00"), _D("3790.00"), _D("3.0"), _D("3990.00"), 112),
    DemoProduct("ALS-TIC-W", "Tic Tac Duvar Saati", "Dekorasyon", _D("20"), _D("2450.00"), _D("4590.00"), _D("2.5"), _D("4790.00"), 68),
    DemoProduct("ALS-VASE-1", "Fiore Vazo Küçük", "Dekorasyon", _D("20"), _D("1680.00"), _D("3190.00"), _D("2.0"), _D("3390.00"), 104),
    DemoProduct("ALS-VASE-2", "Fiore Vazo Büyük", "Dekorasyon", _D("20"), _D("2380.00"), _D("4450.00"), _D("3.0"), _D("4690.00"), 52),
    # Negatif marj örneği: kampanya fiyatı maliyeti kurtarmıyor.
    DemoProduct("ALS-OUTL-1", "Alessi Outlet — Kırık Kutu Tirbuşon", "Outlet", _D("20"), _D("1840.00"), _D("1990.00"), _D("1.5"), None, 8),
    DemoProduct("ALS-OUTL-2", "Alessi Outlet — Teşhir Tepsi", "Outlet", _D("20"), _D("1980.00"), _D("2150.00"), _D("3.0"), None, 5),
)

# Kahveji: premium kahve e-ticaret, gıda KDV %1, ekipmanda %20.
KAHVEJI_PRODUCTS: tuple[DemoProduct, ...] = (
    DemoProduct("KHV-ETH-250", "Etiyopya Yirgacheffe 250g Çekirdek", "Kahve/Tek Origin", _D("1"), _D("185.00"), _D("389.00"), _D("0.5"), None, 480),
    DemoProduct("KHV-ETH-1K", "Etiyopya Yirgacheffe 1kg Çekirdek", "Kahve/Tek Origin", _D("1"), _D("690.00"), _D("1390.00"), _D("1.5"), None, 180),
    DemoProduct("KHV-COL-250", "Kolombiya Huila 250g Çekirdek", "Kahve/Tek Origin", _D("1"), _D("165.00"), _D("349.00"), _D("0.5"), None, 560),
    DemoProduct("KHV-COL-1K", "Kolombiya Huila 1kg Çekirdek", "Kahve/Tek Origin", _D("1"), _D("620.00"), _D("1250.00"), _D("1.5"), None, 208),
    DemoProduct("KHV-BRZ-250", "Brezilya Cerrado 250g Çekirdek", "Kahve/Tek Origin", _D("1"), _D("145.00"), _D("299.00"), _D("0.5"), None, 640),
    DemoProduct("KHV-BRZ-1K", "Brezilya Cerrado 1kg Çekirdek", "Kahve/Tek Origin", _D("1"), _D("540.00"), _D("1090.00"), _D("1.5"), None, 240),
    DemoProduct("KHV-KEN-250", "Kenya AA 250g Çekirdek", "Kahve/Tek Origin", _D("1"), _D("210.00"), _D("429.00"), _D("0.5"), None, 340),
    DemoProduct("KHV-GTM-250", "Guatemala Antigua 250g Çekirdek", "Kahve/Tek Origin", _D("1"), _D("178.00"), _D("369.00"), _D("0.5"), None, 380),
    DemoProduct("KHV-BLD-ESP", "Kahveji Espresso Blend 1kg", "Kahve/Harman", _D("1"), _D("580.00"), _D("1190.00"), _D("1.5"), None, 440),
    DemoProduct("KHV-BLD-FLT", "Kahveji Filtre Blend 1kg", "Kahve/Harman", _D("1"), _D("545.00"), _D("1120.00"), _D("1.5"), None, 392),
    DemoProduct("KHV-BLD-250", "Kahveji Espresso Blend 250g", "Kahve/Harman", _D("1"), _D("158.00"), _D("329.00"), _D("0.5"), None, 700),
    DemoProduct("KHV-DECAF", "Kafeinsiz Kolombiya 250g", "Kahve/Tek Origin", _D("1"), _D("195.00"), _D("399.00"), _D("0.5"), None, 256),
    DemoProduct("KHV-CLDBRW", "Cold Brew Konsantre 500ml", "Kahve/Hazır", _D("1"), _D("98.00"), _D("219.00"), _D("1.0"), None, 352),
    DemoProduct("KHV-DRIP-10", "Pratik Filtre Kahve 10'lu", "Kahve/Hazır", _D("1"), _D("135.00"), _D("289.00"), _D("0.5"), None, 520),
    DemoProduct("KHV-V60-02", "V60 Dripper 02 Seramik", "Ekipman/Demleme", _D("20"), _D("420.00"), _D("890.00"), _D("1.5"), None, 168),
    DemoProduct("KHV-V60-FLT", "V60 Filtre Kağıdı 100'lü", "Ekipman/Sarf", _D("20"), _D("95.00"), _D("219.00"), _D("0.5"), None, 840),
    DemoProduct("KHV-CHEMEX", "Chemex 6 Cup", "Ekipman/Demleme", _D("20"), _D("1180.00"), _D("2290.00"), _D("3.0"), None, 72),
    DemoProduct("KHV-AERO", "AeroPress Go", "Ekipman/Demleme", _D("20"), _D("1450.00"), _D("2690.00"), _D("2.0"), None, 100),
    DemoProduct("KHV-GRND-M", "El Değirmeni Manuel", "Ekipman/Öğütücü", _D("20"), _D("1890.00"), _D("3450.00"), _D("2.0"), None, 120),
    DemoProduct("KHV-GRND-E", "Elektrikli Öğütücü", "Ekipman/Öğütücü", _D("20"), _D("3250.00"), _D("5890.00"), _D("4.0"), None, 48),
    DemoProduct("KHV-SCALE", "Hassas Kahve Terazisi", "Ekipman/Aksesuar", _D("20"), _D("680.00"), _D("1350.00"), _D("1.0"), None, 144),
    DemoProduct("KHV-KETL", "Gooseneck Su Isıtıcı", "Ekipman/Aksesuar", _D("20"), _D("1980.00"), _D("3590.00"), _D("3.5"), None, 80),
    DemoProduct("KHV-MOKA-3", "Moka Pot 3 Cup", "Ekipman/Demleme", _D("20"), _D("540.00"), _D("1090.00"), _D("1.5"), None, 192),
    DemoProduct("KHV-CUP-2", "Espresso Fincan Seti 2'li", "Ekipman/Aksesuar", _D("20"), _D("320.00"), _D("690.00"), _D("2.0"), None, 220),
    DemoProduct("KHV-ABON-3", "3 Aylık Abonelik Paketi", "Abonelik", _D("1"), _D("1450.00"), _D("2890.00"), _D("2.0"), None, 0),
    DemoProduct("KHV-HDY-01", "Hediye Kutusu — Keşif Seti", "Hediye", _D("1"), _D("620.00"), _D("1290.00"), _D("2.5"), None, 160),
    DemoProduct("KHV-HDY-02", "Hediye Kutusu — Ekipman Seti", "Hediye", _D("20"), _D("2150.00"), _D("3890.00"), _D("4.0"), None, 60),
    # Negatif marj örnekleri: kargo + komisyon küçük sepeti eritiyor.
    DemoProduct("KHV-SMPL-50", "Deneme Boyu 50g", "Kahve/Numune", _D("1"), _D("48.00"), _D("69.00"), _D("0.5"), None, 800),
    DemoProduct("KHV-SRVT", "Kahveji Servet Peçete 20'li", "Ekipman/Sarf", _D("20"), _D("62.00"), _D("89.00"), _D("0.5"), None, 600),
    DemoProduct("KHV-STCK", "Karıştırma Çubuğu 50'li", "Ekipman/Sarf", _D("20"), _D("55.00"), _D("79.00"), _D("0.5"), None, 720),
)

# fmt: on


def demo_product_count() -> int:
    """Toplam demo SKU sayısı — testler bu sayıyı referans alır."""
    return len(ALESSI_PRODUCTS) + len(KAHVEJI_PRODUCTS)


def demo_opening_stock_count() -> int:
    """Açılış stoku olan SKU sayısı — adedi 0 olanlara devir hareketi yazılmaz."""
    return sum(1 for item in ALESSI_PRODUCTS + KAHVEJI_PRODUCTS if item.opening_qty > 0)
