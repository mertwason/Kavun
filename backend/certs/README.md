# Ek kök sertifikalar

TLS trafiğini inceleyen kurumsal ağlarda (MITM proxy) imaj kurulumları sertifika hatası verir.
Kurumun kök sertifikasını bu dizine `*.crt` olarak koyun; imaj derlenirken sistem sertifika
deposuna eklenir. Dizin boşken hiçbir şey değişmez.

`.crt` dosyaları repoya commit edilmez (bkz. `.gitignore`).
