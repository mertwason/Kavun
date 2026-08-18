# CLAUDE.md — Kavun Geliştirme Konvansiyonları

> Bu dosya her Claude Code oturumunda bağlayıcıdır. Spec: `docs/KAVUN_Teknik_Spec_v1.md`. Tasarım: `docs/KAVUN_Design_Brief.md`. Çelişki durumunda öncelik: CLAUDE.md > Spec > Brief.

---

## 0. İLERLEME TAKİBİ — HER OTURUMDA ZORUNLU

Repo kökünde `PROGRESS.md` dosyası tutulur. **Her görev durum değişikliğinde ve her oturum sonunda güncellenir — istisnasız.** Bu dosya proje sahibinin (Mert) arka planda çalışan geliştirmeyi tek bakışta görme aracıdır.

### Format (birebir bu yapı):
```markdown
# KAVUN İlerleme

**TOPLAM: %38** ▓▓▓▓▓▓▓░░░░░░░░░░░░░
Son güncelleme: 2026-07-29 16:40 · Aktif görev: KVN-07

| ID     | İş Akışı                                  | Ağırlık | Durum       |
|--------|-------------------------------------------|---------|-------------|
| KVN-01 | Proje iskeleti + Docker + CI              | 4       | ✅ Bitti    |
| KVN-07 | Kâr motoru — çekirdek hesap               | 8       | 🔄 Yapılıyor|
| KVN-08 | Kâr motoru — edge-case testleri           | 6       | ⏳ Sırada   |
```

### Kurallar:
1. **Durumlar yalnızca üç değer:** `✅ Bitti` · `🔄 Yapılıyor` · `⏳ Sırada`. Aynı anda en fazla 1 görev "Yapılıyor" olabilir (odak disiplini).
2. **Toplam yüzde = bitmiş görevlerin ağırlık toplamı / tüm ağırlık toplamı.** "Yapılıyor" durumdaki görev yüzdeye katılmaz — yarım iş bitmiş sayılmaz. Yüzde tam sayıya yuvarlanır, progress bar 20 karakterlik blok ile çizilir.
3. **Görev "Bitti" sayılma şartı:** kod + testler yazıldı, testler yeşil, ilgili spec kabul kriteri karşılandı. Test yazılmamış görev bitmiş İLAN EDİLEMEZ.
4. Görev isimleri aşağıdaki kanonik listeden gelir; Claude Code kendi kafasına göre görev ekleyip çıkaramaz. Yeni ihtiyaç doğarsa `KVN-EK-xx` id'siyle listenin sonuna eklenir ve not düşülür.
5. Her commit mesajı ilgili görev id'siyle başlar: `KVN-07: komisyon çözümleme entegrasyonu`.
6. Oturum sonunda `PROGRESS.md`'nin altına 1-2 satırlık oturum özeti eklenir: ne bitti, ne kaldı, bilinen risk.

### Kanonik görev listesi (Faz 1 + 1.5, toplam ağırlık 100):

| ID     | İş Akışı                                                    | Ağırlık | Spec ref |
|--------|-------------------------------------------------------------|---------|----------|
| KVN-01 | Proje iskeleti + Docker Compose + CI (ruff/mypy/pytest)     | 4       | §2, §12  |
| KVN-02 | Veri modeli + Alembic migration'lar + seed                  | 5       | §5       |
| KVN-03 | Tenancy + Brand-scope middleware (fail-closed)              | 5       | §3, §3A  |
| KVN-04 | Credential vault (Fernet) + mağaza yönetimi                 | 3       | §3, §5.1 |
| KVN-05 | Trendyol connector — orders/products/commissions sync       | 8       | §4       |
| KVN-06 | raw_events + normalize pipeline + replay komutu             | 6       | §3, §5.3 |
| KVN-07 | Kâr motoru — çekirdek hesap (KDV netleştirme dahil)         | 8       | §6       |
| KVN-08 | Kâr motoru — edge-case test paketi (8 senaryo)              | 6       | §6.3     |
| KVN-09 | Dashboard + SKU marj listesi + sipariş detayı (waterfall)   | 7       | §10      |
| KVN-10 | Excel round-trip — fiyat listesi export/import + diff       | 6       | §12A     |
| KVN-11 | Taslak ürün akışı                                           | 3       | §12A.3   |
| KVN-12 | Senaryo motoru + karşılaştırma + hedef marj çözücü          | 6       | §12A.4   |
| KVN-13 | Komisyon çözümleme hiyerarşisi + snapshot/diff + etki       | 6       | §12B     |
| KVN-14 | Tarife Excel yükleme (esnek parser)                         | 4       | §12B.2   |
| KVN-15 | PDF fatura ayrıştırma + öğrenen SKU eşleştirme + onay       | 7       | §12C.3   |
| KVN-16 | Inventory ledger + WAC motoru + açılış stoku                | 7       | §12C.1-4 |
| KVN-17 | İthalat dosyası modu + kur farkı takibi (Alessi)            | 5       | §12C.7-8 |
| KVN-18 | D2B kanal + fire/hasar + MSRP disiplini                     | 3       | §12C.9-10|
| KVN-19 | Workspace UI (Alessi/Kahveji modülleri + Holding)           | 5       | §3A, §10 |
| KVN-20 | Golden dataset doğrulama + uçtan uca kabul turu             | 6       | §11      |

---

## 1. Para ve Hesap Disiplini
- Tüm parasal değerler `decimal.Decimal`; `float` ile para hesabı YASAK (lint kuralı ile zorlanır).
- DB: tutarlar `NUMERIC(14,4)`, ortalama maliyet `NUMERIC(14,6)`. Yuvarlama yalnızca gösterim katmanında.
- Kâr, maliyet ve stok hareketleri **append-only ledger** prensibiyle: geçmiş kayıt güncellenmez, düzeltme kaydı atılır (`profit_revisions`, `inventory_ledger.adjustment`).
- Her hesap fonksiyonu saf (pure) yazılır: girdi → çıktı, yan etkisiz; DB erişimi ayrı katmanda.

## 2. İzolasyon Kuralları
- Her işlem tablosunda `tenant_id` + `brand_id`. Brand filtresi olmayan sorgu `BrandScopeViolation` fırlatır — bu davranışın negatif testleri vardır ve silinemez.
- Credential'lar şifreli saklanır, loglara/hata mesajlarına asla yazılmaz.
- Feature bayrağı kapalı modül endpoint'i 404 döner (403 değil).

## 3. Test Disiplini
- Engine (`app/engine/`, `app/reconciliation/`) coverage ≥ %90; genel ≥ %80. CI altında merge yok.
- Spec'teki her kabul kriteri birebir test olarak yazılır; test adı kriteri referanslar.
- Connector'lar kayıtlı gerçek API yanıtlarına (fixture cassette) karşı test edilir; canlı API'ye testte çıkılmaz.
- Para matematiği için property-based testler (Hypothesis): ör. "iade toplamı satış gelirini aşamaz", "WAC replay = state".

## 4. Kod Standartları
- Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2. `mypy --strict` temiz; `ruff` temiz.
- Frontend tipi OpenAPI şemasından üretilir (`npm run gen:api`); elle API tipi yazmak yasak.
- Trendyol endpoint URL/alan adları developers.trendyol.com'dan doğrulanır; tahmin edilmez. Doğrulanamayan alan `TODO(verify)` ile işaretlenir ve PROGRESS notuna yazılır.
- Türkçe UI metinleri `frontend/locales/tr.json` içinde toplanır; hard-coded string yasak.
- Log: structlog, yapılandırılmış JSON; her sync job sonunda özet metrik loglanır (çekilen/işlenen/hatalı kayıt sayısı).

## 5. Çalışma Şekli
- Önce Faz 1 (KVN-01…09), sonra Faz 1.5 (KVN-10…19), en son KVN-20. Sıra atlanmaz; bağımlılığı olmayan küçük işler paralel alınabilir ama "Yapılıyor" teki korunur.
- Her görev: dal aç → kod + test → CI yeşil → PROGRESS güncelle → commit.
- Belirsizlikte spec'e dön; spec sessizse en muhafazakâr (veri kaybetmeyen, geri alınabilir) çözümü seç ve PROGRESS oturum özetine karar notu düş.

## 6. Canlı Preview — ZORUNLU
- `make dev` tek komutla tüm ortamı kaldırır (Postgres + Redis + API + worker + frontend). KVN-01 bu komut çalışmadan bitmiş sayılmaz.
- Frontend hot-reload açık; dev server oturum boyunca arka planda ayakta tutulur. Preview adresi sabittir: **http://localhost:3000** (API: :8000/docs). PROGRESS.md başlığının altına preview durumu yazılır: `Preview: ✅ ayakta · localhost:3000` veya `Preview: ⛔ bozuk (sebep)`.
- **Preview asla kırık bırakılmaz:** commit anında uygulama açılır durumda olmalı. Yarım özellik feature-flag arkasına alınır; derlenmeyen kod commit edilmez. "Proje sahibi her an tarayıcıdan bakabilir" varsayımıyla çalışılır.
- **Demo seed (KVN-02 kapsamında):** `make seed-demo` → gerçekçi sahte veri: 2 marka, ~40 SKU (markalara uygun isimlerle), ~200 sipariş (farklı statü/iade/negatif marj örnekleri dahil), birkaç fatura, tarife, alert. Amaç: gerçek API bağlanmadan önce TÜM ekranların dolu ve gezilebilir olması. Demo veriler `demo` tenant'ında yaşar; gerçek veriye geçişte `make wipe-demo` ile temizlenir, gerçek tenant'a asla karışmaz.
- Yeni bir ekran görevi "Bitti" sayılmadan önce demo veriyle preview'da gezilebilir olmalı (boş durum + dolu durum ikisi de).
