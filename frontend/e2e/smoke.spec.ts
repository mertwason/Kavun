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
  const kpis = page.locator(".card .tabular");
  await expect(kpis.first()).toBeVisible();
  await expect(await kpis.first().innerText()).toMatch(/\d/);

  // Günlük kâr grafiği ve mağaza kırılımı da render olmalı.
  await expect(page.locator("svg").first()).toBeVisible();
});

test("SKU listesi doludur ve negatif marj filtresi çalışır", async ({ page }) => {
  await page.goto("/kahveji/sku");

  const rows = page.locator("table tbody tr");
  const all = await rows.count();
  expect(all).toBeGreaterThan(5);

  await page.getByRole("link", { name: "Yalnızca negatif marj" }).click();
  await page.waitForLoadState("networkidle");

  const filtered = await page.locator("table tbody tr").count();
  expect(filtered).toBeLessThanOrEqual(all);
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
  const rows = page.locator("table tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(page.locator("main")).toContainText("Alessi");
  await expect(page.locator("main")).toContainText("Kahveji");
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
  const kpis = await page.locator(".card .tabular").allInnerTexts();
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
  const records = await page.locator("span.tabular.text-lg").first().innerText();
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
  await expect(page.locator("table")).toContainText("Açıklandı");
});

test("mutabakat ekranı veri yokken boş durumu gösterir", async ({ page }) => {
  // Alessi'de hakediş kaydı yok: ekran hata değil, boş durum vermeli.
  await page.goto("/alessi/reconciliation");

  await expect(page.locator("main")).toContainText("Bu dönemde fark yok.");
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

  const all = await page.locator("table tbody tr").count();
  expect(all).toBeGreaterThan(0);

  await page.getByRole("link", { name: "Kritik", exact: true }).click();
  await page.waitForLoadState("networkidle");

  // Filtrelenmiş liste daralmalı ve yalnızca kritik satır kalmalı.
  const filtered = await page.locator("table tbody tr").count();
  expect(filtered).toBeLessThanOrEqual(all);
  await expect(page.locator("table tbody")).not.toContainText("Bilgi");
});

test("uyarı kapatılır ama silinmez", async ({ page }) => {
  await page.goto("/kahveji/alerts");

  const before = await page.locator("table tbody tr").count();
  await page.getByRole("button", { name: "Gördüm" }).first().click();
  await page.waitForTimeout(500);
  await page.reload();

  // Açık listeden düşer...
  await expect(page.locator("table tbody tr")).toHaveCount(before - 1);

  // ...ama "Kapatılmış" filtresinde durur (spec §10.6: silme yok).
  await page.goto("/kahveji/alerts?status=acknowledged");
  expect(await page.locator("table tbody tr").count()).toBeGreaterThan(0);
  await expect(page.locator("main")).toContainText("Kapatıldı");
});

test("uyarı filtreleri URL'de taşınır", async ({ page }) => {
  await page.goto("/alessi/alerts?severity=critical");

  // Paylaşılan adres doğrudan filtreli açılmalı.
  const active = page.locator('main a[aria-current="true"]');
  await expect(active.filter({ hasText: "Kritik" })).toHaveCount(1);
});
