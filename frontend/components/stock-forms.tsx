"use client";

/**
 * Açılış stoku ve düzeltme formları (spec §12C.4).
 *
 * Geçmiş hareket düzenlenmez; düzeltme her zaman yeni bir defter satırıdır — bu yüzden
 * formda "düzelt" değil "adet farkı" sorulur (CLAUDE.md §1).
 */

import { useState, useTransition } from "react";

import {
  adjustmentAction,
  damageAction,
  type MovementState,
  openingStockAction,
} from "@/app/[brand]/inventory/actions";
import type { BrandSlug } from "@/lib/brands";
import tr from "@/locales/tr.json";

export type ProductOption = { product_id: string; sku: string; name: string };

const FIELD = "control";

function ProductSelect({ options }: { options: ProductOption[] }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="col-head">{tr.inventory.product} *</span>
      <select name="product_id" required defaultValue="" className={`${FIELD} min-w-64`}>
        <option value="" disabled>
          {tr.inventory.chooseProduct}
        </option>
        {options.map((option) => (
          <option key={option.product_id} value={option.product_id}>
            {option.sku} · {option.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function Feedback({ state }: { state: MovementState }) {
  if (state.status === "idle") return null;
  const tone = state.status === "error" ? "text-negative" : "text-positive";
  return <p className={`text-cell ${tone}`}>{state.message}</p>;
}

export function OpeningStockForm({
  brand,
  products,
}: {
  brand: BrandSlug;
  products: ProductOption[];
}) {
  const [state, setState] = useState<MovementState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  return (
    <div className="flex flex-col gap-3">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const formData = new FormData(form);
          formData.set("brand", brand);
          startTransition(async () => {
            const next = await openingStockAction({ status: "idle" }, formData);
            setState(next);
            if (next.status === "saved") form.reset();
          });
        }}
      >
        <ProductSelect options={products} />
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.inventory.qty} *</span>
          <input
            name="qty"
            type="number"
            step="1"
            min="1"
            required
            className={`${FIELD} w-24 tabular`}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.inventory.unitCost} *</span>
          <input
            name="unit_cost"
            type="number"
            step="0.01"
            min="0"
            required
            className={`${FIELD} w-36 tabular`}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.inventory.onDate}</span>
          <input name="on_date" type="date" className={`${FIELD} w-40`} />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.inventory.saving : tr.inventory.save}
        </button>
      </form>
      <Feedback state={state} />
    </div>
  );
}

export function AdjustmentForm({
  brand,
  products,
}: {
  brand: BrandSlug;
  products: ProductOption[];
}) {
  const [state, setState] = useState<MovementState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  return (
    <div className="flex flex-col gap-3">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const formData = new FormData(form);
          formData.set("brand", brand);
          startTransition(async () => {
            const next = await adjustmentAction({ status: "idle" }, formData);
            setState(next);
            if (next.status === "saved") form.reset();
          });
        }}
      >
        <ProductSelect options={products} />
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.inventory.qtyDelta} *</span>
          <input
            name="qty_delta"
            type="number"
            step="1"
            required
            placeholder="-1"
            className={`${FIELD} w-28 tabular`}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.inventory.unitCostOptional}</span>
          <input
            name="unit_cost"
            type="number"
            step="0.01"
            min="0"
            className={`${FIELD} w-36 tabular`}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1">
          <span className="col-head">{tr.inventory.reason} *</span>
          <input name="reason" type="text" required minLength={3} className={`${FIELD} w-full`} />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.inventory.saving : tr.inventory.save}
        </button>
      </form>
      <p className="text-helper text-ink-muted">{tr.inventory.qtyDeltaHint}</p>
      <Feedback state={state} />
    </div>
  );
}

export function DamageForm({
  brand,
  products,
}: {
  brand: BrandSlug;
  products: ProductOption[];
}) {
  const [state, setState] = useState<MovementState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  return (
    <div className="flex flex-col gap-3">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const formData = new FormData(form);
          formData.set("brand", brand);
          startTransition(async () => {
            const next = await damageAction({ status: "idle" }, formData);
            setState(next);
            if (next.status === "saved") form.reset();
          });
        }}
      >
        <ProductSelect options={products} />
        <label className="flex flex-col gap-1">
          <span className="col-head">{tr.damage.qty} *</span>
          <input
            name="qty"
            type="number"
            step="1"
            min="1"
            required
            className={`${FIELD} w-24 tabular`}
          />
        </label>
        <label className="flex flex-1 flex-col gap-1">
          <span className="col-head">{tr.damage.reason} *</span>
          <input name="reason" type="text" required minLength={3} className={`${FIELD} w-full`} />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {pending ? tr.inventory.saving : tr.damage.record}
        </button>
      </form>
      <p className="text-helper text-ink-muted">{tr.damage.subtitle}</p>
      <Feedback state={state} />
    </div>
  );
}
