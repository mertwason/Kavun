# Handoff: Kavun — Pazaryeri Kârlılık & Stok SaaS (13 ekran)

## Genel Bakış
Kavun, pazaryeri satıcıları (Trendyol/Hepsiburada/Amazon TR) için kârlılık ve stok yönetim SaaS'ıdır. Sipariş satırı bazında GERÇEK net kâr hesaplar (komisyon, kargo, KDV, iade, maliyet düşülmüş), hakediş mutabakatı yapar, fiyat senaryoları simüle eder, alış faturalarından stok ve ortalama maliyet yönetir. Tek şirket, iki marka workspace'i: **Kahveji** (amber aksan) ve **Alessi** (kırmızı aksan) + salt okunur **Holding** görünümü. Mimari çok kiracılı SaaS'a evrilecek — onboarding, boş durumlar, plan/kullanım ekranları baştan tasarlandı.

## Tasarım Dosyaları Hakkında
Bu paketteki `.dc.html` dosyaları **HTML ile üretilmiş tasarım referanslarıdır** — amaçlanan görünümü ve davranışı gösteren prototiplerdir, doğrudan kopyalanacak üretim kodu DEĞİLDİR. Görev: bu tasarımları hedef kod tabanının mevcut ortamında (React + Tailwind/shadcn önerilir; mevcut ortam neyse o) yerleşik kalıplarıyla YENİDEN üretmek. Ortam henüz yoksa öneri stack: **Next.js/React + Tailwind + shadcn/ui + Recharts + TanStack Table** — tasarım dili zaten bu kütüphanelerin desenlerinden derlendi.

Dosyalar tarayıcıda açılabilir; `<x-dc>` içindeki markup ve `<script data-dc-script>` içindeki `Component` sınıfı (state + hesap mantığı) okunmalıdır. Tüm stiller inline'dır — her değer markup'ta görünür.

## Fidelity
**High-fidelity (hifi).** Renkler, tipografi, boşluklar, köşe yarıçapları ve mikro-etkileşimler finaldir; piksel hedefli yeniden üretilmelidir. Yalnızca şunlar placeholder'dır: PDF önizleme içeriği (Fatura Yükleme'de gri bloklar) ve kanal "logoları" (harfli nötr kareler — gerçek logolara bağlanabilir).

## Design Tokens (bağlayıcı)

Renkler:
- Zemin: `#FAFAF9` · Kart: `#FFFFFF` · Hairline border: `#E7E5E4` (ayraç: `#F5F5F4`)
- Metin: birincil `#1C1917`, ikincil `#57534E`, gövde-soluk `#78716C`, muted `#A8A29E`, çok soluk `#D6D3D1`
- Semantik (YALNIZCA veri anlamı taşır): pozitif `#16A34A` (koyu metin `#15803D`, tint `#F0FDF4`, kenar `#BBF7D0`) · negatif `#DC2626` (tint `#FEF2F2`, kenar `#FECACA`, satır zemini `#FEF7F7`) · tahmini/amber `#D97706` (metin `#B45309`, tint `#FFFBEB`, kenar `#FDE68A`) · bilgi `#2563EB` (tint `#EFF6FF`, kenar `#DBEAFE`)
- Workspace aksanı: Kahveji `#B45309` (hover `#92400E`) · Alessi `#C8102E` · Holding `#292524`. Aksan SADECE: aktif nav öğesinin sol çizgisi+metni, birincil buton, workspace rozeti. Başka hiçbir yerde.
- Gölge yok (yalnız modal `0 16px 40px rgba(28,25,23,0.16)`, sağ panel `-12px 0 32px rgba(28,25,23,0.1)`, tooltip `0 4px 12px rgba(0,0,0,0.15)`)

Tipografi: **Geist** (Google Fonts; 400/500/600/700) + **Geist Mono** (SKU kodları, fatura no).
- Gövde 14px/1.5 · ikincil ve tablo hücresi 13px · yardımcı 12–12.5px · mikro 11px
- Başlıklar 14–17px/600 (asla 700 üstü) · KPI rakamı 28–32px/600, `letter-spacing:-0.02em`
- **`font-variant-numeric: tabular-nums` TÜM rakamlarda zorunlu** (kök elemana uygulanmış)
- Para simgesi ₺ büyük rakamın yanında bir kademe küçük (17–18px) ve `#A8A29E`
- Kolon başlıkları: 10.5px/600, uppercase, `letter-spacing:0.06em`, `#A8A29E`

Sayı/tarih formatı: Türkçe — `1.234,56 ₺` biçimi (`toLocaleString("tr-TR")`), negatif `−₺516,00` (U+2212), yüzde `%21,5`, tarih `29 Tem 2026`. Tüm UI metinleri Türkçe.

Radius: kart 10px (executive kartlar 12px) · buton/input 8px · rozet/pill 999px · avatar 999px.
Spacing: içerik padding 24px, max-width 1360px · kart arası 16px · kart iç padding 18–20px · tablo hücre 10–13px dikey / 12–20px yatay.

## Uygulama İskeleti (her ekranda ortak)
- **Sidebar 240px, sticky, tam boy** (`Sidebar.dc.html` — tek paylaşılan komponent; props: `aktif`, `workspace`, `uyariSayisi`). Zemin `#FAFAF9`, sağ hairline. Üstte workspace switcher (renkli 18px yuvarlak-kare harf rozeti + ad + chevrons-up-down; hover'da `#F5F5F4` zemin + border). Nav grupları: Genel Bakış (Dashboard, Uyarılar+kırmızı sayaç), Satış (Siparişler, SKU Marjları, Mutabakat), Ürün & Fiyat (Ürün Çalışma Alanı, Senaryolar, Komisyon Tarifeleri), Stok (Stok & Maliyet, Fatura Yükleme), Yönetim (Ayarlar). Öğe: 13px/500, 15px Lucide ikonu, radius 8, hover `#F5F5F4`; **aktif**: beyaz zemin + `inset 2px 0 0 <aksan>` sol çizgi + `inset 0 0 0 1px #E7E5E4` + aksan renkli metin/ikon. Altta plan bloğu ("Büyüme Planı · 2/3 mağaza" + 4px progress) ve "kavun · v0.4" wordmark.
- **Topbar 56px, beyaz, sticky, alt hairline**: solda breadcrumb (12px muted "Grup / ") + sayfa adı (14px/600); sağda global tarih aralığı butonu ("Son 30 gün ▾", 32px, hairline), senkron durumu (6px yeşil nokta + "Son senkron: 12 dk önce" 12px), zil ikonu + kırmızı okunmamış sayacı (beyaz 2px halkalı), 28px avatar "SA".
- **İkonlar**: Lucide seti. Prototipte `https://api.iconify.design/lucide/<ad>.svg?color=%23<hex>` ile <img>; üretimde `lucide-react` kullan.
- **Tahmini vs kesin (ürünün DNA'sı)**: kesinleşmemiş her rakamın yanında 6px amber (`#D97706`) nokta; hover'da koyu tooltip (`#1C1917` zemin, 12px, radius 6): "Tahmini — kargo faturası bekleniyor". Hücre seviyesinde görünür, asla yalnız tooltip'te değil. Rozet biçimi: `desi tahmini` (amber tint pill).
- Rozet (badge) kalıbı: 20px yükseklik, 11px/500, pill, tint zemin + 1px kenar (renkleri Tokens'ta).

## Ekranlar

### 1. Dashboard — `Dashboard.dc.html`
- 4 KPI kartı (grid 4 kolon): etiket 13px `#78716C`; büyük rakam; delta satırı (12px/500 yeşil/kırmızı + ok ikonu + "· 30 gün" muted) + sağda 64×24 sparkline (1.5px çizgi). Değerler: Ciro ₺284.650 (+%12,4), Net Kâr ₺96.470 (+%8,2, altında "₺84.320 kesin · [amber nokta] ₺12.150 tahmini" 11.5px), Marj %33,9 (−1,2 pt kırmızı), İade Oranı %4,6 (+0,7 pt kırmızı — artış kötü).
- 2. satır grid `1fr 360px`: **Günlük Net Kâr alan grafiği** (SVG 260px; kesin: `#16A34A` 1.8px çizgi + `rgba(22,163,74,0.15)` dolgu; toplam/tahmini: kesikli `rgba(22,163,74,0.45)` çizgi + `0.07` dolgu, son ~6 gün tahmini bandı büyür; yatay kesikli gridline'lar + sol ₺ etiketleri 11px; legend sağ üstte). Yanda dar kolon: "Bugün" kartı (Sipariş 46, Ciro ₺18.640, Net Kâr [amber nokta] ₺4.120, İade 3) + "Son Uyarılar" kartı (5 satır: 6px severity noktası kırmızı/amber/gri + 13px mesaj ellipsis + 11px zaman; "Tümü" → Uyarılar).
- 3. satır iki yarım kart: **Kanal Kırılımı** (Tremor bar-list: harf rozeti T/H/A + ad + ₺ + %pay; 8px track `#F5F5F4`, dolgu stone tonları — Trendyol ₺182.400 %64, Hepsiburada ₺79.700 %28, Amazon TR ₺22.550 %8) ve **SKU Kâr Uçları** (iki kolon, ortada hairline: "EN KÂRLI 5" yeşil tutarlar / "ZARAR EDEN 5" kırmızı; satır: mono SKU 11px + ad ellipsis + tutar).
- **Boş durum** (`durum="boş"` prop'u): içerik yerine ortalanmış kurulum kartı — "Kavun'a hoş geldin", 3 adım (1 aktif: amber dolu daire + "Mağaza Bağla" birincil butonu; 2-3 pasif çerçeveli daire), adımlar arası 1px dikey çizgi; topbar "Henüz senkron yok" (gri nokta) ve zil sayaçsız olur.

### 2. Sipariş Detayı — Waterfall — `Siparis Detayi.dc.html` (imza ekran)
- Grid `300px 1fr`. Sol künye kartı: #TY-8402913 + kopyala ikonu (tıklayınca clipboard + "Kopyalandı" tooltip), tarih; Kanal (T rozeti + Trendyol), Müşteri şehri İzmir, Kargo "Aras · 2,3 desi", Durum "Teslim Edildi" (yeşil pill); ayraç; Kalem: Kolombiya Supremo 1kg / KHV-014 mono / "1 adet × ₺2.400,00"; Hakediş dönemi 16–31 Ağu.
- **Şelale grafiği** (kart içi, 300px yüksek çizim alanı + 24px üst etiket payı, 7 eşit kolon; sol 44px ₺ gutter; yatay kesikli gridline her ₺600):
  - Ölçek 0,125px/₺. Barlar (kolon içinde %20–%80): Satış Fiyatı top 0 h 300 (`#E7E5E4` dolgu + `#D6D3D1` kenar); kırmızı basamaklar `rgba(220,38,38,0.8)`: Komisyon top 0 h 64.5, Kargo top 64.5 h 9.5, Hizmet top 74 h 2, Net KDV top 76 h 22.5, Ürün Maliyeti top 98.5 h 111.5; Net Kâr `#16A34A` top 210 h 90.
  - Basamaklar arası kesikli bağlantı çizgileri (`1px dashed #D6D3D1`, komşu kolonlara %18 taşan).
  - Her barın üstünde tutar (12px/600, renkli): ₺2.400,00 / −₺516,00 / −₺74,90 (+amber nokta) / −₺12,90 / −₺180,20 / −₺890,00 / ₺726,00. Altta kolon etiketleri 12px.
  - Bar hover: hafif koyulaşma + tooltip (kaynak açıklaması, ör. "Kategori: Kahve · %21,5 komisyon — API").
- Kart başlığı sağında durum satırı: amber nokta + "1 tahmini kalem — kargo faturası bekleniyor".
- Altta **Kalem Dökümü** tablosu: Kalem | Kaynak rozeti | Tutar (sağ). Rozetler: `API · kesin` (nötr), `desi tahmini` (amber+nokta), `tarife · kesin`, `hesaplanan` (mavi), `fatura · ort. maliyet`. Footer satırı `#FAFAF9`: Net Kâr + "Marj %30,3" yeşil pill + [amber nokta] ₺726,00.
- **Senaryo prop'u**: `standart` / `kargo faturası geldi` (kargo −₺78,20 kesinleşir, net ₺722,70, marj %30,1, tüm amber işaretler kalkar, "Tüm kalemler kesinleşti" yeşil) / `maliyet eksik` (grafik yerine kesikli çerçeveli boş durum: "Şelale hesaplanamıyor" + "Maliyet Ekle" birincil buton; tabloda maliyet "—" + kırmızı `maliyet eksik` rozeti; net kâr "—").

### 3. SKU Marj Listesi — `SKU Marjlari.dc.html`
- Filtre barı: arama inputu (canlı filtre), "Kanal: Tümü ▾", "Kategori: Tümü ▾", marj aralığı slider'ı (çift tutamaç, statik görsel), **"Sadece negatif marj" toggle** (aktifken kırmızı tint + kırmızı anahtar; canlı filtreler), sağda "Excel'e Aktar" birincil butonu.
- Tablo: sticky header (`#FAFAF9`), compact ~40px satır, 560px scroll alanı. Kolonlar: SKU (mono), Ürün Adı, Kanal (harf rozeti), Adet, Ciro, Birim Maliyet, Komisyon, Kargo (bazı satırlarda amber nokta), Net Kâr (yeşil `#15803D`/kırmızı), Marj % (600; negatifse kırmızı). **Rakam kolonları daima sağa hizalı.** Negatif marj satırı: `#FEF7F7` zemin + kırmızı Marj %. Satır hover `#FAFAF9`.
- 14 satır gerçek hesapla üretilir (logic'te: kâr = ciro − komisyon − kargo − hizmet(₺12,90×adet) − KDV(%7,5) − maliyet). Footer: "14 / 214 SKU · Ciro ₺… · Net kâr ₺…" + sayfalama (1 aktif, 2, 3, Önceki/Sonraki).
- Boş arama sonucu: "Sonuç yok — filtreleri gevşetmeyi dene."

### 4. Ürün Çalışma Alanı — `Urun Calisma Alani.dc.html`
- Üst: açıklama satırı + "Excel'e Aktar" (ikincil) / "Excel'den Yükle" (birincil). Fiyat listesi tablosu: SKU, Ürün, Kategori, Liste Fiyatı, Birim Maliyet, Hedef Marj, Son Güncelleme ("12 Ağu 2026 · Excel"). Footer: satır sayısı + "Son Excel yüklemesi: … · selin@kahveji.com".
- **Diff önizleme modalı** (`diffModal` prop ile açık başlar; 720px, radius 12, scrim `rgba(28,25,23,0.35)`): başlıkta dosya adı + özet rozetleri "14 yeni · 32 güncelleme · 3 hata" (yeşil/mavi/kırmızı tint pill). Gruplu listeler: her grubun satırlarında **3px sol renk çizgisi** (`inset box-shadow`; yeni=yeşil, güncelleme=mavi, hata=kırmızı). Güncelleme satırı eski→yeni: `385,00 → 414,90` (eski muted, ok ikonu, yeni 500). Hata satırı tıklanınca açılır detay (gri zemin): sebep + çözüm önerisi. Footer `#FAFAF9`: "Hatalı 3 satır atlanır; 46 satır uygulanır." + İptal / **Onayla ve Uygula**.

### 5. Fatura Yükleme & Eşleştirme — `Fatura Yukleme.dc.html`
- Full-bleed split: sol %45 (`#F5F5F4` zemin) PDF önizleme — dosya adlı 44px araç çubuğu + sayfa nav "1 / 2"; A4 oranlı beyaz sayfa placeholder'ı (gri çizgi blokları; seçili kalem satırı amber vurgulu; GENEL TOPLAM ₺48.220,00 mono).
- Sağ %55: "Ayrıştırılan satırlar · 5" başlığı + tedarikçi/tarih. Satır kartları (radius 10):
  - ✔ otomatik eşleşti: yeşil `circle-check` + ham fatura adı (büyük harf) + "120 adet × ₺176,00 = ₺21.120,00" + yeşil pill `KHV-001 · otomatik`
  - ⚠ öneri: amber `triangle-alert`, kart kenarı `#FDE68A`; amber pill "öneri: KHV-033 %87" + **Onayla** (birincil mini) / **Değiştir** (ikincil mini)
  - ○ eşleşmedi: gri `circle`; "SKU ara veya oluştur…" combobox görünümü
- **Yapışkan doğrulama barı** (alt): uyumluysa beyaz, yeşil check + "Satır toplamı ₺48.220,00 — fatura toplamıyla uyumlu" + "Onayla ve Stoğa İşle" birincil; **uyumsuzsa** (`durum` prop) kırmızı tint bar + "₺47.600,00 ≠ ₺48.220,00 — fark ₺620,00" + buton disabled (gri).
- **Boş durum**: ortalanmış kesikli çerçeveli dropzone — "Henüz fatura yok — PDF'i buraya sürükle ya da tıkla" + "PDF Seç" butonu; hover'da amber kenar.

### 6. Senaryolar — `Senaryolar.dc.html`
- Üst: ürün seçici butonu (mono SKU + ad + ▾) + sabitler özeti + "Senaryo Ekle".
- 3 senaryo kartı yan yana; **girdiler düzenlenebilir ve çıktılar canlı hesaplanır**: Satış fiyatı (₺ input), Kampanya indirimi (% input), Kargo kim öder (Satıcı/Alıcı segment toggle), Aylık adet. Çıktılar: Birim Kâr, Marj, Aylık Toplam Kâr (17px). Hesap: `net = fiyat×(1−kampanya); birim = net − net×%21,5 − kargo(74,90 satıcıysa) − 12,90 − net×%7,5 − 890`.
- En iyi toplam kârlı kart: yeşil kenar (`#BBF7D0`) + "en iyi toplam kâr" yeşil pill; en iyi değerler yeşil, negatifler kırmızı.
- Altta **Hedef Marj Hesaplayıcı** şeridi: hedef marj % inputu → "Bu marj için minimum fiyat: ₺2.618,40" canlı sonuç (`minFiyat = (maliyet+kargo+hizmet)/(1−komisyon−kdv−hedefMarj)`).

### 7. Komisyon Tarifeleri — `Komisyon Tarifeleri.dc.html`
- Segment sekmeler ("Güncel Oranlar" / "Değişiklik Geçmişi") + "Tarife Excel'i Yükle" birincil buton (aynı diff modal kalıbını kullanır).
- Oranlar: kategori ağacı tablosu — üst kategori satırı (600, oran "—", `üst kategori` rozeti), alt kategoriler `└` girintili; Oran % sağ hizalı 600; kaynak rozetleri `API` (nötr) / `Excel` (amber) / `Hakediş` (nötr); yürürlük tarihi. Sorunlu satır (Züccaciye %23,0) kırmızı tint zemin + kırmızı nokta tooltip'li. Footer notu: "Hakediş kaynaklı oranlar mutabakattan türetilir; API oranını ezer."
- Geçmiş: dikey timeline (renkli nokta + çizgi): "12 Ağu 2026 · Züccaciye · Trendyol · %21,5 → %23,0 [Hakediş]" + **etki kartı** (gri zemin): "Aylık kâr etkisi −₺4.820 · Etkilenen SKU 11 · Negatif marja düşen 3 SKU" + "Listele →" (SKU Marjları'na link).

### 8. Stok & Maliyet — `Stok ve Maliyet.dc.html`
- Üst: "Toplam stok değeri ₺318.460 · 42 SKU · ortalama maliyet yöntemi" + "Fatura Yükle" ikincil buton. Tablo: SKU, Ürün, Eldeki Adet (kritikte kırmızı + nokta tooltip), Ort. Maliyet, Stok Değeri, Son Hareket ("18 Ağu · satış").
- Satıra tıklayınca **sağdan kayan panel** (420px, scrim `rgba(28,25,23,0.2)`, sol gölge): başlıkta ürün + özet; **Maliyet Zaman Çizelgesi** — dikey timeline, hareket tipi ikonlu 24px daire rozetler: alış = yeşil ↓ (yeşil tint), satış = gri ↑, hasar = kırmızı ✕ (kırmızı tint). Kayıt örneği: "Alış faturası #A-2207 · 16 Ağu · 120 adet @ ₺176,00 · ortalama ₺100,00 → ₺114,93" (eski muted → yeni 600). Satış kaydı: "−58 adet · maliyet ₺100,00 üzerinden düşüldü · ortalama değişmez." Panel footer: hareket sayısı + "Fatura yükle →".

### 9. Mutabakat — `Mutabakat.dc.html`
- Üst özet kartı: dönem seçici ("Trendyol · 1–15 Ağu dönemi ▾") + **dairesel progress** (64px SVG halka, yeşil, içinde "%99,2") + "₺412.680 hakediş tutarı · %99,2 eşleşti" + dikey ayraç + mini metrikler (Açık fark ₺3.310 kırmızı, Kayıt 1.284/1.291, Çözülen 4 yeşil) + "Hakediş Raporu Yükle" birincil.
- Segment sekmeler: "Açık Farklar · 7" / "Eşleşmeyen Kayıtlar · 3" / "Çözülenler". Yardımcı not: "Fark = beklenen − gerçekleşen".
- Farklar tablosu (yatay scroll'lu, min 860px): Tür rozeti (komisyon/kargo nötr, ceza kırmızı), Sipariş No (mono, detaya link), Beklenen, Gerçekleşen, Fark (600; kırmızı/yeşil), Durum pill (Açık kırmızı / Açıklandı amber / Çözüldü yeşil — hepsi noktalı), satır aksiyonu "Açıkla ▾" (çözülmüşlerde açıklama metni: "desi farkı · kabul"). Footer: toplam açık fark + "Tekrarlayan komisyon farkları tarife önerisine dönüşür" notu.

### 10. Uyarılar — `Uyarilar.dc.html`
- Filtre çipleri (pill: "Tümü · 6" aktif, Marj, Komisyon, Stok, Mutabakat) + sağda "Tümünü kapat" (check-check ikonu).
- Severity gruplu listeler; grup başlığı uppercase renkli (Kritik kırmızı · Dikkat amber · Bilgi gri). Satır: **3px sol renk çizgisi** (inset shadow), tip ikonu, 13px mesaj (vurgular 600: "−%3,2", "%21,5 → %23,0"), alt satır bağlam + zaman, "İncele →" (ilgili ekrana link), "✓ Kapat" (acknowledge — tıklayınca liste boşalır).
- **Boş durum** (illüstrasyonsuz, sade metin): "Açık uyarı yok — Son tarama 14:00 · kurallar her senkronda çalışır." + "Kapatılanları göster". Zil sayacı ve sidebar rozeti 0 olur.

### 11. Ayarlar — `Ayarlar.dc.html`
- Sol iç-nav (200px, sticky; sidebar'la aynı aktif kalıbı — beyaz + amber sol çizgi): Mağazalar / Ekip & Roller / Parametreler / Faturalama.
- **Mağazalar**: bağlı mağaza kartları (harf rozeti, "Trendyol · Kahveji", maskeli ID, durum pill "Bağlı" yeşil / "Yavaş yanıt" amber; alt satır "Son senkron … · 15 dk'da bir" + "Bağlantıyı Test Et"). "+ Mağaza Bağla" → inline akış kartı: 3 adımlı stepper (Kanal seç → API bilgileri → Doğrulama), kanal seçim kartları (seçili: amber kenar + `#FFFDFB` zemin), İptal/Devam.
- **Ekip & Roller**: kullanıcı listesi (avatar, ad, e-posta) + marka bazlı rol pill'leri (marka renk noktalı: "Kahveji · Operasyon", "Alessi · Görüntüleme"); davet bekleyen amber pill; "Davet Et" birincil.
- **Parametreler**: hizmet bedeli ₺ inputu, KDV % inputu ("değişiklik geriye dönük yeniden hesap tetikler" notu); **kargo tarife tablosu** (desi aralığı, tutar, yürürlük; "Satır Ekle").
- **Faturalama** (SaaS placeholder): plan kartı (Büyüme Planı, ₺1.490/ay, kapsam, "Faturaları Gör"/"Planı Yükselt") + kullanım kartı (3 progress: mağaza 2/3, sipariş satırı 8.412/20.000, fatura ayrıştırma 61/100).

### 12. Holding Görünümü — `Holding.dc.html` (salt okunur, executive)
- Sidebar `workspace="holding"` (koyu rozet, uyarı rozeti yok); topbar'da "salt okunur" kilit pill'i; dönem "Ağustos 2026". Daha geniş boşluk (padding 32, kart padding 24–28, radius 12, gövde 14–15px, rakamlar 15–16px).
- **Marka karşılaştırmalı P&L tablosu**: kolonlar Alessi (kırmızı kare) | Kahveji (amber kare) | Toplam (gri zemin, 600). Satırlar: Ciro, Satış maliyeti, Pazaryeri kesintileri, **Net kâr** (yeşil 600 + her markada amber noktalı "₺… tahmini"), Marj. Değerler: Alessi ₺512.340 / −₺298.120 / −₺131.560 / ₺82.660 / %16,1; Kahveji ₺284.650 / −₺132.410 / −₺55.770 / ₺96.470 / %33,9; Toplam ₺796.990 / ₺179.130 / %22,5.
- İki kart: **Konsolide Stok Değeri** ₺1.284.900 (marka kırılımı satırları) ve **Açık EUR Pozisyonu** €86.400 + "kur riski" amber pill + "+1 ₺ kur artışı etkisi −₺86.400".
- **Aylık Net Kâr Trendi**: iki çizgi (Alessi `#C8102E`, Kahveji `#B45309`, 2px), Mar–Ağu, son noktalar dolu daire; altta içgörü notu. Hiçbir düzenleme aksiyonu yok.

### 13. Onboarding / Boş durumlar (kalıp)
Dashboard'un `boş` durumu birincil onboarding'dir (3 adımlı kurulum kartı). Genel kalıp: her ekranın boş hali = kısa açıklama + TEK birincil aksiyon (örn. Fatura Yükleme dropzone'u, Uyarılar "Açık uyarı yok — son tarama 14:00"). İllüstrasyon/emoji kullanılmaz.

## Etkileşimler & Davranış
- Hover: satırlar `#FAFAF9` · ikincil butonlar `border #D6D3D1 + zemin #FAFAF9` · birincil `#B45309 → #92400E` · ghost ikon butonları `#F5F5F4` · waterfall barları koyulaşır.
- Tooltip: JS ile konumlanan tek global tooltip (hedefin üst-ortası, `translate(-50%,-100%)`, 8px offset); amber noktalar, waterfall barları, kritik stok, kopyala aksiyonunda.
- Navigasyon: sidebar tüm ekranlara link; workspace rozeti → Holding; uyarı satırları ilgili ekrana; mutabakat sipariş no → Sipariş Detayı.
- Canlı mantık: SKU arama + negatif-marj filtresi; senaryo hesapları; diff modal aç/kapat; hata satırı aç/kapat; stok paneli aç/kapat; uyarı kapatma → boş durum; Ayarlar bölüm geçişi; sipariş no kopyalama (clipboard).
- Durum varyantları prop olarak modellendi (üretimde route/query state olabilir): Dashboard `durum` dolu/boş; Sipariş Detayı `senaryo` standart/kargo kesin/maliyet eksik; Fatura `durum` uyumlu/uyumsuz/boş; Uyarılar `durum`; Ayarlar `bolum`; Komisyon `sekme`; Stok `panelAcik`; Ürün `diffModal`; Sidebar `aktif`/`workspace`/`uyariSayisi`.

## State & Veri Gereksinimleri
- Global: aktif workspace (aksan rengini ve veri kapsamını belirler), tarih aralığı, senkron zamanı, okunmamış uyarı sayısı.
- Kâr hesabı tek kaynaktan: `netKâr = satış − komisyon − kargo − hizmetBedeli − netKDV − ürünMaliyeti`; her kalemin `kaynak` (API/tarife/hesaplanan/fatura/desi tahmini) ve `kesin|tahmini` bayrağı var — UI bu bayrağı amber nokta/rozetle gösterir.
- Ortalama maliyet: alış faturası işlendiğinde `yeniOrt = (eldekiAdet×eskiOrt + alınanAdet×birimFiyat) / toplamAdet`; satış ortalamayı değiştirmez.

## Yapılmayacaklar (bağlayıcı)
Koyu tema, gradyan, cam/blur, dekoratif illüstrasyon, stok görsel, emoji durum göstergesi, renkli başlık bantları, ortalanmış rakam kolonu, çift sidebar, soru cevaplamayan grafik.

## Assets
- Font: Geist + Geist Mono (Google Fonts).
- İkonlar: Lucide (üretimde `lucide-react`): layout-dashboard, bell, shopping-cart, trending-up, scale, package, git-compare-arrows, percent, boxes, file-up, settings, chevrons-up-down, chevron-down/up/left/right, calendar, arrow-up-right, arrow-down-right, arrow-right, arrow-up, arrow-down, search, download, upload, plus, x, check, check-check, copy, circle, circle-check, triangle-alert, refresh-cw, rotate-ccw, trending-down, store, users, sliders-horizontal, credit-card, lock, file-text, target.
- Kanal logoları placeholder (harfli nötr kare) — gerçek marka logosu entegrasyonu ürün ekibinin kararı.

## Dosyalar
- `Sidebar.dc.html` — paylaşılan sidebar komponenti (props: aktif, workspace, uyariSayisi)
- `Dashboard.dc.html` · `Siparis Detayi.dc.html` · `SKU Marjlari.dc.html` · `Urun Calisma Alani.dc.html` · `Fatura Yukleme.dc.html` · `Senaryolar.dc.html` · `Komisyon Tarifeleri.dc.html` · `Stok ve Maliyet.dc.html` · `Mutabakat.dc.html` · `Uyarilar.dc.html` · `Ayarlar.dc.html` · `Holding.dc.html`

Her dosya kendi başına tarayıcıda açılır; hesap mantığı ve durum geçişleri dosya sonundaki `Component` sınıfındadır.
