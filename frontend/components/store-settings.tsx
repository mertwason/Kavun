"use client";

/**
 * Mağaza ayarları (spec §10.7, §3.6).
 *
 * Bağlantı bilgileri **yalnızca yazılır**: form kaydedince alanlar boşalır, ekranda
 * yalnızca "kayıtlı / girilmedi" rozeti kalır. Değerler hiçbir yanıtta geri dönmez.
 */

import { useState, useTransition } from "react";

import {
  addStoreAction,
  deleteCredentialsAction,
  type FormState,
  saveCredentialsAction,
  syncStoreAction,
  updateStoreAction,
} from "@/app/[brand]/settings/actions";
import type { Store } from "@/lib/api";
import { BRANDS, type BrandSlug } from "@/lib/brands";
import { formatDateTime, toInputNumber } from "@/lib/format";
import tr from "@/locales/tr.json";

const FIELD = "control";

const CREDENTIAL_LABELS: Record<string, string> = tr.settings.credentialFields;
const CHANNEL_LABELS: Record<string, string> = tr.settings.channels;
const CHANNEL_HINTS: Record<string, string> = tr.settings.channelHints;
const WIZARD_STEPS: Record<string, string> = tr.settings.wizardSteps;

/** Kanal başına zorunlu credential alanları — backend'in beklediğiyle aynı (spec §4). */
const CREDENTIAL_FIELDS: Record<string, string[]> = {
  trendyol: ["api_key", "api_secret", "seller_id"],
  hepsiburada: ["username", "password", "merchant_id"],
  n11: ["app_key", "app_secret"],
  shopify: ["shop_domain", "access_token"],
  manual: [],
};

/**
 * Satıcı kimliğinin ekranda maskelenmiş hâli (`48*****2`).
 *
 * Sır değil ama omuz üstünden okunacak bir tanımlayıcı: handoff da maskeli gösteriyor.
 */
function maskId(value: string): string {
  if (value.length <= 3) return value;
  return `${value.slice(0, 2)}${"*".repeat(Math.max(1, value.length - 3))}${value.slice(-1)}`;
}

/** Girilen değer ekranda gizlenmeli mi? Anahtar/parola alanları maskelenir. */
function isSecret(field: string): boolean {
  return /secret|password|token|key/.test(field);
}

export function StoreList({ brand, stores }: { brand: BrandSlug; stores: Store[] }) {
  return (
    <div className="flex flex-col gap-4">
      {stores.map((store) => (
        <StoreCard key={store.id} brand={brand} store={store} />
      ))}
      <StoreWizard brand={brand} />
    </div>
  );
}

function StoreCard({ brand, store }: { brand: BrandSlug; store: Store }) {
  const fields = CREDENTIAL_FIELDS[store.channel] ?? [];
  const configured = store.credentials.configured;

  return (
    <div className="flex flex-col gap-3 rounded-card border border-hairline p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          {/* Kanal harf rozeti — gerçek logo entegrasyonu ürün ekibinin kararı (handoff). */}
          <span
            aria-hidden
            className="inline-flex h-7 w-7 items-center justify-center rounded-control bg-divider text-cell font-semibold text-ink-secondary"
          >
            {store.channel.slice(0, 1).toLocaleUpperCase("tr-TR")}
          </span>
          <span className="flex flex-col">
            <span className="text-cell font-medium">{store.name}</span>
            <span className="text-helper text-ink-muted">
              {CHANNEL_LABELS[store.channel] ?? store.channel}
              {store.external_seller_id ? ` · ${maskId(store.external_seller_id)}` : ""}
            </span>
          </span>
        </div>
        <span
          className={`badge ${
            configured
              ? "border-positive-border bg-positive-tint text-positive-text"
              : "border-hairline bg-canvas text-ink-muted"
          }`}
        >
          {configured ? tr.settings.credentialsConfigured : tr.settings.credentialsMissing}
          {store.credentials.rotated_at ? ` · ${formatDateTime(store.credentials.rotated_at)}` : ""}
        </span>
      </div>

      <ActionForm
        action={updateStoreAction}
        brand={brand}
        hidden={{ store_id: store.id }}
        submit={tr.settings.save}
      >
        <Labelled label={tr.settings.storeName}>
          <input name="name" defaultValue={store.name} className={`${FIELD} w-52`} />
        </Labelled>
        <Labelled label={tr.settings.sellerId}>
          <input
            name="external_seller_id"
            defaultValue={store.external_seller_id ?? ""}
            className={`${FIELD} w-40`}
          />
        </Labelled>
        <Labelled label={tr.settings.serviceFee}>
          <input
            name="service_fee_per_order"
            inputMode="decimal"
            defaultValue={toInputNumber(store.service_fee_per_order)}
            className={`${FIELD} w-28 tabular`}
          />
        </Labelled>
        <span className="text-helper text-ink-muted">
          {tr.settings.lastSync}:{" "}
          {store.last_synced_at ? formatDateTime(store.last_synced_at) : tr.settings.never}
        </span>
      </ActionForm>

      {fields.length > 0 ? (
        <ActionForm
          action={saveCredentialsAction}
          brand={brand}
          hidden={{ store_id: store.id }}
          submit={tr.settings.credentialsSave}
          resetOnSuccess
        >
          {fields.map((field) => (
            <Labelled key={field} label={CREDENTIAL_LABELS[field] ?? field}>
              <input
                name={`cred_${field}`}
                type={isSecret(field) ? "password" : "text"}
                autoComplete="off"
                placeholder={configured ? "••••••" : ""}
                className={`${FIELD} w-44`}
              />
            </Labelled>
          ))}
          <span className="text-helper text-ink-muted">{tr.settings.credentialsNote}</span>
        </ActionForm>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <ActionForm
          action={syncStoreAction}
          brand={brand}
          hidden={{ store_id: store.id }}
          submit={tr.settings.sync}
          inline
        />
        {configured ? (
          <ActionForm
            action={deleteCredentialsAction}
            brand={brand}
            hidden={{ store_id: store.id }}
            submit={tr.settings.credentialsDelete}
            inline
          />
        ) : null}
      </div>
    </div>
  );
}

/**
 * Yeni mağaza bağlama sihirbazı — handoff `Ayarlar.dc.html` (üç adım).
 *
 * Tek bir düz form yerine adım adım: kanal seç → mağaza + bağlantı bilgileri → doğrulama.
 * Doğrulama adımı **gerçek bir senkron denemesi** yapar; sahte bir "bağlandı" rozeti
 * göstermez. Hata dönerse bilgiler kayıtlı kalır, kullanıcı kartından düzeltir.
 */
function StoreWizard({ brand }: { brand: BrandSlug }) {
  const [step, setStep] = useState<0 | 1 | 2 | 3>(0);
  const [channel, setChannel] = useState<string>("trendyol");
  const [storeId, setStoreId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const accent = BRANDS[brand].accent;

  const fields = CREDENTIAL_FIELDS[channel] ?? [];

  const reset = () => {
    setStep(0);
    setStoreId(null);
    setMessage(null);
    setError(null);
  };

  if (step === 0) {
    return (
      <div className="border-t border-hairline pt-3">
        <button
          type="button"
          onClick={() => setStep(1)}
          className="h-[34px] rounded-control px-3.5 text-cell font-medium text-white"
          style={{ backgroundColor: accent }}
        >
          {tr.settings.wizardStart}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 border-t border-hairline pt-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-body font-medium">{tr.settings.wizardTitle}</span>
        <div className="flex items-center gap-2">
          {(["1", "2", "3"] as const).map((key, index) => (
            <span
              key={key}
              className={`flex items-center gap-1.5 text-helper ${
                step === index + 1 ? "text-ink" : "text-ink-muted"
              }`}
            >
              <span
                aria-hidden
                className={`flex h-5 w-5 items-center justify-center rounded-pill border text-micro font-semibold ${
                  step > index + 1
                    ? "border-positive-border bg-positive-tint text-positive-text"
                    : step === index + 1
                      ? "border-ink bg-ink text-white"
                      : "border-hairline bg-surface text-ink-muted"
                }`}
              >
                {key}
              </span>
              {WIZARD_STEPS[key]}
            </span>
          ))}
        </div>
        <div className="flex-1" />
        <button
          type="button"
          onClick={reset}
          className="text-helper text-ink-muted underline decoration-ink-ghost underline-offset-4 hover:text-ink"
        >
          {tr.settings.wizardCancel}
        </button>
      </div>

      {step === 1 ? (
        <div className="flex flex-col gap-3">
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {Object.keys(CREDENTIAL_FIELDS).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setChannel(code)}
                aria-pressed={channel === code}
                className={`flex items-center gap-2.5 rounded-card border p-3 text-left ${
                  channel === code
                    ? "border-ink bg-canvas"
                    : "border-hairline bg-surface hover:bg-canvas"
                }`}
              >
                <span
                  aria-hidden
                  className="inline-flex h-7 w-7 items-center justify-center rounded-control bg-divider text-cell font-semibold text-ink-secondary"
                >
                  {code.slice(0, 1).toLocaleUpperCase("tr-TR")}
                </span>
                <span className="flex flex-col">
                  <span className="text-cell font-medium">{CHANNEL_LABELS[code] ?? code}</span>
                  <span className="text-helper text-ink-muted">{CHANNEL_HINTS[code] ?? ""}</span>
                </span>
              </button>
            ))}
          </div>
          <div>
            <button
              type="button"
              onClick={() => setStep(2)}
              className="h-[34px] rounded-control px-3.5 text-cell font-medium text-white"
              style={{ backgroundColor: accent }}
            >
              {tr.settings.wizardNext}
            </button>
          </div>
        </div>
      ) : null}

      {step === 2 ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const formData = new FormData(form);
            formData.set("brand", brand);
            formData.set("channel", channel);
            setError(null);
            startTransition(async () => {
              const created = await addStoreAction({ status: "idle" }, formData);
              if (created.status !== "saved" || !created.storeId) {
                setError(created.message ?? tr.error.unreachable);
                return;
              }
              setStoreId(created.storeId);

              // Bilgiler boş bırakılabilir: mağaza önce tanımlanır, bağlantı sonra
              // kartından girilir. Boş formu aksiyona göndermek gereksiz hata üretirdi.
              const filled = fields.some((field) =>
                String(formData.get(`wizard_cred_${field}`) ?? "").trim(),
              );
              if (fields.length > 0 && filled) {
                // Alan adları sihirbazda `wizard_cred_*`: mağaza kartındaki `cred_*`
                // formuyla karışmasınlar. Aksiyona giderken kanonik ada çevrilir.
                const credentials = new FormData();
                credentials.set("brand", brand);
                credentials.set("store_id", created.storeId);
                for (const field of fields) {
                  credentials.set(
                    `cred_${field}`,
                    String(formData.get(`wizard_cred_${field}`) ?? ""),
                  );
                }
                const saved = await saveCredentialsAction({ status: "idle" }, credentials);
                if (saved.status === "error") {
                  setError(saved.message ?? tr.error.unreachable);
                  return;
                }
              }
              setStep(3);
            });
          }}
        >
          <div className="flex flex-wrap items-end gap-3">
            <Labelled label={tr.settings.storeName}>
              <input name="name" required className={`${FIELD} w-52`} />
            </Labelled>
            <Labelled label={tr.settings.sellerId}>
              <input name="external_seller_id" className={`${FIELD} w-40`} />
            </Labelled>
            <Labelled label={tr.settings.serviceFee}>
              <input
                name="service_fee_per_order"
                inputMode="decimal"
                className={`${FIELD} w-28 tabular`}
              />
            </Labelled>
          </div>

          {fields.length > 0 ? (
            <div className="flex flex-wrap items-end gap-3">
              {fields.map((field) => (
                <Labelled key={field} label={CREDENTIAL_LABELS[field] ?? field}>
                  <input
                    name={`wizard_cred_${field}`}
                    data-credential={field}
                    type={isSecret(field) ? "password" : "text"}
                    autoComplete="off"
                    className={`${FIELD} w-44`}
                  />
                </Labelled>
              ))}
              <span className="text-helper text-ink-muted">{tr.settings.credentialsNote}</span>
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
            >
              {tr.settings.wizardBack}
            </button>
            <button
              type="submit"
              disabled={pending}
              className="h-[34px] rounded-control px-3.5 text-cell font-medium text-white disabled:opacity-40"
              style={{ backgroundColor: accent }}
            >
              {tr.settings.wizardNext}
            </button>
          </div>
        </form>
      ) : null}

      {step === 3 ? (
        <div className="flex flex-col gap-3">
          <p className="text-cell text-ink-body">{tr.settings.wizardVerifyHint}</p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={pending || !storeId}
              onClick={() => {
                const formData = new FormData();
                formData.set("brand", brand);
                formData.set("store_id", storeId ?? "");
                setError(null);
                startTransition(async () => {
                  const result = await syncStoreAction({ status: "idle" }, formData);
                  if (result.status === "error") setError(result.message ?? tr.error.unreachable);
                  else setMessage(tr.settings.wizardDone);
                });
              }}
              className="h-[34px] rounded-control px-3.5 text-cell font-medium text-white disabled:opacity-40"
              style={{ backgroundColor: accent }}
            >
              {pending ? tr.settings.wizardVerifying : tr.settings.wizardFinish}
            </button>
            <button
              type="button"
              onClick={reset}
              className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas"
            >
              {tr.settings.wizardCancel}
            </button>
          </div>
        </div>
      ) : null}

      {error ? <p className="text-cell text-negative">{error}</p> : null}
      {message ? <p className="text-cell text-positive-text">{message}</p> : null}
    </div>
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

/** Sunucu aksiyonunu çalıştıran küçük form kabuğu — durum mesajı formun altında görünür. */
function ActionForm({
  action,
  brand,
  hidden,
  submit,
  children,
  resetOnSuccess = false,
  inline = false,
  bordered = false,
}: {
  action: (previous: FormState, formData: FormData) => Promise<FormState>;
  brand: BrandSlug;
  hidden?: Record<string, string>;
  submit: string;
  children?: React.ReactNode;
  resetOnSuccess?: boolean;
  inline?: boolean;
  bordered?: boolean;
}) {
  const [state, setState] = useState<FormState>({ status: "idle" });
  const [pending, startTransition] = useTransition();

  return (
    <div className={bordered ? "border-t border-hairline pt-3" : undefined}>
      <form
        className={inline ? "inline-flex" : "flex flex-wrap items-end gap-3"}
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const formData = new FormData(form);
          formData.set("brand", brand);
          for (const [key, value] of Object.entries(hidden ?? {})) formData.set(key, value);
          startTransition(async () => {
            const next = await action({ status: "idle" }, formData);
            setState(next);
            if (next.status === "saved" && resetOnSuccess) form.reset();
          });
        }}
      >
        {children}
        <button
          type="submit"
          disabled={pending}
          className="h-[34px] rounded-control border border-hairline bg-surface px-3 text-cell font-medium text-ink-secondary hover:border-ink-ghost hover:bg-canvas disabled:opacity-40"
        >
          {submit}
        </button>
      </form>
      {state.status === "error" ? (
        <p className="mt-2 text-cell text-negative">{state.message}</p>
      ) : null}
      {state.status === "saved" ? (
        <p className="mt-2 text-helper text-positive-text">{state.message ?? tr.settings.saved}</p>
      ) : null}
    </div>
  );
}
