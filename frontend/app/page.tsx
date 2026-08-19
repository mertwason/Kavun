/** Giriş sayfası: workspace seçimi + sistem durumu (spec §3A.1). */

import Link from "next/link";

import { Card } from "@/components/ui";
import { fetchHealth } from "@/lib/api";
import { BRANDS } from "@/lib/brands";
import tr from "@/locales/tr.json";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const health = await fetchHealth();

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-20">
      <header className="flex flex-col gap-2">
        <span className="text-sm font-medium text-ink-faint">{tr.app.owner}</span>
        <h1 className="text-3xl font-medium tracking-tight">{tr.app.name}</h1>
        <p className="text-ink-muted">{tr.app.tagline}</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2">
        {Object.values(BRANDS).map((brand) => (
          <Link
            key={brand.slug}
            href={`/${brand.slug}`}
            className="card flex items-center gap-3 p-5 transition-colors hover:bg-canvas"
          >
            <span
              aria-hidden
              className="h-8 w-1.5 rounded-full"
              style={{ backgroundColor: brand.accent }}
            />
            <span className="flex flex-col">
              <span className="font-medium">{brand.name}</span>
              <span className="text-xs text-ink-faint">{tr.nav.dashboard}</span>
            </span>
          </Link>
        ))}
      </section>

      <Link
        href="/holding"
        className="card flex items-center justify-between p-5 transition-colors hover:bg-canvas"
      >
        <span className="flex flex-col">
          <span className="font-medium">{tr.holding.title}</span>
          <span className="text-xs text-ink-faint">{tr.holding.subtitle}</span>
        </span>
        <span className="text-sm text-ink-muted">{tr.holding.open}</span>
      </Link>

      <Card className="p-5">
        <h2 className="text-sm font-medium text-ink-muted">{tr.system.apiStatusTitle}</h2>
        <div className="mt-3 flex items-center gap-3">
          <span
            aria-hidden
            className={`h-2 w-2 rounded-full ${health.online ? "bg-positive" : "bg-negative"}`}
          />
          <span className="font-medium">
            {health.online ? tr.system.apiOnline : tr.system.apiOffline}
          </span>
          {health.environment ? (
            <span className="tabular text-sm text-ink-faint">
              {tr.system.environment}: {health.environment}
            </span>
          ) : null}
        </div>
        <a
          className="mt-4 inline-block text-sm text-ink-muted underline underline-offset-4 hover:text-ink"
          href="http://localhost:8000/docs"
        >
          {tr.system.apiDocs}
        </a>
      </Card>
    </main>
  );
}
