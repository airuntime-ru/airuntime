"use client";

/**
 * The customer's whole journey: open the deep link, pick, book, done.
 *
 * Three rules shaped this screen, all from how a messenger mini app is actually used:
 * - one screen, no navigation. A booking that spans steps loses people in a webview.
 * - the phone number comes from MAX itself when the client offers it (`requestContact`),
 *   so the common case is zero typing.
 * - every state is visible: loading, empty, error, submitting, done. A silent failure in
 *   a webview reads as a broken business, not a broken app.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  MaxApiError,
  createLead,
  fetchService,
  type CustomerLead,
  type ServiceConfig,
  type ServiceItem,
} from "@/lib/max/api";
import { getInitDataUnsafe, requestContact } from "@/lib/max/bridge";
import { commentHint, kindKicker, storefrontMood } from "@/lib/max/theme";

type Phase = "loading" | "ready" | "submitting" | "done" | "error";

function priceLabel(item: ServiceItem): string {
  if (item.price_rub === null || item.price_rub === undefined) return "";
  return `${item.price_rub.toLocaleString("ru-RU")} ₽`;
}

function historyStatus(status: CustomerLead["status"]): string {
  if (status === "confirmed") return "подтверждена";
  if (status === "declined") return "отклонена";
  if (status === "done") return "выполнена";
  return "на рассмотрении";
}

function HistoryList({ leads }: { leads: CustomerLead[] }) {
  if (leads.length === 0) return null;
  return (
    <section className="max-history">
      <h2 className="max-section-title">Ваши записи</h2>
      <ul className="max-list">
        {leads.map((lead) => (
          <li key={lead.id} className="max-sheet max-history-row">
            <div className="max-lead-head">
              <span className="max-option-title">{lead.item_title || "Заявка"}</span>
              <span
                className={`max-badge ${lead.status === "confirmed" || lead.status === "done" ? "max-badge-confirmed" : lead.status === "declined" ? "max-badge-declined" : "max-badge-new"}`}
              >
                {historyStatus(lead.status)}
              </span>
            </div>
            {lead.slot_label ? <p className="max-option-note">{lead.slot_label}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

function durationLabel(item: ServiceItem): string {
  if (!item.duration_min) return "";
  return item.duration_min >= 60 && item.duration_min % 60 === 0
    ? `${item.duration_min / 60} ч`
    : `${item.duration_min} мин`;
}

export function Storefront({ slug }: { slug: string }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [config, setConfig] = useState<ServiceConfig | null>(null);
  const [error, setError] = useState("");

  const [selectedItem, setSelectedItem] = useState("");
  const [selectedSlot, setSelectedSlot] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [comment, setComment] = useState("");
  const [phoneVerified, setPhoneVerified] = useState(false);
  // Sticks once the customer asks to type a number themselves, so declining the MAX
  // dialog does not bounce them back to a button they already rejected.
  const [phoneManual, setPhoneManual] = useState(false);
  const [successText, setSuccessText] = useState("");
  const [history, setHistory] = useState<CustomerLead[]>([]);

  useEffect(() => {
    let cancelled = false;
    // No synchronous setState here: "loading" is already the initial phase, and the slug
    // is fixed for the lifetime of this component (the page mounts it once per launch).
    fetchService(slug)
      .then((response) => {
        if (cancelled) return;
        setConfig(response.config);
        setHistory(response.my_leads || []);
        // Prefill the name from MAX so most customers only pick a time and tap once.
        const user = getInitDataUnsafe().user;
        const full = [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim();
        if (full) setName(full);
        setPhase("ready");
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        const message =
          cause instanceof MaxApiError && cause.status === 404
            ? "AIRuntime не найден или снят с публикации"
            : cause instanceof Error
              ? cause.message
              : "Не удалось загрузить AIRuntime";
        setError(message);
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const accentStyle = useMemo(
    () => (config ? ({ "--max-accent": config.accent } as React.CSSProperties) : undefined),
    [config]
  );

  const needsSlot = Boolean(config && config.kind === "booking" && config.slots.length > 0);
  const canSubmit =
    phase === "ready" &&
    Boolean(config) &&
    (config!.items.length === 0 || Boolean(selectedItem)) &&
    (!needsSlot || Boolean(selectedSlot)) &&
    name.trim().length > 0;

  const onShareContact = useCallback(async () => {
    const contact = await requestContact();
    if (!contact) return;
    setPhone(contact.phone);
    // Marked verified only for the customer's own reassurance; the backend re-checks the
    // signature and never takes this flag from the client.
    setPhoneVerified(true);
  }, []);

  const onSubmit = useCallback(async () => {
    if (!config || !canSubmit) return;
    setPhase("submitting");
    setError("");
    try {
      const result = await createLead({
        slug,
        item_title: selectedItem,
        slot_label: selectedSlot,
        customer_name: name.trim(),
        phone: phone.trim(),
        comment: comment.trim(),
      });
      setSuccessText(result.success_message || config.success_message);
      setHistory((current) => [
        {
          id: result.id,
          item_title: selectedItem,
          slot_label: selectedSlot,
          status: "new",
          created_at: new Date().toISOString(),
          scheduled_at: null,
        },
        ...current,
      ]);
      setPhase("done");
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Не удалось отправить заявку");
      setPhase("ready");
    }
  }, [canSubmit, comment, config, name, phone, selectedItem, selectedSlot, slug]);

  if (phase === "loading") {
    return (
      <div className="max-shell" aria-busy="true" aria-live="polite">
        <div className="max-skeleton" style={{ height: 120 }} />
        <div className="max-skeleton" style={{ height: 18, width: "40%", margin: "24px 0 10px" }} />
        <div className="max-list">
          <div className="max-skeleton" style={{ height: 66 }} />
          <div className="max-skeleton" style={{ height: 66 }} />
          <div className="max-skeleton" style={{ height: 66 }} />
        </div>
        <p className="max-note">Загружаем AIRuntime…</p>
      </div>
    );
  }

  if (phase === "error" || !config) {
    return (
      <div className="max-shell">
        <div className="max-error" role="alert">
          {error || "Не удалось загрузить AIRuntime"}
        </div>
      </div>
    );
  }

  if (phase === "done") {
    return (
      <div className="max-shell" data-mood={storefrontMood(config)} style={accentStyle}>
        <div className="max-sheet max-success" role="status">
          <div className="max-success-mark" aria-hidden>
            ✓
          </div>
          <h1 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 650 }}>{successText}</h1>
          <p className="max-note">
            {selectedItem}
            {selectedSlot ? ` · ${selectedSlot}` : ""}
          </p>
          <p className="max-note">Ответ придёт сюда, в MAX.</p>
        </div>
        <HistoryList leads={history} />
      </div>
    );
  }

  const busy = phase === "submitting";
  const chosen = config.items.find((item) => item.title === selectedItem) ?? null;
  const meta = [config.contacts.address, config.contacts.hours, config.contacts.phone]
    .filter(Boolean)
    .join(" · ");
  // Contacts only appear once there is something to book. On a phone, opening straight
  // into three empty fields reads as paperwork rather than as a two-tap booking.
  const showContacts = config.items.length === 0 || Boolean(selectedItem);
  const missing = !selectedItem
    ? config.kind === "menu"
      ? "Выберите позицию"
      : "Выберите услугу"
    : needsSlot && !selectedSlot
      ? "Выберите время"
      : !name.trim()
        ? "Укажите имя"
        : "";

  return (
    <div className="max-shell" data-mood={storefrontMood(config)} style={accentStyle}>
      <header className="max-hero">
        <p className="max-hero-kicker">{kindKicker(config.kind)}</p>
        <h1>{config.title}</h1>
        {config.tagline ? <p>{config.tagline}</p> : null}
        {meta ? <p className="max-hero-meta">{meta}</p> : null}
      </header>

      {config.about ? <p className="max-about">{config.about}</p> : null}

      {history.length > 0 ? <HistoryList leads={history} /> : null}

      {config.items.length > 0 ? (
        <>
          <h2 className="max-section-title">{config.kind === "menu" ? "Меню" : "Услуги"}</h2>
          <ul className="max-list">
            {config.items.map((item) => {
              const price = priceLabel(item);
              const duration = durationLabel(item);
              const note = item.description;
              const active = selectedItem === item.title;
              return (
                <li key={item.title}>
                  <button
                    type="button"
                    className="max-option"
                    aria-pressed={active}
                    onClick={() => setSelectedItem(item.title)}
                    disabled={busy}
                  >
                    {/* A check mark, not just a border: on a small screen the selected row
                        has to be obvious at a glance. */}
                    <span className="max-radio" aria-hidden>
                      {active ? "✓" : ""}
                    </span>
                    <span className="max-option-label">
                      <span className="max-option-title">{item.title}</span>
                      {note ? <span className="max-option-note">{note}</span> : null}
                    </span>
                    <span className="max-option-meta">
                      {duration ? <span className="max-duration">{duration}</span> : null}
                      {price ? <span className="max-option-price">{price}</span> : null}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {needsSlot && selectedItem ? (
        <>
          <h2 className="max-section-title">Когда удобно</h2>
          <div className="max-chips">
            {config.slots.map((slot) => (
              <button
                key={slot}
                type="button"
                className="max-chip"
                aria-pressed={selectedSlot === slot}
                onClick={() => setSelectedSlot(slot)}
                disabled={busy}
              >
                {slot}
              </button>
            ))}
          </div>
        </>
      ) : null}

      {showContacts ? (
        <>
          <h2 className="max-section-title">Контакты</h2>
          <div className="max-sheet max-form">
            <label className="max-field" style={{ marginTop: 0 }}>
              <span>Имя</span>
              <input
                className="max-input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Как к вам обращаться"
                autoComplete="name"
                disabled={busy}
              />
            </label>

            {config.ask_phone ? (
              <div className="max-field">
                <span className="max-field-label">Телефон</span>
                {phone || phoneManual ? (
                  <>
                    <input
                      className="max-input"
                      value={phone}
                      onChange={(event) => {
                        setPhone(event.target.value);
                        setPhoneVerified(false);
                      }}
                      placeholder="+7 900 000-00-00"
                      inputMode="tel"
                      autoComplete="tel"
                      disabled={busy}
                    />
                    {phoneVerified ? (
                      <p className="max-hint max-hint-ok">Номер подтверждён аккаунтом MAX</p>
                    ) : null}
                  </>
                ) : (
                  <>
                    {/* The whole point of being inside MAX: the common case is zero typing. */}
                    <button
                      type="button"
                      className="max-button max-button-quiet"
                      onClick={onShareContact}
                      disabled={busy}
                    >
                      Взять номер из MAX
                    </button>
                    <button
                      type="button"
                      className="max-linklike"
                      onClick={() => setPhoneManual(true)}
                      disabled={busy}
                    >
                      Ввести вручную
                    </button>
                  </>
                )}
              </div>
            ) : null}

            {config.ask_comment ? (
              <label className="max-field">
                <span>Комментарий</span>
                <textarea
                  className="max-textarea"
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder={commentHint(config)}
                  disabled={busy}
                />
              </label>
            ) : null}
          </div>
        </>
      ) : null}

      {error ? (
        <div className="max-error" role="alert" style={{ marginTop: 14 }}>
          {error}
        </div>
      ) : null}

      <div className="max-submit-bar">
        {/* What exactly is being confirmed, right above the button - so the last tap is a
            confirmation rather than a leap of faith. */}
        {chosen ? (
          <div className="max-summary">
            <span className="max-summary-text">
              {chosen.title}
              {selectedSlot ? ` · ${selectedSlot}` : ""}
            </span>
            {priceLabel(chosen) ? (
              <span className="max-summary-price">{priceLabel(chosen)}</span>
            ) : null}
          </div>
        ) : null}
        <button
          type="button"
          className="max-button"
          onClick={onSubmit}
          disabled={!canSubmit || busy}
        >
          {busy ? "Отправляем…" : config.cta_label}
        </button>
        {missing && !busy ? <p className="max-submit-hint">{missing}</p> : null}
      </div>
    </div>
  );
}
