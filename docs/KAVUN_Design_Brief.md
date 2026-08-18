# KAVUN — UI/UX Tasarım Brief'i (Claude Design için)

## Ürün
Pazaryeri kârlılık ve stok yönetim platformu (internal, Mokka Teknoloji). İki marka workspace'i: **Alessi** (premium İtalyan tasarım markası, ithalat) ve **Kahveji** (premium kahve e-ticaret). Kullanıcılar günde saatlerce tablo, rakam ve rapor okuyacak — bu bir finans aracı, pazarlama sitesi değil.

## Estetik Yön
- **Açık tema (light), premium, sakin.** Referans kalite çıtası: Linear (açık modu), Stripe Dashboard, Mercury Bank. Kalabalık SaaS paneli değil; disiplinli boşluk kullanımı, ince ayrımlar, az ama isabetli renk.
- Zemin: kırık beyaz (#FAFAF9 gibi), kartlar saf beyaz, ayrımlar gölge değil **1px hairline border** ile. Gölge yalnızca modal/popover'da.
- Tipografi: **Geist** (başlık + gövde), rakamlar için **tabular-nums zorunlu** — tablolarda ondalıklar alt alta hizalanacak. Büyük KPI rakamları ince/medium ağırlıkta ve büyük punto; para birimi sembolü rakamdan küçük.
- Renk disiplini: nötr gri skalası temel; **anlam taşıyan renk sadece veri için** — pozitif marj yeşil, negatif kırmızı, tahmini değerler amber. Dekoratif renk kullanılmaz.
- Marka aksanı workspace'e göre değişir: Alessi workspace'inde aksan **Alessi kırmızısı**, Kahveji'de **sıcak amber/kavrulmuş ton**. Aksan yalnızca aktif nav öğesi, birincil buton ve workspace rozetinde — ekranı boyamaz.

## Kritik UX Kalıpları
1. **Workspace kimliği her an belli:** sol üstte marka rozeti + workspace switcher. Kullanıcı hangi markanın evreninde olduğunu asla karıştırmamalı (yanlış markaya fatura yüklemek gerçek para hatası).
2. **Tahmini vs kesin ayrımı:** kâr rakamları iki durumda olabilir — `tahmini` (amber nokta/rozet) ve `kesinleşti` (nokta yok). Bu ayrım tablo hücresi seviyesinde görünür olmalı, tooltip'e gömülmemeli.
3. **Veri yoğun tablolar:** sıkı satır yüksekliği (compact), sticky header, sağa hizalı rakam sütunları, satır hover'da vurgulama, sütun bazlı sıralama. Negatif marj satırı hafif kırmızı zemin.
4. **Waterfall kâr dökümü:** sipariş detayında satış fiyatından net kâra inen şelale grafiği (satış → komisyon → kargo → hizmet bedeli → KDV → maliyet → kâr). Bu ekran ürünün imza görseli.
5. **Excel round-trip akışı:** "Excel'e Aktar" / "Excel'den Yükle" birincil aksiyonlar. Yükleme sonrası **diff önizleme** ekranı: yeşil (yeni), mavi (güncelleme), kırmızı (hata) satır grupları + onay butonu. Hata satırları açılır detayla.
6. **Fatura onay ekranı:** solda PDF önizleme, sağda ayrıştırılmış satırlar + SKU eşleştirme durumu (otomatik eşleşen: yeşil check; öneri: amber, onay ister; eşleşmeyen: gri, manuel seçim). Alt barda toplam kontrolü: "Satır toplamı ✓ fatura toplamıyla uyumlu".
7. **Alert'ler sakin:** kırmızı panik bantları yok; sağ üstte sayaçlı zil + alert listesi ekranı. Severity üç seviye: bilgi (gri), dikkat (amber), kritik (kırmızı).
8. **Boş durumlar öğretici:** ilk kullanımda her ekran ne yapılacağını gösterir ("Henüz fatura yüklenmedi — PDF'i buraya sürükle").

## Ekran Listesi (tasarlanacak)
1. Dashboard (KPI kartları: ciro, net kâr, marj %, iade % + günlük kâr çizgi grafiği + tahmini/kesin ayrımı)
2. SKU Marj Listesi (yoğun tablo, filtre barı, negatif marj vurgusu)
3. Sipariş Detayı (waterfall kâr dökümü)
4. Ürün Çalışma Alanı (fiyat listesi + Excel aktar/yükle + diff modal)
5. Yeni Ürün Değerlendir (form + anlık kâr kartı)
6. Senaryolar (senaryo listesi + 3'lü yan yana karşılaştırma + hedef marj hesaplayıcı)
7. Fatura Yükleme (PDF önizleme + satır eşleştirme + onay)
8. Stok & Maliyet (SKU listesi: eldeki adet, ortalama maliyet, stok değeri + ledger zaman çizelgesi)
9. Mutabakat (dönem özeti: eşleşme %, açık farklar tablosu)
10. Komisyon Tarifeleri (güncel oranlar + değişiklik geçmişi + tarife Excel yükleme + etki analizi kartı)
11. Uyarılar (alert listesi + acknowledge)
12. Holding Görünümü (marka karşılaştırmalı konsolide P&L — salt okunur, daha geniş boşluklu "yönetici" havası)

## Teknik Kısıtlar
- Next.js 14 + Tailwind; komponentler shadcn/ui tabanına oturabilmeli
- Masaüstü öncelikli (1440px tasarım genişliği), tablet responsive; mobil ikincil
- Türkçe UI; sayı formatı `1.234,56 ₺`; tarih `29 Tem 2026`
- Grafik kütüphanesi: Recharts ile uygulanabilir sadelikte tut
- WCAG AA kontrast; renk tek başına anlam taşımaz (ikon/rozet eşlik eder)

## Yapılmayacaklar
- Koyu tema (v1'de yok), gradyan zeminler, cam/blur efektleri, dekoratif illüstrasyon
- Dashboard'a grafik doldurma — her görsel bir soruya cevap vermeli
- Emoji tabanlı durum göstergeleri
