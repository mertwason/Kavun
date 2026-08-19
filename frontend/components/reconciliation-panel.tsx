"use client";

/**
 * Mutabakat paneli: turu çalıştır + farkları açıkla (spec §7.4).
 *
 * Önce `dry_run` önizleme — kaç kalem eşleşti, kaç fark çıktı. Onaydan sonra farklar
 * kaydedilir ve her biri **açıklama notuyla** kapatılabilir; açıklamasız kapatma yoktur.
 */

import { useState, useTransition } from "react";

import {
  applyRun,
  explainAction,
  type ExplainState,
  previewRun,
  type RunState,
} from "@/app/[brand]/reconciliation/actions";
import type { ReconciliationDiff } from "@/lib/api";
import type { BrandSlug } from "@/lib/brands";
import { formatDateTime, formatMoney, formatPercent, signClass } from "@/lib/format";
import tr from "@/locales/tr.json";

const STATUS_LABELS: Record<string, string> = tr.reconciliation.statuses;
const RECORD_TYPES: Record<string, string> = tr.reconciliation.recordTypes;

const FIELD = "control";

export function ReconciliationRunner({
  brand,
  periods,
}: {
  brand: BrandSlug;
  periods: string[];
}) {
  const [period, setPeriod] = useState(periods[0] ?? currentPeriod());
  const [state, setState] = useState<RunState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const send = (apply: boolean) => {
    const formData = new FormData();
    formData.append("brand", brand);
    formData.append("period", period);
    startTransition(async () => {
      const action = apply ? applyRun : previewRun;
      setState(await action({ status: "idle" }, formData));
    });
  };

  const result = state.result;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.reconciliation.period}</span>
          <input
            type="month"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            className={`${FIELD} w-36`}
          />
        </label>
        <button
          type="button"
          onClick={() => send(false)}
          disabled={pending || !period}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.reconciliation.running : tr.reconciliation.preview}
        </button>
        {state.status === "preview" ? (
          <button
            type="button"
            onClick={() => send(true)}
            disabled={pending}
            className="h-[34px] rounded-control border border-ink bg-ink px-3 text-cell font-medium text-white hover:bg-ink-secondary disabled:opacity-40"
          >
            {tr.reconciliation.apply}
          </button>
        ) : null}
      </div>

      {state.status === "error" ? <p className="text-cell text-negative">{state.message}</p> : null}

      {result ? (
        <div className="flex flex-col gap-3 border-t border-hairline pt-3">
          <div className="flex flex-wrap items-baseline gap-6 text-sm">
            <Stat label={tr.reconciliation.records} value={String(result.records)} />
            <Stat
              label={tr.reconciliation.matchRate}
              value={formatPercent(result.match_rate_pct)}
              tone={Number(result.match_rate_pct) < 99 ? "text-negative" : "text-positive"}
            />
            <Stat label={tr.reconciliation.withinTolerance} value={String(result.within_tolerance)} />
            <Stat
              label={tr.reconciliation.diffs}
              value={String(result.diffs)}
              tone={result.diffs > 0 ? "text-negative" : undefined}
            />
            <Stat
              label={tr.reconciliation.unmatched}
              value={String(result.unmatched)}
              tone={result.unmatched > 0 ? "text-negative" : undefined}
            />
            <Stat label={tr.reconciliation.totalDiff} value={formatMoney(result.total_diff)} />
          </div>
          <p className="text-helper text-ink-body">
            {state.status === "applied"
              ? tr.reconciliation.appliedNote
              : tr.reconciliation.previewNote}
          </p>
          {result.unmatched_refs.length > 0 ? (
            <p className="text-helper text-ink-muted">
              {tr.reconciliation.unmatchedRefs}: {result.unmatched_refs.join(", ")}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Fark durumunun rozet rengi: açık kırmızı, açıklanan amber, çözülen yeşil. */
const STATUS_STYLE: Record<string, string> = {
  open: "border-negative-border bg-negative-tint text-negative",
  explained: "border-estimated-border bg-estimated-tint text-estimated-text",
  resolved: "border-positive-border bg-positive-tint text-positive-text",
};

export function DiffRow({ brand, diff }: { brand: BrandSlug; diff: ReconciliationDiff }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<ExplainState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  return (
    <>
      <tr className="border-b border-hairline hover:bg-canvas">
        <td className="px-3 py-2.5 pl-5">
          {diff.record_type ? RECORD_TYPES[diff.record_type] ?? diff.record_type : "—"}
        </td>
        <td
          className="px-3 py-2.5 font-mono text-micro text-ink-secondary"
          title={formatDateTime(diff.created_at)}
        >
          {diff.order_ref ?? "—"}
        </td>
        <td className="px-3 py-2.5 text-right">{formatMoney(diff.expected)}</td>
        <td className="px-3 py-2.5 text-right">{formatMoney(diff.actual)}</td>
        <td className={`px-3 py-2.5 text-right font-semibold ${signClass(-Number(diff.diff))}`}>
          {formatMoney(diff.diff)}
        </td>
        <td className="px-3 py-2.5">
          <span className={`badge ${STATUS_STYLE[diff.status] ?? ""}`}>
            {STATUS_LABELS[diff.status] ?? diff.status}
          </span>
        </td>
        <td className="px-3 py-2.5 pr-5 text-helper text-ink-muted">
          {diff.status === "open" ? (
            <button
              type="button"
              onClick={() => setOpen((value) => !value)}
              className="flex h-7 items-center rounded-control border border-hairline bg-surface px-2.5 text-helper font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
            >
              {tr.reconciliation.explain}
            </button>
          ) : (
            diff.note
          )}
        </td>
      </tr>
      {open ? (
        <tr className="border-b border-hairline bg-canvas">
          <td colSpan={7} className="px-5 py-3">
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault();
                const form = event.currentTarget;
                const formData = new FormData(form);
                formData.set("brand", brand);
                formData.set("diff_id", diff.id);
                startTransition(async () => {
                  const next = await explainAction({ status: "idle" }, formData);
                  setState(next);
                  if (next.status === "saved") setOpen(false);
                });
              }}
            >
              <label className="flex flex-1 flex-col gap-1 text-xs">
                <span className="text-ink-faint">{tr.reconciliation.note} *</span>
                <input name="note" type="text" required minLength={3} className={`${FIELD} w-full`} />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                <span className="text-ink-faint">{tr.reconciliation.status}</span>
                <select name="status" defaultValue="explained" className={`${FIELD} w-36`}>
                  <option value="explained">{STATUS_LABELS.explained}</option>
                  <option value="resolved">{STATUS_LABELS.resolved}</option>
                </select>
              </label>
              <button
                type="submit"
                disabled={pending}
                className="rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas disabled:opacity-40"
              >
                {tr.reconciliation.explain}
              </button>
              <span className="text-xs text-ink-faint">{tr.reconciliation.explainHint}</span>
            </form>
            {state.status === "error" ? (
              <p className="mt-2 text-sm text-negative">{state.message}</p>
            ) : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <span className="flex flex-col gap-0.5">
      <span className="col-head">{label}</span>
      <span data-run-stat className={`text-kpiSm ${tone ?? ""}`}>
        {value}
      </span>
    </span>
  );
}

/** Varsayılan dönem: içinde bulunulan ay. */
function currentPeriod(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}
