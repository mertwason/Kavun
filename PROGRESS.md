# KAVUN İlerleme

**TOPLAM: %67** ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░
Son güncelleme: 2026-08-19 04:55 · Aktif görev: KVN-13
Preview: ✅ ayakta · localhost:3000

| ID     | İş Akışı                                                    | Ağırlık | Durum       |
|--------|-------------------------------------------------------------|---------|-------------|
| KVN-01 | Proje iskeleti + Docker Compose + CI (ruff/mypy/pytest)     | 4       | ✅ Bitti    |
| KVN-02 | Veri modeli + Alembic migration'lar + seed                  | 5       | ✅ Bitti    |
| KVN-03 | Tenancy + Brand-scope middleware (fail-closed)              | 5       | ✅ Bitti    |
| KVN-04 | Credential vault (Fernet) + mağaza yönetimi                 | 3       | ✅ Bitti    |
| KVN-05 | Trendyol connector — orders/products/commissions sync       | 8       | ✅ Bitti    |
| KVN-06 | raw_events + normalize pipeline + replay komutu             | 6       | ✅ Bitti    |
| KVN-07 | Kâr motoru — çekirdek hesap (KDV netleştirme dahil)         | 8       | ✅ Bitti    |
| KVN-08 | Kâr motoru — edge-case test paketi (8 senaryo)              | 6       | ✅ Bitti    |
| KVN-09 | Dashboard + SKU marj listesi + sipariş detayı (waterfall)   | 7       | ✅ Bitti    |
| KVN-10 | Excel round-trip — fiyat listesi export/import + diff       | 6       | ✅ Bitti    |
| KVN-11 | Taslak ürün akışı                                           | 3       | ✅ Bitti    |
| KVN-12 | Senaryo motoru + karşılaştırma + hedef marj çözücü          | 6       | ✅ Bitti    |
| KVN-13 | Komisyon çözümleme hiyerarşisi + snapshot/diff + etki       | 6       | 🔄 Yapılıyor|
| KVN-14 | Tarife Excel yükleme (esnek parser)                         | 4       | ⏳ Sırada   |
| KVN-15 | PDF fatura ayrıştırma + öğrenen SKU eşleştirme + onay       | 7       | ⏳ Sırada   |
| KVN-16 | Inventory ledger + WAC motoru + açılış stoku                | 7       | ⏳ Sırada   |
| KVN-17 | İthalat dosyası modu + kur farkı takibi (Alessi)            | 5       | ⏳ Sırada   |
| KVN-18 | D2B kanal + fire/hasar + MSRP disiplini                     | 3       | ⏳ Sırada   |
| KVN-19 | Workspace UI (Alessi/Kahveji modülleri + Holding)           | 5       | ⏳ Sırada   |
| KVN-20 | Golden dataset doğrulama + uçtan uca kabul turu             | 6       | ⏳ Sırada   |

Toplam ağırlık: 100 · Biten ağırlık: 67 · **Faz 1 (KVN-01…09) tamamlandı**

---

## Oturum özetleri

### 2026-08-19 — KVN-12 bitti

**Ne bitti:** Senaryo motoru, 3'lü karşılaştırma, hedef marj çözücü ve senaryo xlsx
round-trip'i (spec §12A.4) + Senaryolar ekranı. Testler: 316 yeşil, çözücü coverage %100,
genel %95. Ekran gerçek tarayıcıda denendi.

**Kabul kriteri (§12A.6) kanıtlandı:** çözücünün verdiği fiyat motora geri verildiğinde
hedef marjı **±0,01 puan** tutturuyor — hem sabit senaryolarda hem 200 rastgele girdide
(Hypothesis property testi). Ölçülen sapma pratikte 0,0000.

**Karar 1 — çözücü KAPALI FORMÜL (spec §12A.4 gereği, iterasyon yok).** Türetme
`app/engine/pricing.py` docstring'inde adım adım yazılı:

    β = v/(1+v) · α = s/(1+s) · A = 1 − β − k(1−α) · B = c + (G+S)(1−α)
    P = B / [(1−d)(A−m) + d(1−σ)(1−β)]

Başabaş fiyat bunun m=0 hâli. Formülün doğruluğu bağımsız olarak da doğrulandı: bu
maliyet yapısıyla başabaş fiyat 120,00 çıkıyor — KVN-07'nin elle hesaplanmış "kâr = 0"
senaryosuyla birebir aynı.

**Karar 2 — ulaşılamayan hedefe fiyat uydurulmaz.** Payda ≤ 0 ise (komisyon + KDV yapısı
o marja hiçbir fiyatta izin vermiyorsa) çözücü `None` döner ve UI sebebi yazar. Sonsuza
giden bir fiyat üretmek sessiz saçmalık olurdu.

**Karar 3 — kargoyu satıcı ödemiyorsa gelir yazılmaz.** `alici`/`platform` seçilince
satıcının kargo maliyeti sıfırlanıyor ama alıcının ödediği kargo satıcı geliri
sayılmıyor (muhafazakâr varsayım).

**Karar 4 — `pricing_scenarios.kargo_tahmini` kolonu eklendi** (migration `f1820e99ff0d`).
Kargo varsayımı saklanmayınca kayıtlı senaryo, kaydedildiği andakinden farklı bir kâr
gösteriyordu (testte yakalandı: başabaş 120 yerine 90). Desi bazlı tarife KVN-14'te
gelene kadar kullanıcının verdiği tahmin senaryonun parçası.

**Senaryo xlsx round-trip:** export şablonu = import şablonu; `Birim Kâr`, `Marj %`,
`Toplam Kâr`, `Başabaş Fiyat` sütunları import'ta yok sayılır (kaynak motordur), dosya
hesaplanmış hâliyle geri iner. Bilinmeyen SKU sessizce atlanmaz, dosya reddedilir.

**Canlı tarayıcı testi (Playwright):** senaryo hesaplandı → hedef marj %30 için fiyat
çözüldü (₺2.542,29) ve ekranda motorla doğrulanan marj %30,0 göründü → senaryo kaydedildi
→ iki senaryo yan yana karşılaştırıldı. JS hatası yok.

**Yakalanan hata:** karşılaştırma tablosunda komisyon ORANI "Komisyon kaynağı" etiketiyle
gösteriliyordu; etiket "Komisyon oranı" olarak düzeltildi.

**Bilinen risk:** Senaryo hesabı iade ve reklam payı içermiyor (ikisi de gelecek dönem
varsayımı gerektirir; spec de senaryo sütunlarında saymıyor) — yani senaryo kârı
"iadesiz" senaryodur, gerçekleşen kârdan iyimser olabilir. Ekranda bu not yok, KVN-19'da
eklenmeli.

### 2026-08-19 — KVN-11 bitti

**Ne bitti:** Taslak ürün akışı (spec §12A.3) + "Yeni Ürün Değerlendir" ekranı.
Testler: 284 yeşil, genel coverage %96. Akış gerçek tarayıcıda uçtan uca denendi.

**Kabul kriteri (§12A.6) kanıtlandı:** taslak → promote → sipariş kârı zinciri kırılmıyor;
taslağın analizindeki kâr ile aynı fiyatla satılan siparişin motor kârı birebir aynı çıkıyor
(testi var).

**Ne kuruldu:**
- `services/drafts.py` — analiz (motorun kendisi), kaydet, promote, discard
- `POST /{brand}/drafts/analyze` (kaydetmeden kâr kartı), `GET/POST /{brand}/drafts`,
  `/{id}/promote`, `/{id}/discard`
- `/{marka}/drafts` ekranı: form + anlık kâr kartı (şelale dahil) + taslak listesi
- Excel yüklemesinde `?as_draft=true`: SKU'suz satırlar taslak olur (spec §12A.3)
- `product_drafts.kategori` kolonu (migration `21876d415bc0`)

**Karar 1 — kategori kolonu eklendi.** Komisyon tahmini kategori tarifesinden çözülüyor;
`product_drafts`'ta kategori alanı olmadığı için oran hiç bulunamıyordu. Promote sırasında
ürüne de taşınıyor, böylece dönüştürülen ürün ilk günden doğru tarifeye bağlanıyor.

**Karar 2 — promote muhafazakâr.** SKU önerisi boşsa ya da SKU zaten kullanılıyorsa akış
reddediliyor (422): sessizce SKU uydurmak ya da mevcut ürünü ezmek veri kaybı olurdu.
Aynı taslak iki kez dönüştürülemiyor.

**Karar 3 — uydurma tarife yok.** Kargo tahmini girilmezse sıfır sayılıp
`kargo_tarifesi_yok` uyarısı veriliyor; desi bazlı kargo tarifesi KVN-14'te gelecek.
Kullanıcı kâr kartında uyarıyı görüyor, sessiz iyimserlik yok.

**Canlı tarayıcı testi (Playwright):** form dolduruldu → kâr kartı (şelale ile) geldi →
taslak kaydedildi → listede göründü → "Ürüne dönüştür" → durum "Ürüne dönüştü" oldu ve
ürün, fiyat listesi ekranında belirdi.

**Ufak iyileştirme:** `app/icon.svg` eklendi — tarayıcı sekmesindeki 404 favicon isteği
gitti (proje sahibi sekmeyi açık tutacak).

**Bilinen risk:** Taslak formunda kanal seçimi sabit iki seçenek (`trendyol`, `manual`);
marka kanalları büyürse listenin API'den gelmesi gerekir. Kâr kartı her "Hesapla"da sunucuya
gidiyor — alan değiştikçe otomatik hesaplama (debounce) yapılmıyor, bilinçli: her rakam
motordan gelsin diye.

### 2026-08-19 — KVN-10 bitti

**Ne bitti:** Fiyat listesi Excel round-trip'i (spec §12A.1, §12A.2) + Ürün Çalışma Alanı
ekranı. Testler: 265 yeşil, genel coverage %96. Akış gerçek tarayıcıda uçtan uca denendi.

**Kabul kriterleri (§12A.6) kanıtlandı:**
- Export → hiç değiştirmeden import → dry_run: **0 yeni, 0 güncelleme, 0 hata** (testte ve
  canlı demo veride)
- 500 satırlık dosya 10 sn'nin çok altında işleniyor (testte ölçülüyor)

**Ne kuruldu:**
- `services/pricelist.py` — export/import tek sütun tanımından (`COLUMNS`) beslenir;
  şablon sürümü `kavun-template-v1` ilk (gizli) satırda, import bunu doğrular
- `GET /{brand}/price-list` (ekran tablosu), `/price-list/export`, `POST /price-list/import`
  (`?dry_run=`), `POST /price-list/import/errors` (hatalı satırlar işaretli dosya)
- `/{marka}/products` ekranı: tablo + "Excel'e Aktar" + yükleme/diff önizleme
  (tasarım brief'i kalıp 5: yeşil yeni / mavi güncelleme / kırmızı hata, onaysız yazma yok)

**Karar 1 — `sku_prices` tablosu (yeni).** Spec §5.2'de satış fiyatı için tablo yoktu ama
§12A.1'in upsert anahtarı `(SKU, Kanal)`; yani fiyat ürün-kanal çiftinin özelliğidir
(Trendyol fiyatı ile D2B fiyatı aynı olmak zorunda değil). Maliyet gibi versiyonlandı
(migration `5bbc0933e0a3`). Demo seed artık fiyat da yazıyor.

**Karar 2 — ürün seviyesi alan çelişkisi hata sayılır.** Bir SKU iki kanalda satılıyorsa
dosyada iki satırı olur; maliyet/desi/KDV ürünün özelliğidir, satırdan satıra değişemez.
Kullanıcı yalnızca bir satırı düzenlerse dosya kendi içinde çelişir — "son satır kazansın"
demek sessiz veri kaybıdır, o SKU'nun tüm satırları reddedilir (CLAUDE.md §5).

**Karar 3 — ekran ve dosya tek kaynaktan.** `price_rows()` hem tabloyu hem export'u
besliyor; ikisinin ayrışması (ekranda bir rakam, dosyada başka) mümkün değil.

**Yeni bağımlılık:** `openpyxl` (+ `types-openpyxl`), `python-multipart` (dosya yükleme).

**Canlı tarayıcı testi (Playwright):** 30 satırlık export indirildi, bir fiyat değiştirildi,
bir satır bozuldu, bir yeni SKU eklendi → önizleme 1 yeni / 1 güncelleme / 28 değişiklik yok
/ 1 hata gösterdi (hata gerekçesiyle: "Geçersiz KDV oranı: %7"), onaydan sonra tablo yeni
ürünü ve yeni fiyatı gösterdi. Onaydan önce DB'de hiçbir değişiklik olmadı.

**Bilinen risk:** Aynı markanın aynı kanalda birden fazla mağazası olursa `Kanal` sütunu
belirsizleşir (şu an kanal koduna göre tek mağaza varsayılıyor) — gerçek kurulumda böyle
bir durum yok ama D2B genişlerse sütunun mağaza adına dönmesi gerekir. Import tüm satırları
tek transaction'da işliyor; 5.000+ satırlık dosyalarda bellek/süre KVN-20'de ölçülmeli.
`Kargo (tahmini)` sütunu şimdilik 0 yazılıyor — desi bazlı tarife KVN-14'te gelecek.

### 2026-08-19 — KVN-09 bitti · **Faz 1 tamamlandı**

**Ne bitti:** Dashboard, SKU marj listesi ve sipariş detayı (waterfall) — hem API hem
ekranlar. Testler: 238 yeşil, genel coverage %96. Preview'da demo veriyle gezilebilir.

**Ekranlar (spec §10.1-3):**
- `/{marka}` — ciro / net kâr / marj% / iade% kartları, tahmini-kesin ayrımı, günlük kâr
  grafiği, mağaza kırılımı
- `/{marka}/sku` — SKU marj listesi, en düşük kâr üstte, negatif satır kırmızı zeminli,
  "yalnızca negatif marj" filtresi
- `/{marka}/orders` + `/{marka}/orders/{id}` — sipariş listesi ve **şelale kâr dökümü**
- Marka rozeti + workspace switcher her ekranda (tasarım brief'i kalıp 1)

**API (spec §10):** `GET /{brand}/dashboard`, `/sku-margins`, `/orders`, `/orders/{id}`.
Şelale adımları `{key, amount}` olarak döner; Türkçe etiketler `frontend/locales/tr.json`
içinde — backend yanıtında UI metni taşınmıyor (CLAUDE.md §4).

**Karar 1 — okuma katmanı hesap YAPMAZ.** `services/analytics.py` yalnızca motorun
`line_profit`'e yazdığını toplar. Aynı sayının iki yerde (motorda ve SQL'de) hesaplanması
hakediş mutabakatını imkânsız kılardı. Testler ekrandaki toplamın motorun toplamıyla
birebir aynı olduğunu doğruluyor.

**Karar 2 — şema:** `line_profit`'e `revenue_gross` eklendi (migration `7678779e38d0`).
Dashboard'daki "ciro" müşterinin ödediği KDV dahil tutardır; motor bunu zaten hesaplıyordu
ama yazmıyorduk, dolayısıyla SQL'de yeniden türetmek gerekiyordu — Karar 1'e aykırı.
Yine spec §5.4'e additive bir ek.

**Karar 3 — grafik kütüphanesi yok.** Günlük kâr ve şelale düz SVG ile çiziliyor. Brief
"Recharts ile uygulanabilir sadelikte tut" diyor; bu sadelikte kütüphane taşımanın karşılığı
yok, ayrıca sunucu bileşeni olarak kalıyorlar (sıfır istemci JS).

**Karar 4 — dönem URL'de.** `?days=7|30|90|365`; ekran paylaşılabilir, geri tuşu çalışır,
istemci state'i gerekmez. API tarafında dönem 400 günle sınırlı (kazara tüm veriyi tarayan
sorgu atılmasın), ters/geçersiz aralık 422.

**GÜVENLİK — canlı testte yakalanan gerçek izolasyon açığı:** `Session.get()` birincil
anahtar aramasını identity map'ten karşılayabiliyor; o yol hiç sorgu üretmediği için
brand-scope guard'ına da uğramıyor ve **başka markanın siparişi sızıyordu**. Negatif test
(`/alessi/orders/{kahveji_siparişi}` → 404) bunu yakaladı. Marka verisi artık her zaman
`select()` ile okunuyor; kural `app/core/scoping.py` docstring'ine "Bilinen sınır 2" olarak
yazıldı. Kod tabanındaki diğer `session.get()` çağrıları denetlendi: hepsi `system_scope`
altında ve tenant tablolarında — sızıntı yok.

**Ayrıca canlı testte yakalandı:** şelale adımları servis katmanında tuple olarak
dönüyordu, şema ise nesne bekliyordu → sipariş detayı 500 veriyordu. Testler henüz
yazılmamıştı; `Step` dataclass'ı eklendi.

**Bilinen risk:** Faz 1'de hiçbir satır `is_final` olmuyor (kargo faturası ve hakediş
Faz 2'de bağlanacak), yani dashboard'da "Kesinleşmiş kâr" hep 0 görünüyor — bu doğru ama
Mert'e ilk bakışta eksik gelebilir. Ekranlar masaüstü öncelikli; tablet/mobil düzen
gözden geçirilmedi (brief mobili ikincil sayıyor). Sıralama/filtreleme şimdilik sabit
(marj listesi en düşük kârdan), sütun bazlı sıralama KVN-19'da.

### 2026-08-19 — KVN-08 bitti

**Ne bitti:** Spec §6.3'teki 8 edge-case senaryosunun tamamı test olarak yazıldı
(`tests/test_profit_edge_cases.py`, senaryo numarasıyla adlandırıldı) + 6 Hypothesis
property testi. Testler: 221 yeşil, motor coverage %100, genel %96.

**Senaryolar (spec §6.3 sırasıyla):** 1 kısmi iade · 2 değişim (çift kargo) ·
3 kampanya satıcı/platform payı · 4 %1 ve %20 KDV · 5 iptal · 6 pakette çoklu satır
(desi ağırlıklı kargo) · 7 ceza/tazmin (eşleşen vs mağaza seviyesi) · 8 tarihli komisyon
oranı değişimi. 6 ve 8 gerçek DB kayıtları üzerinden, diğerleri motoru doğrudan çağırarak.

**Property testleri (para matematiği değişmezleri, CLAUDE.md §3):** brüt yol = net yol ·
iade geliri satışı aşamaz · maliyet arttıkça kâr azalır (monotonluk) · paylaştırma kuruş
kaybetmez/yaratmaz · ceza kârı artıramaz · şelale adımları kâra iner.

**Motora eklenenler (senaryolar test edilebilsin diye):**
- `ExchangeInput` — değişim iade DEĞİLDİR: müşteri parayı geri almadığı için gelir,
  komisyon ve satış KDV'si durur; yalnızca iki ek kargo bacağı (geri geliş + yeni gönderi)
  gider yazılır. Geri gelen mal hurdaysa tek satış için iki birim maliyet çıkar.
- `campaign_discount` + `campaign_seller_share_rate` — indirimin platform payı satıcıya
  geri ödendiği için gelire eklenir ve satış KDV'si doğurur. **Varsayılan pay 1,00**, yani
  platform desteği kanıtlanana kadar indirimin tamamını satıcı taşır (CLAUDE.md §5:
  muhafazakâr varsayım). Kaynak veri Faz 4'te (`promotions`) gelecek.
- `penalty` + `split_penalties()` — siparişe eşleşen ceza satır gideri; eşleşmeyen ceza
  satırlara DAĞITILMAZ (hangi satırın suçu olduğu bilinmez), mağaza seviyesinde ayrı durur.

**Şema kararı:** `line_profit`'e iki kolon eklendi — `cost_penalty` ve
`revenue_campaign_support` (migration `e6f148a229c0`, additive + geri alınabilir, mevcut
satırlar `0`). Gerekçe: spec §5.4'ün kolon listesi §6.3.3/§6.3.7 sonuçlarını taşımıyordu;
eklenmezse motor hesaplıyor ama sonuç sessizce kayboluyordu. **Spec §5.4 buna göre
güncellenmeli.**

**Test altyapısı:** kâr testlerinin DB kurulum yardımcıları `tests/profit_factories.py`'ye
taşındı; KVN-07 ve KVN-08 testleri aynı zeminden besleniyor.

**Yakalanan hata:** §6.3.1 senaryosunun docstring'indeki elle hesap yanlıştı — komisyonun
KDV'si tutarın üstüne eklenmiş (48 × %20), oysa KDV tutarın İÇİNDEN çıkarılmalı (48 / 1,20).
Motor doğruydu, test beklentisi yanlıştı; hesap düzeltildi ve `vat_net` de assert edildi.

**Bilinen risk:** Ceza kaleminin KDV'sinin indirilebilir olduğu varsayıldı
(`TODO(verify)` — ilk gerçek hakediş faturasından doğrulanacak). Kampanya ve ceza
girdileri Faz 1'de her zaman sıfır; gerçek veriye Faz 2 (hakediş) ve Faz 4 (promotions)
ile bağlanacak — o zamana kadar bu iki kolon dashboard'da hep 0 görünecek.

### 2026-08-18 — KVN-07 bitti

**Ne bitti:** Kâr motoru çekirdek hesabı (KDV netleştirme dahil, spec §6). Testler:
196 test yeşil, motor coverage %100 (`engine/profit.py`, `engine/vat.py`,
`engine/allocation.py` — CLAUDE.md §3 eşiği %90), genel coverage %96.

**Ne kuruldu:**
- `engine/vat.py` — brüt↔net dönüşümleri, 4 haneye `ROUND_HALF_UP` yuvarlama
- `engine/allocation.py` — ağırlıklı paylaştırma; artık kuruş son parçaya eklenir,
  parçaların toplamı her zaman dağıtılan tutara eşittir
- `engine/profit.py` — saf hesap: `LineInput` → `ProfitBreakdown` (+ `waterfall`
  adımları, sipariş detayı ekranı için hazır)
- `services/commission.py` — komisyon çözümleme hiyerarşisi (spec §12B.1)
- `services/profit.py` — girdi toplama, `line_profit` yazımı, `profit_revisions`
  append-only revizyon logu
- `python -m app.cli recompute [--pending] [--store]` + `make recompute`;
  `make seed-demo` artık kâr hesabını da çalıştırıyor
- Celery: `recompute_pending_profits` 30 dakikada bir; normalize sonrası otomatik zincir

**Kabul kriteri kanıtlandı — testte VE canlı ortamda:** demo veride 177 sipariş /
229 satır hesaplandı, uydurma değer uyarısı (`maliyet_yok`, `komisyon_orani_yok`) çıkmadı;
18 iptal satırı sıfır maliyetle geçti. Sonuç dağılımı gerçekçi: 34 negatif marjlı satır,
marj aralığı %−127 … %+40.

**Karar 1 — KDV modeli (spec §6.1 yorumu).** Spec'in formülü brüt tabanlı, dolayısıyla
çıkarılan her maliyet KDV dahil olmalı. Kavun'da satış/komisyon/kargo/hizmet bedeli KDV
**dahil**, stok maliyeti (WAC) KDV **hariç** duruyor (spec §12C: ithalat KDV'si maliyete
girmez). Motor stok maliyetine KDV'yi ekliyor ve eklediği KDV'yi indirilecek KDV sayıyor.
Aynı kâr net tabandan da hesaplanıp her satırda karşılaştırılıyor; tutmazsa
`profit.cross_check_failed` loglanıyor (şimdiye kadar hiç tetiklenmedi).

**Karar 2 — iade modeli (spec §6.1'den BİLİNÇLİ SAPMA).** Spec hem "satış geliri
sıfırlanır" hem de "iade_maliyeti = refund + ..." diyor; ikisi birlikte uygulanırsa aynı
zarar iki kez sayılır (1.000 TL'lik iade edilen üründe satır −1.000 TL görünür, oysa
gerçek kayıp kargodur). Motor tek tutarlı model uyguluyor: iade edilen adedin geliri,
komisyonu ve satış KDV'si birlikte geri çevriliyor; `refund_amount` ayrıca gider
yazılmıyor ama girdide taşınıyor (hakediş mutabakatında, Faz 2, platformun iade ettiği
tutarla karşılaştırılacak). Gerçek kayıplar sayılıyor: gidiş + dönüş kargosu ve mal
hurdaysa (`restocked=False`) o adedin maliyeti (spec §12C.4). **Mert'in onayı gerekiyor —
spec §6.1 buna göre düzeltilmeli.**

**Karar 3 — paylaştırma:** paket kargosu satırlara desi ağırlıklı, hizmet bedeli tutar
ağırlıklı (spec §6.3.6). Desi bilinmiyorsa eşit bölünüyor.

**Karar 4 — uydurma değer yok:** maliyet ya da komisyon oranı bulunamayan satırda kalem
sıfır kalıyor ve satır uyarıyla işaretleniyor. KVN-05'te doğrulandığı gibi Trendyol
komisyon oranı API'si yok; gerçek veride oranlar tarife Excel'inden (KVN-14) gelecek.

**Bilinen risk:** Reklam payı (`ad_alloc`) girdide var ama Faz 4'e kadar sıfır — dashboard'da
"reklam" adımı boş görünecek. `is_final` yalnızca kargo maliyeti kesinleştiğinde true;
komisyonun kesinleşmesi hakedişe (Faz 2) bağlı, yani Faz 1'de hiçbir satır tam kesin değil.
Edge-case paketi (KVN-08) değişim/çift kargo, kampanya satıcı payı, ceza kalemleri ve
Hypothesis property testlerini ekleyecek.

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
