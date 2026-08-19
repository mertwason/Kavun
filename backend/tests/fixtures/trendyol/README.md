# Trendyol fixture'ları

Bu dosyalar **developers.trendyol.com dokümanındaki yanıt şemasından** üretilmiştir
(alan adları 2026-08-18'de doğrulandı), canlı trafikten kaydedilmiş değildir — Kavun'un
henüz gerçek bir Trendyol mağazası credential'ı yok.

İlk gerçek senkrondan sonra `raw_events` tablosundaki bir örnek yanıt buraya kaydedilecek
ve bu dosyalar onunla değiştirilecektir (spec §12.7: "ilk gerçek veriyle şema doğrulaması").

Kaynaklar:
- Siparişler: https://developers.trendyol.com/v3.0/reference/getshipmentpackages
- Onaylı ürünler (V2): https://developers.trendyol.com/v3.0/reference/filterapprovedproducts
- İadeler: https://developers.trendyol.com/reference/getclaims (şema 2026-08-19'da doğrulandı)
- Hakediş / cari hesap: https://developers.trendyol.com/docs/cari-hesap-ekstresi-entegrasyonu
- Kargo faturası kalemleri: https://developers.trendyol.com/reference/getcargoinvoiceitems

## Faz 2 dosyaları (KVN-EK-05)

| Dosya | Uç | Ne içeriyor |
|---|---|---|
| `claims_page0.json` | `/order/sellers/{id}/claims` | biri kabul edilmiş 2 adetlik, biri **reddedilmiş** iki iade talebi |
| `settlements_page0.json` | `/finance/che/sellers/{id}/settlements` | satış, komisyon, iade ve teslimat bedeli kalemleri (borç/alacak sütunlu) |
| `otherfinancials_deductions.json` | `.../otherfinancials?transactionType=DeductionInvoices` | biri kargo faturası, biri iade faturası — seri numarası buradan çıkar |
| `cargo_invoice_items.json` | `.../cargo-invoice/{seri}/items` | gönderi bazlı tutar/desi kalemleri |

Reddedilen talep ve kargo dışı kesinti faturası **bilerek** konuldu: parser'ın onları
ayıklaması test ediliyor.
