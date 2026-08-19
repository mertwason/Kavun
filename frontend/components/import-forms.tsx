"use client";

/** İthalat dosyası formları: masraf kalemi, ödeme, onay (spec §12C.7-8). */

import { useState, useTransition } from "react";

import {
  addCostItemAction,
  confirmFileAction,
  type ImportActionState,
  recordPaymentAction,
} from "@/app/[brand]/imports/[fileId]/actions";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

const FIELD = "rounded-card border border-hairline bg-surface px-2 py-1.5 text-sm";
const BUTTON =
  "rounded-card border border-hairline px-3 py-1.5 text-sm hover:bg-canvas disabled:opacity-40";

const ITEM_TYPES: Record<string, string> = tr.imports.itemTypes;

function Feedback({ state }: { state: ImportActionState }) {
  if (state.status === "idle") return null;
  const tone = state.status === "error" ? "text-negative" : "text-positive";
  return <p className={`text-sm ${tone}`}>{state.message}</p>;
}

type FormProps = { brand: BrandSlug; fileId: string; disabled?: boolean };

function useAction(action: (state: ImportActionState, data: FormData) => Promise<ImportActionState>) {
  const [state, setState] = useState<ImportActionState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  const submit = (event: React.FormEvent<HTMLFormElement>, brand: string, fileId: string) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    data.set("brand", brand);
    data.set("file_id", fileId);
    startTransition(async () => {
      const next = await action({ status: "idle" }, data);
      setState(next);
      if (next.status === "saved") form.reset();
    });
  };

  return { state, pending, submit };
}

export function CostItemForm({ brand, fileId, disabled = false }: FormProps) {
  const { state, pending, submit } = useAction(addCostItemAction);

  return (
    <div className="flex flex-col gap-3">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => submit(event, brand, fileId)}
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.itemType} *</span>
          <select name="item_type" required defaultValue="navlun" className={`${FIELD} min-w-44`}>
            {Object.entries(ITEM_TYPES)
              .filter(([code]) => code !== "mal_bedeli")
              .map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.amount} *</span>
          <input
            name="amount_original"
            type="number"
            step="0.01"
            min="0"
            required
            className={`${FIELD} w-32 tabular`}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.currency}</span>
          <select name="currency" defaultValue="TRY" className={`${FIELD} w-24`}>
            <option value="TRY">TRY</option>
            <option value="EUR">EUR</option>
            <option value="USD">USD</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.fxBeyanname}</span>
          <input name="fx_rate" type="number" step="0.000001" className={`${FIELD} w-32 tabular`} />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.vendor}</span>
          <input name="vendor" type="text" className={`${FIELD} w-44`} />
        </label>
        <button type="submit" disabled={pending || disabled} className={BUTTON}>
          {pending ? tr.imports.saving : tr.imports.add}
        </button>
      </form>
      <Feedback state={state} />
    </div>
  );
}

export function PaymentForm({ brand, fileId }: FormProps) {
  const { state, pending, submit } = useAction(recordPaymentAction);

  return (
    <div className="flex flex-col gap-3">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => submit(event, brand, fileId)}
      >
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.payDate} *</span>
          <input name="pay_date" type="date" required className={`${FIELD} w-40`} />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.payAmount} *</span>
          <input
            name="amount_original"
            type="number"
            step="0.01"
            min="0"
            required
            className={`${FIELD} w-32 tabular`}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="text-ink-faint">{tr.imports.payRate} *</span>
          <input
            name="fx_rate_payment"
            type="number"
            step="0.000001"
            min="0"
            required
            className={`${FIELD} w-32 tabular`}
          />
        </label>
        <button type="submit" disabled={pending} className={BUTTON}>
          {pending ? tr.imports.saving : tr.imports.addPayment}
        </button>
      </form>
      <Feedback state={state} />
    </div>
  );
}

export function ConfirmFileForm({ brand, fileId, disabled = false }: FormProps) {
  const { state, pending, submit } = useAction(confirmFileAction);

  return (
    <div className="flex flex-col gap-2">
      <form onSubmit={(event) => submit(event, brand, fileId)}>
        <button type="submit" disabled={pending || disabled} className={BUTTON}>
          {pending ? tr.imports.saving : tr.imports.confirm}
        </button>
      </form>
      <p className="text-xs text-ink-faint">{tr.imports.confirmNote}</p>
      <Feedback state={state} />
    </div>
  );
}
