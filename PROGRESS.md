# KAVUN İlerleme

**TOPLAM: %4** ▓░░░░░░░░░░░░░░░░░░░
Son güncelleme: 2026-08-18 14:25 · Aktif görev: KVN-02
Preview: ✅ ayakta · localhost:3000

| ID     | İş Akışı                                                    | Ağırlık | Durum       |
|--------|-------------------------------------------------------------|---------|-------------|
| KVN-01 | Proje iskeleti + Docker Compose + CI (ruff/mypy/pytest)     | 4       | ✅ Bitti    |
| KVN-02 | Veri modeli + Alembic migration'lar + seed                  | 5       | ⏳ Sırada   |
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

Toplam ağırlık: 100 · Biten ağırlık: 4

---

## Oturum özetleri

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

**Bilinen risk:** Yok. Sıradaki iş KVN-02 — veri modeli, migration'lar ve `make seed-demo`
(2 marka, ~40 SKU, ~200 sipariş) ile tüm ekranların dolu gezilebilir olması.
