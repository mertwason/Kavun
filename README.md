# Kavun

Pazaryeri kârlılık ve mutabakat platformu — Mokka Teknoloji.
Trendyol, Hepsiburada, N11 ve Shopify satışlarının **sipariş satırı bazında gerçek net kârını** hesaplar,
hakediş mutabakatı yapar, fiyat/kampanya kararlarını simüle eder.

- Teknik spec: [`docs/KAVUN_Teknik_Spec_v1.md`](docs/KAVUN_Teknik_Spec_v1.md)
- Tasarım brief: [`docs/KAVUN_Design_Brief.md`](docs/KAVUN_Design_Brief.md)
- Geliştirme konvansiyonları (bağlayıcı): [`CLAUDE.md`](CLAUDE.md)
- İlerleme durumu: [`PROGRESS.md`](PROGRESS.md)
- Kabul kriteri → test eşlemesi: [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md)

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
make typecheck   # mypy --strict (app + tools + tests — CI ile aynı kapsam)
make migrate     # alembic upgrade head
make revision m="açıklama"   # yeni migration üret (autogenerate)
make seed        # çekirdek veri: mokka tenant, 2 marka, kanallar, mağazalar
make seed-demo   # demo veri: 50 SKU, ~210 sipariş, iade, fatura, tarife, alert (+ kâr hesabı)
make recompute   # kâr kaydı olmayan satırların kârını hesaplar
make stock       # satış/iade stok hareketlerini deftere yaz (idempotent)
make acceptance  # kabul turu: golden dataset + uçtan uca tutarlılık
make e2e         # ekran smoke testleri (çalışan yığına karşı)
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
**Zamanlanmış işler (Celery beat, spec §9):**

| Job | Sıklık | Ne yapar |
|---|---|---|
| `sync_all_stores` | 15 dk | credential'ı tanımlı her mağaza için sync kuyruğa alır |
| `normalize_pending` | 15 dk | işlenmemiş ham olayları domain tablolarına aktarır |
| `recompute_pending_profits` | 30 dk | kâr kaydı olmayan satırları hesaplar |
| `record_stock_movements` | 45 dk | satış/iade stok hareketleri |
| `alert_scan` | saatlik | senkronu durmuş mağazaları uyarır |
| `ensure_raw_event_partitions` | 02:30 | gelecek ayların partition'larını açar |
| `detect_commission_changes` | 03:00 | tarife snapshot diff'i |
| `check_price_discipline` | 04:00 | MSRP / marj tabanı taraması |
| `reconciliation_run` | 07:00 | dönemin hakediş mutabakatı |

`sync_all_stores` credential'ı olmayan mağazayı atlar — boşuna istek atıp 401 toplamak
yerine Ayarlar ekranında "Girilmedi" olarak bekler.

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

### Senaryo motoru ve hedef marj çözücü

Senaryolar **deterministiktir**: talep tahmini, elastikiyet ya da olasılık yok. Girdi
(fiyat, kampanya indirimi ve satıcı payı, kargoyu kim öder, adet varsayımı) → kâr motoru →
birim kâr, marj, toplam kâr ve başabaş fiyat. En fazla 3 senaryo yan yana konur.

**Hedef marj çözücü kapalı formüldür** (iterasyon yok, spec §12A.4). Türetme
`app/engine/pricing.py` docstring'inde:

    β = v/(1+v) · α = s/(1+s) · A = 1 − β − k(1−α) · B = c + (G+S)(1−α)
    P = B / [(1−d)(A−m) + d(1−σ)(1−β)]

Doğruluğu iki yoldan test edilir: çözülen fiyat motora geri verildiğinde hedef marj
±0,01 puan tutar (kabul kriteri §12A.6) ve bu, 200 rastgele girdi üzerinde Hypothesis
property testiyle de doğrulanır. Hedefe hiçbir fiyatta ulaşılamıyorsa (komisyon + KDV
yapısı elvermiyorsa) fiyat uydurulmaz — çözücü bunu açıkça söyler.

Senaryolar da Excel'e aktarılıp geri yüklenebilir; sonuç sütunları import'ta yok sayılır,
dosya hesaplanmış hâliyle geri iner.

### Komisyon tarife motoru

Komisyon statik parametre değil, **versiyonlu tarife verisidir**; motor ve senaryolar her
zaman bu modülden çözer. Çözümleme sırası: `settlement_actual` > `api_product` >
`api_category` / `manual_tariff_upload` > `manual`; aynı seviyede daha güncel `valid_from`
kazanır.

Her gece 03:00'te `detect_commission_changes` job'ı dünkü geçerli oranla bugünkünü
karşılaştırır. Değişen kategori için `commission_changes` kaydı + alert üretilir; alert
metni parasal etkiyi taşır: *"Kahve/Harman kategorisinde komisyon %21,5 → %23,0. Mevcut
satış hızıyla aylık kâr etkisi: −25 TL. Negatif marja düşen SKU: 1 (…)"*.

**Etki formülü motorla birebir tutarlıdır.** Komisyon kâra `−P·k` girer, KDV'si `+P·k·α`
indirilir; dolayısıyla `Δkâr = −P·(k₁−k₀)·(1−α)`. Bu kapalı ifade, aynı satırın iki oranla
motorda hesaplanmasıyla test edilerek doğrulanır — ikinci bir "yaklaşık" formül yaşamaz.

`POST /{brand}/tariffs/impact` tek çağrıda "komisyon %1,5 artarsa katalogda ne olur"
sorusunu cevaplar: etkilenen SKU'lar, mevcut fiyatla yeni marj, negatife düşenler ve
hedef marjı **koruyan** yeni fiyat (hedef marj çözücüsüyle, ±0,01 puan garantili).

Hakedişten gelen gerçek oran tarifeden farklıysa sessiz geçilmez: `settlement_actual`
kaydı yazılır ve çözümleme hiyerarşisi bundan sonra onu kullanır.

**Tarife Excel yüklemesi (esnek parser).** Kanalın yayımladığı dosya **formatı
değiştirilmeden** yüklenir: parser başlık satırını arar (ilk satırda olmak zorunda değil),
sütunları Türkçe başlık varyasyonlarıyla eşleştirir (`Komisyon %`, `Komisyon Oranı`,
`Ana Kategori`, `Alt Kategori`…) ve oranı `%21,5` · `21,5` · `0,215` biçimlerinin
hepsinden okur. Dry-run yanıtı "şu sütunu kategori, şu sütunu oran olarak okudum" bilgisini
ve tarifenin kâra etkisini taşır; onaydan önce hiçbir kayıt yazılmaz.

Çok seviyeli kategori desteklenir, eşleştirme en spesifik seviyeden yapılır. Kavun'da
karşılığı olmayan tarife satırları **hata değildir** — `unmatched` listesinde raporlanır.
İleri tarihli yükleme bugünün hesabını etkilemez; senaryoların `future_tariff` modu o
tarihteki oranı kullanır ("yeni tarife yürürlüğe girince marjım ne olur").

### Alış faturası akışı

`Yükle → İncele → Eşleştir → Onayla`. Ayrıştırma sonucu **asla doğrudan stoka yazılmaz**;
her zaman onay ekranından geçer (spec §12C.3).

1. **Ayrıştırma:** PDF metni pdfplumber ile okunur, satırlar (ad · adet · birim fiyat ·
   KDV · tutar) çıkarılır. Metin çıkmayan (taranmış) PDF sessizce boş dönmez, açık hata
   verir — OCR bu kurulumda etkin değil.
2. **Doğrulama:** satır toplamları fatura genel toplamıyla ±0,10 TL tutmalı; tutmuyorsa
   fatura `review` durumunda kalır.
3. **Öğrenen eşleştirme:** barkod → tedarikçi bazlı öğrenilmiş eşleşme → fuzzy öneri.
   **Fuzzy sonuç otomatik kabul edilmez**, kullanıcı onayı şarttır; onaylanan eşleşme
   `supplier_product_map`'e yazılır, aynı tedarikçiden aynı ürün bir daha sorulmaz.
4. **Onay:** her satır için `inventory_ledger` girişi + ağırlıklı ortalama maliyet (WAC)
   güncellemesi + `sku_costs` versiyonu **tek transaction'da** yazılır. Navlun/gümrük
   (`landed_cost_extra`) satırlara tutar ağırlıklı dağıtılır.
5. **Onaylanmış fatura değiştirilemez** — değiştirme girişimi 409 döner; düzeltme ancak
   ters kayıtla yapılır (muhasebe disiplini: geçmiş silinmez).

WAC formülü bağlayıcıdır (spec §12C.1) ve `app/engine/inventory.py` içinde saf fonksiyon
olarak durur: yalnızca girişler ortalamayı günceller, çıkışlar stoku düşürür ama ortalamayı
değiştirmez. Spec'in örneği testtir: 34 adet @100 + 100 adet @120 → **114,9254**.

### Stok defteri (KVN-16)

`inventory_ledger` **append-only**'dir: hiçbir hareket güncellenmez ya da silinmez,
düzeltme her zaman yeni bir satırdır. `sku_cost_state` (eldeki adet + ortalama maliyet)
bu defterin türevidir ve her an yeniden kurulabilir:

```bash
python -m app.cli stock                      # satış/iade hareketlerini yaz (idempotent)
python -m app.cli stock --rebuild --dry-run  # durumu defterden kur, farkı raporla
python -m app.cli stock --rebuild            # farkı uygula
```

Hareket yönleri (spec §12C.1): `purchase_in` · `opening` · `return_in` stoku artırır ve
**ortalamayı günceller**; `sale_out` · `return_out` (hurda) · `damage` · negatif
`adjustment` stoku düşürür, **ortalamaya dokunmaz**.

Kurallar:

- **Satış hareketleri idempotenttir** — aynı sipariş satırı için ikinci `sale_out`
  yazılmaz (`ref_type='order_line'`). İptal siparişler stoktan düşmez.
- **Açılış (devir) ürün başına tektir.** Kontrol referansa değil ürüne bakar: açılışı kim
  yazmış olursa olsun (seed, içe aktarım, API) ikincisi reddedilir.
- **Düzeltmede gerekçe zorunludur**; kayıt `adjustment` olarak deftere düşer.
- Stok eksiye düşerse `negatif_stok` uyarısı üretilir — genelde açılış stoku girilmemiştir.
- Arka planda `kavun.record_stock_movements` (45 dakikada bir) aynı işi yapar.

`stock --rebuild --dry-run` demo veride de koşulur ve CI'da testtir: elle kurulan seed
satırları motorun üreteceğinden saparsa test kırılır.

### İthalat dosyası ve kur farkı (KVN-17)

İthal alım tek fatura değildir; bir **dosyadır**: mal faturası (EUR) + beyanname + masraf
kalemleri (navlun, sigorta, gümrük müşavirliği, ardiye…). Dosya `Alessi` gibi `import_files`
bayrağı açık markalarda görünür; kapalı markada uç ve ekran **404** döner.

1. Dosya açılır, **beyanname kuru** girilir — maliyet bu kurla sabitlenir.
2. Masraf kalemleri kendi para biriminde girilir; TL karşılığı girişte sabitlenir.
3. Mal faturası dosyaya bağlanır; artık `landed_cost_extra` kullanılmaz (basit yurtiçi
   modun alanıdır, iki kaynak birden sayılmaz).
4. Dağıtım önizlemesi satır bazlı landed cost'u gösterir — **onaya kadar hiçbir şey
   stoka yazılmaz**.
5. Onayda 12C.3 zinciri çalışır: ledger + WAC + `sku_costs` versiyonu tek transaction.

İki kural şaşmaz:

- **İthalat KDV'si maliyet kalemi değildir.** Gümrükte ödenir ama indirilecek KDV'dir;
  `import_files.import_vat_paid` alanında nakit akışı/KDV raporu için durur, landed cost
  hesabına asla katılmaz.
- **Kur farkı ürün maliyetine girmez.** Ödeme günü kur değiştiyse fark
  `supplier_payments.fx_diff_try`de raporlanır. İşaret P&L yönündedir: **negatif = kur farkı
  gideri**, pozitif = gelir. `GET /{brand}/imports/fx-exposure` açık pozisyonu, maliyet
  kurunu ve gerçekleşen farkı verir.

Dağıtım mal bedeli ağırlıklıdır ve kuruş kaybetmez; testler elle hesaplanan örneği birebir
doğrular (EUR mal + TL navlun + EUR sigorta + müşavirlik → 4.650,00 ve 13.950,00).

### D2B kanal, fire/hasar ve fiyat disiplini (KVN-18)

**D2B (kurumsal satış)** pazaryerinden gelmez ama Kavun'da **normal sipariş** olarak yazılır:
stok düşer, kâr motoru aynı formülle hesaplar, satış marka P&L'ine girer. Tek fark
kanaldır — komisyon 0, pazaryeri hizmet bedeli yok. Fiyat müşteri kademesine göre
iskontoludur; "hangi kademe ne bırakıyor" özeti `customers.tier` üstünden çıkar.

```
Şablonu indir → doldur → Önizle (dry-run) → Uygula
```

Şablon disiplini fiyat listesindekiyle aynı: indirilen dosya = yüklenen şablon, sürüm
hücresi tutmuyorsa dosya reddedilir. Yükleme idempotenttir — aynı dosya iki kez
yüklenirse sipariş çoğalmaz, satır "zaten yazılmış" olarak raporlanır. Hatalı satır
(bilinmeyen SKU, geçersiz KDV, aşırı iskonto) gerekçesiyle listelenir, diğer satırlar işlenir.

**Fire/hasar** (`damage`) gerekçesiz yazılamaz. Hasar stoktan **o anki ortalama maliyetle**
düşer ve ortalamayı değiştirmez; kayıtta o günün ortalaması saklandığı için fire gideri
sonradan değişen maliyetle oynamaz. Rapor SKU bazında adet, fire gideri ve
`hasar / (hasar + satış)` oranını verir — porselen-cam üründe kritik metrik.

**Fiyat disiplini** iki kuraldan oluşur ve **uyarır, engellemez**:

- **MSRP:** tavsiye fiyatının *altında* satış ihlaldir (marka değerini aşındırır); üstünde
  fiyatlamak serbesttir.
- **Marj tabanı:** ürün bazlı `min_margin_floor_pct` yoksa markanın varsayılanı geçerlidir.

Tarama her gece 04:00'te koşar (`kavun.check_price_discipline`) ve ihlal başına günde en
fazla bir uyarı yazar. Taban **aktif markadan** okunur: `brands` marka-kapsamlı bir tablo
değildir, guard onu filtrelemez — yanlış markadan okunursa Alessi'nin tabanı Kahveji'nin
değeriyle ölçülürdü.

### Workspace izolasyonu ve holding görünümü (KVN-19)

Menü **yetkiye ve bayrağa göre** kurulur: kapalı modül (Kahveji'de ithalat/D2B) menüde
görünmez, workspace switcher yalnızca çoklu marka yetkisi olan kullanıcıya çıkar, Holding
bağlantısı yalnızca `holding_viewer` rolüne. Aktif menü öğesi marka aksanıyla altı çizili.

**İçe aktarım izolasyonu (§3A.2).** Bir workspace'ten yüklenen dosya yalnızca o markaya
yazılır. Dosyada başka markaya ait SKU varsa satır `cross_brand_rejected` ile reddedilir,
kalan satırlar işlenir. Bu, sessiz veri bozulmasına karşı bir kilittir: aksi halde aynı SKU
ikinci markada yeniden yaratılır, maliyet ve stok ikiye bölünürdü. Kural fiyat listesi ve
D2B satış yüklemesinde uygulanır; kontrol tek bir evet/hayır sorusudur (karşı markanın
hiçbir alanı çağırana geçmez). Excel dosya adları marka önekiyle üretilir
(`alessi-fiyat-listesi-2026-08-19.xlsx`).

**Holding görünümü (§3A.3)** `/holding` altındadır ve **salt okunurdur**: konsolide P&L,
toplam stok değeri, fire gideri, gerçekleşen kur farkı ve açık döviz pozisyonu markalar
yan yana. Sayılar yeniden hesaplanmaz — marka içindeki motorun yazdığı kayıtlardan
toplanır, böylece holding ile marka görünümü çelişemez. Erişim (ve her ret) audit'e
yazılır; yetkisiz kullanıcı 403 alır.

### Kargo faturası: `estimated → actual` (KVN-EK-02)

Faz 1'de kargo maliyeti **tahminidir** (desi × tarife). Gerçek tutar ay sonunda kargo
firmasının faturasından gelir; bu akış o faturayı gönderilerle eşleştirir ve maliyeti
kesinleştirir.

```
Şablonu indir → kargo firmasının dökümünü doldur → Önizle → Uygula
```

- Eşleştirme anahtarı **gönderi (takip) numarasıdır**; kanal onu vermiyorsa **sipariş
  numarası** kullanılır. İkisi de tutmazsa satır "eşleşmedi" kuyruğuna düşer ve uyarı
  üretilir — uydurma eşleştirme yapılmaz, yanlış gönderiye yazılan maliyet sessizce
  yanlış kâr üretirdi.
- **Kesinleşmiş maliyet ezilmez:** `cost_state = actual` olan gönderi ikinci faturayla
  güncellenmez, satır "zaten kesin" olarak raporlanır.
- Kesinleşen her sipariş için kâr yeniden hesaplanır ve değişen alanlar
  `profit_revisions`'a **tetikleyici gerekçesiyle** (`kargo_faturasi`) loglanır (spec §6.2).
  Satır böylece "Tahmini" rozetinden "Kesinleşti"ye geçer (tasarım brief'i, kalıp 2).
- Önizleme "tahmin farkı"nı gösterir: pozitifse tahmin düşük kalmış, kâr aşağı revize olur.

### Hakediş mutabakatı (KVN-EK-03)

Kâr motoru "olması gerekeni" hesaplar; hakediş dosyası platformun **gerçekten** ne kestiğini
söyler. Mutabakat tek soruyu sorar: **ikisi aynı mı, değilse fark nerede?** (spec §7)

```
Dönem seç → Önizle (hiçbir şey yazılmaz) → Uygula → açık farkları açıkla
```

| Kalem türü    | Beklenen değerin kaynağı                          |
|---------------|---------------------------------------------------|
| `commission`  | motorun hesapladığı komisyon (`line_profit`)      |
| `sale`        | satır brüt cirosu                                 |
| `cargo`       | gönderinin kesinleşmiş/tahmini kargo maliyeti     |
| `service_fee` | mağazanın sipariş başına hizmet bedeli            |
| `refund`      | siparişin iade tutarları toplamı                  |
| `penalty`, `ad_spend` | beklenen yok — tanımı gereği siparişten türetilemez |

- **Eşik 0,05 TL** ve tek yerden gelir (`app/reconciliation/engine.py`). Mağaza bazında
  ayarlanabilir yapılmadı: "eşiği büyüterek farkı gizleme" kolaylığı bilinçli olarak yok.
- Platform kesintileri hakedişte negatif gelir; karşılaştırma **mutlak değer** üzerinden
  yapılır — işaret bilgisi kalem türünde zaten var, tutarda tekrarı yanıltıcı olurdu.
- Siparişe bağlanamayan kalem (ceza/reklam dışında) sessiz geçilmez, **eşleşmedi** olarak
  raporlanır ve uyarı üretir. Çok satırlı siparişlerde satır referansı belirsizse kalem
  eşleştirilmez — uydurma eşleştirme yapılmaz.
- Tur **idempotenttir:** aynı dönem ikinci kez çalıştırılınca önceki turda işlenmiş kalemler
  `skipped` sayılır ve eşleşme oranına eşleşmiş olarak girer; ikinci fark kaydı üretilmez.
- Fark **açıklamasız kapatılamaz:** en az 3 karakterlik not zorunludur, `open` durumuna geri
  dönüş yoktur. Açıklamasız kapatılan fark, kapatılmamış farktan daha tehlikelidir.

### Trendyol Faz 2 uçları (KVN-EK-05)

Faz 1'de yalnızca sipariş ve ürün çekiliyordu; iade, hakediş ve kargo faturası uçları
`NotImplementedError` idi. Üçü de yazıldı — alan adları developers.trendyol.com'dan
**2026-08-19'da doğrulandı**, tahmin edilen alan yok.

| Ne | Uç | Not |
|---|---|---|
| İadeler | `GET /order/sellers/{id}/claims` | `size` max 200; adet `claimItems` sayısından |
| Hakediş | `GET /finance/che/sellers/{id}/settlements` | aralık max **15 gün**, `size` 500\|1000, `transactionType` **tek tip** |
| Kargo faturası | `.../otherfinancials` → `.../cargo-invoice/{seri}/items` | **iki adımlı**, aşağıya bak |

**İade kuralları.** Adet `claimItems` dizisinin uzunluğundan sayılır (servis her iade
edilen adedi ayrı kayıt olarak veriyor). **Kabul edilmeyen talep iade sayılmaz** — reddedilen
talebi iade yazmak ciroyu haksız yere düşürürdü; kısmen kabul edilen satır kabul edilen ve
edilmeyen adetlere bölünür. Sipariş satırı bulunamazsa iade **yazılmaz** ama sessizce de
geçilmez (`iade_satir_yok` sayacı). `restocked` alanı serviste yok ve **False** varsayılır:
malın yeniden satılabilir olduğunu kanıtsız varsaymak kârı olduğundan yüksek gösterirdi.

**Hakediş tutarı.** Servis borç (`debt`) ve alacak (`credit`) sütunlarını ayrı veriyor;
Kavun tek tutar taşır: `credit − debt`. Bizden kesilen kalem negatif, bize ödenen pozitif
olur. Bilinmeyen `transactionType` **atılmaz**, `other` olarak yazılır — mutabakatta
"tanımadığım kalem" görünür kalmalı, atılan kalem farkı gizler.

**Kargo faturası zinciri.** Fatura numaralarını doğrudan listeleyen bir servis yok:

```
otherfinancials?transactionType=DeductionInvoices
   → transactionType'ı "Kargo Faturası" olan kayıtların `id`'si = fatura seri no
   → cargo-invoice/{seri}/items  →  parcelUniqueId · orderNumber · amount · desi
```

Kalemler gönderiyle eşleşince maliyet `estimated → actual` olur; kurallar Excel
akışıyla aynıdır (kesinleşmiş maliyet ezilmez, eşleşmeyen satır uydurulmaz).

**Takip numarası artık doldruluyor.** `cargoTrackingNumber` sipariş yanıtında doğrulandı
(KVN-EK-02'de doğrulanamadığı için boş bırakılıyordu ve eşleştirme sipariş numarasına
düşüyordu). Kargo faturası eşleştirmesinin birincil anahtarı artık gerçekten takip
numarası.

### Uyarılar ve acknowledge (KVN-EK-06)

Altı ayrı akış uyarı üretiyor ama KVN-EK-06'ya kadar **hiçbiri ekranda görünmüyordu**;
`acknowledged_at` kolonu vardı ve onu yazan tek bir uç yoktu, yani uyarılar sonsuza kadar
birikiyordu. `/{marka}/alerts` bunu kapatır (spec §10.6).

| Tür | Nereden gelir |
|---|---|
| `negatif_stok` | stok hareketi yazılırken (§12C.4) |
| `komisyon_degisikligi` | günlük tarife snapshot diff'i (§12B.3) |
| `msrp_ihlali`, `marj_tabani` | fiyat disiplini taraması (§12C.10) |
| `kargo_faturasi_eslesmedi` | kargo faturası yüklemesi (§6.2) |
| `hakedis_farki` | mutabakat turu (§7) |
| `stale_sync` | saatlik `alert_scan` — senkron sessizce durmuşsa |

- **Acknowledge tek yönlü ve idempotenttir.** İkinci çağrı ilk damgayı bozmaz; "görüldü"
  zamanı geriye alınmaz. Geri alma yok çünkü acknowledge bir karar değil, bir okuma
  kaydıdır.
- **Kapatılan uyarı silinmez:** "Kapatılmış" filtresinde durmaya devam eder. Yanlışlıkla
  kapatılan bir uyarı böylece kaybolmaz.
- Filtreler (`?severity=&type=&status=`) **URL'de taşınır** — ekran paylaşılabilir, geri
  tuşu çalışır; dönem seçicisiyle aynı disiplin.
- Uyarı üretimi bu ekrana ait değil: her akış uyarıyı **olay anında** yazar. `alert_scan`
  onları tekrar taramaz — aynı uyarının iki kez üretilmesi ekranı gürültüye boğardı.

### Ayarlar: mağaza, bağlantı ve kargo tarifesi (KVN-EK-04)

Gerçek veriye geçişin kapısı (spec §10.7). `/{marka}/settings` altında üç şey yönetilir:

- **Mağaza** — kanal, satıcı no, sipariş başına hizmet bedeli. Senkron buradan elle
  tetiklenebilir; credential yoksa uç 409 döner (boşuna kuyruğa iş atılmaz).
- **Bağlantı bilgileri** — Fernet ile şifrelenip `store_credentials`'a yazılır.
  **Yalnızca yazılır:** hiçbir uç içeriği geri döndürmez, ekranda sadece "kayıtlı /
  girilmedi" ve son güncelleme zamanı görünür (CLAUDE.md §2).
- **Kargo tarifesi** — desi bandı tablosu. Spec §6.1 kargoyu
  `desi_bazli_tahmin(desi, carrier_tarife)` diye tanımlıyor; KVN-07'de tarife tablosu
  yoktu ve tahmin iki sabite gömülüydü. Artık tahmin gerçekten tablodan çözülüyor.

**Bant çözümleme sırası** (`app/engine/cargo.py`, saf fonksiyon):

```
firma eşleşmesi  >  en yeni yürürlük tarihi  >  dar bant
```

- Aralık **`[alt, üst)`**: bitişik bantlar (0–1, 1–2, 2–5) boşluk ve çakışma üretmez;
  1,00 desi ikinci banda düşer. Üst sınır boşsa bant sınırsızdır ("10 desi ve üzeri").
- Hiçbir bant eşleşmezse **varsayılan formüle** düşülür (taban + desi başı ücret) —
  sessizce sıfır kargo yazılmaz; kargosu sıfır sanılan sipariş kârı olduğundan yüksek
  gösterirdi.
- Bant **silinmez, kapatılır** (`valid_to`): geçmiş tahminin hangi tarifeden çıktığı
  kayıtta kalır.
- **Tarife değişikliği geçmişi ezmez.** Spec §6.2'nin yeniden hesap tetikleyicileri
  arasında tarife değişikliği yok; sessizce geçmişe dokunmak "dün gördüğüm kâr bugün
  neden farklı" sorusunu doğurur. Bunun yerine açık bir eylem var: **Tahminleri yenile**
  → önce önizler, yalnızca `estimated` gönderileri günceller, **kesinleşmiş (`actual`)
  maliyete asla dokunmaz** ve değişen kârı `profit_revisions`'a `kargo_tarifesi`
  gerekçesiyle yazar.

Demo veri de bu tarifeden üretilir: Ayarlar ekranında görünen bantlar, siparişlerdeki
gönderi maliyetlerinin gerçek kaynağıdır.

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

## Kabul turu ve golden dataset (KVN-20)

Spec'teki her kabul kriterinin karşılığı bir testtir; eşleme
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) dosyasındadır.

```bash
make acceptance   # golden dataset + uçtan uca tutarlılık turu
```

**Golden dataset.** Faz 1'in kabul kriteri "rastgele 20 sipariş için elle hesaplanan
kârla motor çıktısı kuruş kuruş eşit" der. `tests/golden/orders.json` bu 20 satırı
girdileri **ve** beklenen değerleriyle donmuş literal olarak taşır. Beklenen değerler
motordan değil, bağımsız bir ikinci uygulamadan (`tests/golden_reference.py`) üretilir;
testler üç kaynağı birden karşılaştırır:

```
motor  ==  referans uygulama  ==  dosyadaki donmuş değer
```

Ara adımlar 4 haneyle taşınır (yuvarlama yalnızca gösterimde), karşılaştırma kuruşta
yapılır ve iki uygulama arasındaki fark yarım kuruşu geçemez — yuvarlamanın gizleyeceği
yapısal fark da yakalanır. Dosyayı yeniden üretmek insan kararıdır:
`python -m tests.golden_generate`.

**Uçtan uca tur.** `tests/test_acceptance.py` tek tek modülleri değil aralarındaki
tutarlılığı doğrular: dashboard kârı SKU listesinin toplamına, mağaza kırılımı ciroya,
günlük seri dönem kârına, şelale adımları satır kârına, stok değeri adet × ortalama
maliyete, holding cirosu markaların toplamına eşit olmalı. Bir halka koparsa hangi
ekranın yalan söylediği buradan görülür.

### Ekran smoke testleri (KVN-EK-01)

`frontend/e2e/` altındaki Playwright testleri **çalışan yığına** bağlanır (kendi sunucusunu
başlatmaz): her ekran açılıyor mu, konsol temiz mi, demo veri görünüyor mu, kapalı modül
menüde yok mu, formlar kayıt yazıyor mu, önizleme gerçekten yazmadan gösteriyor mu.
Ayrıntılı davranış backend testlerinde; buradaki ağ ekranların **sessizce** bozulmasını
engeller.

```bash
make dev && make seed-demo && make recompute   # yığın + dolu demo veri
make e2e                                        # 47 smoke testi
```

CI'da `docker compose smoke` işi ortamı kaldırır, demo veriyi yükler, kârı hesaplar ve
aynı testleri koşar; başarısızlıkta Playwright izleri artifact olarak yüklenir. Ortamdaki
hazır Chromium farklı sürümdeyse `PLAYWRIGHT_CHROMIUM_PATH` ile yol verilebilir.

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
| `/{marka}/scenarios` | Senaryolar — karşılaştırma tablosu + hedef marj çözücü |
| `/{marka}/tariffs` | Komisyon tarifeleri — geçerli oranlar, değişiklik geçmişi, etki analizi |
| `/{marka}/invoices` | Alış faturaları — PDF yükleme + satır eşleştirme + onay |
| `/{marka}/inventory` | Stok & maliyet — eldeki adet, ortalama maliyet, hareket defteri, açılış/düzeltme |
| `/{marka}/cargo` | Kargo faturaları — kesinleşme durumu + fatura yükleme/eşleştirme |
| `/{marka}/reconciliation` | Hakediş mutabakatı — dönem turu, eşleşme oranı, farklar + açıklama akışı |
| `/{marka}/alerts` | Uyarılar — seviye/tür/durum filtreleri + "gördüm" akışı |
| `/{marka}/settings` | Ayarlar — mağaza + şifreli bağlantı bilgileri + hizmet bedeli + kargo tarifesi |
| `/{marka}/imports` | İthalat dosyaları + açık döviz pozisyonu (yalnızca bayrağı açık markada) |
| `/{marka}/imports/{id}` | Dosya detayı — masraf kalemleri, dağıtım önizlemesi, ödemeler/kur farkı |
| `/{marka}/d2b` | D2B satışlar — şablon indir/yükle + kademe bazlı özet (bayrağa bağlı) |
| `/holding` | Holding görünümü — konsolide P&L, stok, fire, kur (salt okunur) |

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

GET  /{brand}/scenarios            # kayıtlı senaryolar + güncel sonuçları
POST /{brand}/scenarios/evaluate   # senaryoyu hesapla (kaydetmeden)
POST /{brand}/scenarios            # senaryo kaydet
POST /{brand}/scenarios/compare    # en fazla 3 senaryoyu yan yana
POST /{brand}/scenarios/target-margin  # hedef marj için gereken fiyatı çöz
GET  /{brand}/scenarios/export     # senaryoları xlsx indir
POST /{brand}/scenarios/import     # senaryo dosyası → hesaplanmış dosya

GET  /{brand}/tariffs              # geçerli komisyon tarifeleri
GET  /{brand}/tariffs/changes      # değişiklik geçmişi + etki tutarları
POST /{brand}/tariffs/detect-changes  # günlük diff'i elle tetikle
POST /{brand}/tariffs/impact       # "komisyon %X artarsa ne olur" (toplu senaryo)
POST /{brand}/tariffs/upload       # tarife Excel'i yükle (?valid_from&dry_run)

GET  /{brand}/invoices             # alış faturaları
GET  /{brand}/invoices/suppliers   # tedarikçi listesi
POST /{brand}/invoices/upload      # fatura PDF'i ayrıştır (stoka YAZMAZ)
GET  /{brand}/invoices/{id}        # onay ekranı: satırlar + SKU önerileri
POST /{brand}/invoices/{id}/lines/{line}/match  # SKU eşleştir (öğrenilir)
POST /{brand}/invoices/{id}/confirm             # ledger + WAC + maliyet versiyonu

GET  /{brand}/inventory            # eldeki stok + ortalama maliyet + stok değeri
GET  /{brand}/inventory/ledger     # append-only hareket defteri (?product_id&limit)
POST /{brand}/inventory/opening    # açılış (devir) stoku — ürün başına tek seferlik
POST /{brand}/inventory/adjust     # düzeltme kaydı (gerekçe zorunlu)
POST /{brand}/inventory/rebuild    # durumu defterden yeniden kur (?dry_run)

GET  /{brand}/imports              # ithalat dosyaları (bayrak kapalıysa 404)
GET  /{brand}/imports/fx-exposure  # açık döviz pozisyonu + gerçekleşen kur farkı
POST /{brand}/imports              # yeni dosya (beyanname kuru burada sabitlenir)
GET  /{brand}/imports/{id}         # masraf kalemleri + dağıtım önizlemesi + ödemeler
POST /{brand}/imports/{id}/cost-items          # masraf kalemi (ithalat KDV'si GİRMEZ)
POST /{brand}/imports/{id}/invoices/{invoice}  # mal faturasını dosyaya bağla
POST /{brand}/imports/{id}/confirm             # ledger + WAC + maliyet versiyonu
POST /{brand}/imports/{id}/payments            # ödeme + kur farkı

GET  /{brand}/b2b/template         # D2B satış şablonu (xlsx)
GET  /{brand}/b2b/tiers            # kademe bazlı satış özeti
POST /{brand}/b2b/import           # D2B satışlarını yükle (?dry_run)
POST /{brand}/inventory/damage     # fire/hasar kaydı (gerekçe zorunlu)
GET  /{brand}/inventory/damage     # SKU bazlı hasar oranı ve fire gideri
GET  /{brand}/discipline           # MSRP ve marj tabanı ihlalleri (bayrağa bağlı)

GET  /{brand}/cargo-invoices             # yüklenen kargo faturaları
GET  /{brand}/cargo-invoices/cost-state  # kaç gönderi kesinleşti / tahmini kaldı
GET  /{brand}/cargo-invoices/template    # kargo faturası şablonu (xlsx)
POST /{brand}/cargo-invoices/import      # eşleştir + kesinleştir (?dry_run)

GET  /{brand}/alerts                 # uyarılar (?severity&type&acknowledged)
GET  /{brand}/alerts/summary         # seviye bazlı açık/kapalı sayımlar + türler
POST /{brand}/alerts/{id}/acknowledge  # "gördüm" — tek yönlü, idempotent

GET  /{brand}/settings/cargo-tariffs          # desi bandı tarifesi (?include_closed)
POST /{brand}/settings/cargo-tariffs          # bant ekle (geçersiz aralık 422)
POST /{brand}/settings/cargo-tariffs/{id}/close    # bandı yürürlükten kaldır (silmez)
GET  /{brand}/settings/cargo-tariffs/preview  # "bu desi kaça çıkar" + kaynağı
POST /{brand}/settings/cargo-tariffs/reestimate    # tahminleri yenile (?dry_run)

GET  /{brand}/reconciliation/periods  # hakediş kaydı olan dönemler
GET  /{brand}/reconciliation/diffs    # eşik üstü farklar (?period&status)
GET  /{brand}/reconciliation/summary  # dönem özeti: fark/açık/açıklanan + toplam fark
POST /{brand}/reconciliation/run      # dönemi mutabakatla (?dry_run — önizleme yazmaz)
POST /{brand}/reconciliation/diffs/{id}/explain  # farkı açıkla/çöz (not zorunlu)

GET  /{brand}/products      # marka kapsamlı ürün listesi
GET  /{brand}/import-files  # yalnızca `import_files` bayrağı açık markada (aksi halde 404)

GET  /holding/summary       # markalar arası sayımlar (holding_viewer, salt okunur)
GET  /holding/consolidated  # konsolide P&L + stok değeri + fire + kur maruziyeti
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

Uç noktalar ve alan adları developers.trendyol.com'dan doğrulandı (siparişler/ürünler
2026-08-18, Faz 2 uçları 2026-08-19); tahmin edilen alan yok, doğrulanamayanlar kodda
`TODO(verify)` ile işaretli.

| Ne | Uç | Kısıtlar |
|---|---|---|
| Siparişler | `GET /order/sellers/{sellerId}/orders` | `size` max 200, tarih aralığı max 2 hafta, 3 ay geriye, 1.000 istek/dk |
| Ürünler (onaylı, V2) | `GET /product/sellers/{sellerId}/products/approved` | `size` max 100, 10.000 üstü `nextPageToken` |
| İadeler | `GET /order/sellers/{sellerId}/claims` | `size` max 200, tarih milisaniye damgası |
| Hakediş | `GET /finance/che/sellers/{sellerId}/settlements` | `transactionType` zorunlu ve tek tip, aralık max 15 gün, `size` 500\|1000 |
| Kesinti faturaları | `GET /finance/che/sellers/{sellerId}/otherfinancials` | kargo faturasının seri numarası buradan çıkar |
| Kargo faturası kalemleri | `GET /finance/che/sellers/{sellerId}/cargo-invoice/{seri}/items` | `parcelUniqueId`, `orderNumber`, `amount`, `desi` |

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

Faz 1 ve Faz 1.5'in kanonik görev listesi (KVN-01…20) ve şu ana kadar açılan Faz 2 ek
görevleri (KVN-EK-01…03) tamamlandı: ekran smoke testleri, kargo faturası eşleştirme ve
hakediş mutabakatı. Ürün artık "olması gereken"i hesaplamakla kalmıyor, platformun
gerçekte ne kestiğini de karşılaştırıyor.

Kalan iş **gerçek veriyle** ilgili ve dışarıdan girdi bekliyor (bkz. `PROGRESS.md` karar
notları): Trendyol mağaza anahtarlarıyla ilk canlı sync, gerçek bir aylık hakediş
dökümünün mutabakattan geçirilmesi (Faz 2'nin nihai kabul kriteri, §11) ve gönderi takip
numarası alan adının developers.trendyol.com'dan doğrulanması — doğrulanana kadar kargo
eşleştirmesi sipariş numarasına düşüyor.
