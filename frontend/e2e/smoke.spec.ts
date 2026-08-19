/**
 * KVN-EK-01: ekran smoke testleri.
 *
 * Amaç dar ve net: **her ekran gerçek yığında açılıyor mu, veri geliyor mu, konsolda
 * hata var mı**. Ayrıntılı davranış backend testlerinde doğrulanıyor; burada UI'ın
 * sessizce bozulmasına karşı bir ağ geriyoruz (o boşluk PROGRESS'te risk olarak yazılıydı).
 *
 * Testler demo veriye güvenir: dolu ekran beklenir, boş ekran hata sayılır.
 */

import { expect, test } from "@playwright/test";

/** Her marka için ortak ekranlar. */
const SHARED_PAGES = [
  { path: "", heading: "Panel" },
  { path: "/sku", heading: "SKU marjları" },
  { path: "/orders", heading: "Siparişler" },
  { path: "/products", heading: "Ürün çalışma alanı" },
  { path: "/drafts", heading: "Yeni ürün değerlendir" },
  { path: "/scenarios", heading: "Senaryolar" },
  { path: "/tariffs", heading: "Komisyon tarifeleri" },
  { path: "/invoices", heading: "Alış faturaları" },
  { path: "/inventory", heading: "Stok & maliyet" },
  { path: "/cargo", heading: "Kargo faturaları" },
  { path: "/reconciliation", heading: "Hakediş mutabakatı" },
  { path: "/alerts", heading: "Uyarılar" },
  { path: "/settings", heading: "Ayarlar" },
] as const;

/** Yalnızca bayrağı açık markada (Alessi) bulunan ekranlar. */
const ALESSI_ONLY_PAGES = [
  { path: "/imports", heading: "İthalat dosyaları" },
  { path: "/d2b", heading: "D2B satışlar" },
] as const;

test.describe("ekranlar açılıyor", () => {
  for (const brand of ["alessi", "kahveji"] as const) {
    for (const page of SHARED_PAGES) {
      test(`${brand}${page.path || "/"} açılır ve konsol temiz`, async ({ page: browser }) => {
        const errors: string[] = [];
        browser.on("pageerror", (error) => errors.push(String(error)));
        browser.on("console", (message) => {
          if (message.type() === "error") errors.push(message.text());
        });

        const response = await browser.goto(`/${brand}${page.path}`);

        expect(response?.status()).toBe(200);
        await expect(browser.locator("main h1").first()).toHaveText(page.heading);
        expect(errors).toEqual([]);
      });
    }
  }

  for (const page of ALESSI_ONLY_PAGES) {
    test(`alessi${page.path} açılır`, async ({ page: browser }) => {
      const response = await browser.goto(`/alessi${page.path}`);

      expect(response?.status()).toBe(200);
      await expect(browser.locator("main h1").first()).toHaveText(page.heading);
    });
  }
});

test("panelde demo verisi görünür", async ({ page }) => {
  await page.goto("/kahveji");

  // KPI şeridi dolu olmalı: boş dashboard demo verinin bozulduğunu gösterir.
  const kpis = page.locator("[data-kpi-value]");
  await expect(kpis.first()).toBeVisible();
  await expect(await kpis.first().innerText()).toMatch(/\d/);

  // Günlük kâr grafiği ve mağaza kırılımı da render olmalı.
  await expect(page.locator("svg").first()).toBeVisible();
});

test("SKU listesi doludur; arama ve negatif marj filtresi canlı çalışır", async ({ page }) => {
  await page.goto("/kahveji/sku");

  const rows = page.locator("table tbody tr");
  const all = await rows.count();
  expect(all).toBeGreaterThan(5);

  // Negatif marj anahtarı listeyi daraltır ve kalan satırların marjı kırmızıdır.
  await page.getByRole("button", { name: "Sadece negatif marj" }).click();
  const negative = await rows.count();
  expect(negative).toBeGreaterThan(0);
  expect(negative).toBeLessThan(all);
  await expect(page.locator("main")).toContainText(`${negative} / ${all} SKU`);

  // Arama sunucuya gitmeden daraltır: eşleşmeyen terimde boş durum metni çıkar.
  await page.getByRole("button", { name: "Sadece negatif marj" }).click();
  await page.locator("input[placeholder*='ara']").fill("zzzzzz");
  await expect(page.locator("main")).toContainText("Sonuç yok");
});

test("SKU tablosu kolon başlığından sıralanır", async ({ page }) => {
  await page.goto("/kahveji/sku");

  // Varsayılan sıra: net kâr azalan. Başlığa tıklamak yönü çevirir.
  const profitHeader = page.getByRole("button", { name: /^Net Kâr/ });
  await expect(page.locator('th[aria-sort="descending"]')).toHaveCount(1);

  const firstProfit = () => page.locator("table tbody tr").first().locator("td").nth(8).innerText();
  const top = await firstProfit();

  await profitHeader.click();
  await expect(page.locator('th[aria-sort="ascending"]')).toHaveCount(1);
  expect(await firstProfit()).not.toBe(top);
});

test("SKU marj listesi Excel'e aktarılır ve filtre dosyaya taşınır", async ({ page }) => {
  await page.goto("/kahveji/sku");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /Excel'e Aktar/i }).click(),
  ]);
  expect(download.suggestedFilename()).toContain("kahveji-sku-marjlari");
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);

  // Ekrandaki filtre dosyaya da taşınmalı: aynı listeyi indirdiğinden emin olunsun.
  await page.getByRole("button", { name: "Sadece negatif marj" }).click();
  const href = await page.getByRole("link", { name: /Excel'e Aktar/i }).getAttribute("href");
  expect(href).toContain("only_negative=true");
});

test("sipariş detayında şelale render olur", async ({ page }) => {
  await page.goto("/kahveji/orders");
  await page.locator("table tbody tr a").first().click();
  await page.waitForLoadState("networkidle");

  // Şelale, tasarım brief'inin imza ekranı: adımlar görünmeli.
  await expect(page.getByText("Satış", { exact: false }).first()).toBeVisible();
  await expect(page.locator("main")).toContainText("Kâr");
});

test("kapalı modül Kahveji menüsünde yok, Alessi'de var", async ({ page }) => {
  await page.goto("/kahveji");
  const kahvejiNav = await page.locator("aside nav a").allInnerTexts();
  expect(kahvejiNav).not.toContain("İthalat dosyaları");
  expect(kahvejiNav).not.toContain("D2B satışlar");

  await page.goto("/alessi");
  const alessiNav = await page.locator("aside nav a").allInnerTexts();
  expect(alessiNav).toContain("İthalat dosyaları");
  expect(alessiNav).toContain("D2B satışlar");
});

test("kapalı modülün sayfası hata değil, 'kapalı' durumu gösterir", async ({ page }) => {
  const response = await page.goto("/kahveji/imports");

  expect(response?.status()).toBe(200);
  await expect(page.locator("main")).toContainText("Bu modül bu markada kapalı.");
});

test("holding görünümü markaları yan yana verir", async ({ page }) => {
  await page.goto("/holding");

  await expect(page.locator("main h1")).toHaveText("Holding görünümü");

  // Transpoze P&L: satırlar kalem, kolonlar marka + toplam (handoff).
  const rows = page.locator("table tbody tr");
  await expect(rows).toHaveCount(5);
  await expect(page.locator("table thead")).toContainText("Alessi");
  await expect(page.locator("table thead")).toContainText("Kahveji");
  await expect(page.locator("table thead")).toContainText("Toplam");
  await expect(rows.filter({ hasText: "Net kâr" })).toHaveCount(1);
});

test("aktif menü öğesi vurgulanır", async ({ page }) => {
  await page.goto("/alessi/inventory");

  const active = page.locator('aside nav a[aria-current="page"]');
  await expect(active).toHaveCount(1);
  await expect(active).toHaveText("Stok & maliyet");
});

test("stok ekranında hasar formu kayıt yazar", async ({ page }) => {
  await page.goto("/alessi/inventory");

  const form = page.locator("form").filter({ has: page.getByRole("button", { name: "Hasar kaydet" }) });
  await form.locator("select[name=product_id]").selectOption({ index: 1 });
  await form.locator("input[name=qty]").fill("1");
  await form.locator("input[name=reason]").fill("Smoke testi — vitrin hasarı");
  await form.getByRole("button", { name: "Hasar kaydet" }).click();

  await expect(form.locator("xpath=..").getByText("Hareket yazıldı.")).toBeVisible();
});

test("açılış stoku ikinci kez girilemez", async ({ page }) => {
  await page.goto("/alessi/inventory");

  const form = page.locator("form").first();
  await form.locator("select[name=product_id]").selectOption({ index: 1 });
  await form.locator("input[name=qty]").fill("5");
  await form.locator("input[name=unit_cost]").fill("100");
  await form.getByRole("button", { name: "Kaydet" }).click();

  // Demo veri açılışı zaten yazdı: ikinci giriş reddedilmeli (stok sessizce şişmesin).
  await expect(form.locator("xpath=..").getByText(/zaten girilmiş/)).toBeVisible();
});

test("fiyat listesi Excel'i indirilebilir", async ({ page }) => {
  await page.goto("/alessi/products");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /Excel'e Aktar/i }).click(),
  ]);

  // Dosya adı marka önekiyle üretilir (spec §3A.2).
  expect(download.suggestedFilename()).toContain("alessi");
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
});

test("kargo ekranı kesinleşme durumunu gösterir", async ({ page }) => {
  await page.goto("/kahveji/cargo");

  // Demo veride gönderilerin bir kısmı kesinleşmiş olmalı (spec §6.2).
  const kpis = await page.locator("[data-kpi-value]").allInnerTexts();
  expect(kpis.length).toBeGreaterThanOrEqual(4);
  expect(Number(kpis[1].replace(/\D/g, ""))).toBeGreaterThan(0);

  // Yüklenen fatura listesi dolu.
  await expect(page.locator("table tbody tr").last()).toContainText("KRG-");
});

test("mutabakat turu: önizleme yazmaz, uygulama fark üretir, açıklamasız kapanmaz", async ({
  page,
}) => {
  await page.goto("/kahveji/reconciliation");

  // Önizleme: kalem sayısı gelmeli ama hiçbir fark kaydı yazılmamalı (spec §7.4).
  await page.getByRole("button", { name: "Önizle" }).click();
  await expect(page.getByText("Bu bir önizlemedir")).toBeVisible();
  const records = await page.locator("[data-run-stat]").first().innerText();
  expect(Number(records)).toBeGreaterThan(0);

  // Uygulama: farklar kaydedilir ve tabloda "Açıkla" akışıyla listelenir.
  await page.getByRole("button", { name: "Uygula" }).click();
  await expect(page.getByText("Farklar kaydedildi")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Açıkla" }).first().click();

  const form = page.locator("form").filter({ has: page.locator("input[name=note]") });
  const note = form.locator("input[name=note]");
  await note.fill("ab"); // 3 karakterin altı: tarayıcı doğrulaması göndermeyi engeller
  await form.getByRole("button", { name: "Açıkla" }).click();
  await expect(note).toBeFocused();

  await note.fill("Smoke testi — platform kesinti farkı incelendi");
  await form.getByRole("button", { name: "Açıkla" }).click();
  await page.waitForLoadState("networkidle");

  // Açıklanan fark "Açık farklar" sekmesinden düşer, "Çözülenler"de durur.
  await page.getByRole("link", { name: /^Çözülenler/ }).click();
  await expect(page.locator("table")).toContainText("Açıklandı");
});

test("mutabakat ekranı veri yokken boş durumu gösterir", async ({ page }) => {
  // Alessi'de hakediş kaydı yok: ekran hata değil, boş durum vermeli.
  await page.goto("/alessi/reconciliation");

  await expect(page.locator("main")).toContainText("Henüz mutabakat turu koşulmadı.");
});

test("ayarlarda kargo tarifesi dolu ve geçersiz bant reddedilir", async ({ page }) => {
  await page.goto("/kahveji/settings");

  // Demo tarifesi ekranda görünmeli: gönderi maliyetleri bu bantlardan üretiliyor.
  const bands = page.locator("table tbody tr");
  expect(await bands.count()).toBeGreaterThan(3);
  await expect(page.locator("main")).toContainText("Tüm firmalar");

  const form = page.locator("form").filter({ has: page.locator("input[name=desi_min]") });
  await form.locator("input[name=desi_min]").fill("5");
  await form.locator("input[name=desi_max]").fill("2");
  await form.locator("input[name=price]").fill("10");
  await form.getByRole("button", { name: "Bant ekle" }).click();

  // Ters aralık sessizce kabul edilmez.
  await expect(page.locator("main")).toContainText("Desi üst sınırı alt sınırdan büyük olmalı");
});

test("bağlantı bilgileri kaydedilir ama ekrana geri dönmez", async ({ page }) => {
  await page.goto("/alessi/settings");

  const form = page.locator("form").filter({ has: page.locator("input[name=cred_api_key]") }).first();
  await form.locator("input[name=cred_api_key]").fill("E2E-KEY");
  await form.locator("input[name=cred_api_secret]").fill("E2E-SECRET");
  await form.locator("input[name=cred_seller_id]").fill("123456");
  await form.getByRole("button", { name: "Bağlantıyı kaydet" }).click();

  // Kaydedilen değer hiçbir alanda geri gösterilmez (CLAUDE.md §2).
  await expect(form.locator("input[name=cred_api_key]")).toHaveValue("");
  await expect(page.locator("main")).not.toContainText("E2E-SECRET");
  await page.reload();
  await expect(page.locator("main")).toContainText("Kayıtlı");
});

test("tahmin yenileme kesinleşmiş maliyete dokunmaz", async ({ page }) => {
  await page.goto("/kahveji/settings");

  await page.getByRole("button", { name: "Önizle" }).click();
  await expect(page.getByText("Kesinleşmiş (dokunulmadı)")).toBeVisible();

  // Kargo faturasıyla kesinleşmiş gönderiler önizlemede "dokunulmadı" sayısına düşer.
  const skipped = page
    .locator("span")
    .filter({ hasText: /^Kesinleşmiş \(dokunulmadı\)$/ })
    .locator("xpath=following-sibling::span");
  expect(Number(await skipped.innerText())).toBeGreaterThan(0);
});

test("uyarı listesi doludur ve seviye filtresi çalışır", async ({ page }) => {
  await page.goto("/kahveji/alerts");

  const rows = page.locator("[data-alert-row]");
  const all = await rows.count();
  expect(all).toBeGreaterThan(0);

  // Liste aciliyete göre gruplanır. Kaç grup kaldığı sabit DEĞİLDİR: "gördüm" testi her
  // turda bir uyarı kapatıyor, demo veri de tur arasında yenilenmiyor olabilir.
  const groups = page.locator("[data-alert-group]");
  expect(await groups.count()).toBeGreaterThan(0);

  // Seviye SABİT seçilmez: "gördüm" testi uyarı kapattığı için hangi seviyenin ekranda
  // kaldığı turlar arasında değişir. En üstteki grubun seviyesi filtrelenir.
  const severity = await groups.first().getAttribute("data-alert-group");
  const label = { critical: "Kritik", warning: "Dikkat", info: "Bilgi" }[severity ?? ""];
  await page.getByRole("link", { name: new RegExp(`^${label}`) }).click();
  await page.waitForLoadState("networkidle");

  // Filtrelenmiş liste daralmalı ve yalnızca o seviye kalmalı.
  const filtered = await rows.count();
  expect(filtered).toBeLessThanOrEqual(all);
  await expect(groups).toHaveCount(1);
  await expect(page.locator(`[data-alert-group="${severity}"]`)).toBeVisible();
});

test("uyarı kapatılır ama silinmez", async ({ page }) => {
  await page.goto("/kahveji/alerts");

  const rows = page.locator("[data-alert-row]");
  const before = await rows.count();
  // En az acil uyarı kapatılır: kritik grubu tüketirsek seviye filtresi testi
  // demo veriyi ikinci turda bulamazdı.
  await page.getByRole("button", { name: "Kapat" }).last().click();
  await page.waitForTimeout(500);
  await page.reload();

  // Açık listeden düşer...
  await expect(rows).toHaveCount(before - 1);

  // ...ama "Kapatılmış" filtresinde durur (spec §10.6: silme yok).
  await page.goto("/kahveji/alerts?status=acknowledged");
  expect(await rows.count()).toBeGreaterThan(0);
  await expect(page.locator("main")).toContainText("Kapatıldı");
});

test("uyarı filtreleri URL'de taşınır", async ({ page }) => {
  await page.goto("/alessi/alerts?severity=critical");

  // Paylaşılan adres doğrudan filtreli açılmalı.
  const active = page.locator('main a[aria-current="true"]');
  await expect(active.filter({ hasText: "Kritik" })).toHaveCount(1);
});

test("fatura onay ekranı eşleşmemiş satırda onayı kapatır, öneriyi gösterir", async ({ page }) => {
  await page.goto("/kahveji/invoices");
  await page.getByRole("link", { name: "EGE20260012" }).click();

  // Fuzzy öneri otomatik kabul edilmez: rozet + onay butonu ile kullanıcıya sorulur.
  await expect(page.getByText("öneri:")).toBeVisible();
  await expect(page.locator("main")).toContainText("KHV-GTM-250");

  // Hiç benzemeyen satır için öneri yok, yalnızca SKU seçici kalır.
  await expect(page.getByRole("combobox").last()).toBeVisible();

  // Eşleşmemiş satır varken stoka işleme kapalıdır (sunucu da reddeder).
  await expect(page.getByRole("button", { name: "Onayla ve stoka işle" })).toBeDisabled();
  await expect(page.locator("main")).toContainText("2 satır henüz bir SKU'ya bağlanmadı");
});

test("fatura toplamı tutmuyorsa onay kapalı ve fark yazılı", async ({ page }) => {
  await page.goto("/kahveji/invoices");
  await page.getByRole("link", { name: "EGE20260078" }).click();

  // Okunamayan satır yüzünden satır toplamı fatura toplamını tutmuyor.
  await expect(page.locator("main")).toContainText("fark var");
  await expect(page.getByRole("button", { name: "Onayla ve stoka işle" })).toBeDisabled();
});

test("mağaza bağlama sihirbazı üç adımda ilerler", async ({ page }) => {
  await page.goto("/kahveji/settings");

  await page.getByRole("button", { name: "Mağaza bağla" }).click();

  // 1. adım: kanal seçimi — seçim aria-pressed ile taşınır.
  const trendyol = page.getByRole("button", { name: /^Trendyol/ });
  await expect(trendyol).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Devam" }).click();

  // 2. adım: kanalın istediği bağlantı alanları çıkar (Trendyol → api_key/secret/seller).
  await expect(page.locator("input[name=wizard_cred_api_key]")).toBeVisible();
  await expect(page.locator("input[name=wizard_cred_seller_id]")).toBeVisible();

  // Sihirbaz iptal edilince ekran ilk hâline döner; hiçbir kayıt yazılmaz.
  await page.getByRole("button", { name: "İptal" }).click();
  await expect(page.getByRole("button", { name: "Mağaza bağla" })).toBeVisible();
});
