# KAVUN İlerleme

**TOPLAM: %100** ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
**FAZ 2 (ek görevler): %61** ▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░
Son güncelleme: 2026-08-19 12:20 · Aktif görev: — (sırada: KVN-EK-06)
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
| KVN-13 | Komisyon çözümleme hiyerarşisi + snapshot/diff + etki       | 6       | ✅ Bitti    |
| KVN-14 | Tarife Excel yükleme (esnek parser)                         | 4       | ✅ Bitti    |
| KVN-15 | PDF fatura ayrıştırma + öğrenen SKU eşleştirme + onay       | 7       | ✅ Bitti    |
| KVN-16 | Inventory ledger + WAC motoru + açılış stoku                | 7       | ✅ Bitti    |
| KVN-17 | İthalat dosyası modu + kur farkı takibi (Alessi)            | 5       | ✅ Bitti    |
| KVN-18 | D2B kanal + fire/hasar + MSRP disiplini                     | 3       | ✅ Bitti    |
| KVN-19 | Workspace UI (Alessi/Kahveji modülleri + Holding)           | 5       | ✅ Bitti    |
| KVN-20 | Golden dataset doğrulama + uçtan uca kabul turu             | 6       | ✅ Bitti    |

Toplam ağırlık: **110** · Biten ağırlık: 110 · **Faz 1 ve Faz 1.5 tamamlandı**

### Faz 2 ve ek görevler (KVN-EK)

> CLAUDE.md §0 kuralı 4: kanonik liste dışındaki ihtiyaçlar `KVN-EK-xx` id'siyle listenin
> sonuna eklenir ve not düşülür. Aşağıdakiler spec §7'nin (Faz 2) ve KVN-20'de risk olarak
> yazılan boşluğun karşılığıdır. **Yüzde ayrı tutulur**: kanonik listenin %100'ü Faz 1+1.5'in
> tamamlandığını gösterir, aşağıdaki yüzde Faz 2'nin ilerlemesidir.

| ID        | İş Akışı                                                  | Ağırlık | Durum        | Not |
|-----------|-----------------------------------------------------------|---------|--------------|-----|
| KVN-EK-01 | Ekran smoke testleri (Playwright) + CI adımı              | 4       | ✅ Bitti     | KVN-20'de yazılan risk: UI regresyona karşı korumasızdı |
| KVN-EK-02 | Kargo faturası eşleştirme + `estimated → actual` + revizyon | 6       | ✅ Bitti     | spec §5.3, §6.2 |
| KVN-EK-03 | Hakediş mutabakatı: eşleştirme + fark motoru + ekran       | 8       | ✅ Bitti     | spec §7 — "katil özellik" |
| KVN-EK-04 | Ayarlar ekranı: mağaza + credential + hizmet bedeli + kargo tarifesi | 5 | ✅ Bitti     | spec §10.7 — kargo tarife TABLOSU da bu görevde yazıldı (yoktu) |
| KVN-EK-05 | Trendyol Faz 2 uçları + eksik beat programı                | 8       | ✅ Bitti     | spec §4, §9 — iade/hakediş/kargo senkronu; `workers/tasks.py` coverage ≥ %80 |
| KVN-EK-06 | Uyarılar ekranı + acknowledge akışı                        | 4       | ⏳ Sırada    | spec §10.6 — `acknowledged_at` yazan uç dahil |
| KVN-EK-07 | Gerçek veri kalibrasyon haftası                            | 6       | ⏳ Sırada    | **Mert'in dosyalarına bağlı** — geldiğinde sıraya girer; kurgu fixture'lar + 3 `TODO(verify)` + `tracking_no` |
| KVN-EK-08 | Tasarım sistemi rework (token seti + Tremor + TanStack)    | 10      | ⏳ Sırada    | **BLOKE:** brief'in "Kaynak Kütüphaneler" bölümü repoda yok (aşağıya bak) |

Faz 2 ağırlığı: 51 · Biten: 31

> **Sıra (2026-08-19, Mert onayı):** EK-04 → EK-05 → EK-06 → **EK-08**. EK-07 dosyalar
> geldiğinde araya girer. Bu dört görev, KVN-EK-03 sonrası çıkarılan durum raporunun karşılığıdır:
> ürün bugün "manuel/Excel beslemeli" çalışıyor, veri borusu ve ayar/uyarı ekranları eksik.

> **Düzeltme (2026-08-19):** CLAUDE.md §0'daki kanonik listenin başlığı "toplam ağırlık 100"
> diyor ama tablodaki 20 görevin ağırlıkları **110** ediyor. §0 kuralı yüzdeyi "bitmiş
> ağırlık / TÜM ağırlık toplamı" olarak tanımladığı için payda 110 alındı. Önceki
> oturumlarda 100'e bölünmüştü; bu yüzden bu satırın üstündeki yüzde bir önceki
> güncellemeye göre düşük görünüyor — iş azalmadı, ölçü düzeldi. (Ör. KVN-17 sonunda
> gerçek oran %96 değil %87'ydi.) CLAUDE.md'nin başlık satırı Mert onaylarsa düzeltilmeli.

---

> **KVN-EK-08 açıldı ama BAŞLANAMAZ (2026-08-19).** Görev tanımı: Tailwind v4 token seti
> (brief'teki renk/tipografi/spacing + workspace aksanları), Tremor Blocks dashboard
> desenlerinin token setine bağlanması, 15 ekranın geçişi (Dashboard → SKU marj → sipariş
> detayı/şelale → fatura yükleme sırasıyla), yoğun tabloların TanStack Table + shadcn
> DataTable desenine taşınması (sticky header, `tabular-nums`, sağa hizalı rakamlar), her
> ekranın demo veriyle gezilebilir kalması ve brief'teki "Yapılmayacaklar" listesinin lint
> niyetine geçerli sayılması.
>
> **Engel:** `docs/KAVUN_Design_Brief.md` bu repoda **güncellenmemiş** — dosyada
> "Kaynak Kütüphaneler" bölümü yok, içerik KVN-01'deki (884c1ae) haliyle duruyor ve
> `origin`'de de aynı. Görevin 1. ve 5. maddeleri doğrudan o bölümün içeriğine dayanıyor
> (token değerleri, "Yapılmayacaklar" listesi). Brief push edilmeden token seti
> uydurulmuş olur; CLAUDE.md §4 "tahmin etme" kuralı bunu yasaklıyor.
>
> **Ek riskler (başlamadan netleşmeli):** (a) proje Tailwind **3.4.13** kullanıyor, v4
> geçişi Next 14.2 + PostCSS zinciriyle birlikte ayrı bir iş; (b) Tremor Blocks'un ticari
> lisans gerektiren bir ürün olup olmadığı ve hangi bloklara erişim olduğu doğrulanmalı;
> (c) Tremor'un mevcut sürümü Tailwind v3 tema yapılandırmasına dayanıyorsa v4 ile
> birlikte kullanımı ayrıca doğrulanmalı.

## Oturum özetleri

### 2026-08-19 — KVN-EK-05 bitti (Trendyol Faz 2 uçları + zamanlama)

**Ne bitti:** İade, hakediş ve kargo faturası uçları yazıldı; sync onları `raw_events`'e,
normalize da `returns` / `settlement_records` / `cargo_invoices`'a aktarıyor. Beat programı
spec §9'a tamamlandı. Alan adları ve kısıtlar developers.trendyol.com'dan **2026-08-19'da
doğrulandı** — tahmin edilen alan yok. Testler: connector +15, veri borusu +30.

**Kararlar / notlar:**
- **Kargo faturası iki adımlı bir zincir.** Fatura numarasını listeleyen servis yok:
  `otherfinancials?transactionType=DeductionInvoices` → `transactionType`'ı "Kargo
  Faturası" olan kayıtların `id`'si seri numarası → `cargo-invoice/{seri}/items`.
- **Hakediş servisi tek tip alıyor**, aralık 15 günü aşamıyor, `size` yalnızca 500/1000.
  Bu yüzden her tip için ayrı istek atılıyor.
- **Tutar `credit − debt`.** Servis borç/alacak sütunlarını ayrı veriyor; kesinti negatif,
  ödeme pozitif olacak şekilde tek tutara indirgeniyor.
- **Bilinmeyen `transactionType` atılmıyor**, `other` yazılıyor — atılan kalem mutabakatta
  farkı gizler.
- **Reddedilen iade talebi iade sayılmıyor**; kısmen kabul edilen satır kabul edilen ve
  edilmeyen adetlere bölünüyor. Satır bulunamazsa iade yazılmıyor ama `iade_satir_yok`
  sayacına düşüyor. `restocked` serviste yok, **False** varsayılıyor: yeniden satılabilirliği
  kanıtsız varsaymak kârı yüksek gösterirdi.
- **`cargoTrackingNumber` doğrulandı ve artık doldruluyor** — KVN-EK-02'den beri açık duran
  risk kapandı; kargo eşleştirmesi artık sipariş numarasına düşmüyor.
- **`alert_scan` ne tarayacak?** Spec §9 işi sayıyor ama içeriğini yazmıyor. Uyarı üreten
  akışların hepsi uyarıyı olay anında yazıyor; tekrar taramak ekranı gürültüye boğardı.
  Bu yüzden hiçbir akışın yazmadığı tek duruma bakılıyor: **senkronun sessizce durması**
  (bayat `last_synced_at`). Açık uyarı varken tekrarı yazılmıyor.
- **Hypothesis eski bir test kusurunu yakaladı (EK-05 ile ilgisiz).** Hedef marj çözücüsünün
  property testi sabit ±0,01 puan tolerans istiyordu. Teşhis: çözücünün formülü DOĞRU —
  kesin aritmetikte hedefi tam tutturuyor. Sapma motorun her parasal bileşeni 4 haneye
  (DB hassasiyeti) yuvarlamasından geliyor; ~0,0005 TL'lik mutlak sapma 1,24 TL'lik üründe
  0,012 puan marj hatası demek. Tolerans artık fiyatla ölçekleniyor ve neden ölçeklendiği
  testte yazılı. Motor ve çözücü değişmedi.

**Ne kaldı / risk:** Uçlar yazıldı ama **hiç gerçek veriyle çalışmadılar** — fixture'lar
dokümandaki şemadan üretildi, canlı trafikten kaydedilmedi. Gerçek doğrulama KVN-EK-07'de.
Sırada KVN-EK-06 (Uyarılar ekranı) var; EK-05'in ürettiği bayat-senkron uyarısı orada
görünür hale gelecek.

### 2026-08-19 — KVN-EK-04 bitti (Ayarlar + kargo tarife tablosu)

**Ne bitti:** `/{marka}/settings` ekranı (spec §10.7): mağaza ekleme/düzenleme, hizmet
bedeli, Fernet kasasına credential yazma, elle senkron tetikleme ve **kargo tarife
tablosu**. Testler: 603 backend (+20 tarife) + 42 e2e (+3); `app/engine/cargo.py` %100.
Ruff/format/para-float/`mypy app tools tests` temiz, tarayıcıda doğrulandı.

**Kararlar / notlar:**
- **Kapsam sürprizi: kargo tarife tablosu hiç yoktu.** Görev "tarife yönetimi UI'sı"
  diyordu ama yönetilecek tablo yazılmamıştı — tahmin `normalize.py` içinde iki sabite
  gömülüydü (42 TL + 18,50/desi). Spec §6.1 kargoyu `desi_bazli_tahmin(desi,
  carrier_tarife)` diye tanımlıyor, yani tablo tasarımın parçası. Bu yüzden EK-04 önce
  `cargo_tariffs` tablosunu, motorunu (`app/engine/cargo.py`) ve uçlarını yazdı; ekran
  onun üstüne kondu.
- **Bant çözümleme sırası:** firma eşleşmesi > en yeni yürürlük > dar bant. Aralık
  `[alt, üst)` — bitişik bantlar boşluk/çakışma üretmiyor.
- **Eşleşme yoksa varsayılan formüle düşülür**, sıfır yazılmaz. Kargosu sıfır sanılan
  sipariş kârı olduğundan yüksek gösterirdi; eski davranış da böylece korundu (tarife
  tanımlanmamış kurulumlarda sayılar değişmez).
- **Tarife değişikliği geçmişi ezmiyor.** §6.2'nin tetikleyici listesinde tarife
  değişikliği yok; sessizce geçmişe dokunmak yerine açık bir "Tahminleri yenile" eylemi
  var: önce önizler, yalnızca `estimated` gönderilere dokunur, `actual` maliyeti ASLA
  değiştirmez ve revizyonları `kargo_tarifesi` gerekçesiyle loglar. Tarayıcıda demo
  veride doğrulandı: 61 kesinleşmiş gönderi "dokunulmadı" sayısına düştü.
- **Bant silinmiyor, kapatılıyor** (`valid_to`) — geçmiş tahminin dayanağı kayıtta kalır.
- **`system_scope` sızıntısı önlendi:** normalize marka bağlamı olmadan koşuyor;
  `bands_for_brand()` markayı AÇIKÇA filtreliyor. Kahveji'nin tarifesiyle Alessi'nin
  kargosunu hesaplamak sessiz bir hata olurdu — negatif testi yazıldı.
- **Yöntem hatası (kendi hatam, not düşülüyor):** arka plan test koşularını
  `pytest ... | tail` ile çalıştırdım; boru hattının çıkış kodu **`tail`'in** kodudur,
  pytest'in değil. Bu yüzden kırık bir paketi "yeşil" sandım ve öyle rapor ettim. Gerçekte
  `test_schema_matches_models` kırıktı: migration'a modelde karşılığı olmayan bir
  `updated_at` sütunu yazmışım (`TimestampMixin` yalnızca `created_at` tanımlıyor).
  Sütun migration'dan kaldırıldı, test veritabanı sıfırlanıp yeniden kuruldu, `alembic
  check` temiz. Bundan sonra test çıkış kodu boruya sokulmadan okunacak.
- **Demo veri artık ekrandaki tarifeden üretiliyor:** Ayarlar'da görünen bantlar,
  siparişlerdeki gönderi maliyetlerinin gerçek kaynağı. "Ekranda tarife var ama veri
  başka yerden geliyor" tutarsızlığı bilinçli olarak bırakılmadı.

**Ne kaldı / risk:** Sırada KVN-EK-05 (Trendyol Faz 2 uçları + eksik beat programı).
Ayarlar ekranı mağaza/credential tarafını açtı ama **senkron hâlâ elle**: spec §9'daki
`fetch_orders` dahil hiçbir sync job'ı zamanlanmış değil, EK-05 onu kapatacak.

### 2026-08-19 — KVN-EK-03 bitti (Faz 2'nin açılan görevleri tamamlandı)

**Ne bitti:** Hakediş mutabakatı (spec §7) — hakediş kalemlerinin sipariş/satırla
eşleştirilmesi, kalem türüne göre beklenen tutarın üretilmesi, 0,05 TL eşiğiyle
karşılaştırma, `reconciliation_diffs` + uyarı yazımı ve `/{marka}/reconciliation` ekranı
(dönem turu, eşleşme oranı, fark listesi, açıklama akışı). Testler: 583 yeşil (backend,
+27 mutabakat) + 37 e2e; `app/reconciliation/engine.py` %100, mutabakat servisi %90,
motor paketi toplam %99, genel %94. Ruff/format/para-float/`mypy app tools tests` temiz.

**Kararlar / notlar:**
- **Eşik tek yerden gelir (0,05 TL), mağaza bazında ayarlanabilir değil.** Spec §7.3 eşiği
  veriyor ama nerede yaşayacağını söylemiyor; en muhafazakâr seçim eşiği tek yerde tutmak:
  "eşiği büyüterek farkı gizleme" kolaylığı bilinçli olarak verilmedi.
- **Karşılaştırma mutlak değer üzerinden.** Platform kesintileri hakedişte negatif geliyor;
  işaret bilgisi kalem türünde zaten var, tutarda tekrarı karşılaştırmayı yanıltırdı.
- **`refund` beklentisi siparişin iade tutarları toplamı.** Spec §6.1'in iki iade modeli
  arasındaki çelişkisi burada da çıktı; motorun fiilen uyguladığı (tek) model esas alındı —
  Mert'e sorulacaklar listesindeki madde hâlâ geçerli.
- **Siparişe bağlanamayan kalem sessiz geçilmiyor.** Yalnızca ceza (`penalty`) ve reklam
  (`ad_spend`) beklenensiz kabul edilir; diğerleri "eşleşmedi" kuyruğuna düşer ve uyarı
  üretir. Çok satırlı siparişte satır referansı belirsizse eşleştirme yapılmaz — uydurma
  eşleştirme yanlış farkı doğru gibi gösterirdi.
- **Fark açıklamasız kapatılamaz** (en az 3 karakter not) ve `open` durumuna geri dönüş yok.
- **Tarayıcıda bulunan hata:** dönem ikinci kez çalıştırıldığında eşleşme oranı %97,62'den
  %81'e düşüyordu — önceki turda işlenmiş (`skipped`) kalemler eşleşmemiş sayılıyordu.
  Oran artık `(matched + skipped) / records`; regresyon testi eklendi. Tur idempotent:
  ikinci fark kaydı üretilmiyor.
- **CI'da compose smoke işi iki turdur kırmızıydı** (KVN-EK-01 ve KVN-EK-02 commit'leri):
  `docker compose up`, frontend servisinde `node_modules`'ı adlandırılmış volume ile
  gölgeliyor ve bağlama noktasını host'ta **root** olarak yaratıyor; sonrasında çalışan
  host tarafındaki `npm ci` EACCES ile ölüyordu. Testlerin kendisi değil, kurulum sırası
  bozuktu. Playwright kurulumu artık ortam kaldırılmadan önce yapılıyor. Ders (KVN-19 ve
  KVN-20'de de yaşandı): **push sonrası CI sonucu fiilen kontrol edilmeden görev bitmiş
  sayılmamalı** — yerel yeşil, CI yeşil demek değil.

**Ne kaldı / risk:** Kalan iş gerçek veriye bağlı ve dışarıdan girdi bekliyor: (1) Trendyol
mağaza anahtarlarıyla ilk canlı sync, (2) gerçek bir aylık hakediş dökümünün mutabakattan
geçirilmesi — Faz 2'nin nihai kabul kriteri (§11), (3) `shipments.tracking_no` alan adı
developers.trendyol.com'dan doğrulanmadığı için connector tarafından doldurulmuyor; kargo
eşleştirmesi sipariş numarasına düşüyor (CLAUDE.md §4: tahmin yasak). Mert'e sorulacak iki
karar hâlâ açık: spec §6.1 iade modelinin düzeltilmesi ve LLM tabanlı fatura ayrıştırmanın
gerçekten istenip istenmediği.

### 2026-08-19 — KVN-EK-02 bitti

**Ne bitti:** Kargo faturası eşleştirme ve `estimated → actual` geçişi (spec §5.3, §6.2)
+ Kargo faturaları ekranı. Şablon indirilir, kargo firmasının dökümü doldurulur, önizleme
kaç gönderinin kesinleşeceğini ve tahminle farkı gösterir; onayda maliyetler kesinleşir ve
etkilenen siparişlerin kârı yeniden hesaplanır. Testler: 556 yeşil (backend) + 33 e2e,
kargo servisi coverage %94, genel %94.

**Kararlar / notlar:**
- **Revizyon gerekçesi artık tetikleyiciyi taşıyor.** `profit_revisions.reason` sabit
  `recompute` yazıyordu; §6.2 "her tetikleyici loglanır" diyor. Kargo faturasından gelen
  revizyonlar `kargo_faturasi` gerekçesiyle düşüyor — "kâr neden değişti" sorusunun cevabı
  kayıttan okunabiliyor.
- **Eşleştirme anahtarı:** önce gönderi (takip) numarası, yoksa sipariş numarası. `shipments`
  tablosuna `tracking_no` eklendi (migration `d1444dcdfe5c`). Trendyol connector'ı bu alanı
  doldurmuyor — alan adı developers.trendyol.com'dan doğrulanmadan yazılmaz (CLAUDE.md §4);
  `TODO(verify)` olarak aşağıda risk notunda.
- **Kesinleşmiş maliyet ezilmez**, eşleşmeyen satır uydurulmaz: ikisi de testli.
- Demo veri artık gönderilerin ~%60'ını kesinleştiriyor. Böylece "Tahmini / Kesinleşti"
  rozeti (KVN-09'dan beri duruyordu) demo veride ilk kez gerçek bir ayrım gösteriyor:
  145 satırın 74'ü kesinleşmiş.

**Bilinen risk:** `shipments.tracking_no` şu an yalnızca demo seed ve fatura yüklemesi
tarafından doldurulur; Trendyol sync'i doldurmaz çünkü alan adı doğrulanmadı
(`cargoTrackingNumber` olduğu sanılıyor ama CLAUDE.md §4 tahmini yasaklıyor). Doğrulanana
kadar gerçek veride eşleştirme **sipariş numarası** üzerinden yürür — kargo faturası
sipariş numarası taşımıyorsa eşleşme yapılamaz. Mert'in Trendyol dokümanına erişimi varsa
alan adı doğrulanıp connector'a eklenmeli.


### 2026-08-19 — KVN-EK-01 bitti

**Ne bitti:** Ekran smoke testleri (Playwright) ve CI adımı. 30 test: her marka için 9
ortak ekran + Alessi'ye özel 2 ekran açılıyor mu, konsol temiz mi; panelde demo verisi
görünüyor mu; SKU listesi dolu ve negatif filtre çalışıyor mu; sipariş detayında şelale
render oluyor mu; kapalı modül Kahveji menüsünde yok ama sayfası hata değil "kapalı"
durumu gösteriyor mu; holding markaları yan yana veriyor mu; aktif menü öğesi vurgulu mu;
hasar formu kayıt yazıyor mu; açılış stoku ikinci kez reddediliyor mu; fiyat listesi
marka önekli dosya adıyla iniyor mu.

CI'ın `docker compose smoke` işi artık demo veriyi yükleyip kârı hesaplıyor ve testleri
gerçek yığına karşı koşuyor; başarısızlıkta Playwright izleri artifact olarak yükleniyor.
`make e2e` yerelde aynısını yapıyor.

**Kararlar / notlar:**
- Testler **çalışan yığına** bağlanır, kendi sunucusunu başlatmaz. Amaç "gerçek ortam
  gerçekten açılıyor mu" sorusudur; mock'lanmış bir frontend bu soruyu yanıtlamaz.
- Ortamdaki hazır Chromium (1194) ile `@playwright/test` 1.62.1'in beklediği sürüm
  (1234) uyuşmuyor; yapılandırma `PLAYWRIGHT_CHROMIUM_PATH` ile ezilebiliyor. CI kendi
  tarayıcısını kurduğu için orada bu değişken gerekmiyor.
- Kapsam bilinçli olarak dar: ayrıntılı davranış backend testlerinde. Buradaki ağ,
  ekranların **sessizce** bozulmasını engellemek için.

**Bilinen risk:** Smoke testleri demo veriye bağlı; `seed-demo` çıktısı değişirse
(ör. ürün sayısı) birkaç eşik (`> 5 satır`) güncellenmeli. Eşikler bilinçli olarak gevşek
tutuldu ama veri seti küçülürse kırılırlar.


### 2026-08-19 — KVN-20 bitti · Faz 1 + Faz 1.5 tamam

**Ne bitti:** Golden dataset ve uçtan uca kabul turu (spec §11). 20 sipariş satırı
girdileri ve beklenen kârlarıyla `tests/golden/orders.json` içinde donmuş literal olarak
duruyor; beklenen değerler motordan değil, bağımsız ikinci bir uygulamadan
(`tests/golden_reference.py`) üretiliyor ve testler üç kaynağı birden karşılaştırıyor:
motor = referans = donmuş değer. Kabul kriteri "kuruş kuruş eşit" olduğu için
karşılaştırma kuruşta, ara adımlar 4 hanede; ayrıca iki uygulama arasındaki fark yarım
kuruşu geçemiyor (yuvarlamanın gizleyeceği yapısal fark da yakalanıyor).

`tests/test_acceptance.py` modüller arası tutarlılığı doğruluyor: dashboard kârı = SKU
listesi toplamı, ciro = mağaza kırılımı, günlük seri = dönem kârı, şelale = satır kârı,
stok değeri = adet × ortalama maliyet, holding cirosu = markaların toplamı. Kabul
kriteri → test eşlemesi `docs/ACCEPTANCE.md`'de; `make acceptance` ikisini birden koşuyor.
Testler: 536 yeşil, motor coverage %94-100, genel %94.

**Kararlar / notlar:**
- **Yuvarlama sorusu netleşti.** İlk yazdığım elle hesap ara adımları kuruşa yuvarlıyordu
  ve GOLD-01 için 73,34 veriyordu; motor 4 hane taşıyıp 73,3334 (kuruşta 73,33) veriyor.
  CLAUDE.md §1 net: yuvarlama yalnızca gösterim katmanında. Referans hesap da 4 haneye
  çekildi, çözümlü örnek bu farkı açıkça anlatıyor — ileride aynı soru tekrar sorulmasın.
- Golden dataset'i **yeniden üretmek bir insan kararıdır**: `python -m tests.golden_generate`
  çalıştırmak "beklenen değer değişsin" demektir; sebebi commit mesajına yazılmalı.
- Faz 2'nin kabul kriteri (gerçek hakediş dökümüyle %99+ satır eşleşmesi) kapsam dışı
  bırakıldı — gerçek veri ister, mutabakat modülü Faz 2'nin işi.

**Süreç notu:** KVN-19'un CI'ı `mypy` adımında kırıldı — CI `mypy app tools tests`
koşuyor, ben yerelde `app tools` koşuyordum ve testlerdeki bir tip hatası gözden kaçtı.
Yerel kapı artık CI'ın komutunun aynısıdır (`mypy app tools tests`); commit `03031fa`.

**Bilinen risk:** Frontend davranışı otomatik test edilmiyor (projede frontend test
koşucusu yok; CI tsc/eslint/build koşuyor). Her görevde ekranlar gerçek tarayıcıda elle
gezildi ama bu regresyona karşı koruma sağlamaz. Faz 2'ye geçmeden önce Playwright ile
birkaç kritik akışın (fiyat listesi round-trip, fatura onayı, stok ekranı) smoke testi
yazılması önerilir — KVN-EK-01 olarak listeye eklenebilir.


### 2026-08-19 — KVN-19 bitti

**Ne bitti:** Workspace izolasyonu ve holding görünümü (spec §3A). Menü artık yetkiye ve
bayrağa göre kuruluyor: kapalı modül görünmüyor, workspace switcher yalnızca çoklu marka
yetkisi olan kullanıcıya, Holding bağlantısı yalnızca `holding_viewer`'a çıkıyor; aktif
menü öğesi marka aksanıyla vurgulanıyor. `/holding` konsolide raporu geldi: birleşik P&L,
toplam stok değeri, fire gideri, gerçekleşen kur farkı ve açık döviz pozisyonu (KVN-18'de
not düşülen "fire ve kur farkı ekrana inmedi" riski kapandı). Testler: 475 yeşil, holding
servisi %99, izolasyon %93, genel %94.

**Kararlar / notlar:**
- **Sessiz veri bozulması kapatıldı (§3A.2).** Fiyat listesine başka markanın SKU'su
  karışırsa import onu "yeni ürün" sayıp O MARKADA ikinci bir ürün yaratıyordu — aynı SKU
  iki markada yaşar, maliyet ve stok ikiye bölünürdü. Artık satır `cross_brand_rejected`
  ile reddediliyor, kalan satırlar işleniyor; aynı kural D2B yüklemesinde de var. Üç
  regresyon testi yazıldı (ret mesajı, diğer satırların işlenmesi, ikinci ürün YARATILMAMASI).
- Kontrol için tek bir guard bypass'ı gerekiyor ("bu SKU başka markada var mı?"); bypass
  salt okuma ve **boolean** dönerek yapılıyor — karşı markanın hiçbir alanı çağırana geçmiyor.
- Holding raporu hesap yapmıyor, **topluyor**: her sayı marka içindeki motorun yazdığı
  kayıttan geliyor. Böylece holding ile marka ekranı çelişemez.
- Excel dosya adları marka önekiyle üretiliyor (`alessi-fiyat-listesi-2026-08-19.xlsx`).

**Bilinen risk:** Frontend'in yetkiye göre menü kurması test edilmiyor (projede frontend
test koşucusu yok; CI yalnızca tsc/eslint/build koşuyor). Backend tarafı `/auth/me` ve
403 + audit testleriyle korunuyor; UI davranışı tarayıcıda elle doğrulandı.

### 2026-08-19 — KVN-18 bitti

**Ne bitti:** D2B kanalı, fire/hasar ve fiyat disiplini (spec §12C.9-10). D2B satışları
xlsx ile yükleniyor ve normal sipariş olarak yazılıyor (komisyon 0, stok düşüyor, marka
P&L'ine giriyor); yükleme idempotent ve önizlemeli. Hasar hareketi gerekçe zorunlu,
stoktan o anki ortalama maliyetle düşüyor, ortalamayı değiştirmiyor; SKU bazlı hasar
oranı raporu var. MSRP altı fiyat ve marj tabanı ihlalleri taranıp uyarıya çevriliyor
(`kavun.check_price_discipline`, her gece 04:00). Testler: 469 yeşil, D2B servisi %94,
disiplin %95, genel %94. Ekranlar tarayıcıda denendi: D2B yükleme uçtan uca (önizleme →
uygula → kademe özeti güncellendi), hasar formu ve disiplin tablosu doğrulandı.

**Kararlar / notlar:**
- **MSRP ihlali "altında satış" olarak yorumlandı.** Spec "MSRP disiplinini bozuyorsa"
  diyor, yönünü söylemiyor; Alessi gibi premium markada disiplin tavsiye fiyatının altına
  inmemektir. Üstünde fiyatlamak ihlal sayılmıyor (pazaryeri fiyatı serbest).
- **Marka ayarı aktif markadan okunmalı.** İlk yazımda marj tabanı `select(Brand)` ile
  alınıyordu; `brands` marka-kapsamlı bir tablo olmadığı için guard onu filtrelemiyor ve
  Alessi'nin tabanı Kahveji'nin değeriyle ölçülüyordu. Bağlamdaki marka çözülüyor artık;
  aynı hata uyarı tekrar kontrolünü de bozuyordu (yanlış markaya yazılan uyarı görünmüyordu).
- **`orders.customer_id` eklendi** (migration `a4fe24269be3`). Kademe analizi için sipariş
  → müşteri bağı gerekliydi; ilk yazımda bağ sipariş numarasından türetiliyordu, hem
  O(n²) hem kırılgandı.
- Demo D2B siparişleri komisyonlu yazılıyordu — §12C.9'a aykırıydı, düzeltildi. Demoya üç
  kademeli müşteri ve iki hasar kaydı eklendi.

**Yüzde düzeltmesi:** Kanonik listenin ağırlıkları 110 ediyor, CLAUDE.md başlığı 100
diyor. §0 kuralı paydayı "tüm ağırlık toplamı" olarak tanımladığı için 110'a bölündü;
tablo üstündeki nota bakın. Bu bir gerileme değil, ölçü düzeltmesi.

**Bilinen risk:** Fire gideri şu an marka P&L'inde ayrı satır olarak GÖSTERİLMİYOR; veri
(`inventory_ledger.damage` + hasar raporu) hazır ama dashboard'a inmedi. Aynı şey kur
farkı için de geçerli. İkisi de KVN-19'un workspace/holding özet ekranında yerini almalı.

### 2026-08-19 — KVN-17 bitti

**Ne bitti:** İthalat dosyası modu ve kur farkı takibi (spec §12C.7-8) + İthalat dosyaları
ekranı (liste + detay). Dosya = mal faturası + beyanname + masraf kalemleri; masraflar mal
bedeli ağırlıklı dağıtılır, onayda 12C.3 zinciri (ledger + WAC + `sku_costs`) çalışır.
İthalat KDV'si maliyete girmiyor, kur farkı ürün maliyetine dokunmuyor — ikisi de testle
sabitlendi. `GET /{brand}/imports/fx-exposure` açık pozisyonu raporluyor. Modül bayrağı
kapalı markada hem uç hem menü öğesi yok (404). Testler: 434 yeşil, ithalat servisi
coverage %93, genel %94. Ekranlar gerçek tarayıcıda denendi: Alessi'de dolu, Kahveji'de
"modül kapalı"; ödeme formu ve onay kilidi doğrulandı.

**Kararlar / notlar:**
- **Kur farkının işareti P&L yönüne çevrildi:** negatif = kur farkı gideri, pozitif = gelir.
  Uygulamanın geri kalanında negatif rakam kârı azaltan kalem; kur farkı da aynı okumayı
  taşımalı. Aksi halde ekranda "pahalıya ödedik" yeşil görünüyordu.
- **Replay sırası kayıt sırasına (`id`) çevrildi** — hareket tarihine değil. Bugün onaylanan
  40 gün önceki ithalat faturası, tarih sırasıyla oynatılınca farklı ortalama üretiyor ve
  §12C.11'in "birebir aynı" kriterini bozuyordu. Defter bir yevmiye kaydıdır; kayıtlar
  yazıldıkları sırayla uygulanır. Geriye dönük tarihli hareket için regresyon testi yazıldı.
- **`purchase_invoices.import_file_id` eklendi** (migration `a8595701d7b5`). Fatura dosyaya
  bağlıysa `landed_cost_extra` sıfırlanır: masraf iki kaynaktan birden sayılmaz.
- Guard yine iş gördü: `goods_lines` faturaları alt sorguyla çekiyordu, marka filtresi
  taşımayan alt sorgu reddedildi. Faturalar önce ayrı sorguyla çözülüyor.
- Demo seed ithalat akışını artık servisin kendisiyle kuruyor (elle ledger satırı yazmıyor),
  böylece demo durumu da defterden birebir yeniden kurulabiliyor.

**Bilinen risk:** `fx_exposure` açık pozisyonu dosya bazında hesaplıyor; aynı tedarikçiye
dosya dışı (yurtiçi/serbest) dövizli borç varsa kapsam dışında kalır. Spec §12C.8 yalnızca
ithalat dosyası bağlamını tanımlıyor; genel döviz borcu raporu gerekirse KVN-EK olarak
açılmalı.

### 2026-08-19 — KVN-16 bitti

**Ne bitti:** Stok defteri, WAC motoru ve açılış stoku (spec §12C.1-4) + Stok & maliyet
ekranı (tasarım brief'i ekran 8). `inventory_ledger` append-only; `sku_cost_state` onun
türevi ve her an defterden yeniden kurulabiliyor (`stock --rebuild`, §12C.11 kabul
kriteri testtir). Satış/iade hareketleri idempotent (`ref_type='order_line'`), iptal
sipariş stoktan düşmüyor, negatif stokta `negatif_stok` uyarısı üretiliyor. Arka planda
`kavun.record_stock_movements` 45 dakikada bir koşuyor. Testler: 413 yeşil, stok servisi
ve motoru coverage %94, genel %95. Ekran gerçek tarayıcıda dolu ve boş durumla denendi;
açılış tekrarı ve düzeltme akışı UI'dan doğrulandı.

**Kararlar / notlar:**
- **Açılış kontrolü referansa değil ürüne bakıyor.** İlk yazımda "aynı ref bir daha
  yazılmasın" idempotency kontrolü açılış için de kullanılmıştı; seed farklı bir referans
  yazdığı için tarayıcıdan ikinci bir açılış girilebildi ve stok sessizce şişti. Kural
  artık şu: bir üründe OPENING hareketi varsa ikincisi reddedilir — kim yazmış olursa
  olsun. Regresyon testi yazıldı.
- **Replay kontrolü elle kurulan seed satırını yakaladı.** `stock --rebuild --dry-run`
  demo veride 1 uyuşmazlık verdi: adedi 0 olan abonelik SKU'suna açılış hareketi
  yazılıyordu, sıfır adetli devir ortalama maliyet üretemediği için durum defterden
  yeniden kurulunca tutmuyordu. Seed düzeltildi (adet 0 → hareket yok) ve "demo veri
  defterden birebir yeniden kurulabilir" testi eklendi.
- **Loglar stderr'e alındı.** `seed-demo` artık stok hareketi de yazdığı için log satırları
  CLI'nin stdout'undaki JSON çıktısını kirletiyordu. structlog stderr'e bağlandı; akış
  nesnesi kurulumda yakalanmıyor (pytest test başına değiştiriyor), yazma anında çözülüyor.
  İki regresyon testi var.
- Demo açılış adetleri 4 katına çıkarıldı: 4 aylık satış hacmi karşısında 13 SKU eksiye
  düşüyordu ve ekran bozuk görünüyordu. Şimdi tek negatif örnek kaldı (stok tutulmayan
  abonelik SKU'su) — uyarı akışının demosu olarak bilinçli bırakıldı.
- Frontend'de prettier kullanılmadı: repoda config'i ve CI adımı yok, varsayılan 80 sütun
  mevcut 100 sütunluk stille çakışıyor.

**Bilinen risk:** `record_sales` sipariş satırını stoktan düşerken maliyet kaynağı olarak
`sku_cost_state`'i kullanmıyor — kâr motoru maliyeti hâlâ `sku_costs` versiyonundan
okuyor. İkisinin birleştirilmesi (WAC'ın kâr hesabının tek maliyet kaynağı olması)
KVN-20'nin golden dataset turunda netleşmeli; şu an iki kaynak da doğru ama aynı anda
farklı değer taşıyabilir.

### 2026-08-19 — KVN-15 bitti

**Ne bitti:** Alış faturası akışı — PDF ayrıştırma, öğrenen SKU eşleştirme, onay
(spec §12C.3) + fatura onay ekranı. Testler: 389 yeşil, fatura servisi coverage %94,
genel %95. Zincir gerçek tarayıcıda uçtan uca denendi.

**Kabul kriterleri kanıtlandı:**
- Fatura PDF'i fixture olarak repoda; parser → review → confirm zinciri uçtan uca (§12C.11)
- Onaylanmış faturayı değiştirme girişimi → **409** (§12C.11)
- WAC formülü: 34@100 + 100@120 → **114,9254**; 50 satış sonrası ortalama değişmiyor,
  ardından 20@130 alışta doğru güncelleniyor (§12C.1)

**Ne kuruldu:**
- `engine/inventory.py` — WAC saf fonksiyonu (§12C.1 bağlayıcı formül) + landed cost
  paylaştırması
- `services/invoices.py` — PDF metin çıkarımı, satır ayrıştırma, toplam doğrulama,
  öğrenen eşleştirme, atomik onay
- `GET/POST /{brand}/invoices…` uçları + `/{marka}/invoices` liste ve onay ekranları

**Karar 1 — ayrıştırıcı deterministik (spec §12C.3.2'den BİLİNÇLİ SAPMA).** Spec "LLM
destekli ayrıştırma (Claude API)" diyor. Yapılandırılmış bir LLM anahtarı yok ve harici
servise bağımlı, tekrarlanamayan bir ayrıştırma testte doğrulanamaz. Varsayılan ayrıştırıcı
e-arşiv tablo düzenini okuyan deterministik bir parser; `LineExtractor` protokolü LLM
ayrıştırıcısının sonradan takılması için duruyor. Spec'in ASIL kuralı korunuyor: çıktı
asla doğrudan yazılmıyor, her zaman review ekranından geçiyor. **Mert'in kararı gerekiyor:
LLM ayrıştırıcı gerçekten isteniyorsa API anahtarı + maliyet/gizlilik kararı lazım.**

**Karar 2 — fuzzy eşleşme asla otomatik kabul edilmez.** Öneri olarak gösterilir, kullanıcı
onaylayınca `supplier_product_map`'e yazılır. Benzerlik ölçüsü kapsama tabanlı (fatura adı
katalog adından uzun olduğu için saf Jaccard doğru eşleşmeyi cezalandırıyordu) ve en az
iki ortak kelime şartı var — tek ortak kelime ("kahve") öneri üretmiyor.

**Karar 3 — eşleşmemiş satır varken onay REDDEDİLİR.** Yanlış ürüne maliyet yazmaktansa
akış duruyor.

**Karar 4 — OCR yok, sessizlik de yok.** tesseract bu kurulumda yok; metin çıkmayan PDF
boş sonuç dönmüyor, "taranmış olabilir, OCR etkin değil" hatası veriyor.

**WAC motoru bölüşümü:** §12C.1 formülü ve landed cost paylaştırması burada kuruldu
(onay adımı bunlarsız çalışamazdı). KVN-16 bunun üzerine ledger replay, açılış stoku,
negatif stok uyarısı ve fire/hasar hareketlerini ekleyecek.

**Fixture dürüstlüğü:** `tests/fixtures/invoices/earsiv_fatura_ornek.pdf` gerçek bir
tedarikçi faturası DEĞİL; e-arşiv faturalarının metin düzenini taklit ediyor (üretici
script yanında). Gerçek fatura elde edilince değiştirilip testler tekrar çalıştırılmalı.

**Canlı tarayıcı testi (Playwright):** PDF yüklendi → 3 satır ayrıştırıldı → öneriler
göründü (⚑ KHV-BRZ-1K, %80 güven) → satırlar eşleştirildi → toplam kontrolü ✓
(₺15.750,00 / ₺15.750,00) → onaylandı. DB'de 3 `purchase_in` hareketi, güncellenen
ortalama maliyetler (ör. KHV-BRZ-1K 60 adet stoka 20@420 girince ortalama 510,00) ve
fatura referanslı `sku_costs` versiyonları oluştu. JS hatası yok.

**Yakalanan hata:** benzerlik skorları `float` olarak yazılmıştı; kendi para/float lint
kuralım 12 ihlal saydı. Skorlar para değil ama 12 istisna yazmak yerine `Decimal`e
çevrildi — kod tabanında float hiç dolaşmıyor.

**Bilinen risk:** Ayrıştırıcı tek bir satır kalıbına dayanıyor; farklı tedarikçi
şablonlarında satır kaçırabilir (kaçan satır sessizce atlanır, ama toplam doğrulaması
bunu yakalar ve fatura `review`de kalır). Tedarikçi listesi tenant seviyesindedir —
Kahveji formunda Alessi'nin tedarikçisi de görünür (şema böyle tasarlanmış). `pdf_path`
yalnızca dosya adını saklıyor; PDF'in kendisi henüz saklanmıyor, onay ekranında önizleme
(tasarım brief'i kalıp 6'nın sol paneli) bu yüzden yok — KVN-19'da ele alınmalı.

### 2026-08-19 — KVN-14 bitti

**Ne bitti:** Tarife Excel yüklemesi — esnek parser (spec §12B.2) + yükleme ekranı.
Testler: 362 yeşil, parser coverage %94, genel %95. Akış gerçek tarayıcıda denendi.

**Kabul kriterleri (§12B.2) kanıtlandı:**
- Tarife dosyası SIFIR manuel müdahale ile okunuyor: başlık satırı 4. satırda (üstte
  duyuru blokları), sütun sırası sabit değil, oranlar `%16,0` biçiminde METİN
- Eşleşmeyen kategoriler hata değil, `unmatched` listesi
- İleri tarihli yükleme + `future_tariff` senaryosu uçtan uca çalışıyor

**Parser davranışı:**
- Başlık satırı ilk 20 satır içinde aranıyor; tanınan başlık sayısı en yüksek satır seçiliyor
- Türkçe başlık varyasyonları fuzzy eşleşiyor (aksan/büyük-küçük harf duyarsız)
- Oran `%21,5` · `21,5` · `21.5` · `0,215` · sayı hücresi — hepsinden doğru okunuyor
- Çok seviyeli kategori (ana > alt) destekleniyor, eşleştirme EN SPESİFİK seviyeden
- Oran hücresi tamamen boş olan satırlar (dosya sonu notları, ara başlıklar) sessizce
  atlanıyor — sahte hata üretmemek için
- Dry-run yanıtı "şu sütunu kategori, şu sütunu oran olarak okudum" bilgisini taşıyor;
  ekran bunu onay kutusunda gösteriyor

**Otomatik fark analizi:** yükleme anında yeni tarife ile mevcut oranlar karşılaştırılıp
değişen kategoriler, etkilenen SKU sayısı ve aylık kâr etkisi dönüyor — kullanıcı
tarifeyi yüklerken "bu tarife sana ne yapacak" raporunu anında görüyor.

**`future_tariff` senaryo modu tamamlandı** (§12B.4): duyurulmuş ileri tarihli tarife
varsa senaryo o oranı kullanıyor. `pricing_scenarios.future_tariff_date` alanı artık
gerçekten okunuyor.

**Fixture dürüstlüğü:** `tests/fixtures/tariffs/trendyol_komisyon_2026_09.xlsx` gerçek bir
Trendyol dosyası DEĞİL — yayımlanan dosyaların yapısını (üstte duyuru blokları, çok
seviyeli kategori, metin oranlar) taklit ediyor. Gerçek satıcı hesabı ve tarife sayfasına
erişim yok. `tests/fixtures/tariffs/README.md` bunu açıkça yazıyor; ilk gerçek dosya elde
edilince fixture değiştirilip testler tekrar çalıştırılmalı.

**Canlı tarayıcı testi (Playwright):** fixture yüklendi → parser eşleştirmesi ekranda
göründü → 5 değişen kategori (Kahve/Harman %14,5 → %16,0 …), 6 eşleşmeyen kategori ve
−₺412,38 aylık etki listelendi → onaydan sonra 5 kayıt yazıldı. JS hatası yok.

**Bilinen risk:** Parser'ın başlık sözlüğü Trendyol'un YAYIMLADIĞI biçime göre yazıldı;
gerçek dosyada farklı başlıklar çıkarsa sözlüğe eklenmesi gerekecek (kod tek yerde,
`CATEGORY_HEADERS`/`RATE_HEADERS`). Hepsiburada/N11 için kanal bazlı sözlükler Faz 3'te.
Yüklenen tarifenin `valid_to` alanı doldurulmuyor: aynı kategoriye yeni tarife gelince
eskisi kapanmıyor, sadece daha güncel `valid_from` kazanıyor — çözümleme doğru çalışıyor
ama tarife tablosu zamanla birikecek.

### 2026-08-19 — KVN-13 bitti

**Ne bitti:** Komisyon snapshot diff'i, etki analizi, toplu tarife senaryosu (spec §12B.3,
§12B.4) + Komisyon Tarifeleri ekranı. Testler: 333 yeşil, tarife servisi coverage %98,
genel %95. Ekran gerçek tarayıcıda denendi.

**Kabul kriterleri (§12B.5) kanıtlandı:**
- Üç kaynaktan çözümleme (api_product / api_category / manual + settlement) sırası doğru
- Snapshot diff: oran değişince change kaydı + alert, etki tutarı formülle birebir aynı
- `tariff-impact` round-trip: önerilen fiyat motorla geri hesaplanınca hedef marjı ±0,01 tutuyor
- Hakediş çelişkisi sessiz geçilmiyor: `settlement_actual` kaydı yazılıyor ve hiyerarşi
  bundan sonra onu kullanıyor

**Karar 1 — etki formülü motorla ispatlanıyor.** `Δkâr = −P·(k₁−k₀)·(1−α)` kapalı ifadesi
kullanılıyor (α = hizmet KDV payı); doğruluğu, aynı satırın iki oranla motorda
hesaplanmasıyla test ediliyor. "Yaklaşık" ikinci bir formül yok.

**Karar 2 — değişiklik yalnızca yürürlük gününde tespit edilir.** Job dünkü geçerli oranla
bugünkünü karşılaştırıyor; ileri tarihli tarife yüklense bile alert, tarife yürürlüğe
girdiği gün çıkıyor. Aksi hâlde aynı değişiklik için her gün alert yağardı.

**Karar 3 — alert seviyesi etkiye göre.** Negatife düşen SKU varsa `critical`, yoksa
`warning`. Alert metni spec §12B.3'teki cümlenin birebir karşılığı (oranlar + TL etkisi +
negatife düşen SKU listesi).

**Günlük job:** `kavun.detect_commission_changes`, beat programında her gece 03:00
(spec §12B.3: "03:00 sync'in parçası"). Görev kaydı regresyon testine eklendi.

**Canlı tarayıcı testi (Playwright):** Kahveji kataloğunda komisyon +1,5 puan senaryosu
çalıştırıldı → aylık kâr etkisi −₺926,65, etkilenen 22 SKU, negatife düşen 1 SKU ve her
SKU için %25 marjı koruyan yeni fiyat listelendi. JS hatası yok.

**Yakalanan hata:** alert kaydı `brand_id` olmadan yazılıyordu (NOT NULL ihlali) — testte
yakalandı, düzeltildi. Marka kapsamlı her kayıt için bu alan zorunlu.

**Bilinen risk:** Etki analizi son 30 günün satış hızını sabit varsayıyor (spec böyle
istiyor) — mevsimsellik yok. Şu an yalnızca KATEGORİ tarifelerindeki değişim tespit
ediliyor; ürün bazlı oran değişimi (`api_product`) Faz 2'de hakedişle gelecek.
`api_category` kaydı üretecek bir kaynak henüz yok (Trendyol'da komisyon API'si yok);
tarife verisi KVN-14'teki Excel yüklemesiyle girecek.

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
