# KAVUN İlerleme

**TOPLAM: %9** ▓▓░░░░░░░░░░░░░░░░░░
Son güncelleme: 2026-08-18 15:10 · Aktif görev: KVN-03
Preview: ✅ ayakta · localhost:3000

| ID     | İş Akışı                                                    | Ağırlık | Durum       |
|--------|-------------------------------------------------------------|---------|-------------|
| KVN-01 | Proje iskeleti + Docker Compose + CI (ruff/mypy/pytest)     | 4       | ✅ Bitti    |
| KVN-02 | Veri modeli + Alembic migration'lar + seed                  | 5       | ✅ Bitti    |
| KVN-03 | Tenancy + Brand-scope middleware (fail-closed)              | 5       | ⏳ Sırada   |
| KVN-04 | Credential vault (Fernet) + mağaza yönetimi                 | 3       | ⏳ Sırada   |
| KVN-05 | Trendyol connector — orders/products/commissions sync       | 8       | ⏳ Sırada   |
| KVN-06 | raw_events + normalize pipeline + replay komutu             | 6       | ⏳ Sırada   |
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

Toplam ağırlık: 100 · Biten ağırlık: 9

---

## Oturum özetleri

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
