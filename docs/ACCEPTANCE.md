# Kabul Kriterleri → Test Eşlemesi

Spec'teki her kabul kriterinin karşılığı bir testtir. Bu dosya "hangi kriteri hangi test
kanıtlıyor" sorusunun tek cevabıdır; kriter değişirse test de değişmelidir.

Tümünü koşmak için:

```bash
make acceptance     # golden dataset + uçtan uca kabul turu
make test           # tüm test paketi (kabul testleri dahil)
```

---

## Faz 1 — §11: "rastgele 20 sipariş için elle hesaplanan kârla motor çıktısı kuruş kuruş eşit"

| Kriter | Test |
|---|---|
| 20 siparişlik golden dataset var | `test_golden_dataset.py::test_dataset_has_twenty_orders` |
| Motor = elle hesap (kuruş kuruş) | `test_golden_dataset.py::test_engine_matches_the_hand_calculation` |
| Marj yüzdesi de donmuş değerle eşleşir | `test_golden_dataset.py::test_engine_margin_matches_the_frozen_value` |
| Toplam kâr donmuştur | `test_golden_dataset.py::test_totals_match_the_frozen_summary` |
| Çözümlü örnek elle takip edilebilir | `test_golden_dataset.py::test_worked_example_is_reproducible_by_hand` |

**Yöntem.** `tests/golden/orders.json` girdileri **ve** beklenen değerleri donmuş literal
olarak taşır. Beklenen değerler motordan değil, `tests/golden_reference.py` içindeki
bağımsız ikinci uygulamadan üretilir. Testler üç kaynağı birden karşılaştırır:

```
motor  ==  referans uygulama  ==  dosyadaki donmuş değer
```

Yuvarlama: ara adımlar 4 haneyle taşınır (CLAUDE.md §1 — yuvarlama yalnızca gösterimde),
karşılaştırma kuruşta yapılır. Ayrıca iki uygulama arasındaki fark yarım kuruşu geçemez;
bu, yuvarlamanın gizleyebileceği yapısal farkı yakalar.

Dosyayı yeniden üretmek: `python -m tests.golden_generate`. Üretim bir insan kararıdır —
beklenen bir değer değişiyorsa nedeni commit mesajında yazılmalıdır.

---

## §12A.6 — Ürün & fiyat çalışma alanı

| Kriter | Test |
|---|---|
| Export → değiştirmeden import → 0 yeni / 0 güncelleme / 0 hata | `test_pricelist.py::test_unchanged_roundtrip_reports_no_changes`, `test_acceptance.py::test_price_list_round_trip_reports_no_change` |
| 500 satırlık dosya < 10 sn | `test_pricelist.py::test_five_hundred_rows_process_under_ten_seconds` |
| Hedef marj çözücü round-trip (±0,01 puan) | `test_scenarios.py::test_solved_price_hits_the_target_margin`, `::test_target_margin_endpoint_round_trip` |
| Taslak → promote → sipariş kârı zinciri | `test_drafts.py::test_draft_to_promote_to_order_profit_chain` |

## §12B.5 — Komisyon tarife motoru

| Kriter | Test |
|---|---|
| Üç kaynaklı çözümleme hiyerarşisi | `test_tariffs.py::test_hierarchy_prefers_settlement_over_api_and_manual` |
| Snapshot diff → change kaydı + doğru etki | `test_tariffs.py::test_rate_change_creates_change_record_and_alert` |
| Tarife senaryosu round-trip (±0,01 puan) | `test_tariffs.py::test_tariff_impact_round_trip_hits_target_margin` |
| Settlement çelişkisi sessiz geçilmez | `test_tariffs.py::test_settlement_conflict_writes_actual_rate` |
| Etki analizi kârı doğru yönde değiştirir | `test_acceptance.py::test_commission_change_detection_and_impact_agree` |

## §12C.11 — Fatura, stok, WAC, ithalat, D2B, fire

| Kriter | Test |
|---|---|
| Formül: 34@100 + 100@120 → 114,9254 | `test_invoices.py::test_wac_formula_matches_the_spec_example` |
| 50 satış sonrası +20@130 → ortalama doğru | `test_invoices.py::test_further_inbound_updates_average_correctly` |
| Ledger replay = birebir aynı durum | `test_inventory.py::test_state_can_be_rebuilt_from_the_ledger`, `test_seeds.py::test_demo_state_can_be_rebuilt_from_the_ledger`, `test_acceptance.py::test_ledger_replay_reproduces_the_state` |
| Fatura PDF fixture'ı + parser → review → confirm | `test_invoices.py::test_pdf_lines_are_extracted`, `::test_full_chain_upload_match_confirm` |
| Onaylanmış faturayı değiştirme → 409 | `test_invoices.py::test_editing_a_confirmed_invoice_returns_409` |
| İthalat dosyası landed cost (elle hesap) | `test_imports.py::test_landed_cost_matches_the_hand_calculation` |
| İthalat KDV'si maliyete girmez | `test_imports.py::test_import_vat_is_not_part_of_the_cost` |
| Kur farkı doğru, WAC değişmez | `test_imports.py::test_payment_records_the_fx_difference`, `::test_fx_difference_does_not_touch_the_average_cost` |
| D2B satışı: stok düşer, komisyon 0 | `test_b2b.py::test_import_creates_orders_without_commission`, `::test_imported_sale_reduces_stock` |
| Damage: stok ve fire gideri doğru, ortalama değişmez | `test_b2b.py::test_damage_reduces_stock_without_changing_average`, `::test_damage_report_shows_rate_and_cost` |

## §3A.6 — Marka izolasyonu

| Kriter | Test |
|---|---|
| Brand filtresi olmayan sorgu `BrandScopeViolation` (≥3 tablo) | `test_brand_scope.py` (negatif testler) |
| Karşı markanın kaynağı → 404 | `test_analytics.py::test_order_detail_of_other_brand_returns_404`, `test_invoices.py::test_invoice_of_other_brand_returns_404`, `test_drafts.py::test_draft_of_other_brand_returns_404`, `test_scenarios.py::test_scenario_of_other_brand_product_returns_404`, `test_acceptance.py::test_other_brands_order_is_not_reachable` |
| Karışmış SKU → `cross_brand_rejected`, kalan satırlar işlenir | `test_api_isolation.py::test_foreign_brand_sku_is_rejected_in_price_list`, `::test_other_rows_still_process_when_one_is_cross_brand`, `::test_foreign_sku_does_not_create_a_product_in_this_brand`, `test_b2b.py::test_foreign_brand_sku_is_rejected_in_d2b_import` |
| Tek marka yetkili kullanıcının `/holding` isteği → 403 + audit | `test_api_isolation.py::test_holding_view_requires_permission`, `::test_consolidated_report_requires_holding_permission` |
| Kapalı modül endpoint'i → 404 | `test_acceptance.py::test_closed_modules_stay_invisible_for_kahveji`, `test_imports.py::test_module_returns_404_when_the_feature_flag_is_off`, `test_b2b.py::test_modules_return_404_when_flags_are_off` |

---

## Uçtan uca tur (KVN-20)

`tests/test_acceptance.py` tek tek modülleri değil **modüller arası tutarlılığı** doğrular:
demo tenant kurulur, kâr motoru koşar ve aynı gerçeğin farklı ekranlarda aynı sayıyı
verdiği kontrol edilir.

| Ne doğrulanır | Test |
|---|---|
| Dashboard kârı = SKU listesi kâr toplamı | `test_dashboard_and_sku_list_tell_the_same_story` |
| Dashboard cirosu = mağaza kırılımı toplamı | `test_dashboard_revenue_matches_the_store_breakdown` |
| Günlük seri toplamı = dönem kârı | `test_daily_series_adds_up_to_the_period_total` |
| Şelale adımları = satır kârı | `test_order_detail_waterfall_ends_at_the_line_profit` |
| Stok değeri = adet × ortalama maliyet | `test_stock_value_matches_qty_times_average_cost` |
| Holding cirosu = markaların toplamı | `test_holding_totals_match_the_brand_screens` |
| İkinci hesap yeni kayıt/revizyon üretmez | `test_recompute_is_idempotent` |
| Demo veri son çeyrekte gezilebilir | `test_demo_period_covers_the_last_quarter` |

---

## Kapsam dışı (bilerek)

- **Faz 2 kabul kriteri** ("bir aylık gerçek hakediş dökümü ile %99+ satır eşleşmesi")
  gerçek hakediş verisi ister; mutabakat modülü Faz 2'nin işidir.
- **Frontend davranış testi** yok: projede frontend test koşucusu kurulu değil, CI
  yalnızca `tsc`, `eslint` ve `next build` koşuyor. Ekranlar her görevde gerçek tarayıcıda
  elle gezildi (boş durum + dolu durum).
- **LLM tabanlı fatura ayrıştırma** (§12C.3.2) uygulanmadı; gerekçe README'de.
