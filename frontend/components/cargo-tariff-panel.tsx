"use client";

/**
 * Kargo tarifesi paneli (spec §6.1, §10.7).
 *
 * Bantlar `[alt, üst)` aralığıdır; kargo tahmini bunlardan çözülür. Tarife değiştirmek
 * geçmişi kendiliğinden değiştirmez — "Tahminleri yenile" ayrı ve açık bir eylemdir,
 * önce önizler, yalnızca tahmini gönderilere dokunur.
 */

import { useState, useTransition } from "react";

import {
  addTariffAction,
  closeTariffAction,
  type FormState,
  reestimateAction,
  type ReestimateState,
} from "@/app/[brand]/settings/actions";
import type { CargoTariff } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDate, formatDesi, formatMoney, signClass } from "@/lib/format";
import tr from "@/locales/tr.json";

const FIELD = "control";
const BUTTON =
  "h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40";

export function CargoTariffPanel({
  brand,
  tariffs,
}: {
  brand: BrandSlug;
  tariffs: CargoTariff[];
}) {
  return (
    <div className="flex flex-col gap-4">
      {tariffs.length === 0 ? (
        <p className="text-cell text-ink-body">
          {tr.settings.noBands} <span className="text-ink-muted">{tr.settings.noBandsHint}</span>
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-cell">
            <thead>
              <tr>
                <Head>{tr.settings.carrier}</Head>
                <Head>{tr.settings.desiRange}</Head>
                <Head align="right">{tr.settings.price}</Head>
                <Head>{tr.settings.validFrom}</Head>
                <Head align="right"> </Head>
              </tr>
            </thead>
            <tbody>
              {tariffs.map((row) => (
                <TariffRow key={row.id} brand={brand} tariff={row} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AddBandForm brand={brand} />
      <ReestimatePanel brand={brand} />
    </div>
  );
}

function TariffRow({ brand, tariff }: { brand: BrandSlug; tariff: CargoTariff }) {
  const [state, setState] = useState<FormState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const range =
    tariff.desi_max === null
      ? `${formatDesi(tariff.desi_min)} ${tr.settings.unbounded}`
      : `${formatDesi(tariff.desi_min)} – ${formatDesi(tariff.desi_max)}`;

  return (
    <tr className="border-b border-hairline hover:bg-canvas">
      <td className="px-3 py-2.5">{tariff.carrier ?? tr.settings.allCarriers}</td>
      <td className="px-3 py-2.5">{range}</td>
      <td className="px-3 py-2.5 text-right">{formatMoney(tariff.price)}</td>
      <td className="px-3 py-2.5 text-ink-secondary">{formatDate(tariff.valid_from)}</td>
      <td className="px-3 py-2.5 text-right">
        <button
          type="button"
          disabled={pending}
          title={tr.settings.closeBandHint}
          onClick={() => {
            const formData = new FormData();
            formData.set("brand", brand);
            formData.set("tariff_id", tariff.id);
            startTransition(async () => setState(await closeTariffAction({ status: "idle" }, formData)));
          }}
          className="text-helper text-ink-muted underline decoration-ink-ghost underline-offset-4 hover:text-ink"
        >
          {tr.settings.closeBand}
        </button>
        {state.status === "error" ? (
          <span className="ml-2 text-helper text-negative">{state.message}</span>
        ) : null}
      </td>
    </tr>
  );
}

function AddBandForm({ brand }: { brand: BrandSlug }) {
  const [state, setState] = useState<FormState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  return (
    <div className="border-t border-hairline pt-3">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const formData = new FormData(form);
          formData.set("brand", brand);
          startTransition(async () => {
            const next = await addTariffAction({ status: "idle" }, formData);
            setState(next);
            if (next.status === "saved") form.reset();
          });
        }}
      >
        <Labelled label={tr.settings.carrier}>
          <input name="carrier" placeholder={tr.settings.allCarriers} className={`${FIELD} w-40`} />
        </Labelled>
        <Labelled label={tr.settings.desiMin}>
          <input name="desi_min" required inputMode="decimal" className={`${FIELD} w-24 tabular`} />
        </Labelled>
        <Labelled label={tr.settings.desiMax}>
          <input name="desi_max" inputMode="decimal" className={`${FIELD} w-24 tabular`} />
        </Labelled>
        <Labelled label={tr.settings.price}>
          <input name="price" required inputMode="decimal" className={`${FIELD} w-28 tabular`} />
        </Labelled>
        <Labelled label={tr.settings.validFrom}>
          <input name="valid_from" type="date" className={`${FIELD} w-40`} />
        </Labelled>
        <button type="submit" disabled={pending} className={BUTTON}>
          {tr.settings.addBand}
        </button>
      </form>
      {state.status === "error" ? (
        <p className="mt-2 text-cell text-negative">{state.message}</p>
      ) : null}
    </div>
  );
}

function ReestimatePanel({ brand }: { brand: BrandSlug }) {
  const [state, setState] = useState<ReestimateState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const send = (apply: boolean) => {
    const formData = new FormData();
    formData.set("brand", brand);
    if (apply) formData.set("apply", "1");
    startTransition(async () => setState(await reestimateAction({ status: "idle" }, formData)));
  };

  const result = state.result;

  return (
    <div className="flex flex-col gap-2 border-t border-hairline pt-3">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={() => send(false)} disabled={pending} className={BUTTON}>
          {tr.settings.reestimatePreview}
        </button>
        {state.status === "preview" && result && result.changed > 0 ? (
          <button
            type="button"
            onClick={() => send(true)}
            disabled={pending}
            className="h-[34px] rounded-control border border-ink bg-ink px-3 text-cell font-medium text-white hover:bg-ink-secondary disabled:opacity-40"
          >
            {tr.settings.reestimate}
          </button>
        ) : null}
        <span className="text-helper text-ink-muted">{tr.settings.reestimateNote}</span>
      </div>

      {state.status === "error" ? <p className="text-cell text-negative">{state.message}</p> : null}

      {result ? (
        <div className="flex flex-wrap items-baseline gap-6 text-cell">
          <Stat label={tr.settings.changed} value={`${result.changed} ${tr.settings.reestimateResult}`} />
          <Stat label={tr.settings.skippedActual} value={String(result.skipped_actual)} />
          <Stat
            label={tr.settings.delta}
            value={formatMoney(result.delta)}
            tone={signClass(-Number(result.delta))}
          />
          {state.status === "applied" ? (
            <span className="text-helper text-positive-text">{tr.settings.reestimateApplied}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="flex flex-col gap-0.5">
      <span className="col-head">{label}</span>
      <span className={tone ?? ""}>{value}</span>
    </span>
  );
}

function Labelled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="col-head">{label}</span>
      {children}
    </label>
  );
}

function Head({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  /** Hizalama prop'tur, sınıfla ezilmez (bkz. `sku-table.tsx`). */
  align?: "left" | "right";
}) {
  return (
    <th
      className={`border-b border-hairline bg-canvas px-3 py-2.5 ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      <span className="col-head">{children}</span>
    </th>
  );
}
