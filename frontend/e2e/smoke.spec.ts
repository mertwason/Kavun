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
  const kahvejiNav = await page.locator("header nav a").allInnerTexts();
  expect(kahvejiNav).not.toContain("İthalat dosyaları");
  expect(kahvejiNav).not.toContain("D2B satışlar");

  await page.goto("/alessi");
  const alessiNav = await page.locator("header nav a").allInnerTexts();
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

  const active = page.locator('header nav a[aria-current="page"]');
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
