/**
 * Playwright yapılandırması — smoke testleri (KVN-EK-01).
 *
 * Testler **çalışan bir yığına** karşı koşar (Postgres + API + frontend). Yerelde
 * `make dev` sonrası, CI'da `docker compose` işinde ayakta olan ortama bağlanır;
 * Playwright kendi sunucusunu başlatmaz — asıl amaç "gerçek yığın gerçekten açılıyor mu"
 * sorusunu yanıtlamak.
 *
 * Ön koşul: demo veri yüklü olmalı (`make seed-demo` + `make recompute`), çünkü testler
 * hem boş hem dolu durumu değil, **gezilebilir dolu durumu** doğrular (CLAUDE.md §6).
 */

import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.KAVUN_WEB_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  // Smoke testleri hızlı olmalı; takılan bir test yığının bozuk olduğunu söyler.
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["list"], ["github"]] : [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    // Ortamdaki hazır tarayıcı kullanılır; sürüm uyuşmazlığında bu değişkenle ezilir.
    ...(process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } }
      : {}),
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
