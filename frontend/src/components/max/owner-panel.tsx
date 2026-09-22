"use client";

/**
 * The owner's side of the mini app - which is now the whole owner product.
 *
 * Storefronts used to be made by writing to the bot. That chat wizard turned every message
 * into a storefront, "привет" included, and gave no way to see what had been made. So it all
 * lives here: describe the business once and get a published storefront, then share its
 * link, change it in words, hide it, and work through the leads it brings. The bot only
 * opens this screen and brings news.
 */

import { useCallback, useEffect, useState } from "react";

import { Storefront } from "@/components/max/storefront";
import {
  MaxApiError,
  createService,
  deleteService,
  editService,
  fetchOwnerLeads,
  fetchOwnerOverview,
  setLeadStatus,
  setServiceStatus,
  type Lead,
  type OwnerService,
} from "@/lib/max/api";
import { attachHeaderBack, guardClosing, haptic, shareInMax } from "@/lib/max/bridge";

type Phase = "loading" | "ready" | "error";

// The backend refuses anything shorter: "привет" is not something a storefront can be
// built from, and saying so before the request beats a round trip to find out.
const MIN_BRIEF = 12;

const EXAMPLES: { label: string; brief: string }[] = [
  {
    label: "Автосервис",
    brief:
      "Автосервис на Лесной, 12. Диагностика подвески 1500, замена масла 900, шиномонтаж 2400. Работаем с 9 до 20.",
  },
  {
    label: "Барбершоп",
    brief:
      "Барбершоп «Борода» на Садовой. Мужская стрижка 1200, стрижка бороды 700, камуфляж седины 900. Каждый день с 10 до 21.",
  },
  {
    label: "Кофейня",
    brief:
      "Кофейня у метро Чкаловская. Капучино 250, раф 290, круассан 180, сырники 320. Заказ навынос с 8 до 22.",
  },
  {
    label: "Репетитор",
    brief:
      "Репетитор по математике, ЕГЭ и ОГЭ. Занятие 60 минут\u00a0— 1500, пробный урок 500. Онлайн, по будням с 16 до 21.",
  },
];

const STATUS_LABEL: Record<Lead["status"], string> = {
  new: "новая",
  confirmed: "подтверждена",
  declined: "отклонена",
  done: "выполнена",
};

const KIND_LABEL: Record<OwnerService["config"]["kind"], string> = {
  booking: "Запись",
  menu: "Меню",
  landing: "Заявки",
};

/** "1 новая" / "2 новые" / "5 новых" - the count is always in the owner's face, so a
    wrong ending reads as sloppiness on every single screen. */
function pluralNew(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return "новая";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "новые";
  return "новых";
}

function pluralItems(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} позиция`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} позиции`;
  return `${count} позиций`;
}

function formatCreated(value: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function messageOf(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}

async function fetchAll(): Promise<{ services: OwnerService[]; leads: Lead[] } | Error> {
  try {
    const [overview, leadList] = await Promise.all([fetchOwnerOverview(), fetchOwnerLeads()]);
    return { services: overview.services, leads: leadList.leads };
  } catch (cause: unknown) {
    return cause instanceof Error ? cause : new Error("Не удалось загрузить данные");
  }
}

export function OwnerPanel() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState("");
  const [services, setServices] = useState<OwnerService[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [pendingLeadId, setPendingLeadId] = useState("");

  // Creating a storefront.
  const [composerOpen, setComposerOpen] = useState(false);
  const [brief, setBrief] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [freshSlug, setFreshSlug] = useState("");

  // Working on an existing one.
  const [busySlug, setBusySlug] = useState("");
  const [copiedSlug, setCopiedSlug] = useState("");
  const [editingSlug, setEditingSlug] = useState("");
  const [editText, setEditText] = useState("");
  const [editNote, setEditNote] = useState("");
  const [confirmDeleteSlug, setConfirmDeleteSlug] = useState("");
  const [previewSlug, setPreviewSlug] = useState("");

  const apply = useCallback((result: { services: OwnerService[]; leads: Lead[] } | Error) => {
    if (!(result instanceof Error)) {
      setServices(result.services);
      setLeads(result.leads);
      setPhase("ready");
      return;
    }
    // 404 means "no owner row yet", which is a normal first-run state, not a failure.
    if (result instanceof MaxApiError && result.status === 404) {
      setServices([]);
      setLeads([]);
      setPhase("ready");
      return;
    }
    setError(result.message || "Не удалось загрузить данные");
    setPhase("error");
  }, []);

  // Fetching is kept free of state updates so the mount effect can await it without
  // touching state synchronously; the retry button is an event handler and may.
  const retry = useCallback(() => {
    setPhase("loading");
    setError("");
    void fetchAll().then(apply);
  }, [apply]);

  useEffect(() => {
    let cancelled = false;
    void fetchAll().then((result) => {
      if (!cancelled) apply(result);
    });
    return () => {
      cancelled = true;
    };
  }, [apply]);

  // While a storefront is previewed, MAX's own header shows a back arrow that leads here.
  useEffect(
    () => attachHeaderBack(previewSlug ? () => setPreviewSlug("") : null),
    [previewSlug]
  );

  // A second tap on "Удалить" confirms; left alone, the question goes away by itself.
  useEffect(() => {
    if (!confirmDeleteSlug) return;
    const timer = window.setTimeout(() => setConfirmDeleteSlug(""), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmDeleteSlug]);

  const onCreate = useCallback(async () => {
    const text = brief.trim();
    if (text.length < MIN_BRIEF || creating) return;
    haptic("tap");
    setCreating(true);
    setCreateError("");
    guardClosing(true);
    try {
      const created = await createService(text);
      setServices((current) => [created, ...current]);
      setFreshSlug(created.slug);
      setBrief("");
      setComposerOpen(false);
      haptic("success");
    } catch (cause: unknown) {
      setCreateError(messageOf(cause, "Не удалось собрать AIRuntime. Попробуйте ещё раз."));
      haptic("error");
    } finally {
      guardClosing(false);
      setCreating(false);
    }
  }, [brief, creating]);

  const onEdit = useCallback(
    async (service: OwnerService) => {
      const instruction = editText.trim();
      if (instruction.length < 3) return;
      setBusySlug(service.slug);
      setEditNote("");
      guardClosing(true);
      try {
        const updated = await editService(service.slug, instruction);
        setServices((current) =>
          current.map((row) => (row.slug === service.slug ? { ...row, ...updated } : row))
        );
        if (updated.changed) {
          setEditingSlug("");
          setEditText("");
          haptic("success");
        } else {
          setEditNote("Не получилось применить правку\u00a0— переформулируйте, пожалуйста.");
        }
      } catch (cause: unknown) {
        setEditNote(messageOf(cause, "Не удалось изменить AIRuntime"));
      } finally {
        guardClosing(false);
        setBusySlug("");
      }
    },
    [editText]
  );

  const onToggle = useCallback(async (service: OwnerService) => {
    setBusySlug(service.slug);
    try {
      const next = service.status === "live" ? "disabled" : "live";
      const updated = await setServiceStatus(service.slug, next);
      setServices((current) =>
        current.map((row) => (row.slug === service.slug ? { ...row, status: updated.status } : row))
      );
    } catch (cause: unknown) {
      setError(messageOf(cause, "Не удалось обновить AIRuntime"));
    } finally {
      setBusySlug("");
    }
  }, []);

  const onDelete = useCallback(
    async (service: OwnerService) => {
      if (confirmDeleteSlug !== service.slug) {
        setConfirmDeleteSlug(service.slug);
        return;
      }
      setConfirmDeleteSlug("");
      setBusySlug(service.slug);
      try {
        await deleteService(service.slug);
        setServices((current) => current.filter((row) => row.slug !== service.slug));
        setLeads((current) => current.filter((lead) => lead.service_slug !== service.slug));
      } catch (cause: unknown) {
        setError(messageOf(cause, "Не удалось удалить AIRuntime"));
      } finally {
        setBusySlug("");
      }
    },
    [confirmDeleteSlug]
  );

  const onCopy = useCallback(async (service: OwnerService) => {
    if (!service.link) return;
    try {
      await navigator.clipboard.writeText(service.link);
      setCopiedSlug(service.slug);
      window.setTimeout(() => setCopiedSlug(""), 2000);
    } catch {
      // Clipboard access is blocked in some webviews; the link is on screen to copy by hand.
      setCopiedSlug("");
    }
  }, []);

  const onShare = useCallback(
    async (service: OwnerService) => {
      if (!service.link) return;
      haptic("tap");
      const shared = await shareInMax(`${service.config.title}\u00a0— запись онлайн`, service.link);
      if (!shared) await onCopy(service);
    },
    [onCopy]
  );

  const onResolve = useCallback(async (lead: Lead, status: Lead["status"]) => {
    setPendingLeadId(lead.id);
    try {
      const updated = await setLeadStatus(lead.id, status);
      setLeads((current) =>
        current.map((row) => (row.id === lead.id ? { ...row, status: updated.status } : row))
      );
      setServices((current) =>
        current.map((service) =>
          service.slug === lead.service_slug && lead.status === "new"
            ? { ...service, new_leads: Math.max(0, service.new_leads - 1) }
            : service
        )
      );
      haptic("success");
    } catch (cause: unknown) {
      setError(messageOf(cause, "Не удалось обновить заявку"));
    } finally {
      setPendingLeadId("");
    }
  }, []);

  if (phase === "loading") {
    return (
      <div className="max-shell" aria-busy="true" aria-live="polite">
        <div className="max-skeleton" style={{ height: 26, width: "45%", marginBottom: 16 }} />
        <div className="max-list">
          <div className="max-skeleton" style={{ height: 96 }} />
          <div className="max-skeleton" style={{ height: 96 }} />
        </div>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="max-shell">
        <div className="max-error" role="alert">
          {error}
        </div>
        <button
          type="button"
          className="max-button max-button-secondary"
          style={{ marginTop: 14 }}
          onClick={retry}
        >
          Повторить
        </button>
      </div>
    );
  }

  if (previewSlug) {
    return (
      <div className="max-preview">
        <div className="max-preview-bar">
          <button type="button" className="max-preview-back" onClick={() => setPreviewSlug("")}>
            ← К моим сервисам
          </button>
          <span>Так её видят клиенты</span>
        </div>
        <Storefront slug={previewSlug} />
      </div>
    );
  }

  const composer = creating ? (
    <section className="max-sheet max-progress" role="status" aria-live="polite">
      <div className="max-progress-track" aria-hidden>
        <i />
      </div>
      <p className="max-progress-title">Собираем AIRuntime…</p>
      <p className="max-note" style={{ marginTop: 4 }}>
        Обычно это около десяти секунд. Не закрывайте приложение.
      </p>
      <p className="max-progress-brief">«{brief.trim()}»</p>
    </section>
  ) : (
    <section className="max-sheet max-composer">
      <label className="max-field-label" htmlFor="max-brief">
        Расскажите о бизнесе
      </label>
      <textarea
        id="max-brief"
        className="max-textarea max-composer-input"
        rows={5}
        maxLength={2000}
        value={brief}
        onChange={(event) => setBrief(event.target.value)}
        placeholder="Например: барбершоп на Садовой. Стрижка 1200, борода 700. Каждый день с 10 до 21."
      />
      <div className="max-chips max-examples" role="group" aria-label="Примеры описаний">
        {EXAMPLES.map((example) => (
          <button
            key={example.label}
            type="button"
            className="max-chip"
            aria-pressed={brief === example.brief}
            onClick={() => setBrief(example.brief)}
          >
            {example.label}
          </button>
        ))}
      </div>
      <p className="max-hint">
        Названия, цены, адрес и часы работы&nbsp;— всё, что напишете, попадёт в AIRuntime.
      </p>
      {createError ? (
        <div className="max-error" role="alert" style={{ marginTop: 12 }}>
          {createError}
        </div>
      ) : null}
      <button
        type="button"
        className="max-button"
        style={{ marginTop: 14 }}
        disabled={brief.trim().length < MIN_BRIEF}
        onClick={() => void onCreate()}
      >
        Собрать AIRuntime
      </button>
      {services.length > 0 ? (
        <button
          type="button"
          className="max-linklike"
          onClick={() => {
            setComposerOpen(false);
            setCreateError("");
          }}
        >
          Отмена
        </button>
      ) : null}
    </section>
  );

  if (services.length === 0) {
    return (
      <div className="max-shell">
        <header className="max-hero max-welcome">
          <h1>AIRuntime за одно сообщение</h1>
          <p>
            Опишите бизнес&nbsp;— соберём AIRuntime с услугами, ценами и онлайн-записью. Клиенты
            откроют его прямо в MAX.
          </p>
        </header>
        <div style={{ marginTop: 12 }}>{composer}</div>
        {!creating ? (
          <ol className="max-steps">
            <li>
              <b>Опишите бизнес</b>
              <span>одним сообщением, как рассказали бы другу</span>
            </li>
            <li>
              <b>Отправьте ссылку</b>
              <span>клиентам в чат или повесьте QR-код</span>
            </li>
            <li>
              <b>Получайте заявки</b>
              <span>они придут в чат с ботом</span>
            </li>
          </ol>
        ) : null}
      </div>
    );
  }

  const newLeads = leads.filter((lead) => lead.status === "new");
  const rest = leads.filter((lead) => lead.status !== "new");

  return (
    <div className="max-shell">
      <div className="max-toolbar">
        <h2 className="max-section-title" style={{ margin: 0 }}>
          Мои сервисы
        </h2>
        {!composerOpen && !creating ? (
          <button type="button" className="max-toolbar-add" onClick={() => setComposerOpen(true)}>
            + Новая
          </button>
        ) : null}
      </div>

      {composerOpen || creating ? <div style={{ marginBottom: 10 }}>{composer}</div> : null}

      <ul className="max-list">
        {services.map((service) => {
          const busy = busySlug === service.slug;
          const live = service.status === "live";
          const editing = editingSlug === service.slug;
          const summary = [
            KIND_LABEL[service.config.kind],
            service.config.items.length ? pluralItems(service.config.items.length) : "",
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <li
              key={service.slug}
              className={`max-sheet max-card${freshSlug === service.slug ? " max-card-fresh" : ""}`}
            >
              {freshSlug === service.slug ? (
                <p className="max-card-flag">✓ AIRuntime готов&nbsp;— ссылку уже можно отправлять</p>
              ) : null}
              <div className="max-lead-head">
                <span className="max-option-title">{service.config.title}</span>
                {service.new_leads > 0 ? (
                  <span className="max-badge max-badge-new">
                    {service.new_leads} {pluralNew(service.new_leads)}
                  </span>
                ) : (
                  <span className={`max-badge ${live ? "max-badge-confirmed" : "max-badge-declined"}`}>
                    {live ? "опубликована" : "скрыта"}
                  </span>
                )}
              </div>
              <p className="max-option-note">{summary}</p>

              {service.link ? (
                <>
                  <div className="max-link-box">{service.link}</div>
                  <div className="max-row" style={{ marginTop: 10 }}>
                    <button
                      type="button"
                      className="max-button max-button-compact"
                      onClick={() => void onShare(service)}
                      disabled={!live}
                    >
                      Поделиться
                    </button>
                    <button
                      type="button"
                      className="max-button max-button-secondary max-button-compact"
                      onClick={() => void onCopy(service)}
                    >
                      {copiedSlug === service.slug ? "Скопировано" : "Скопировать"}
                    </button>
                  </div>
                </>
              ) : (
                <p className="max-note">Ссылка появится после настройки имени бота.</p>
              )}

              <div className="max-card-actions">
                <button type="button" onClick={() => setPreviewSlug(service.slug)} disabled={busy}>
                  Посмотреть
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditingSlug(editing ? "" : service.slug);
                    setEditText("");
                    setEditNote("");
                  }}
                  disabled={busy}
                >
                  Изменить
                </button>
                <button type="button" onClick={() => void onToggle(service)} disabled={busy}>
                  {live ? "Скрыть" : "Опубликовать"}
                </button>
                <button
                  type="button"
                  className="max-danger"
                  onClick={() => void onDelete(service)}
                  disabled={busy}
                >
                  {confirmDeleteSlug === service.slug ? "Точно удалить?" : "Удалить"}
                </button>
              </div>

              {editing ? (
                <div className="max-edit">
                  <textarea
                    className="max-textarea"
                    rows={3}
                    maxLength={1000}
                    value={editText}
                    onChange={(event) => setEditText(event.target.value)}
                    placeholder="Что поменять? Например: добавь развал-схождение 3000, убери субботу"
                    disabled={busy}
                  />
                  {editNote ? <p className="max-hint">{editNote}</p> : null}
                  <button
                    type="button"
                    className="max-button max-button-compact"
                    style={{ marginTop: 8 }}
                    onClick={() => void onEdit(service)}
                    disabled={busy || editText.trim().length < 3}
                  >
                    {busy ? "Меняем…" : "Применить"}
                  </button>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>

      <h2 className="max-section-title">
        Заявки{newLeads.length > 0 ? ` · ${newLeads.length} ${pluralNew(newLeads.length)}` : ""}
      </h2>
      {leads.length === 0 ? (
        <p className="max-note">Заявок пока нет. Отправьте ссылку клиентам или повесьте QR-код.</p>
      ) : (
        <ul className="max-list">
          {[...newLeads, ...rest].map((lead) => (
            <li key={lead.id} className="max-sheet max-lead">
              <div className="max-lead-head">
                <span className="max-option-title">{lead.customer_name || "Без имени"}</span>
                <span
                  className={`max-badge max-badge-${lead.status === "new" ? "new" : lead.status === "confirmed" ? "confirmed" : "declined"}`}
                >
                  {STATUS_LABEL[lead.status]}
                </span>
              </div>
              <p className="max-option-note">
                {[lead.service_title, lead.item_title, lead.slot_label].filter(Boolean).join(" · ")}
              </p>
              {lead.phone ? <p className="max-option-note">{lead.phone}</p> : null}
              {lead.comment ? <p className="max-option-note">{lead.comment}</p> : null}
              <p className="max-option-note">{formatCreated(lead.created_at)}</p>

              {lead.status === "new" ? (
                <div className="max-row">
                  <button
                    type="button"
                    className="max-button"
                    onClick={() => void onResolve(lead, "confirmed")}
                    disabled={pendingLeadId === lead.id}
                  >
                    Подтвердить
                  </button>
                  <button
                    type="button"
                    className="max-button max-button-secondary"
                    onClick={() => void onResolve(lead, "declined")}
                    disabled={pendingLeadId === lead.id}
                  >
                    Отклонить
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {error ? (
        <div className="max-error" role="alert" style={{ marginTop: 14 }}>
          {error}
        </div>
      ) : null}
      <div style={{ height: 24 }} aria-hidden />
    </div>
  );
}
