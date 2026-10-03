export type GenerationNotice = {
  id: string;
  projectId: string;
  chatId: string;
  title: string;
  body: string;
  outcome: "success" | "error" | "attention";
};

export const OPEN_GENERATION_NOTICE_EVENT = "airuntime:open-generation-notice";
const ENABLED_KEY = "airuntime:generation-notifications-enabled";
const EMPTY_NOTICES: GenerationNotice[] = [];
let notices = EMPTY_NOTICES;
const listeners = new Set<() => void>();
let enabledWithoutStorage = false;

export function getGenerationNotices(): GenerationNotice[] {
  return notices;
}

export function getServerGenerationNotices(): GenerationNotice[] {
  return EMPTY_NOTICES;
}

export function subscribeGenerationNotices(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function dismissGenerationNotice(id: string): void {
  notices = notices.filter((notice) => notice.id !== id);
  listeners.forEach((listener) => listener());
}

export function generationNoticeHref(notice: Pick<GenerationNotice, "projectId" | "chatId">): string {
  return `/app/projects/${encodeURIComponent(notice.projectId)}/chat?chat=${encodeURIComponent(notice.chatId)}`;
}

export function getGenerationNotificationPermission(): NotificationPermission | "unsupported" {
  if (typeof window === "undefined" || !window.isSecureContext || !("Notification" in window)) {
    return "unsupported";
  }
  return Notification.permission;
}

export function generationNotificationsEnabled(): boolean {
  if (getGenerationNotificationPermission() !== "granted") return false;
  try {
    return localStorage.getItem(ENABLED_KEY) === "true";
  } catch {
    return enabledWithoutStorage;
  }
}

export function setGenerationNotificationsEnabled(enabled: boolean): void {
  enabledWithoutStorage = enabled;
  try {
    localStorage.setItem(ENABLED_KEY, String(enabled));
  } catch {
    // Notification support must never affect generation if browser storage is unavailable.
  }
}

/** Called only by the tab owning the stream, so mirrored tabs do not duplicate alerts. */
export function notifyGenerationFinished(notice: GenerationNotice): void {
  if (typeof window === "undefined" || notices.some((item) => item.id === notice.id)) return;
  notices = [...notices.slice(-4), notice];
  listeners.forEach((listener) => listener());

  if (!generationNotificationsEnabled()) return;
  if (document.visibilityState === "visible" && document.hasFocus()) return;
  try {
    const notification = new Notification(notice.title, {
      body: notice.body,
      icon: "/icon-192.png",
      tag: notice.id,
      requireInteraction: true,
    });
    notification.onclick = (event) => {
      event.preventDefault();
      notification.close();
      dismissGenerationNotice(notice.id);
      window.focus();
      const href = generationNoticeHref(notice);
      const open = new CustomEvent(OPEN_GENERATION_NOTICE_EVENT, { detail: { href }, cancelable: true });
      if (window.dispatchEvent(open)) window.location.assign(href);
    };
  } catch {
    // Some browsers only support service-worker notifications. The cabinet notice remains.
  }
}
