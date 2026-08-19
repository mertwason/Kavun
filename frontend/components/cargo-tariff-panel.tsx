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

const FIELD = "rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm";
const BUTTON =
  "rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas disabled:opacity-40";

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
        <p className="text-sm text-ink-muted">
          {tr.settings.noBands} <span className="text-ink-faint">{tr.settings.noBandsHint}</span>
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-hairline text-xs font-medium text-ink-faint">
                <th className="px-3 py-2 text-left">{tr.settings.carrier}</th>
                <th className="px-3 py-2 text-left">{tr.settings.desiRange}</th>
                <th className="px-3 py-2 text-right">{tr.settings.price}</th>
                <th className="px-3 py-2 text-left">{tr.settings.validFrom}</th>
                <th className="px-3 py-2 text-right" />
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
    <tr className="border-b border-hairline">
      <td className="px-3 py-2">{tariff.carrier ?? tr.settings.allCarriers}</td>
      <td className="px-3 py-2 tabular">{range}</td>
      <td className="px-3 py-2 text-right tabular">{formatMoney(tariff.price)}</td>
      <td className="px-3 py-2 text-ink-muted">{formatDate(tariff.valid_from)}</td>
      <td className="px-3 py-2 text-right">
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
          className="text-sm text-ink-muted underline underline-offset-4 hover:text-ink"
        >
          {tr.settings.closeBand}
        </button>
        {state.status === "error" ? (
          <span className="ml-2 text-xs text-negative">{state.message}</span>
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
        <p className="mt-2 text-sm text-negative">{state.message}</p>
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
            className="rounded-card border border-ink px-3 py-1.5 text-sm hover:bg-canvas disabled:opacity-40"
          >
            {tr.settings.reestimate}
          </button>
        ) : null}
        <span className="text-xs text-ink-faint">{tr.settings.reestimateNote}</span>
      </div>

      {state.status === "error" ? <p className="text-sm text-negative">{state.message}</p> : null}

      {result ? (
        <div className="flex flex-wrap items-baseline gap-6 text-sm">
          <Stat label={tr.settings.changed} value={`${result.changed} ${tr.settings.reestimateResult}`} />
          <Stat label={tr.settings.skippedActual} value={String(result.skipped_actual)} />
          <Stat
            label={tr.settings.delta}
            value={formatMoney(result.delta)}
            tone={signClass(-Number(result.delta))}
          />
          {state.status === "applied" ? (
            <span className="text-xs text-positive">{tr.settings.reestimateApplied}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="flex flex-col">
      <span className="text-xs text-ink-faint">{label}</span>
      <span className={`tabular ${tone ?? ""}`}>{value}</span>
    </span>
  );
}

function Labelled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-ink-faint">{label}</span>
      {children}
    </label>
  );
}
