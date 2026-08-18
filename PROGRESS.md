# KAVUN İlerleme

**TOPLAM: %31** ▓▓▓▓▓▓░░░░░░░░░░░░░░
Son güncelleme: 2026-08-18 23:20 · Aktif görev: KVN-07
Preview: ✅ ayakta · localhost:3000

| ID     | İş Akışı                                                    | Ağırlık | Durum       |
|--------|-------------------------------------------------------------|---------|-------------|
| KVN-01 | Proje iskeleti + Docker Compose + CI (ruff/mypy/pytest)     | 4       | ✅ Bitti    |
| KVN-02 | Veri modeli + Alembic migration'lar + seed                  | 5       | ✅ Bitti    |
| KVN-03 | Tenancy + Brand-scope middleware (fail-closed)              | 5       | ✅ Bitti    |
| KVN-04 | Credential vault (Fernet) + mağaza yönetimi                 | 3       | ✅ Bitti    |
| KVN-05 | Trendyol connector — orders/products/commissions sync       | 8       | ✅ Bitti    |
| KVN-06 | raw_events + normalize pipeline + replay komutu             | 6       | ✅ Bitti    |
| KVN-07 | Kâr motoru — çekirdek hesap (KDV netleştirme dahil)         | 8       | ⏳ Sırada   |
| KVN-08 | Kâr motoru — edge-case test paketi (8 senaryo)              | 6       | ⏳ Sırada   |
| KVN-09 | Dashboard + SKU marj listesi + sipariş detayı (waterfall)   | 7       | ⏳ Sırada   |
| KVN-10 | Excel round-trip — fiyat listesi export/import + diff       | 6       | ⏳ Sırada   |
| KVN-11 | Taslak ürün akışı                                           | 3       | ⏳ Sırada   |
| KVN-12 | Senaryo motoru + karşılaştırma + hedef marj çözücü          | 6       | ⏳ Sırada   |
| KVN-13 | Komisyon çözümleme hiyerarşisi + snapshot/diff + etki       | 6       | ⏳ Sırada   |
| KVN-14 | Tarife Excel yükleme (esnek parser)                         | 4       | ⏳ Sırada   |
| KVN-15 | PDF fatura ayrıştırma + öğrenen SKU eşleştirme + onay       | 7       | ⏳ Sırada   |
| KVN-16 | Inventory ledger + WAC motoru + açılış stoku                | 7       | ⏳ Sırada   |
| KVN-17 | İthalat dosyası modu + kur farkı takibi (Alessi)            | 5       | ⏳ Sırada   |
| KVN-18 | D2B kanal + fire/hasar + MSRP disiplini                     | 3       | ⏳ Sırada   |
| KVN-19 | Workspace UI (Alessi/Kahveji modülleri + Holding)           | 5       | ⏳ Sırada   |
| KVN-20 | Golden dataset doğrulama + uçtan uca kabul turu             | 6       | ⏳ Sırada   |

Toplam ağırlık: 100 · Biten ağırlık: 31

---

## Oturum özetleri

### 2026-08-18 — KVN-06 bitti

**Ne bitti:** Normalize pipeline, `replay` komutu ve zamanlanmış işler. Testler:
164 test yeşil, coverage %96.

**Ne kuruldu:**
- `services/normalize.py`: ham olay → `orders`, `order_lines`, `shipments`,
  `product_channel_map`. Upsert anahtarları: sipariş `(tenant, store, external_order_id)`,
  satır `(order_id, external_line_id)`, eşleme `(store_id, external_product_id)`.
- `python -m app.cli normalize` (işlenmemiş olaylar) ve
  `python -m app.cli replay --channel trendyol --from 2026-08-01 [--store] [--to] [--dry-run]`
- Celery zinciri: sync başarılıysa normalize otomatik tetiklenir; beat programı
  `normalize_pending` 15 dk, `ensure_raw_event_partitions` 02:30.

**Kabul kriteri (spec §3.2) kanıtlandı — testte VE canlı ortamda:** normalize tablolar
tamamen silindi, `replay` ham olaylardan birebir aynı siparişleri/satırları/gönderileri
geri kurdu; `raw_events` hiç değişmedi.

**Kararlar / notlar:**
- **Normalize ürün YARATMAZ.** Katalog Kavun'un doğruluk kaynağıdır (fiyat listesi
  Excel'i, KVN-10); kanal ürün olayı yalnızca `product_channel_map` eşlemesini kurar.
  Eşleşmeyen sipariş satırı düşürülmez, `product_id` boş kalır — kâr motoru maliyetsiz
  satırı raporlayabilsin.
- **KDV oranı katalogdan alınır**, kanaldan değil: ürün eşleşmişse `products.vat_rate`
  kullanılır. Trendyol'un `vatBaseAmount` alanının birimi dokümanda net değil
  (`TODO(verify)`), eşleşmeyen satırda geri düşüş olarak kullanılıyor.
- **Kesinleşmiş maliyet ezilmez:** `cost_state=actual` olan gönderinin maliyeti yeniden
  normalize'de güncellenmez (spec §3.4). Testi var.
- Replay, etkilenen satırların `line_profit` kayıtlarını da siler; kâr motoru (KVN-07)
  yeniden hesaplayacak. Sahte kâr kaydı bırakılmaz.
- KVN-02'de not edilen partition riski kapatıldı: `ensure_raw_event_partitions` job'ı
  gelecek ayların partition'larını açıyor, sync de yazmadan önce ayın partition'ını
  garanti ediyor.

**Bilinen risk:** Normalize şu an tüm ham olayları tek turda (limit 5.000) işliyor.
Gerçek hacimde (yüz binlerce olay) job süresi uzayabilir; KVN-20 kabul turunda
toplu işleme/batch boyutu ölçülmeli.

### 2026-08-18 — KVN-05 bitti

**Ne bitti:** Trendyol connector'ı, sync servisi ve manuel tetikleme ucu. Testler:
148 test yeşil, coverage %97.

**Doğrulama (spec §12.2 — tahmin YOK):** tüm uçlar ve alan adları
developers.trendyol.com'dan doğrulandı:
- Siparişler `GET /order/sellers/{sellerId}/orders` — `size` max 200, tarih aralığı
  max 2 hafta, 3 ay geriye, 1.000 istek/dk
- Ürünler (onaylı, **V2**) `GET /product/sellers/{sellerId}/products/approved` —
  `size` max 100, 10.000 üstü `nextPageToken`
- Hakediş (Faz 2) `GET /finance/che/sellers/{sellerId}/settlements` — `commissionRate`
  ve `commissionAmount` burada; aralık max 15 gün
- Kimlik: Basic + `User-Agent: {SellerID} - SelfIntegration` (başlık yoksa 403)

**Ne kuruldu:**
- `connectors/base.py`: sabit adapter arayüzü + `Raw*` DTO'ları (spec §4)
- `connectors/http.py`: ortak istemci — JSON `parse_float=Decimal` (httpx'in `.json()`
  tutarları float'a çevirirdi), 429/5xx'te üstel geri çekilme + jitter, `Retry-After`
  desteği, dakikalık hız sınırına göre pas
- `connectors/trendyol.py`: sayfalama + iki haftalık pencere bölme, statü normalizasyonu,
  varyant bazlı ürün ayrıştırma
- `services/sync.py`: çekilen ham veri `raw_events`'e yazılır, normalize tablolara
  dokunulmaz (spec §12.7 dry-run); yazmadan önce ayın partition'ı garanti edilir
- `POST /{brand}/stores/{id}/sync` + Celery `kavun.sync_store` görevi

**Kritik bulgu — komisyon oranı API'si YOK.** Trendyol'un pazaryeri servislerinde
ürün/kategori komisyon oranı döndüren bir uç bulunmuyor (doküman indeksinde yok; oranlar
Satıcı Yardım Merkezi'nde dönemsel tablo olarak yayımlanıyor). Spec §12B.1'deki
`api_product`/`api_category` kaynakları Trendyol için **doldurulamaz**.
`fetch_commission_rates()` uydurma oran üretmek yerine boş liste döner; komisyon iki
gerçek kaynaktan çözülecek: hakediş (`settlement_actual`, Faz 2) ve tarife Excel
yüklemesi (KVN-14). Bu, KVN-13/14'ün önemini artırıyor — KVN-07 kâr motoru komisyonu
tarife tablosundan çözmek zorunda.

**Canlı testte yakalanan hata:** worker `kavun.sync_store` görevini "unregistered" sayıyordu
(Celery `include` eksikti). Düzeltildi + görev kaydının regresyon testi yazıldı. Uçtan uca
zincir doğrulandı: API → Redis → worker → connector → yapılandırılmış özet log. (Gerçek
Trendyol credential'ı olmadığı ve sandbox dışarı çıkamadığı için çağrı beklendiği gibi
`ConnectorError` ile bitti; yeniden denemeler ve hata özeti loglandı, credential loglara
sızmadı.)

**Kararlar / notlar:**
- Fixture'lar dokümandaki yanıt şemasından üretildi (canlı trafikten kaydedilmiş DEĞİL —
  gerçek mağaza credential'ı yok). `tests/fixtures/trendyol/README.md` bunu açıkça yazıyor;
  ilk gerçek senkrondan sonra `raw_events`'teki örnek yanıtla değiştirilecek.
- V2 onaylı-ürün yanıtında `vatRate` ve `dimensionalWeight` YOK (onaysız ürün filtresinde
  var). `TODO(verify)` ile işaretlendi; Faz 1'de bu iki alan fiyat listesi Excel'inden
  (KVN-10) beslenecek.
- Faz 2 uçları (iade, hakediş, kargo faturası) sahte veri döndürmüyor; `NotImplementedError`
  ile açıkça "yazılmadı" diyor (spec §12.1).

**Bilinen risk:** Product V1 servisleri 10 Ağustos 2026'da geçersiz oldu, Order V2 için son
tarih 15 Ekim 2026. Ürün tarafında zaten V2 kullanılıyor; sipariş ucu hâlâ V1 şemasında
(doküman V1.0.0 diyor). Ekim'den önce Order V2 farkları gözden geçirilmeli — KVN-20 kabul
turuna madde olarak eklenmeli.

### 2026-08-18 — KVN-04 bitti

**Ne bitti:** Credential kasası ve mağaza yönetimi. Testler: 109 test yeşil, coverage %98.

**Ne kuruldu:**
- **Kasa** (`app/core/crypto.py`): Fernet şifreleme, `KAVUN_ENCRYPTION_KEY` virgülle ayrılmış
  çoklu anahtar destekliyor (ilki şifreler, tümü çözer) → kesintisiz anahtar rotasyonu.
  Anahtar yoksa fail-closed: `VaultUnavailableError`, uçlar 503; düz metin asla yazılmaz.
- **Mağaza servisi** (`app/services/stores.py`): credential erişimi HER ZAMAN mağaza
  üzerinden çözülüyor. `store_credentials` tablosunda `brand_id` yok (mağazanın çocuğu);
  bu yolla KVN-03'ün "dolaylı tablo" riski credential'lar için kapatıldı.
- **API** (`/{brand}/stores/...`): mağaza CRUD + credential kaydet/döndür/sil.
  Yazma yetkisi rol bazlı (mağaza: admin+editor, credential: yalnızca admin).
- `make dev` artık `.env` yoksa şifreleme anahtarını kendisi üretiyor;
  `python -m app.cli generate-key` ile de üretilebiliyor.

**Sızıntı testleri (CLAUDE.md §2):**
- DB'de düz metin yok (ciphertext'te secret aranıyor)
- Hiçbir API yanıtı credential içermiyor (liste, durum, kaydetme yanıtları taranıyor)
- Kaydetme akışının logları secret içermiyor
- `CredentialWrite.__repr__/__str__` değerleri maskeliyor (exception/log'a düşse bile)
- Aynı secret her seferinde farklı ciphertext üretiyor (Fernet IV)
- Yabancı anahtarla çözme denemesi hata veriyor ve hata mesajı içerik sızdırmıyor

Canlı ortamda da doğrulandı: kaydedilen credential DB'de `gAAAAA...` Fernet token'ı olarak
duruyor, `LIKE '%CANLI-SECRET%'` sorgusu 0 satır dönüyor, API loglarında secret geçmiyor.

**Kararlar / notlar:**
- Credential durumu yanıtı yalnızca `configured/created_at/rotated_at` döner — maskeli
  önizleme (son 4 hane) bile eklenmedi; ihtiyaç doğarsa bilinçli bir karar olarak eklenir.
- Kanal başına zorunlu alanlar şemada tanımlı (Trendyol: api_key/api_secret/seller_id,
  spec §4). Eksik/boş alan 422 ile reddediliyor — yarım credential sessizce kaydedilmiyor.

**Bilinen risk:** Şifreleme anahtarı şu an `.env` dosyasında düz duruyor (tek makine,
internal kullanım). Üretimde bir secret manager'a (ör. ops.mokka vault) taşınmalı; kod
tarafında değişiklik gerekmez, yalnızca env kaynağı değişir.

### 2026-08-18 — KVN-03 bitti

**Ne bitti:** Marka izolasyonu üç katmanda zorlanıyor ve spec §3A.6'daki kabul kriterlerinin
tamamı test olarak yazıldı. Testler: 86 test yeşil, backend coverage %98.

**Ne kuruldu:**
- **Brand-scope guard** (`app/core/scoping.py`): SQLAlchemy `do_orm_execute` dinleyicisi.
  Marka bağlamı yoksa `BrandScopeViolation` (fail-closed); bağlam varsa sorguya
  `brand_id` filtresi otomatik ekleniyor — hem ORM varlıklarına (`with_loader_criteria`,
  ilişki yüklemeleri dahil) hem de üst seviye FROM tablolarına (count/aggregate sorguları).
  Bilinçli bypass yalnızca `holding_scope()` (audit'li) ve `system_scope()` (seed/replay) ile.
- **İstek bağlamı** (`app/core/context.py`): tenant + aktif marka `contextvars` ile taşınıyor;
  API, worker ve CLI aynı mekanizmayı kullanıyor.
- **Kimlik** (`app/core/security.py`, `/auth/*`): HS256 JWT; token tenant, marka rolleri,
  aktif workspace ve holding yetkisini taşıyor. `sso-exchange` ops.mokka token'ını doğruluyor;
  `dev-login` yalnızca local/ci'de var (üretimde 404).
- **Workspace API'si**: `/{brand}/products`, `/{brand}/alerts`, `/{brand}/import-files`
  (feature bayrağına bağlı) ve `/holding/summary`.

**Kabul kriterleri (spec §3A.6) — hepsi testli ve canlı doğrulandı:**
- Marka filtresi olmayan sorgu → `BrandScopeViolation` (products, orders, alerts + update,
  Core sorgu ve alt sorgu varyantları)
- Kahveji token'ı ile Alessi kaynağı → **404** (403 değil); yanıtta karşı markanın hiçbir
  SKU/id'si yok
- Tek marka yetkili kullanıcının `/holding` isteği → **403 + audit kaydı**
- Kahveji'de `import_files` bayrağı kapalı → uç **404**; Alessi'de aynı uç 200

**Kararlar / notlar:**
- Kavun kullanıcı parolası tutmuyor: kimlik ops.mokka SSO'sundan geliyor. Parola alanı
  uydurmak yerine SSO değişimi gerçek şekilde yazıldı, geliştirme girişi ortamla sınırlandı.
- Guard yalnızca *okuma/güncelleme* sorgularını kısıtlar; INSERT'te izolasyonu şemadaki
  `brand_id NOT NULL` + API katmanı sağlıyor.
- Seed ve model testleri artık `system_scope()` içinde koşuyor — guard devrede olduğu için
  bu bilinçli bir "markalar üstü gözlemci" beyanı.

**Bilinen risk:** Guard yalnızca `brand_id` sütunu OLAN tablolara bakıyor. `sku_costs`,
`purchase_invoice_lines` gibi ürüne/faturaya dolaylı bağlı tablolar doğrudan sorgulanırsa
markalar arası veri görünebilir; bunların izolasyonu API katmanının join'lerine bağlı.
KVN-04'ten itibaren bu tablolara dokunan her endpoint ürün/sipariş üzerinden join'lemeli.

### 2026-08-18 — KVN-02 bitti

**Ne bitti:** Spec §5, §12A, §12B ve §12C'deki veri modelinin tamamı: 41 tablo, tek Alembic
migration'ı, çekirdek seed ve demo veri seti. `make dev` artık migration'ları da uyguluyor;
`make seed-demo` ile demo tenant tek komutta doluyor. Testler: 46 test yeşil, backend
coverage %99.

**Ne kuruldu:**
- **Model katmanı** `app/models/` altında altı dosyaya ayrıldı (identity, catalog,
  transactions, results, inventory, workspace). İşlem verisi taşıyan her tabloda
  `tenant_id` + `brand_id NOT NULL` — KVN-03'ün fail-closed middleware'i bu zeminin üstüne oturacak.
- **Para tipleri tek yerden** (`models/base.py`): tutar `NUMERIC(14,4)`, ortalama maliyet
  `NUMERIC(14,6)`, oran `NUMERIC(6,4)`. Hassasiyetin şemada da korunduğu testle doğrulanıyor.
- **`raw_events` aya göre partition'lı** (spec §5.3): migration 24 aylık pencereyi açıyor,
  `raw_events_default` güvenlik ağı olarak duruyor, yeni aylar `ensure_monthly_partition`
  ile açılacak (KVN-06 job'ı). Yazılan olayın doğru partition'a düştüğü test ediliyor.
- **Seed'ler:** `make seed` (mokka tenant, 2 marka, 5 kanal, 3 mağaza, marka bazlı feature
  bayrakları) idempotent; `make seed-demo` 50 SKU, ~210 sipariş, iade, açılış stoku, komisyon
  tarifeleri, 2 alış faturası, 1 ithalat dosyası (EUR + kur farkı), 6 alert üretiyor.
  `make wipe-demo` demo tenant'ını siliyor, gerçek tenant'a dokunmuyor (testli).

**Kararlar / notlar:**
- Faz 2+ tabloları (settlement, reconciliation, ad_spend, promotions) şema olarak
  kuruldu ama kodları yazılmadı — spec §12.1 gereği.
- Demo veri `line_profit` ÜRETMİYOR: kâr sonucu motorun çıktısıdır (KVN-07), sahte
  hesaplanmış kâr repoya girmemeli. Demo yalnızca motorun gireceği ham gerçekleri kuruyor.
- Migration downgrade'i Postgres enum tiplerini de düşürüyor; aksi halde tekrar upgrade
  "type already exists" ile patlıyordu. upgrade→downgrade→upgrade turu testte koşuyor.
- `alembic check` (model/şema drift'i) test olarak koşuyor; partition çocuk tabloları
  autogenerate karşılaştırmasından `include_object` ile hariç tutuldu.
- Para/float lint kuralı seed'de üç olasılık literali yakaladı (`rng.random() < 0.20`);
  istisna işareti koymak yerine tamsayı çekilişine çevrildi — kod tabanı tümüyle float'sız.
- Demo barkodları yerleşik `hash()` ile üretiliyordu; `hash()` süreç başına tohumlandığı
  için "deterministik demo" iddiası bozuluyordu. sha1 tabanlı kararlı özete çevrildi ve
  testi yazıldı.

**Bilinen risk:** `raw_events` partition penceresi 2028 başına kadar açık. KVN-06'da
partition açma job'ı zamanlanmazsa o tarihten sonra yazılan olaylar `raw_events_default`'a
düşer (veri kaybı yok, performans kaybı var). KVN-06 kabul kriterlerine eklenmeli.

### 2026-08-18 — KVN-01 bitti

**Ne bitti:** Monorepo iskeleti kuruldu (`backend/` FastAPI + Celery, `frontend/` Next.js 14 +
Tailwind, `docs/`). `make dev` tek komutla Postgres + Redis + API + worker + frontend'i ayağa
kaldırıyor; frontend hot-reload açık, preview http://localhost:3000, API http://localhost:8000/docs.
CI hattı üç iş halinde kuruldu: backend (ruff lint+format, `mypy --strict`, pytest coverage ≥ %80),
frontend (tsc, eslint, next build) ve `docker compose up` sonrası API/frontend uçlarını gerçekten
çağıran smoke testi. Testler: 18 test yeşil, backend coverage %91. İlk CI koşusu GitHub'da
üç işin üçünde de yeşil (run #1).

**Kararlar / notlar:**
- Para disiplini (CLAUDE.md §1) lint kuralı olarak yazıldı: `backend/tools/check_money_float.py`
  `app/` altındaki her `float` anotasyonunu ve literal'ini reddeder; bilinçli istisna için
  `# allow-float: <gerekçe>` işareti var. Kural `make lint` ve CI'da koşuyor, kendi testleri var.
- Secret redaksiyonu daha ilk günden devrede: structlog processor'ü `api_key`, `api_secret`,
  `encrypted_payload`, `jwt_secret` gibi alanları maskeliyor (CLAUDE.md §2) — negatif testleri var.
- Türkçe metinler `frontend/locales/tr.json` içinde; hard-coded string yok. Tasarım tokenları
  (kırık beyaz zemin, hairline border, tabular-nums, marka aksanları) Tailwind config'e girdi.
- Alembic yapılandırıldı ama migration üretilmedi — şema KVN-02'nin işi.
- `docs/` altına spec ve tasarım brief'i eklendi; CLAUDE.md'deki referans yolları buna göre
  güncellendi (içerik değişmedi).

**Bilinen risk:** Yok.
