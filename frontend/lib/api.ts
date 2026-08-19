/**
 * Kavun API istemcisi.
 *
 * Tipler OpenAPI şemasından üretilir (`npm run gen:api`) — elle API tipi yazmak
 * yasak (CLAUDE.md §4). Bu dosya yalnızca üretilen tipleri kullanır.
 *
 * Oturum: gerçek kurulumda token ops.mokka SSO'sundan gelir. Local/CI'da
 * `POST /auth/dev-login` ile alınır; bu uç diğer ortamlarda 404 döndüğü için
 * ortam sızıntısı riski yok (spec §3A).
 */

import type { components, paths } from "@/lib/api-types";

const API_URL = process.env.KAVUN_API_URL ?? "http://localhost:8000";
const DEV_USER = process.env.KAVUN_DEV_USER ?? "demo@mokkalabs.com";

export type Dashboard = components["schemas"]["DashboardOut"];
export type SkuMargin = components["schemas"]["SkuMarginOut"];
export type OrderRow = components["schemas"]["OrderRowOut"];
export type OrderDetail = components["schemas"]["OrderDetailOut"];
export type WaterfallStep = components["schemas"]["WaterfallStep"];
export type PriceRow = components["schemas"]["PriceRowOut"];
export type ImportSummary = components["schemas"]["ImportSummaryOut"];

export type HealthStatus = {
  online: boolean;
  environment?: string;
};

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; reason: string };

type DashboardQuery = paths["/{brand_slug}/dashboard"]["get"]["parameters"]["query"];

export async function fetchHealth(): Promise<HealthStatus> {
  try {
    const response = await fetch(`${API_URL}/healthz`, { cache: "no-store" });
    if (!response.ok) {
      return { online: false };
    }
    const payload = (await response.json()) as { environment?: string };
    return { online: true, environment: payload.environment };
  } catch {
    return { online: false };
  }
}

async function issueToken(brand: string): Promise<string | null> {
  try {
    const response = await fetch(`${API_URL}/auth/dev-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: DEV_USER, brand }),
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    const payload = (await response.json()) as { access_token: string };
    return payload.access_token;
  } catch {
    return null;
  }
}

/** Marka kapsamlı GET; hata durumunda ekranın kırılmaması için sonuç tipi döner. */
async function get<T>(brand: string, path: string): Promise<ApiResult<T>> {
  const token = await issueToken(brand);
  if (!token) {
    return { ok: false, status: 401, reason: "no-session" };
  }
  try {
    const response = await fetch(`${API_URL}/${brand}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      return { ok: false, status: response.status, reason: "http-error" };
    }
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return { ok: false, status: 0, reason: "unreachable" };
  }
}

function periodQuery(query?: DashboardQuery): string {
  const params = new URLSearchParams();
  if (query?.from) params.set("from", String(query.from));
  if (query?.to) params.set("to", String(query.to));
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

export function fetchDashboard(brand: string, query?: DashboardQuery) {
  return get<Dashboard>(brand, `/dashboard${periodQuery(query)}`);
}

export function fetchSkuMargins(brand: string, query?: DashboardQuery) {
  return get<SkuMargin[]>(brand, `/sku-margins${periodQuery(query)}`);
}

export function fetchOrders(brand: string, query?: DashboardQuery) {
  return get<OrderRow[]>(brand, `/orders${periodQuery(query)}`);
}

export function fetchOrderDetail(brand: string, orderId: string) {
  return get<OrderDetail>(brand, `/orders/${orderId}`);
}

export function fetchPriceRows(brand: string) {
  return get<PriceRow[]>(brand, "/price-list");
}

/** Fiyat listesi dosyasını indirir (tarayıcı token taşıyamadığı için sunucudan geçer). */
export async function downloadPriceList(
  brand: string,
): Promise<{ ok: true; body: ArrayBuffer; filename: string } | { ok: false; status: number }> {
  const token = await issueToken(brand);
  if (!token) return { ok: false, status: 401 };
  const response = await fetch(`${API_URL}/${brand}/price-list/export`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) return { ok: false, status: response.status };
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  return {
    ok: true,
    body: await response.arrayBuffer(),
    filename: match ? match[1] : `kavun-fiyat-listesi-${brand}.xlsx`,
  };
}

/** Yüklenen dosyayı API'ye iletir; `dryRun` iken hiçbir şey yazılmaz. */
export async function uploadPriceList(
  brand: string,
  file: File,
  dryRun: boolean,
): Promise<ApiResult<ImportSummary> & { detail?: string }> {
  const token = await issueToken(brand);
  if (!token) return { ok: false, status: 401, reason: "no-session" };
  const form = new FormData();
  form.append("file", file, file.name);
  try {
    const response = await fetch(
      `${API_URL}/${brand}/price-list/import?dry_run=${dryRun ? "true" : "false"}`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form, cache: "no-store" },
    );
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      return {
        ok: false,
        status: response.status,
        reason: "http-error",
        detail: payload?.detail,
      };
    }
    return { ok: true, data: (await response.json()) as ImportSummary };
  } catch {
    return { ok: false, status: 0, reason: "unreachable" };
  }
}
