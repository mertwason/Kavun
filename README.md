# Kavun

Pazaryeri kârlılık ve mutabakat platformu — Mokka Teknoloji.
Trendyol, Hepsiburada, N11 ve Shopify satışlarının **sipariş satırı bazında gerçek net kârını** hesaplar,
hakediş mutabakatı yapar, fiyat/kampanya kararlarını simüle eder.

- Teknik spec: [`docs/KAVUN_Teknik_Spec_v1.md`](docs/KAVUN_Teknik_Spec_v1.md)
- Tasarım brief: [`docs/KAVUN_Design_Brief.md`](docs/KAVUN_Design_Brief.md)
- Geliştirme konvansiyonları (bağlayıcı): [`CLAUDE.md`](CLAUDE.md)
- İlerleme durumu: [`PROGRESS.md`](PROGRESS.md)

## Hızlı başlangıç

Gereksinimler: Docker + Docker Compose. (Yerel geliştirme için ayrıca Python 3.12 ve Node 22.)

```bash
make dev
```

Tek komut Postgres, Redis, API, Celery worker ve frontend'i ayağa kaldırır:

| Servis   | Adres                        |
|----------|------------------------------|
| Frontend | http://localhost:3000        |
| API      | http://localhost:8000        |
| API doc  | http://localhost:8000/docs   |

İlk çalıştırmada `.env` dosyası `.env.example`'dan üretilir. Gerçek secret'lar (`KAVUN_ENCRYPTION_KEY`,
mağaza API anahtarları) `.env` içine yazılır ve repoya **commit edilmez**.

`make dev` ilk çalıştırmada `KAVUN_ENCRYPTION_KEY`'i kendisi üretir. Elle üretmek için:

```bash
docker compose exec api python -m app.cli generate-key
```

**Anahtar rotasyonu:** `KAVUN_ENCRYPTION_KEY` virgülle ayrılmış birden fazla anahtar kabul
eder — ilki şifrelemede kullanılır, tümü çözmede denenir. Yeni anahtarı listenin başına
ekleyin, kayıtları `POST /{brand}/stores/{id}/credentials/rotate` ile taşıyın, sonra eski
anahtarı listeden çıkarın. Anahtar tanımlı değilse credential uçları 503 döner —
düz metin ASLA yazılmaz.

TLS trafiğini inceleyen kurumsal ağların arkasındaysanız kurumun kök sertifikasını
`backend/certs/` ve `frontend/certs/` altına `*.crt` olarak koyun — imajlar derlenirken
sistem sertifika deposuna eklenir. Bu dizinler boşken kurulum davranışı değişmez.

## Sık kullanılan komutlar

```bash
make help        # tüm komutlar
make dev         # ortamı ayağa kaldır (migration'lar otomatik uygulanır)
make down        # durdur          (make clean → volume'ları da siler)
make logs        # logları izle
make check       # CI'nin çalıştırdığı her şey: lint + typecheck + test + frontend build
make test        # pytest + coverage
make lint        # ruff + para/float kuralı
make typecheck   # mypy --strict
make migrate     # alembic upgrade head
make revision m="açıklama"   # yeni migration üret (autogenerate)
make seed        # çekirdek veri: mokka tenant, 2 marka, kanallar, mağazalar
make seed-demo   # demo veri: 50 SKU, ~210 sipariş, iade, fatura, tarife, alert (+ kâr hesabı)
make recompute   # kâr kaydı olmayan satırların kârını hesaplar
make wipe-demo   # demo verisini sil (gerçek tenant'a dokunmaz)
make gen-api     # OpenAPI şemasından frontend tipleri
```

### Ham veri, normalize ve replay

Kanaldan gelen her yanıt önce `raw_events`'e yazılır (değişmez); domain tabloları ondan
üretilir. Bu yüzden normalize veri her zaman yeniden kurulabilir:

```bash
docker compose exec api python -m app.cli normalize                       # işlenmemiş olaylar
docker compose exec api python -m app.cli replay --channel trendyol --from 2026-08-01
docker compose exec api python -m app.cli replay --store <uuid> --dry-run  # yalnızca sayar
```

`replay` normalize kayıtları siler ve ham olaylardan yeniden üretir; ham veriye asla
dokunmaz. Kesinleşmiş (`actual`) kargo maliyeti yeniden normalize'de ezilmez.
Zamanlanmış işler (Celery beat): `normalize_pending` 15 dakikada bir,
`recompute_pending_profits` 30 dakikada bir, `ensure_raw_event_partitions` her gece 02:30
(gelecek ayların partition'larını açar).

### Kâr hesabı

```bash
docker compose exec api python -m app.cli recompute --pending        # kâr kaydı olmayan satırlar
docker compose exec api python -m app.cli recompute --store <uuid>   # bir mağazanın tamamı
```

Motor (`app/engine/profit.py`) saf fonksiyondur — DB'ye dokunmaz, girdi → çıktı. Sonuç
`line_profit`'e yazılır; değişen her alan `profit_revisions`'a append-only loglanır
(geçmiş kayıt güncellenmez, düzeltme kaydı atılır).

**KDV modeli.** Spec §6.1'in formülü brüt (KDV dahil) tabanlıdır, dolayısıyla çıkarılan
her maliyet KDV dahil olmalıdır. Kavun'da satış, komisyon, kargo ve hizmet bedeli KDV
**dahil**; stok maliyeti (WAC) KDV **hariç** durur — motor stok maliyetine KDV'yi ekler ve
eklediği KDV'yi indirilecek KDV sayar. Aynı hesap net tabandan da yapılır ve iki yol her
satırda karşılaştırılır; tutmazsa `profit.cross_check_failed` loglanır.

**İade modeli (spec §6.1'den bilinçli sapma).** Spec hem "satış geliri sıfırlanır" hem de
"iade_maliyeti = refund + …" diyor; ikisi birlikte aynı zararı iki kez sayar. Motor tek
model uygular: iade edilen adedin geliri, komisyonu ve satış KDV'si birlikte geri çevrilir;
`refund_amount` ayrıca gider yazılmaz (hakediş mutabakatı için saklanır). Gerçek kayıp
kalemleri sayılır — gidiş + dönüş kargosu, ve mal hurdaysa (`restocked=False`) o adedin
maliyeti.

**Paylaştırma.** Paket kargosu satırlara desi ağırlıklı, hizmet bedeli tutar ağırlıklı
dağıtılır; artık kuruş son parçaya eklenir, böylece parçaların toplamı her zaman dağıtılan
tutara eşittir.

**Değişim, kampanya, ceza.** Değişim iade değildir: müşteri parayı geri almadığı için gelir
ve komisyon durur, yalnızca iki ek kargo bacağı gider yazılır. Kampanya indiriminin platform
payı satıcıya geri ödendiği için gelire eklenir — ama varsayılan `seller_share_rate = 1`,
yani platform desteği kanıtlanana kadar indirimin tamamını satıcı taşır. Siparişe eşleşmeyen
ceza kalemleri satırlara dağıtılmaz, mağaza seviyesinde gider olarak ayrı tutulur.

Spec §6.3'teki 8 edge-case senaryosunun tamamı `tests/test_profit_edge_cases.py` içinde
senaryo numarasıyla adlandırılmış testtir; aynı dosyada para matematiğinin değişmezleri
Hypothesis property testleriyle doğrulanır (paylaştırma kuruş kaybetmez, iade geliri aşamaz,
maliyet arttıkça kâr azalır, şelale adımları kâra iner).

Maliyet veya komisyon oranı bulunamayan satırda motor uydurma değer kullanmaz: kalem sıfır
kalır ve satır `maliyet_yok` / `komisyon_orani_yok` uyarısıyla işaretlenir.

### Fiyat listesi Excel round-trip'i

**Export edilen dosya = import şablonu.** İkinci bir format yok; ekrandaki tablo, indirilen
dosya ve import doğrulaması aynı sütun tanımından beslenir.

Akış: `Excel'e Aktar` → dosyayı düzenle → `Excel'den Yükle` → **önizleme** (`dry_run`,
hiçbir şey yazılmaz; yeşil yeni / mavi güncelleme / kırmızı hata) → onay → uygulanır.

- `Net Kâr` ve `Marj %` sütunları export'ta motorun hesabıyla dolar, import'ta **yok
  sayılır** — kârın tek doğruluk kaynağı motordur.
- Maliyet ve fiyat değişiklikleri versiyonlu yazılır (`sku_costs`, `sku_prices`,
  `effective_from = bugün`); geçmiş kayıt ezilmez, eski siparişlerin kârı bozulmaz.
- Bir SKU birden fazla kanalda satılıyorsa dosyada birden fazla satırı olur. Fiyat kanal
  bazlıdır; **maliyet, desi ve KDV ürün bazlıdır** — bunlar satırdan satıra çelişirse o
  SKU'nun tüm satırları reddedilir ("son satır kazansın" sessiz veri kaybı olurdu).
- Hatalı satırlar (boş SKU, bilinmeyen kanal, geçersiz KDV, negatif tutar) reddedilir;
  diğer satırlar işlenir. Hata raporu, orijinal dosyaya "Hatalar" sayfası eklenmiş
  olarak indirilebilir.
- Her import (dry-run dahil) `import_batches` tablosuna loglanır.

### Taslak ürün akışı

"Bu ürünü satsak ne kazanırız?" — form doldurulurken kâr motorun kendisiyle hesaplanır ve
kartta gösterilir; hiçbir şey kaydedilmez. Beğenilirse taslak olarak kaydedilir, sonra
`Ürüne dönüştür` ile gerçek ürüne çevrilir (`products` + `sku_costs` + `sku_logistics` +
fiyat kayıtları doğar). İptal edilen taslak silinmez, `discarded` olarak işaretlenir.

Komisyon **kategori tarifesinden** tahmin edilir; kategori yoksa ya da tarife bulunamazsa
oran uydurulmaz — analiz `komisyon_orani_yok` uyarısı taşır. Kargo tahmini de girilmezse
sıfır sayılır ve `kargo_tarifesi_yok` uyarısı çıkar (desi bazlı tarife KVN-14'te gelecek).

Excel yüklemesinde `?as_draft=true` ile **SKU'su boş satırlar** ürün yerine taslak olarak
alınır — ürün ağacına yarım kayıt düşmez (spec §12A.3).

### Veri: gerçek mi, demo mu

İki tenant birbirinden tamamen ayrıdır:

| Tenant  | Ne içerir                                   | Komut            |
|---------|---------------------------------------------|------------------|
| `mokka` | Gerçek yapı (marka, kanal, mağaza); veri yok | `make seed`      |
| `demo`  | Gerçekçi örnek veri — tüm ekranlar dolu      | `make seed-demo` |

`make seed-demo` deterministiktir (sabit tohum) ve her çalıştırmada demo tenant'ını
sıfırlayıp yeniden kurar; gerçek tenant'a asla dokunmaz. Temizlik: `make wipe-demo`.

Demo veri seti: 2 marka (Alessi/Kahveji), 50 SKU, ~210 sipariş (iptal/iade/negatif marj
örnekleri dahil), açılış stoku ve stok hareketleri, komisyon tarifeleri (kategori + ürün
bazlı), 2 alış faturası, 1 ithalat dosyası (EUR + kur farkı), uyarılar, taslak ürünler ve
fiyat senaryoları. Kâr sonuçları demo verisinde ÜRETİLMEZ; `make seed-demo` sonrası
`python -m app.cli recompute --pending` ile motor tarafından hesaplanır.

## Ekranlar

| Yol | Ekran |
|---|---|
| `/` | Workspace seçimi + sistem durumu |
| `/{marka}` | Dashboard — ciro, net kâr, marj%, iade% + günlük kâr grafiği + mağaza kırılımı |
| `/{marka}/sku` | SKU marj listesi — negatif marj kırmızı, "yalnızca negatif" filtresi |
| `/{marka}/orders` | Sipariş listesi |
| `/{marka}/orders/{id}` | Sipariş detayı — **waterfall kâr dökümü** (ürünün imza ekranı) |
| `/{marka}/products` | Ürün çalışma alanı — fiyat listesi + Excel aktar/yükle + diff önizleme |
| `/{marka}/drafts` | Yeni ürün değerlendir — form + anlık kâr kartı + taslak listesi |

Dönem seçimi URL'de taşınır (`?days=7|30|90|365`), böylece ekran paylaşılabilir ve geri
tuşu çalışır. Kâr rakamlarının yanındaki amber "Tahmini" rozeti kargo/komisyon
kesinleşene kadar durur; kesinleşince nötr "Kesinleşti" olur (tasarım brief'i, kalıp 2).

Grafikler ek bağımlılık olmadan düz SVG ile çizilir — brief "Recharts ile uygulanabilir
sadelikte tut" diyor, bu sadelikte kütüphane taşımaya gerek yok.

## Proje yapısı

```
kavun/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI router'ları
│   │   ├── connectors/      # kanal adapter'leri (KVN-05)
│   │   ├── core/            # config, logging, db, tenancy (KVN-03)
│   │   ├── engine/          # kâr motoru — saf hesap (KVN-07)
│   │   ├── reconciliation/  # hakediş mutabakatı (Faz 2)
│   │   ├── models/          # SQLAlchemy (KVN-02)
│   │   ├── schemas/         # Pydantic
│   │   ├── workers/         # Celery görevleri
│   │   ├── alerts/          # uyarı motoru
│   │   ├── services/        # iş mantığı (mağaza, credential kasası, sync, normalize)
│   │   ├── seeds/           # çekirdek + demo veri
│   │   └── cli.py           # seed, wipe-demo, replay, recompute komutları
│   ├── alembic/             # migration'lar
│   ├── tools/               # lint kuralları (para/float yasağı)
│   └── tests/
├── frontend/
│   ├── app/[brand]/         # marka workspace ekranları (KVN-09)
│   ├── components/          # kart, tablo, şelale, grafik
│   ├── lib/                 # API istemcisi (üretilen tipler) + biçimlendirme
│   └── locales/tr.json      # tüm Türkçe metinler
├── docs/                    # spec + tasarım brief
└── docker-compose.yml
```

## API yüzeyi (şu ana kadar)

```
POST /auth/sso-exchange     # ops.mokka SSO token'ı → Kavun token'ı
POST /auth/dev-login        # yalnızca local/ci; diğer ortamlarda 404
POST /auth/switch-brand     # workspace değiştir (yetkisiz marka → 403)
GET  /auth/me               # kullanıcı, yetkili markalar, aktif workspace, modül bayrakları

GET  /{brand}/stores                        # mağaza listesi + sync ve credential durumu
POST /{brand}/stores                        # mağaza ekle (admin/editor)
PATCH /{brand}/stores/{id}                  # mağaza güncelle
GET  /{brand}/stores/{id}/credentials       # credential durumu (içerik ASLA dönmez)
POST /{brand}/stores/{id}/credentials       # credential kaydet (Fernet ile şifreli, admin)
POST /{brand}/stores/{id}/credentials/rotate# anahtar rotasyonu
DEL  /{brand}/stores/{id}/credentials       # credential sil
POST /{brand}/stores/{id}/sync              # senkronu elle tetikle (Celery job)

GET  /{brand}/dashboard     # dönem KPI'ları + günlük kâr serisi + mağaza kırılımı
GET  /{brand}/sku-margins   # SKU marj listesi (en düşük kâr üstte)
GET  /{brand}/orders        # dönemdeki siparişler + kârları
GET  /{brand}/orders/{id}   # sipariş detayı — satır bazlı şelale dökümü

GET  /{brand}/price-list           # fiyat listesi (ekran tablosu)
GET  /{brand}/price-list/export    # xlsx indir (aynı zamanda yükleme şablonu)
POST /{brand}/price-list/import    # yükle — ?dry_run=true iken hiçbir şey yazılmaz
POST /{brand}/price-list/import/errors  # hatalı satırlar işaretlenmiş dosya

GET  /{brand}/drafts               # taslak listesi + güncel analizleri
POST /{brand}/drafts/analyze       # anlık kâr analizi (hiçbir şey kaydedilmez)
POST /{brand}/drafts               # taslak kaydet
POST /{brand}/drafts/{id}/promote  # ürüne dönüştür (ürün + maliyet + desi + fiyat)
POST /{brand}/drafts/{id}/discard  # iptal et (kayıt silinmez)

GET  /{brand}/products      # marka kapsamlı ürün listesi
GET  /{brand}/alerts        # marka kapsamlı uyarılar
GET  /{brand}/import-files  # yalnızca `import_files` bayrağı açık markada (aksi halde 404)

GET  /holding/summary       # markalar arası konsolide özet (holding_viewer, salt okunur)
GET  /healthz  /readyz  /docs
```

Marka izolasyonu üç katmanda zorlanır:

1. **Şema:** işlem verisi taşıyan her tabloda `brand_id NOT NULL`
2. **Guard:** marka bağlamı olmayan sorgu `BrandScopeViolation` fırlatır; bağlam varsa
   sorguya `brand_id` filtresi otomatik eklenir (`app/core/scoping.py`)
3. **API:** yetkisiz markanın kaynağı 404 döner (403 değil — markanın varlığı sızdırılmaz)

Bilinçli bypass yalnızca iki yolla: `holding_scope()` (audit'e yazılır) ve `system_scope()`
(seed/replay/sync gibi arka plan işleri).

## Trendyol entegrasyonu

Uç noktalar ve alan adları developers.trendyol.com'dan doğrulandı (2026-08-18);
tahmin edilen alan yok, doğrulanamayanlar kodda `TODO(verify)` ile işaretli.

| Ne | Uç | Kısıtlar |
|---|---|---|
| Siparişler | `GET /order/sellers/{sellerId}/orders` | `size` max 200, tarih aralığı max 2 hafta, 3 ay geriye, 1.000 istek/dk |
| Ürünler (onaylı, V2) | `GET /product/sellers/{sellerId}/products/approved` | `size` max 100, 10.000 üstü `nextPageToken` |
| Hakediş (Faz 2) | `GET /finance/che/sellers/{sellerId}/settlements` | `transactionType` zorunlu, aralık max 15 gün |

Kimlik: HTTP Basic (API Key : Secret) + `User-Agent: {SellerID} - SelfIntegration`
(başlık yoksa 403). Base URL: `https://apigw.trendyol.com/integration`.

**Komisyon oranları API'de yok.** Trendyol'un pazaryeri servislerinde ürün/kategori
komisyon oranı döndüren bir uç bulunmuyor; oranlar Satıcı Yardım Merkezi'nde dönemsel
tablo olarak yayımlanıyor. Bu yüzden `fetch_commission_rates()` boş liste döner ve
komisyon iki gerçek kaynaktan çözülür: **hakediş** (`settlement_actual`, Faz 2) ve
**tarife Excel yüklemesi** (KVN-14, spec §12B.2).

Sync ham veriyi `raw_events`'e yazar; normalize pipeline (KVN-06) domain tablolarını
ondan üretir ve sync sonrası otomatik zincirlenir.

## Geliştirme kuralları (özet)

Tam liste `CLAUDE.md` içinde; en kritik dördü:

1. **Para `Decimal`'dir.** `float` ile para hesabı yasaktır ve `tools/check_money_float.py`
   lint kuralıyla CI'da zorlanır. Bilinçli istisna: satır sonuna `# allow-float: <gerekçe>`.
2. **Ham veri değişmez.** API yanıtları önce `raw_events`'e yazılır; normalize tablolar
   `replay` komutuyla yeniden üretilebilir.
3. **Marka izolasyonu fail-closed.** İşlem verisi taşıyan her tabloda `brand_id NOT NULL`;
   brand filtresi olmayan sorgu `BrandScopeViolation` fırlatır (KVN-03).
4. **Preview asla kırılmaz.** Her commit'te uygulama açılır durumda olmalı; yarım özellik
   feature-flag arkasına alınır.

## CI

`.github/workflows/ci.yml` üç iş çalıştırır:

- **backend** — ruff (lint + format), para/float kuralı, `mypy --strict`, pytest (coverage ≥ %80)
- **frontend** — `tsc --noEmit`, ESLint, `next build`
- **compose** — `docker compose up` sonrası API ve frontend uçlarının gerçekten cevap verdiği smoke testi

## Sonraki adımlar

Görev sırası ve durumu `PROGRESS.md` dosyasındadır. Sıradaki iş: **KVN-12 — senaryo motoru,
karşılaştırma ve hedef marj çözücü** (spec §12A.4).
