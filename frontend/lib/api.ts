/**
 * Kavun API istemcisi.
 *
 * Tip üretimi: `npm run gen:api` (OpenAPI şemasından) — elle API tipi yazmak yasak
 * (CLAUDE.md §4). Şu an yalnızca sağlık ucu kullanılıyor.
 */

const API_URL = process.env.KAVUN_API_URL ?? "http://localhost:8000";

export type HealthStatus = {
  online: boolean;
  environment?: string;
};

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
