# Tarife fixture'ları

`trendyol_komisyon_2026_09.xlsx` — Trendyol'un yayımladığı kategori komisyon tarifesi
dosyalarının **yapısını** taklit eder: başlık satırı ilk satırda değildir (üstte duyuru
blokları vardır), sütun sırası sabit değildir, oranlar `%21,5` biçiminde metin gelir ve
kategori çok seviyelidir (ana > alt).

**Bu dosya canlı indirilmiş bir Trendyol dosyası DEĞİLDİR** (gerçek satıcı hesabı ve
Trendyol'un yayın sayfasına erişim yok). Parser'ın "dosyayı olduğu gibi oku" davranışını
sınamak için bu yapı yeterlidir; ilk gerçek tarife dosyası elde edildiğinde bu fixture
onunla değiştirilmeli ve testler tekrar çalıştırılmalıdır (spec §12B.2 kabul kriteri).

İçerikte Kavun kataloğunda karşılığı OLMAYAN kategoriler de bilinçli olarak vardır
(`Elektronik/...`) — bunlar hata değil, `unmatched` listesinde raporlanır.
