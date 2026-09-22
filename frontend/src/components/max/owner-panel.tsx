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

import { useCallback, useEffect, useRef, useState } from "react";

import { Storefront } from "@/components/max/storefront";
import { filterLeadsForDay, OwnerCalendar } from "@/components/max/owner-calendar";
import { OwnerServicePicker } from "@/components/max/owner-service-picker";
import {
  MaxApiError,
  createService,
  deleteService,
  editService,
  fetchOwnerLeads,
  fetchOwnerOverview,
  patchService,
  setLeadStatus,
  setServiceStatus,
  type AttachedFile,
  type Lead,
  type OwnerService,
} from "@/lib/max/api";
import { attachHeaderBack, guardClosing, haptic, openMaxChat, shareInMax } from "@/lib/max/bridge";

type Phase = "loading" | "ready" | "error";

// The backend refuses anything shorter: "привет" is not something a storefront can be
// built from, and saying so before the request beats a round trip to find out.
const MIN_BRIEF = 12;
const MAX_ATTACHMENTS = 4;

function looksLikeUrl(value: string): boolean {
  const text = value.trim();
  if (!text || /\s/.test(text)) return false;
  try {
    const parsed = new URL(text.includes("://") ? text : `https://${text}`);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function bufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}

function resizeImage(file: File): Promise<AttachedFile> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(file);
    image.onload = () => {
      const max = 1024;
      const scale = Math.min(1, max / Math.max(image.width, image.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      const context = canvas.getContext("2d");
      if (!context) {
        URL.revokeObjectURL(url);
        reject(new Error("canvas"));
        return;
      }
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
      URL.revokeObjectURL(url);
      resolve({
        filename: file.name.replace(/\.[^.]+$/, "") + ".jpg",
        content_type: "image/jpeg",
        data_base64: dataUrl.split(",")[1] || "",
      });
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Не удалось прочитать изображение"));
    };
    image.src = url;
  });
}

async function fileToAttachment(file: File): Promise<AttachedFile> {
  if (file.type.startsWith("image/")) return resizeImage(file);
  if (file.size > 900_000) {
    throw new Error(`${file.name}: файл больше 900 КБ`);
  }
  return {
    filename: file.name,
    content_type: file.type || "application/octet-stream",
    data_base64: bufferToBase64(await file.arrayBuffer()),
  };
}

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

function pluralLeads(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} заявка`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} заявки`;
  return `${count} заявок`;
}

function pluralServices(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} сервис`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} сервиса`;
  return `${count} сервисов`;
}

const SELECTED_SLUG_KEY = "airuntime-owner-service";

function readStoredSlug(): string {
  try {
    return sessionStorage.getItem(SELECTED_SLUG_KEY) ?? "";
  } catch {
    return "";
  }
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

function looksLikeStub(service: OwnerService): boolean {
  const title = service.config.title.trim().toLowerCase();
  if (title.startsWith("описание владельца") || title === "мой сервис") return true;
  if (service.config.tagline === "Заполните описание в приложении") return true;
  return service.config.items.length > 0 && service.config.items.every((item) => /^Позиция \d+$/i.test(item.title));
}

type CatalogRow = { title: string; price: string };

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
  const [siteUrl, setSiteUrl] = useState("");
  const [attachments, setAttachments] = useState<AttachedFile[]>([]);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");
  const [freshSlug, setFreshSlug] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  // Working on an existing one.
  const [busySlug, setBusySlug] = useState("");
  const [copiedSlug, setCopiedSlug] = useState("");
  const [editingSlug, setEditingSlug] = useState("");
  const [editText, setEditText] = useState("");
  const [editNote, setEditNote] = useState("");
  const [confirmDeleteSlug, setConfirmDeleteSlug] = useState("");
  const [previewSlug, setPreviewSlug] = useState("");
  const [calendarDay, setCalendarDay] = useState<string | null>(null);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [catalog, setCatalog] = useState<CatalogRow[]>([]);
  const [catalogNote, setCatalogNote] = useState("");

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

  useEffect(() => {
    if (services.length === 0) {
      setSelectedSlug("");
      return;
    }
    if (services.some((service) => service.slug === selectedSlug)) return;
    const stored = readStoredSlug();
    if (stored && services.some((service) => service.slug === stored)) {
      setSelectedSlug(stored);
      return;
    }
    const withNew = services.find((service) => service.new_leads > 0);
    setSelectedSlug((withNew ?? services[0]).slug);
  }, [services, selectedSlug]);

  useEffect(() => {
    if (!selectedSlug) return;
    try {
      sessionStorage.setItem(SELECTED_SLUG_KEY, selectedSlug);
    } catch {
      // Private mode or a webview without storage — selection still lives in React state.
    }
  }, [selectedSlug]);

  useEffect(() => {
    const current = services.find((service) => service.slug === selectedSlug);
    if (!current) {
      setCatalog([]);
      return;
    }
    setCatalog(
      current.config.items.map((item) => ({
        title: item.title,
        price: item.price_rub != null ? String(item.price_rub) : "",
      }))
    );
    setCatalogNote("");
  }, [services, selectedSlug]);

  const onCreate = useCallback(async () => {
    const text = brief.trim();
    const url = siteUrl.trim();
    const ready = text.length >= MIN_BRIEF || looksLikeUrl(url) || attachments.length > 0;
    if (!ready || creating) return;
    haptic("tap");
    setCreating(true);
    setCreateError("");
    guardClosing(true);
    try {
      const created = await createService({
        brief: text,
        site_url: url,
        files: attachments,
      });
      setServices((current) => [created, ...current]);
      setFreshSlug(created.slug);
      setSelectedSlug(created.slug);
      setCalendarDay(null);
      setBrief("");
      setSiteUrl("");
      setAttachments([]);
      setComposerOpen(false);
      haptic("success");
    } catch (cause: unknown) {
      setCreateError(messageOf(cause, "Не удалось собрать страницу. Попробуйте ещё раз."));
      haptic("error");
    } finally {
      guardClosing(false);
      setCreating(false);
    }
  }, [attachments, brief, creating, siteUrl]);

  const onPickFiles = useCallback(async (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const room = MAX_ATTACHMENTS - attachments.length;
    const chosen = Array.from(list).slice(0, room);
    try {
      const next = await Promise.all(chosen.map(fileToAttachment));
      setAttachments((current) => [...current, ...next].slice(0, MAX_ATTACHMENTS));
      setCreateError("");
    } catch (cause: unknown) {
      setCreateError(messageOf(cause, "Не удалось прикрепить файл"));
    }
    if (fileInput.current) fileInput.current.value = "";
  }, [attachments.length]);

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

  const onSaveCatalog = useCallback(
    async (service: OwnerService) => {
      const items = catalog
        .map((row) => {
          const title = row.title.trim();
          if (!title) return null;
          const raw = row.price.trim().replace(/\s/g, "");
          const price = raw ? Number.parseInt(raw, 10) : null;
          return {
            title,
            price_rub: Number.isFinite(price) ? price : null,
          };
        })
        .filter((row): row is { title: string; price_rub: number | null } => row !== null);
      setBusySlug(service.slug);
      setCatalogNote("");
      try {
        const updated = await patchService(service.slug, { items });
        setServices((current) =>
          current.map((row) => (row.slug === service.slug ? { ...row, ...updated } : row))
        );
        haptic("success");
        setCatalogNote("Меню сохранено");
      } catch (cause: unknown) {
        setCatalogNote(messageOf(cause, "Не удалось сохранить меню"));
      } finally {
        setBusySlug("");
      }
    },
    [catalog]
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

  const canCreate =
    brief.trim().length >= MIN_BRIEF || looksLikeUrl(siteUrl) || attachments.length > 0;

  const composer = creating ? (
    <section className="max-sheet max-progress" role="status" aria-live="polite">
      <div className="max-progress-track" aria-hidden>
        <i />
      </div>
      <p className="max-progress-title">Собираем страницу записи…</p>
      <p className="max-note" style={{ marginTop: 4 }}>
        Обычно меньше минуты. Не закрывайте приложение.
      </p>
      {brief.trim() ? <p className="max-progress-brief">«{brief.trim()}»</p> : null}
    </section>
  ) : (
    <section className="max-sheet max-composer">
      <label className="max-field-label" htmlFor="max-brief">
        Что предлагаете клиентам
      </label>
      <textarea
        id="max-brief"
        className="max-textarea max-composer-input"
        rows={5}
        maxLength={2000}
        value={brief}
        onChange={(event) => setBrief(event.target.value)}
        placeholder="Барбершоп на Садовой. Стрижка 1200, борода 700. Каждый день с 10 до 21."
      />
      <div className="max-chips max-examples" role="group" aria-label="Примеры">
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

      <label className="max-field-label" htmlFor="max-site" style={{ marginTop: 16 }}>
        Сайт <span className="max-optional">необязательно</span>
      </label>
      <input
        id="max-site"
        className="max-input"
        type="url"
        inputMode="url"
        autoComplete="url"
        placeholder="https://yoursite.ru"
        value={siteUrl}
        onChange={(event) => setSiteUrl(event.target.value)}
      />
      <p className="max-hint">Подтянем услуги, цены и цвета, если они есть на странице.</p>

      <p className="max-field-label" style={{ marginTop: 16 }}>
        Файлы <span className="max-optional">необязательно</span>
      </p>
      <input
        ref={fileInput}
        type="file"
        hidden
        multiple
        accept="image/jpeg,image/png,image/webp,image/gif,application/pdf,text/plain,.pdf,.txt"
        onChange={(event) => void onPickFiles(event.target.files)}
      />
      {attachments.length > 0 ? (
        <ul className="max-attach-list">
          {attachments.map((file, index) => (
            <li key={`${file.filename}-${index}`}>
              <span>{file.filename}</span>
              <button
                type="button"
                className="max-attach-remove"
                onClick={() =>
                  setAttachments((current) => current.filter((_, item) => item !== index))
                }
              >
                Убрать
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {attachments.length < MAX_ATTACHMENTS ? (
        <button
          type="button"
          className="max-button max-button-secondary max-button-compact"
          style={{ marginTop: 8 }}
          onClick={() => fileInput.current?.click()}
        >
          Прикрепить логотип, прайс или референс
        </button>
      ) : null}
      <p className="max-hint">Фото смотрим как образец стиля. PDF и текст — как прайс и описание.</p>

      {createError ? (
        <div className="max-error" role="alert" style={{ marginTop: 12 }}>
          {createError}
        </div>
      ) : null}
      <button
        type="button"
        className="max-button"
        style={{ marginTop: 14 }}
        disabled={!canCreate}
        onClick={() => void onCreate()}
      >
        Собрать страницу записи
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
        <header className="max-intro">
          <h1>Страница записи в MAX</h1>
          <p>Опишите бизнес, при желании добавьте сайт или файлы. Клиенты запишутся здесь, заявки придут вам в чат.</p>
        </header>
        {composer}
      </div>
    );
  }

  const selected = services.find((service) => service.slug === selectedSlug) ?? services[0];
  const scopedLeads = leads.filter((lead) => lead.service_slug === selected.slug);
  const newLeads = scopedLeads.filter((lead) => lead.status === "new");
  const rest = scopedLeads.filter((lead) => lead.status !== "new");
  const visibleLeads = filterLeadsForDay([...newLeads, ...rest], calendarDay);
  const busy = busySlug === selected.slug;
  const live = selected.status === "live";
  const editing = editingSlug === selected.slug;
  const summary = [
    KIND_LABEL[selected.config.kind],
    pluralLeads(selected.lead_count ?? 0),
    selected.new_leads > 0
      ? `${selected.new_leads} ${pluralNew(selected.new_leads)}`
      : live
        ? ""
        : "скрыт",
    services.length > 1 ? pluralServices(services.length) : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="max-shell">
      <button
        type="button"
        className="max-switcher"
        aria-haspopup="dialog"
        aria-expanded={pickerOpen}
        onClick={() => {
          haptic("tap");
          setPickerOpen(true);
        }}
      >
        <span className="max-switcher-icon" aria-hidden>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5.5v-6h-3v6H5a1 1 0 0 1-1-1v-9.5Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span className="max-switcher-body">
          <span className="max-switcher-kicker">Сервис</span>
          <span className="max-switcher-title">{selected.config.title}</span>
          <span className="max-switcher-note">{summary}</span>
        </span>
        <span className="max-switcher-chevron" aria-hidden>
          ▾
        </span>
      </button>

      {composerOpen || creating ? <div style={{ marginBottom: 10 }}>{composer}</div> : null}

      {!composerOpen && !creating ? (
        <article
          className={`max-sheet max-card${freshSlug === selected.slug ? " max-card-fresh" : ""}`}
          style={{ marginBottom: 14 }}
        >
          {freshSlug === selected.slug ? (
            <p className="max-card-flag">✓ AIRuntime готов&nbsp;— ссылку уже можно отправлять</p>
          ) : null}

          {looksLikeStub(selected) ? (
            <p className="max-card-flag" style={{ color: "#b45309" }}>
              Черновик: модель не собрала страницу. Проверьте меню ниже.
            </p>
          ) : null}

          {selected.link ? (
            <>
              <div className="max-link-box">{selected.link}</div>
              <div className="max-row" style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="max-button max-button-compact"
                  onClick={() => void onShare(selected)}
                  disabled={!live}
                >
                  Поделиться
                </button>
                <button
                  type="button"
                  className="max-button max-button-secondary max-button-compact"
                  onClick={() => void onCopy(selected)}
                >
                  {copiedSlug === selected.slug ? "Скопировано" : "Скопировать"}
                </button>
              </div>
            </>
          ) : (
            <p className="max-note">Ссылка появится после настройки имени бота.</p>
          )}

          <div className="max-catalog">
            <p className="max-field-label">Меню</p>
            {catalog.map((row, index) => (
              <div className="max-catalog-row" key={`${selected.slug}-${index}`}>
                <input
                  className="max-input"
                  value={row.title}
                  placeholder="Название"
                  onChange={(event) =>
                    setCatalog((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, title: event.target.value } : item
                      )
                    )
                  }
                />
                <input
                  className="max-input max-catalog-price"
                  inputMode="numeric"
                  placeholder="₽"
                  value={row.price}
                  onChange={(event) =>
                    setCatalog((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, price: event.target.value } : item
                      )
                    )
                  }
                />
                <button
                  type="button"
                  className="max-catalog-remove"
                  aria-label="Убрать позицию"
                  onClick={() =>
                    setCatalog((current) => current.filter((_, itemIndex) => itemIndex !== index))
                  }
                >
                  ✕
                </button>
              </div>
            ))}
            <div className="max-row" style={{ marginTop: 8 }}>
              <button
                type="button"
                className="max-button max-button-secondary max-button-compact"
                onClick={() => setCatalog((current) => [...current, { title: "", price: "" }])}
              >
                + Позиция
              </button>
              <button
                type="button"
                className="max-button max-button-compact"
                onClick={() => void onSaveCatalog(selected)}
                disabled={busy}
              >
                Сохранить меню
              </button>
            </div>
            {catalogNote ? <p className="max-hint">{catalogNote}</p> : null}
          </div>

          <div className="max-card-actions">
            <button type="button" onClick={() => setPreviewSlug(selected.slug)} disabled={busy}>
              Посмотреть
            </button>
            <button
              type="button"
              onClick={() => {
                setEditingSlug(editing ? "" : selected.slug);
                setEditText("");
                setEditNote("");
              }}
              disabled={busy}
            >
                  Изменить словами
            </button>
            <button type="button" onClick={() => void onToggle(selected)} disabled={busy}>
              {live ? "Скрыть" : "Опубликовать"}
            </button>
            <button
              type="button"
              className="max-danger"
              onClick={() => void onDelete(selected)}
              disabled={busy}
            >
              {confirmDeleteSlug === selected.slug ? "Точно удалить?" : "Удалить"}
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
                onClick={() => void onEdit(selected)}
                disabled={busy || editText.trim().length < 3}
              >
                {busy ? "Меняем…" : "Применить"}
              </button>
            </div>
          ) : null}
        </article>
      ) : null}

      <h2 className="max-section-title">Календарь</h2>
      <OwnerCalendar leads={scopedLeads} selectedKey={calendarDay} onSelect={setCalendarDay} />
      {calendarDay ? (
        <button type="button" className="max-linklike" onClick={() => setCalendarDay(null)}>
          Показать все заявки
        </button>
      ) : null}

      <h2 className="max-section-title">
        {calendarDay
          ? `Заявки · ${visibleLeads.length}`
          : `Заявки${newLeads.length > 0 ? ` · ${newLeads.length} ${pluralNew(newLeads.length)}` : ""}`}
      </h2>
      {scopedLeads.length === 0 ? (
        <p className="max-note">Заявок пока нет. Отправьте ссылку клиентам или повесьте QR-код.</p>
      ) : visibleLeads.length === 0 ? (
        <p className="max-note">На этот день записей нет.</p>
      ) : (
        <ul className="max-list">
          {visibleLeads.map((lead) => (
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
                {[lead.item_title, lead.slot_label].filter(Boolean).join(" · ")}
              </p>
              {lead.phone ? <p className="max-option-note">{lead.phone}</p> : null}
              {lead.comment ? <p className="max-option-note">{lead.comment}</p> : null}
              <p className="max-option-note">{formatCreated(lead.created_at)}</p>

              {lead.chat_url ? (
                <button
                  type="button"
                  className="max-button max-button-quiet"
                  style={{ marginTop: 12 }}
                  onClick={() => {
                    haptic("tap");
                    openMaxChat(lead.chat_url);
                  }}
                >
                  Написать в MAX
                </button>
              ) : null}

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

      <OwnerServicePicker
        open={pickerOpen}
        services={services}
        selectedSlug={selected.slug}
        onSelect={(slug) => {
          if (slug === selectedSlug) return;
          setSelectedSlug(slug);
          setCalendarDay(null);
          setEditingSlug("");
          setConfirmDeleteSlug("");
          haptic("tap");
        }}
        onClose={() => setPickerOpen(false)}
        onAdd={() => {
          setPickerOpen(false);
          setComposerOpen(true);
          haptic("tap");
        }}
      />
    </div>
  );
}
