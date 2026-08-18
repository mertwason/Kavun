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
make seed-demo   # demo veri: 50 SKU, ~210 sipariş, iade, fatura, tarife, alert
make wipe-demo   # demo verisini sil (gerçek tenant'a dokunmaz)
make gen-api     # OpenAPI şemasından frontend tipleri
```

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
fiyat senaryoları. Kâr sonuçları demo verisinde ÜRETİLMEZ — onlar kâr motorunun işidir (KVN-07).

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
│   │   ├── services/        # iş mantığı (mağaza, credential kasası)
│   │   ├── seeds/           # çekirdek + demo veri
│   │   └── cli.py           # seed, wipe-demo, replay komutları
│   ├── alembic/             # migration'lar
│   ├── tools/               # lint kuralları (para/float yasağı)
│   └── tests/
├── frontend/                # Next.js 14 (App Router) + Tailwind
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

Görev sırası ve durumu `PROGRESS.md` dosyasındadır. Sıradaki iş: **KVN-05 — Trendyol
connector** (orders / products / commissions senkronu).
