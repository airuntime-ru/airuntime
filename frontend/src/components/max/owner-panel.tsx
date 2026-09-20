"use client";

/**
 * The owner's side of the mini app: what I made, who wants it, confirm or decline.
 *
 * The bot chat already handles creating and editing, so this screen deliberately does not
 * duplicate that. It exists for the two things a chat is bad at: seeing every service and
 * its link at once, and working through a list of leads.
 */

import { useCallback, useEffect, useState } from "react";

import {
  MaxApiError,
  fetchOwnerLeads,
  fetchOwnerOverview,
  setLeadStatus,
  type Lead,
  type OwnerService,
} from "@/lib/max/api";

type Phase = "loading" | "ready" | "error";

const STATUS_LABEL: Record<Lead["status"], string> = {
  new: "новая",
  confirmed: "подтверждена",
  declined: "отклонена",
  done: "выполнена",
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
  const [copiedSlug, setCopiedSlug] = useState("");

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
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Не удалось обновить заявку");
    } finally {
      setPendingLeadId("");
    }
  }, []);

  const onCopyLink = useCallback(async (service: OwnerService) => {
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

  if (services.length === 0) {
    return (
      <div className="max-shell">
        <header className="max-hero">
          <h1>Пока ничего не создано</h1>
          <p>Вернитесь в чат с ботом и опишите бизнес одним сообщением — витрина соберётся за пару секунд.</p>
        </header>
        <p className="max-note">
          Например: «Автосервис на Лесной. Диагностика 1500, замена масла 900. Работаем с 9 до 20».
        </p>
      </div>
    );
  }

  const newLeads = leads.filter((lead) => lead.status === "new");
  const rest = leads.filter((lead) => lead.status !== "new");

  return (
    <div className="max-shell">
      <h2 className="max-section-title" style={{ marginTop: 0 }}>
        Мои сервисы
      </h2>
      <ul className="max-list">
        {services.map((service) => (
          <li key={service.slug} className="max-sheet" style={{ padding: "14px 16px" }}>
            <div className="max-lead-head">
              <span className="max-option-title">{service.config.title}</span>
              {service.new_leads > 0 ? (
                <span className="max-badge max-badge-new">
                  {service.new_leads} {pluralNew(service.new_leads)}
                </span>
              ) : (
                <span className="max-badge max-badge-declined">
                  {service.status === "live" ? "опубликован" : "черновик"}
                </span>
              )}
            </div>
            {service.link ? (
              <>
                <div className="max-link-box">{service.link}</div>
                <button
                  type="button"
                  className="max-button max-button-secondary"
                  style={{ marginTop: 8, minHeight: 42, fontSize: "0.92rem" }}
                  onClick={() => void onCopyLink(service)}
                >
                  {copiedSlug === service.slug ? "Ссылка скопирована" : "Скопировать ссылку"}
                </button>
              </>
            ) : (
              <p className="max-note">Ссылка появится после настройки имени бота.</p>
            )}
          </li>
        ))}
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
                <span className={`max-badge max-badge-${lead.status === "new" ? "new" : lead.status === "confirmed" ? "confirmed" : "declined"}`}>
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
    </div>
  );
}
