# KAVUN — Pazaryeri Kârlılık ve Mutabakat Platformu
## Teknik Tasarım Dokümanı v1.0 (Claude Code için uygulama spec'i)

> Sahip: Mokka Teknoloji. İlk kullanım: internal (Kahveji + Alessi mağazaları).
> Mimari hedef: multi-tenant hazır, single-tenant çalışan; ops.mokka'ya SSO ile bağlı bağımsız servis.

---

## 1. Ürünün Amacı

Trendyol, Hepsiburada, N11 ve Shopify kanallarındaki satışların **sipariş satırı bazında gerçek net kârını** hesaplamak, hakediş (settlement) mutabakatı yapmak, kampanya/fiyat kararlarını simüle etmek ve marj erimelerinde uyarı üretmek.

Referans rakip: Melontik (Trendyol+Hepsiburada kârlılık SaaS'ı). Bizim farklarımız:
1. **Hakediş mutabakatı** (platformun ödediği vs bizim hesapladığımız, satır bazında diff)
2. **Marka bazlı P&L** (Kahveji / Alessi ayrımı)
3. Maliyetlerin **versiyonlu ve fatura-bazlı** tutulması (elle tek değer değil)
4. Shopify (D2C) kanalının aynı motora dahil olması

---

## 2. Mimari Genel Bakış

```
┌─────────────────────────────────────────────────────┐
│  ops.mokka (mevcut)  ── SSO / link ──►  Kavun UI    │
│                                         (Next.js)   │
└─────────────────────────────────────────────────────┘
                              │ REST/JSON
┌─────────────────────────────▼───────────────────────┐
│  Kavun API (FastAPI, Python 3.12)                   │
│  - Auth (JWT, tenant-scoped)                        │
│  - Reporting endpoints                              │
│  - Settings / cost management                       │
├─────────────────────────────────────────────────────┤
│  Worker katmanı (Celery + Redis broker)             │
│  - Sync jobs (kanal başına, cron)                   │
│  - Normalization pipeline                           │
│  - Profit engine (recompute)                        │
│  - Reconciliation jobs                              │
│  - Alert engine                                     │
├─────────────────────────────────────────────────────┤
│  Connector katmanı (abstract interface + adapters)  │
│  - TrendyolConnector  (Faz 1)                       │
│  - HepsiburadaConnector (Faz 3)                     │
│  - N11Connector (Faz 3)                             │
│  - ShopifyConnector (Faz 3)                         │
├─────────────────────────────────────────────────────┤
│  PostgreSQL 16          Redis (cache + broker)      │
│  raw_events (JSONB)  +  normalize domain tablolar   │
└─────────────────────────────────────────────────────┘
```

**Repo yapısı (monorepo):**
```
kavun/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── connectors/     # base.py + trendyol.py + ...
│   │   ├── core/           # config, security, tenancy middleware
│   │   ├── engine/         # profit engine, vat, allocation
│   │   ├── reconciliation/
│   │   ├── models/         # SQLAlchemy
│   │   ├── schemas/        # Pydantic
│   │   ├── workers/        # celery tasks
│   │   └── alerts/
│   ├── alembic/
│   └── tests/
├── frontend/               # Next.js 14 (App Router) + Tailwind
└── docker-compose.yml      # postgres, redis, api, worker, frontend
```

---

## 3. Temel Tasarım Kuralları (Claude Code için bağlayıcı)

1. **Her tabloda `tenant_id`** (UUID, FK → tenants). Tüm query'ler tenancy middleware'den geçer. Şimdilik tek tenant: "mokka".
1a. **Brand Workspace izolasyonu (bkz. bölüm 3A):** işlem verisi taşıyan her tabloda `brand_id` zorunludur; brand-scope middleware filtresiz sorguyu exception ile durdurur. UI marka bazlı ayrı modüller halinde çalışır; markalar arası veri erişimi yalnızca Holding görünümü rolüyle mümkündür.
2. **Ham veri immutable.** API'den gelen her yanıt önce `raw_events`'e yazılır; normalize işlem bu tablodan okur. Normalize tablolar silinip `raw_events`'ten yeniden üretilebilir olmalı (replay komutu: `python -m app.cli replay --channel trendyol --from 2026-08-01`).
3. **Para birimleri:** tüm tutarlar `NUMERIC(14,4)`, kuruş hassasiyeti korunur; float YASAK. TL varsayılan, `currency` alanı yine de tutulur.
4. **Maliyet kalemleri state machine:** `estimated → actual`. Actual geldiğinde ilgili sipariş satırının kârı yeniden hesaplanır ve `profit_revisions` tablosuna eski/yeni değer loglanır.
5. **Connector arayüzü sabit:** yeni kanal = yeni adapter, motor koduna dokunulmaz.
6. **API credential'ları** `store_credentials` tablosunda **Fernet ile şifreli** saklanır (key env'den: `KAVUN_ENCRYPTION_KEY`). Loglara asla yazılmaz.
7. Idempotency: sync job'lar aynı veriyi iki kez çekerse duplicate oluşmaz (upsert, unique constraint: `(tenant_id, channel_id, external_id)`).

---

## 3A. Brand Workspace Mimarisi (Alessi ↔ Kahveji tam ayrımı)

> İş gereksinimi: Alessi, site içinde ayrı modül olarak çalışacak ve Kahveji ile hiçbir şekilde karışmayacak. Çözüm: motor tek, izolasyon mutlak. Fiziksel altyapı ayrımı YAPILMAZ (çift bakım + konsolidasyon kaybı); izolasyon mimari seviyede zorlanır.

### 3A.1 Workspace kavramı
- Her marka bir **workspace**'tir: `Kavun · Alessi` (`/alessi/...`) ve `Kavun · Kahveji` (`/kahveji/...`) ayrı URL ağaçları, ayrı menüler, ayrı dashboard'lar.
- Aktif workspace JWT claim'inde taşınır (`active_brand`); frontend tüm istekleri bu context ile atar. Workspace switcher yalnızca çoklu marka yetkisi olan kullanıcılara görünür.
- Bir workspace içinde diğer markaya ait hiçbir veri, sayı, SKU, alert veya menü öğesi render edilmez.

### 3A.2 Zorunlu veri izolasyonu
- İşlem verisi taşıyan tüm tablolarda `brand_id NOT NULL` (products, orders, order_lines, purchase_invoices, import_files, inventory_ledger, sku_cost_state, pricing_scenarios, alerts, commission_changes...). Kanal/mağaza zaten `stores.brand_id` üzerinden markaya bağlıdır.
- **Brand-scope middleware:** SQLAlchemy session event ile uygulanır; brand filtresi içermeyen sorgu `BrandScopeViolation` exception'ı fırlatır (fail-closed). Holding rolü bu kuralı yalnızca `X-Holding-View: true` + rol kontrolü ile bypass edebilir; bypass her seferinde audit log'a yazılır.
- Import izolasyonu: bir workspace'ten yüklenen her dosya (fiyat listesi, tarife, alış faturası, B2B satış) yalnızca o markaya yazılır. Dosyada başka markaya ait SKU tespit edilirse satır `cross_brand_rejected` hatasıyla reddedilir ve hata sheet'inde raporlanır.
- Excel export dosya adları marka önekiyle üretilir (`alessi_fiyat_listesi_2026-08-01.xlsx`) — dosya karışıklığı insan seviyesinde de önlenir.

### 3A.3 Yetki matrisi
- `user_brand_roles(user_id, brand_id, role ENUM(viewer, editor, admin))` — kullanıcı yalnızca yetkili olduğu workspace'leri görür; tek markaya yetkili kullanıcı için diğer marka UI'da hiç var olmaz.
- **Holding görünümü** (`/holding/...`): ayrı rol (`holding_viewer`); markalar arası konsolide raporlar burada yaşar: birleşik P&L, toplam stok değeri, kur maruziyeti, nakit takvimi. Salt okunur; işlem yapılamaz.

### 3A.4 Marka bazlı fonksiyon bayrakları
- `brand_features(brand_id, feature_code, enabled)` — modüller marka bazında açılır/kapanır:
  - Alessi: `import_files`, `fx_tracking`, `b2b_channel`, `msrp_discipline` AÇIK
  - Kahveji: bu dördü KAPALI (menüde görünmez); ileride `subscription_cohorts` gibi Kahveji'ye özel modüller aynı mekanizmayla eklenir
- Backend endpoint'leri feature kontrolü yapar: kapalı modülün endpoint'i o marka için 404 döner (403 değil — modülün varlığı bile sızdırılmaz).

### 3A.5 Kaçış kapısı
- Mimari multi-tenant olduğundan, ileride tam ayrım istenirse Alessi ayrı tenant'a migration ile taşınır (brand_id → yeni tenant eşlemesi + credential taşıma). Bu senaryo için hiçbir ek kod yazılmaz; sadece mimari bu kapıyı kapatmaz.

### 3A.6 Kabul kriterleri
- Brand filtresi olmayan sorgu testte `BrandScopeViolation` fırlatır (en az 3 tablo için negatif test)
- Alessi workspace token'ı ile Kahveji kaynağına istek → 404; API yanıtlarında karşı markaya ait hiçbir id/SKU sızmaz (response şema testi)
- Kahveji fiyat listesine Alessi SKU'su karıştırılmış xlsx → ilgili satırlar `cross_brand_rejected`, kalan satırlar işlenir
- Tek marka yetkili kullanıcının `/holding` isteği → 403 + audit kaydı
- Feature bayrağı kapalı modül endpoint'i → 404 (Kahveji için `import_files` örneğiyle test)

---

## 4. Connector Arayüzü

```python
class MarketplaceConnector(ABC):
    channel_code: str  # "trendyol" | "hepsiburada" | "n11" | "shopify"

    @abstractmethod
    async def fetch_orders(self, since: datetime, until: datetime) -> list[RawOrder]: ...
    @abstractmethod
    async def fetch_returns(self, since: datetime) -> list[RawReturn]: ...
    @abstractmethod
    async def fetch_settlements(self, since: datetime) -> list[RawSettlementRow]: ...
    @abstractmethod
    async def fetch_cargo_invoices(self, since: datetime) -> list[RawCargoInvoice]: ...
    @abstractmethod
    async def fetch_products(self) -> list[RawProduct]: ...
    @abstractmethod
    async def fetch_commission_rates(self) -> list[RawCommission]: ...
    # Faz 4:
    async def fetch_ad_spend(self, since: datetime) -> list[RawAdSpend]: ...
    async def fetch_promotions(self) -> list[RawPromotion]: ...
```

### Trendyol adapter notları (Faz 1)
- Auth: Basic Auth (API Key : API Secret), header `User-Agent: {SellerID} - SelfIntegration`.
- Base URL: `https://apigw.trendyol.com/integration/` (dokümandan doğrulanacak; developers.trendyol.com güncel referans alınacak).
- Kullanılacak servis grupları: Orders (paket bazlı sipariş çekme), Claims (iade/talepler), Finance / Settlements (hakediş, kesintiler, cargo invoice kalemleri), Product (ürün listesi, komisyon oranları, desi/barkod eşleşmesi).
- Rate limit: dokümandaki limitlere uy; exponential backoff + jitter; 429'da retry.
- Sayfalama: `page/size` parametreleri; tüm sayfalar tüketilecek.
- Sipariş statüleri normalize edilecek: Created/Picking/Shipped/Delivered/Cancelled/Returned → internal enum.

---

## 5. Veri Modeli (PostgreSQL)

### 5.1 Kimlik / yapı
- `tenants(id, name, created_at)`
- `brands(id, tenant_id, name)` — Kahveji, Alessi
- `channels(id, code, name)` — trendyol, hepsiburada, n11, shopify
- `stores(id, tenant_id, brand_id, channel_id, external_seller_id, name, is_active)`
- `store_credentials(id, store_id, encrypted_payload, created_at, rotated_at)`

### 5.2 Katalog & maliyet
- `products(id, tenant_id, brand_id, sku, name, barcode, category, vat_rate NUMERIC(5,2))`
- `product_channel_map(id, product_id, store_id, external_product_id, external_barcode)`
- `sku_costs(id, product_id, unit_cost NUMERIC(14,4), currency, source ENUM(manual, invoice, erp), invoice_ref, effective_from DATE, created_by)`
  - Bir tarihteki geçerli maliyet = `effective_from <= order_date` olan en güncel kayıt.
- `sku_logistics(id, product_id, desi NUMERIC(8,2), default_carrier, effective_from)`
- `commission_rates(id, store_id, scope ENUM(product, category), product_id NULL, category_code NULL, rate NUMERIC(6,4), valid_from DATE, valid_to DATE NULL, source ENUM(api_product, api_category, settlement_actual, manual), snapshot_date, is_campaign_period BOOLEAN DEFAULT false, campaign_name NULL)`
  - Günlük snapshot ile versiyonlu; çözümleme hiyerarşisi ve değişiklik tespiti için bkz. bölüm 12B.
- `commission_changes(id, store_id, product_id NULL, category_code NULL, old_rate, new_rate, detected_at, monthly_profit_impact NUMERIC(14,2) NULL, alert_id NULL)`

### 5.3 İşlem verisi
- `raw_events(id BIGSERIAL, tenant_id, store_id, event_type, external_id, payload JSONB, fetched_at, processed_at NULL)` — partition by month.
- `orders(id, tenant_id, store_id, external_order_id, order_date, status, customer_city, gross_total, currency)`
- `order_lines(id, order_id, product_id, external_line_id, qty, unit_sale_price, line_gross, vat_rate, commission_rate_used, status)`
- `shipments(id, order_id, carrier, desi_declared, desi_invoiced NULL, cargo_cost_estimated, cargo_cost_actual NULL, cost_state ENUM(estimated, actual))`
- `returns(id, order_line_id, return_date, reason, refund_amount, return_cargo_cost_estimated, return_cargo_cost_actual NULL, cost_state)`
- `settlement_records(id, tenant_id, store_id, external_ref, record_type ENUM(sale, commission, cargo, service_fee, penalty, ad_spend, refund, other), amount, vat_amount, transaction_date, order_line_id NULL, matched BOOLEAN DEFAULT false)`
- `cargo_invoices(id, store_id, invoice_no, period, total, lines JSONB)`
- `ad_spend(id, store_id, date, campaign_id, campaign_name, spend, product_id NULL)` — Faz 4
- `promotions(id, store_id, name, type, seller_share_rate, start_at, end_at)` — Faz 4

### 5.4 Hesap sonuçları
- `line_profit(id, order_line_id UNIQUE, revenue_net_vat, cost_cogs, cost_commission, cost_cargo, cost_service_fee, cost_return, cost_ad_alloc, vat_net, profit NUMERIC(14,4), margin_pct, computed_at, is_final BOOLEAN)`
- `profit_revisions(id, order_line_id, field, old_value, new_value, reason, revised_at)`
- `reconciliation_diffs(id, store_id, period, settlement_record_id, expected, actual, diff, status ENUM(open, explained, resolved), note)`
- `alerts(id, tenant_id, type, severity, entity_ref, message, created_at, acknowledged_at NULL)`

---

## 6. Kâr Motoru

### 6.1 Formül (sipariş satırı bazında)
```
satis_kdv_haric   = line_gross / (1 + vat_rate)
komisyon          = line_gross * commission_rate          (KDV dahil gelir üzerinden; Trendyol pratiği doğrulanacak)
kargo             = shipment.cargo_cost_actual  ?? desi_bazli_tahmin(desi, carrier_tarife)
hizmet_bedeli     = platform_siparis_basi_sabit (store ayarından; sipariş satırlarına tutar bazlı paylaştır)
iade_maliyeti     = return varsa: refund + gidis_kargo + donus_kargo (satis geliri sıfırlanır)
reklam_pay        = Faz 4: gün+ürün bazlı ad_spend / satılan adet (allocation)

indirilecek_kdv   = kdv(cogs) + kdv(komisyon) + kdv(kargo) + kdv(hizmet_bedeli)
net_kdv           = satis_kdv - indirilecek_kdv

kar = satis_kdv_haric ... (eşdeğer gösterim):
kar = line_gross - cogs - komisyon - kargo - hizmet_bedeli - iade_maliyeti - reklam_pay - net_kdv
marj = kar / line_gross
```

### 6.2 Yeniden hesaplama tetikleyicileri
- Kargo faturası kalemi eşleşince (`cargo_cost_estimated → actual`)
- Hakediş kaydında komisyon farkı görülünce
- `sku_costs`'a geçmişe etkili yeni maliyet girilince (yalnızca `effective_from` sonrası siparişler)
- İade kaydı düşünce
Her tetikleyici `profit_revisions`'a log atar. Dashboard'da "revize edilen kâr" ayrı gösterilir.

### 6.3 Edge-case listesi (test senaryoları olarak yazılacak)
1. Kısmi iade (3 adetlik satırın 1 adedi iade)
2. Değişim (iade + yeni gönderi, çift kargo)
3. Kampanya indirimi: satıcı payı vs platform payı (promotions.seller_share_rate)
4. Farklı KDV oranları (%1 gıda vs %20 genel) — Kahveji/Alessi ikisini de kapsar
5. İptal (kargolanmadan) → maliyet kalemleri sıfır
6. Aynı pakette çoklu satır → kargo maliyetinin satırlara desi-ağırlıklı dağıtımı
7. Ceza/tazmin kalemleri (settlement `penalty`) → sipariş eşleşmezse store-level gider
8. Komisyon oranı değişimi (tarihli commission_rates ile çözülür)

---

## 7. Hakediş Mutabakatı (Faz 2 — bizim katil özellik)

1. `settlement_records` çekilir, `order_line_id` eşleştirmesi yapılır (external ref üzerinden).
2. Her kalem türü için beklenen değer hesaplanır: komisyon = bizim hesapladığımız; kargo = fatura/tahmin; vs.
3. `|expected - actual| > eşik` (varsayılan 0.05 TL) → `reconciliation_diffs` kaydı + alert.
4. UI'da dönem bazlı mutabakat ekranı: eşleşen %, açık farklar, "explained" işaretleme akışı.
5. Eşleşmeyen settlement kalemleri (sipariş bulunamayan) ayrı kuyrukta gösterilir.

---

## 8. API Yüzeyi (FastAPI)

```
POST /auth/login                          # JWT
GET  /stores                              # mağaza listesi + sync durumu
POST /stores/{id}/credentials             # şifreli kaydet
POST /stores/{id}/sync                    # manuel tetik

GET  /reports/dashboard?from&to&brand&store      # KPI: ciro, kâr, marj, iade oranı, revize etkisi
GET  /reports/sku-margins?from&to&sort           # SKU bazlı marj listesi
GET  /reports/orders?filters                     # satır bazlı kâr dökümü
GET  /reports/pnl?group_by=brand|store|month     # marka bazlı P&L

GET  /reconciliation/{store_id}?period           # mutabakat özeti + diff listesi
POST /reconciliation/diffs/{id}/resolve

GET/POST /costs/{product_id}                     # versiyonlu maliyet CRUD
POST /costs/bulk-upload                          # xlsx import (sku, maliyet, effective_from)

GET  /alerts?status=open

# Ürün & Fiyat Çalışma Alanı (bkz. bölüm 13)
GET  /exports/price-list.xlsx?brand&channel&category   # export = import şablonu (tek format)
POST /imports/price-list?dry_run=true                  # multipart xlsx; dry_run → diff önizleme
POST /imports/price-list?dry_run=false                 # onaylı yazma; hatalar xlsx olarak döner
GET  /products/drafts  POST /products/drafts           # taslak ürün + anlık kâr analizi
POST /products/drafts/{id}/promote                     # taslağı gerçek ürüne çevir
GET/POST /scenarios?product_id                         # kayıtlı senaryolar
POST /imports/commission-tariff?valid_from&dry_run     # Trendyol tarife Excel'i olduğu gibi yüklenir (12B.2)
POST /scenarios/compare                                # 2-3 senaryo yan yana sonuç
POST /scenarios/target-margin                          # hedef marj → minimum fiyat
GET  /exports/scenarios.xlsx  POST /imports/scenarios  # senaryo round-trip
```

ops.mokka entegrasyonu: Kavun JWT'yi ops.mokka SSO token'ından exchange eder (`POST /auth/sso-exchange`); UI ops.mokka menüsünden linklenir.

---

## 9. Sync Zamanlaması (Celery beat)

| Job | Sıklık |
|---|---|
| fetch_orders | 15 dk |
| fetch_returns | 1 saat |
| fetch_settlements | günlük 06:00 |
| fetch_cargo_invoices | günlük 06:30 |
| fetch_products + commissions | günlük 03:00 |
| recompute_pending_profits | settlement/cargo joblarından sonra zincirleme |
| reconciliation_run | günlük 07:00 |
| alert_scan | 1 saat |

---

## 10. Frontend (Next.js) Ekranları

> Tüm ekranlar Brand Workspace context'i içinde çalışır (bölüm 3A): `/alessi/...` ve `/kahveji/...` ayrı modül ağaçları; Holding görünümü `/holding/...` altında ayrı, salt-okunur rapor seti.

1. **Dashboard** — dönem seçici; ciro / net kâr / marj% / iade% kartları; marka kırılımı; günlük kâr grafiği; "tahmini vs kesinleşmiş" ayrımı
2. **SKU Marj Listesi** — sıralanabilir tablo, negatif marj kırmızı, filtre: marka/kanal/kategori
3. **Sipariş Detayı** — satır bazlı maliyet dökümü (waterfall: satış → kâr)
4. **Mutabakat** — dönem bazlı eşleşme özeti + diff tablosu
5. **Maliyet Yönetimi** — SKU maliyet geçmişi, xlsx toplu yükleme
6. **Uyarılar** — açık alertler, acknowledge akışı
7. **Ayarlar** — mağaza + credential yönetimi, hizmet bedeli, kargo tarife tablosu
8. (Faz 4) **Fiyatlandırma** ve **Promosyon Simülatörü**

Tasarım: **açık tema (light), premium finans/ops estetiği** — detaylı tasarım sistemi için `KAVUN_Design_Brief.md` bağlayıcıdır (Claude Design çıktısı bu brief'e göre üretilecek). Türkçe UI, TL formatı `1.234,56 ₺`.

---

## 11. Faz Planı ve Kabul Kriterleri

### Faz 1 — Trendyol MVP (hedef: 4-6 hafta)
- Docker compose ayağa kalkar; Trendyol sync (orders, products, commissions) çalışır
- Maliyet girişi (tekil + xlsx) çalışır
- Kâr motoru estimated modda hesaplar; Dashboard + SKU listesi + sipariş detayı canlı
- **Kabul:** rastgele 20 sipariş için elle hesaplanan kârla motor çıktısı kuruş kuruş eşit

### Faz 1.5 — Ürün & Fiyat Çalışma Alanı + Komisyon Tarife Motoru + Fatura/Stok/WAC (bölüm 12A + 12B + 12C; hedef: +4-5 hafta)
- Fiyat listesi export/import round-trip, taslak ürün akışı, senaryo motoru + karşılaştırma + hedef marj çözücü
- Komisyon çözümleme hiyerarşisi, tarife Excel yükleme, günlük snapshot + değişiklik alerti + etki analizi, toplu tarife senaryosu
- PDF alış faturası ayrıştırma + öğrenen SKU eşleştirme + inventory ledger + hareketli ağırlıklı ortalama maliyet
- **Kabul:** bölüm 12A.6, 12B.5 ve 12C.11'deki kriterler

### Faz 2 — Kesinleşme + Mutabakat
- Cargo invoice ve settlements sync; estimated→actual geçişleri; profit_revisions
- Reconciliation modülü + UI
- **Kabul:** bir aylık gerçek hakediş dökümü ile motor sonuçları %99+ satır eşleşmesi; farklar diff listesinde açıklanabilir

### Faz 3 — Çoklu kanal
- Hepsiburada, N11, Shopify adapterleri (aynı interface, motor değişmez)
- **Kabul:** dört kanal tek dashboard'da, marka bazlı P&L doğru

### Faz 4 — Karar araçları
- Reklam harcaması sync + allocation; promosyon simülatörü; hedef marj → fiyat hesaplayıcı; alert kuralları (negatif marj SKU, iade eşiği, marj düşüş trendi)

### Faz 5 — SaaS hardening (opsiyonel/ileri)
- Tenant onboarding akışı, kullanım ölçümü, faturalama entegrasyonu, KVKK veri işleme sözleşme akışı, rate-limit izolasyonu

---

## 12C. Alış Faturası (PDF) + Stok + Hareketli Ağırlıklı Ortalama Maliyet — Faz 1.5

> Maliyetin doğruluk kaynağı elle giriş değil, alış faturasıdır. Yöntem: hareketli ağırlıklı ortalama (moving weighted average cost, WAC).

### 12C.1 Formül (bağlayıcı)
```
yeni_ortalama = (eldeki_adet × mevcut_ortalama + gelen_adet × gelen_birim_maliyet)
                ─────────────────────────────────────────────────────────────────
                              (eldeki_adet + gelen_adet)

Örnek: 34 adet @100 TL stok + 100 adet @120 TL alış
     = ((34×100)+(100×120)) / (34+100) = 15.400 / 134 = 114,9254 TL
```
- Satış, iade-red, fire → stok düşer, ortalama DEĞİŞMEZ (çıkışlar mevcut ortalamadan).
- Yalnızca girişler (alış faturası, iade-kabul kendi maliyetiyle, sayım fazlası) ortalamayı günceller.
- COGS = satış adedi × satış tarihindeki geçerli ortalama. `line_profit.cost_cogs` buradan beslenir.
- Tüm ara hesaplar `Decimal`, ortalama `NUMERIC(14,6)` hassasiyetle saklanır (yuvarlama birikimi önlenir).

### 12C.2 Veri modeli ekleri
- `suppliers(id, tenant_id, name, vkn, default_currency)`
- `purchase_invoices(id, tenant_id, supplier_id, invoice_no, invoice_date, currency, fx_rate NUMERIC(12,6), landed_cost_extra NUMERIC(14,2) DEFAULT 0, pdf_path, status ENUM(parsed, review, confirmed), created_at)`
  - `fx_rate`: fatura para birimi TL değilse fatura tarihindeki kur (TCMB döviz satış varsayılan; elle override edilebilir). Orijinal tutarlar da satırda saklanır.
  - `landed_cost_extra`: nakliye + gümrük + sigorta toplamı; onayda satırlara **tutar ağırlıklı** dağıtılır → satır bazlı landed unit cost.
- `purchase_invoice_lines(id, invoice_id, raw_text, product_id NULL, qty NUMERIC(12,3), unit_price_original, unit_price_try, vat_rate, landed_unit_cost_try, match_status ENUM(auto, manual, unmatched))`
- `supplier_product_map(id, supplier_id, raw_name_normalized, barcode NULL, product_id, confirmed_at)` — öğrenen eşleştirme belleği
- `inventory_ledger(id, tenant_id, product_id, movement ENUM(purchase_in, sale_out, return_in, return_out, adjustment, opening), qty_delta, unit_cost_at_movement, avg_cost_after NUMERIC(14,6), on_hand_after, ref_type, ref_id, moved_at)` — append-only
- `sku_cost_state(product_id PK, on_hand_qty, avg_cost NUMERIC(14,6), last_movement_at)` — güncel durum (ledger'dan türetilebilir; replay ile yeniden kurulabilir olmalı)
- `sku_costs` mevcut tablosu korunur: her WAC değişimi `source=invoice_wac, invoice_ref, effective_from=fatura_tarihi` ile yeni versiyon satırı yazar → kâr motoru tarih bazlı maliyet çözümünü değiştirmeden kullanır.

### 12C.3 PDF ayrıştırma akışı
1. Upload → `pdf_path` kaydı; metin çıkarımı: önce pdfplumber (metin tabanlı e-fatura/e-arşiv PDF'leri), metin yoksa OCR fallback (tesseract, tur dil paketi).
2. Satır çıkarımı: LLM destekli ayrıştırma (Claude API) — çıkarılan alanlar: ürün adı, adet, birim fiyat, KDV oranı, satır toplamı. Model çıktısı **asla doğrudan yazılmaz**; her zaman review ekranından geçer.
3. Doğrulama kuralları: satır toplamları ± fatura genel toplamı tutmalı (tolerans 0,10 TL); tutmuyorsa fatura `review` durumunda kalır ve uyarı gösterilir.
4. SKU eşleştirme sırası: barkod → `supplier_product_map` (normalize edilmiş ürün adı) → fuzzy öneri (kullanıcı onayı şart). Onaylanan her manuel eşleştirme map'e yazılır → **aynı tedarikçiden aynı ürün bir daha sorulmaz.**
5. Kullanıcı "Onayla" → invoice `confirmed`; her satır için `inventory_ledger`'a `purchase_in` hareketi + WAC güncellemesi + `sku_costs` versiyonu atomik tek transaction'da yazılır.
6. Onaylanmış fatura düzenlenemez; hata varsa ters kayıt (`adjustment`) + yeniden giriş. (Muhasebe disiplini: geçmiş silinmez.)

### 12C.4 Açılış stoku ve kenar durumlar
- **Açılış (devir) girişi:** ürünler ekranından tek seferlik `opening` hareketi (adet + birim maliyet) veya xlsx toplu yükleme (12A şablonuna `Açılış Adet` sütunu eklenir). Sistem kullanılmaya başlarken eldeki 34 adet @100 TL buradan girilir.
- **Negatif stok:** satış sync'i stokta olmayan adedi düşerse hareket yine yazılır, `on_hand_after < 0` → alert ("stok kaydı eksik: X SKU"). Ortalama maliyet negatif stokta değişmez; ilk alış girişinde normalleşir.
- **Kısmi iade-kabul:** iade edilen ürün tekrar satılabilir durumdaysa `return_in` (satış anındaki COGS maliyetiyle girer, ortalamayı günceller); hurdaysa stok girmez, kâr motorunda zarar kalır.
- **EUR faturalar (Alessi):** `unit_price_original` EUR saklanır; TL maliyet kur ile hesaplanır. Raporlarda "maliyetin kur bileşeni" ayrıştırılabilir (kur maruziyeti analizi bu veriden beslenir).
- **Aynı üründe iki tedarikçi / iki para birimi:** sorun değil — WAC ürün bazındadır, kaynak fark etmez; TL'ye çevrilmiş landed cost havuza girer.

### 12C.5 API ve ekranlar
```
POST /purchase-invoices              # PDF upload → parse başlat
GET  /purchase-invoices?status      
GET  /purchase-invoices/{id}         # satırlar + eşleştirme durumu
POST /purchase-invoices/{id}/lines/{line_id}/match   # manuel SKU eşleştirme
POST /purchase-invoices/{id}/confirm # atomik: ledger + WAC + sku_costs
POST /inventory/opening              # açılış stoku (tekil + xlsx)
GET  /inventory?filters              # SKU bazlı: eldeki adet, ortalama maliyet, son hareket
GET  /inventory/{product_id}/ledger  # hareket geçmişi (maliyetin izi)
```
- **Fatura Yükleme** ekranı: sürükle-bırak PDF → ayrıştırılmış satır tablosu → eşleştirme onayı → toplam kontrol → Onayla
- **Stok & Maliyet** ekranı: SKU listesi (eldeki adet, ortalama maliyet, stok değeri), satır detayında ledger zaman çizelgesi ("maliyet neden değişti" tek bakışta)

### 12C.7 İthalat Dosyası Modu (Alessi ve tüm ithal alımlar) — ZORUNLU
> Tek fatura + tek "ekstra" alanı ithalat için yetersizdir. İthal alım = **ithalat dosyası**: mal faturası + beyanname + masraf kalemleri.

- `import_files(id, tenant_id, supplier_id, file_no, beyanname_no NULL, beyanname_date, currency, fx_rate_beyanname NUMERIC(12,6), status ENUM(open, confirmed), created_at)`
- `import_cost_items(id, import_file_id, item_type ENUM(mal_bedeli, navlun, sigorta, gumruk_vergisi, gumruk_musavirligi, ardiye_liman, diger), amount_original, currency, amount_try, vendor NULL, doc_ref NULL)`
  - Mal bedeli EUR faturadan; diğer kalemler kendi para birimi ve faturasıyla girilir.
  - **İthalat KDV'si maliyet kalemi DEĞİLDİR** — gümrükte ödenir, indirilecek KDV'dir. `import_cost_items`'a girilmez; ayrı alan `import_files.import_vat_paid` olarak kayıt altına alınır (nakit akışı ve KDV raporu için), landed cost hesabına ASLA dahil edilmez.
  - Not: AB menşeli sanayi ürünlerinde Gümrük Birliği gereği gümrük vergisi çoğunlukla 0'dır; alan yine de tutulur (menşe/istisna değişimlerine dayanıklılık).
- Landed cost dağıtımı: toplam masraf kalemleri, dosyadaki mal satırlarına **mal bedeli ağırlıklı** dağıtılır → satır bazlı `landed_unit_cost_try`. Onayda 12C.3 adım 5 ile aynı atomik zincir çalışır (ledger + WAC + sku_costs).
- Yurtiçi basit alımlar için 12C.2'deki tek faturalı akış geçerliliğini korur; `landed_cost_extra` alanı yalnızca bu basit modda kullanılır.

### 12C.8 Kur farkı takibi (ödeme gerçeği)
- Maliyet, **beyanname (veya fatura) tarihi kuruyla sabitlenir** ve WAC'a öyle girer — muhasebeyle tutarlı, geriye dönük oynamaz.
- `supplier_payments(id, supplier_id, import_file_id NULL, invoice_id NULL, pay_date, amount_original, currency, fx_rate_payment, fx_diff_try NUMERIC(14,2))` — ödeme kaydedildiğinde kur farkı otomatik hesaplanır.
- Kur farkı **ürün maliyetine girmez**; marka bazlı P&L'de ayrı satır olarak raporlanır: "Alessi — kur farkı gideri/geliri". Böylece marj erimesinin ürün mü kur mu kaynaklı olduğu ayrışır.
- Rapor: `GET /reports/fx-exposure?brand` — açık (ödenmemiş) EUR pozisyonu, ortalama maliyet kuru, güncel kurla revalüasyon etkisi.

### 12C.9 D2B / manuel satış kanalı (Alessi kurumsal satışlar)
- `channels` tablosuna `manual` kanalı eklenir; `stores` altında "Alessi D2B" mağazası tanımlanır.
- B2B satış girişi: xlsx import (`POST /imports/b2b-sales`) — sütunlar: tarih, müşteri, SKU, adet, birim fiyat, iskonto %, KDV. İleride Logo/Paraşüt connector'ı aynı arayüzü doldurur.
- Bu satışlar normal `orders/order_lines` olarak yazılır → stok düşer (WAC korunur), kâr motoru komisyonsuz/pazaryeri-masrafsız hesaplar, marka P&L'ine dahil olur.
- `customers(id, tenant_id, name, tier, default_discount_pct)` — müşteri kademesi bazlı iskonto analizi (hangi tier ne marj bırakıyor raporu).

### 12C.10 Fire/hasar ve marka fiyat disiplini
- `inventory_ledger.movement` enum'una `damage` eklenir (kırılma/hasar; neden alanı zorunlu). Hasar, stoktan mevcut ortalama maliyetle düşer ve marka P&L'inde "fire gideri" satırına yazılır. Rapor: SKU/dönem bazlı hasar oranı (porselen-cam ürün için kritik metrik).
- `products` tablosuna: `msrp NUMERIC(14,2) NULL`, `min_margin_floor_pct NULL` (marka bazlı varsayılan `brands` tablosundan devralınır). Alert kuralı: herhangi bir kanalda liste fiyatı MSRP disiplinini bozuyor veya hesaplanan marj tabanın altındaysa → alert. Senaryo motoru ve hedef marj çözücüsü tabanı uyarı olarak gösterir (engellemez).

### 12C.11 Kabul kriterleri (çekirdek + Alessi modu)
- Formül testi: 34@100 + 100@120 → ortalama 114,9254; ardından 50 satış → ortalama değişmez, on_hand 84; ardından 20@130 alış → yeni ortalama doğru
- Ledger replay: `sku_cost_state` tablosu silinip ledger'dan yeniden üretildiğinde birebir aynı sonuç
- Gerçek bir e-arşiv fatura PDF'i fixture olarak repoda; parser + review + confirm zinciri uçtan uca test
- Onaylanmış faturayı değiştirme girişimi → 409 hata; düzeltme yalnızca adjustment ile
- İthalat dosyası testi: EUR mal faturası + TL navlun + EUR sigorta + müşavirlik → satır bazlı landed cost elle hesapla birebir; ithalat KDV'sinin maliyete girmediği asserte edilir
- Kur farkı testi: beyanname kuru 37,50, ödeme kuru 39,20 → fx_diff doğru; WAC değişmediği asserte edilir
- D2B satış importu → stok düşer, komisyon 0, marka P&L'de doğru kanalda görünür
- Damage hareketi → stok ve fire gideri doğru, ortalama maliyet değişmez

---

## 12B. Komisyon Tarife Motoru — Faz 1.5 kapsamında

> Komisyon statik parametre değil, versiyonlu tarife verisidir. Motor ve senaryolar her zaman bu modülden çözer.

### 12B.1 Çözümleme hiyerarşisi (`resolve_commission(product, store, date) -> (rate, source)`)
1. `settlement_actual` — hakedişte kesinleşmiş oran (yalnızca geçmiş siparişler; ground truth)
2. `api_product` — API'den gelen ürün bazlı güncel oran
3. `api_category` — kategori tarife tablosu (ürün oranı yoksa)
4. `manual` — kullanıcı override (en son çare, UI'da uyarıyla)
- Fonksiyon her zaman `(rate, source)` çifti döner; `line_profit` ve senaryo sonuçlarına `commission_source` alanı eklenir. UI'da tahmin/kesin ayrımı bu alandan gösterilir.
- Tarih bazlı çözüm: `valid_from <= date < valid_to` penceresi; kampanya dönemi kayıtları (`is_campaign_period=true`) aynı pencere mantığıyla normal tarifeyi ezer.

### 12B.2 Tarife Excel yükleme (Melontik paritesi — ZORUNLU özellik)
> Trendyol kategori komisyon tarifelerini dönemsel olarak Excel dosyası halinde yayınlar. Kullanıcı bu dosyayı **Trendyol'dan indirdiği haliyle, formatını değiştirmeden** Kavun'a yükleyebilmelidir.

- Endpoint: `POST /imports/commission-tariff?store_id&valid_from&dry_run=true|false` (multipart xlsx)
- **Esnek parser:** sabit sütun sırası varsayma. Parser başlık satırını arar ve şu alanları fuzzy eşleştirir: kategori adı / kategori kodu / komisyon oranı (+ varsa vade, kampanya dönemi sütunları). Türkçe başlık varyasyonları (`Komisyon %`, `Komisyon Oranı`, `Kategori`, `Ana Kategori`, `Alt Kategori` vb.) desteklenir. Eşleştirme sonucu dry-run önizlemesinde kullanıcıya gösterilir: "Şu sütunu kategori, şu sütunu oran olarak okudum — onaylıyor musun?"
- Çok seviyeli kategori (ana > alt > yaprak) desteklenir; eşleştirme en spesifik seviyeden yapılır. Kavun'daki ürün kategorileriyle eşleşmeyen tarife satırları hata değil, `unmatched` listesi olarak raporlanır (ileride ürün gelirse kullanılır).
- `valid_from` zorunlu (tarifenin yürürlük tarihi; Trendyol duyurusundaki tarih girilir). İleri tarihli yükleme desteklenir → `future_tariff` senaryo modu bu kayıtları kullanır.
- Yükleme anında **otomatik fark analizi**: yüklenen tarife vs şu an geçerli oranlar → değişen kategoriler, etkilenen SKU sayısı, `monthly_profit_impact` (12B.3'teki etki hesabıyla aynı) dry-run yanıtında döner. Yani kullanıcı tarifeyi yüklerken "bu tarife sana ne yapacak" raporunu anında görür.
- Kaynak: bu kayıtlar `source=manual_tariff_upload` olarak yazılır; çözümleme hiyerarşisinde `api_category` ile aynı seviyededir, **daha güncel `valid_from` kazanır**.
- Hepsiburada/N11 tarife dosyaları için aynı parser altyapısı kullanılır (Faz 3'te kanal bazlı başlık sözlükleri eklenir).
- Kabul: gerçek bir Trendyol tarife Excel'i fixture olarak repoya konur; parser bu dosyayı sıfır manuel müdahale ile okur; ileri tarihli yükleme + future_tariff senaryosu uçtan uca test edilir.

### 12B.3 Snapshot ve değişiklik tespiti
- Günlük job (03:00 sync'in parçası): ürün listesi + kategori komisyonları çekilir, `snapshot_date=bugün` ile yazılır.
- Diff: dünkü geçerli oran ≠ bugünkü → `commission_changes` kaydı + alert.
- **Etki analizi:** değişen her ürün/kategori için son 30 gün satış adedi × birim ciro × oran farkı = `monthly_profit_impact`. Alert mesajı: "X kategorisinde komisyon %21,5 → %23,0. Mevcut satış hızıyla aylık kâr etkisi: −4.820 TL. Negatif marja düşen SKU: 3 (listele)."
- Hakediş mutabakatı (bölüm 7) ile çift yönlü doğrulama: settlement'taki gerçek oran, snapshot'taki orandan farklıysa `reconciliation_diffs` + tarife kaydı `settlement_actual` olarak güncellenir.

### 12B.4 Senaryolarla entegrasyon
- `pricing_scenarios` tablosuna ek alanlar: `commission_mode ENUM(current, pinned, future_tariff)`, `pinned_commission_rate NULL`, `future_tariff_date NULL`
  - `current`: çözümleme hiyerarşisinden bugünkü oran
  - `pinned`: kullanıcının girdiği sabit oran (what-if)
  - `future_tariff`: duyurulmuş ileri tarihli tarife varsa o tarihteki oran
- **Toplu tarife senaryosu** endpoint'i: `POST /scenarios/tariff-impact` — girdi: `{scope: category|all, new_rate | rate_delta}`; çıktı: tüm etkilenen SKU'lar için mevcut fiyatla yeni marj + hedef marjı korumak için gereken yeni fiyat listesi (xlsx olarak indirilebilir). Kullanım: "komisyon %1,5 artarsa katalogda ne olur" sorusu tek çağrıda.
- Hedef marj çözücüsü (12A.4) `commission_mode` parametresini kabul eder.

### 12B.5 Kabul kriterleri
- Aynı ürün için üç kaynaktan (api_product, api_category, manual) çözümleme testleri: hiyerarşi sırası doğru
- Snapshot diff testi: fixture'da oran değiştir → change kaydı + doğru etki tutarı üretilir
- Tarife senaryosu round-trip: `tariff-impact` çıktısındaki önerilen fiyat, motorla geri hesaplanınca hedef marjı ±0,01 puan tutturur
- Settlement'tan gelen gerçek oran ile snapshot çelişkisi → reconciliation diff üretilir (sessiz geçilmez)

---

## 12A. Ürün & Fiyat Çalışma Alanı (Excel Round-Trip + Senaryo Motoru) — Faz 1.5

> Kural: export edilen dosya = import şablonu. İkinci bir şablon formatı YOK.

### 12A.1 Fiyat listesi xlsx formatı (openpyxl ile üretilir/okunur)
Sütunlar: `SKU | Ürün Adı | Marka | Kanal | KDV % | Desi | Alış Maliyeti | Satış Fiyatı | Komisyon % | Kargo (tahmini) | Hizmet Bedeli | Net Kâr | Marj %`
- İlk satırda gizli meta (şablon versiyonu: `kavun-template-v1`) — import'ta versiyon kontrolü yapılır.
- `Net Kâr` ve `Marj %` export'ta formül sonucu olarak yazılır; import'ta bu sütunlar **yok sayılır** (tek doğruluk kaynağı motor).
- Import upsert anahtarı: `(SKU, Kanal)`. Yeni SKU satırı = yeni ürün + maliyet kaydı; mevcut SKU = maliyet/fiyat güncellemesi.
- Maliyet değişiklikleri `sku_costs`'a `effective_from = bugün` (veya dosyadaki opsiyonel tarih sütunu) ile versiyonlu yazılır — geçmiş kâr kayıtları bozulmaz.

### 12A.2 Import akışı
1. `dry_run=true` → hiçbir yazma yok; dönen JSON: `{yeni: n, guncelleme: m, hata: k, satirlar: [...]}` — UI diff önizleme ekranı gösterir.
2. Kullanıcı onaylar → `dry_run=false` ile aynı dosya gönderilir, işlenir.
3. Hatalı satırlar (eksik zorunlu alan, negatif fiyat, bilinmeyen kanal, KDV oranı geçersiz) reddedilir; yanıt olarak orijinal dosya + "Hatalar" sheet'i (satır no + hata açıklaması) xlsx döner.
4. Her import `import_batches(id, filename, user, dry_run, yeni, guncelleme, hata, created_at)` tablosuna loglanır; batch geri alınabilir olmak zorunda DEĞİL (versiyonlu maliyet zaten geçmişi korur).

### 12A.3 Taslak ürün (draft product)
- `product_drafts(id, tenant_id, brand_id, name, sku_onerisi, alis_maliyeti, hedef_satis_fiyati, kanal, vat_rate, desi, created_at, status ENUM(draft, promoted, discarded))`
- Kayıt anında motor komisyon (kategori bazlı tahmin) + kargo (desi tarife) + hizmet bedeli ile kâr analizini hesaplar ve yanıtta döner.
- `promote` → products + sku_costs + sku_logistics kayıtları oluşur, taslak `promoted` olur.
- Excel import'ta `SKU` boş bırakılan satırlar otomatik taslak olarak da alınabilir (`?as_draft=true` parametresi).

### 12A.4 Senaryo motoru
- `pricing_scenarios(id, product_id, name, satis_fiyati, kampanya_indirim_pct, kampanya_satici_pay_pct, kargo_kim_oder ENUM(satici, alici, platform), adet_varsayimi, created_by, created_at)`
- Hesap: mevcut kâr motorunun aynı fonksiyonu, girdiler senaryodan → çıktı: birim kâr, marj %, toplam kâr, break-even fiyat.
- **Deterministik**: talep tahmini, elastikiyet, olasılık YOK. Girdi → hesap → sonuç.
- `compare`: en fazla 3 senaryo, yan yana tablo (UI'da sütun karşılaştırma).
- `target-margin`: hedef marj % girdisi → çözücü minimum satış fiyatını iteratif değil kapalı formülle döndürür (formül: fiyat = f(maliyet, komisyon%, kargo, hizmet, KDV, hedef marj) — cebirsel çözüm, engine'de türetilecek ve test edilecek).
- Senaryo xlsx round-trip: export şablonu senaryo sütunlarını içerir; import sonrası hesaplanmış sonuç sütunlarıyla dolu dosya yanıt olarak iner.

### 12A.5 UI ekran ekleri
- **Ürün Çalışma Alanı** ekranı: fiyat listesi tablo + "Excel'e Aktar" / "Excel'den Yükle" butonları + import diff modal
- **Yeni Ürün Değerlendir** ekranı: form → anlık kâr kartı → "Ürüne Dönüştür"
- **Senaryolar** ekranı: ürün seç → senaryo listesi → karşılaştırma görünümü + hedef marj hesaplayıcı

### 12A.6 Kabul kriterleri (Faz 1.5)
- Export → hiç değiştirmeden import → dry_run sonucu: 0 yeni, 0 güncelleme, 0 hata (idempotency kanıtı)
- 500 satırlık dosya < 10 sn işlenir
- Hedef marj çözücüsünün sonucu, o fiyatla motor hesabına geri verildiğinde hedef marjı ±0,01 puan tutturur (round-trip testi)
- Taslak → promote → sipariş kârı hesaplama zinciri uçtan uca testte kırılmaz

---

## 12. Claude Code'a Çalışma Talimatları

1. Önce Faz 1 kapsamını uygula; Faz 2+ için sadece şema alanlarını hazırla, kod yazma.
2. Trendyol API çağrılarını `connectors/trendyol.py` içinde izole et; endpoint URL'lerini ve alan adlarını **developers.trendyol.com güncel dokümanından doğrula**, tahmin etme.
3. Tüm parasal hesaplar `decimal.Decimal` ile; test coverage: engine %90+.
4. Edge-case listesi (bölüm 6.3) birebir pytest senaryosu olacak; fixture'lar `tests/fixtures/` altında gerçek API yanıt formatında JSON.
5. Migration'lar Alembic ile; seed script: mokka tenant, 2 brand, 4 channel.
6. `.env.example` dosyası: DB, Redis, KAVUN_ENCRYPTION_KEY, store credential'ları için placeholder.
7. Sync job'ları önce `--dry-run` modu ile yaz (raw_events'e yazar, normalize etmez) — ilk gerçek veriyle şema doğrulaması böyle yapılacak.
8. README: kurulum, ilk mağaza bağlama, replay komutu, mutabakat akışı.
