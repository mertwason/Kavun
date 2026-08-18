import { fetchHealth } from "@/lib/api";
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

      <section className="card p-5">
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
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-medium text-ink-muted">{tr.roadmap.title}</h2>
        <p className="mt-1 text-sm text-ink-faint">{tr.roadmap.subtitle}</p>
        <ul className="mt-4 flex flex-col gap-2 text-sm">
          <li className="flex items-start gap-3 border-t border-hairline pt-3">
            <span className="text-positive">✓</span>
            <span>{tr.roadmap.done}</span>
          </li>
          <li className="flex items-start gap-3 border-t border-hairline pt-3 text-ink-muted">
            <span className="text-ink-faint">→</span>
            <span>{tr.roadmap.next}</span>
          </li>
        </ul>
      </section>
    </main>
  );
}
