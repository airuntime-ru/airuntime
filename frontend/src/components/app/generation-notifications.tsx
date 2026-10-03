"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, BellRing, CheckCircle2, CircleAlert, X } from "lucide-react";

import {
  dismissGenerationNotice,
  generationNoticeHref,
  generationNotificationsEnabled,
  getGenerationNotices,
  getGenerationNotificationPermission,
  getServerGenerationNotices,
  OPEN_GENERATION_NOTICE_EVENT,
  setGenerationNotificationsEnabled,
  subscribeGenerationNotices,
} from "@/lib/generation-notifications";
import { cn } from "@/lib/cn";

export function GenerationNotifications() {
  const router = useRouter();
  const notices = useSyncExternalStore(subscribeGenerationNotices, getGenerationNotices, getServerGenerationNotices);
  const [enabled, setEnabled] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [hint, setHint] = useState("");

  useEffect(() => {
    const sync = () => setEnabled(generationNotificationsEnabled());
    const timer = window.setTimeout(sync, 0);
    const onOpen = (event: Event) => {
      const href = (event as CustomEvent<{ href: string }>).detail.href;
      event.preventDefault();
      router.push(href);
    };
    window.addEventListener("focus", sync);
    window.addEventListener("storage", sync);
    window.addEventListener(OPEN_GENERATION_NOTICE_EVENT, onOpen);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("focus", sync);
      window.removeEventListener("storage", sync);
      window.removeEventListener(OPEN_GENERATION_NOTICE_EVENT, onOpen);
    };
  }, [router]);

  const toggle = async () => {
    setHint("");
    if (generationNotificationsEnabled()) {
      setGenerationNotificationsEnabled(false);
      setEnabled(false);
      setHint("Уведомления браузера выключены. Сообщения о завершении останутся в кабинете.");
      return;
    }
    const permission = getGenerationNotificationPermission();
    if (permission === "unsupported") {
      setHint("Этот браузер не поддерживает уведомления. Сообщение о завершении появится в кабинете.");
      return;
    }
    if (permission === "denied") {
      setHint("Разрешите уведомления для этого сайта в настройках браузера, затем включите их здесь.");
      return;
    }
    setRequesting(true);
    try {
      // Request inside the button gesture: browsers block unsolicited permission prompts.
      const result = permission === "granted" ? permission : await Notification.requestPermission();
      const allowed = result === "granted";
      setGenerationNotificationsEnabled(allowed);
      setEnabled(generationNotificationsEnabled());
      setHint(allowed
        ? "Сообщим, когда генерация завершится. Оставьте вкладку открытой — можно работать в других окнах."
        : "Уведомления не разрешены. Сообщение о завершении появится в кабинете.");
    } catch {
      setHint("Не удалось включить уведомления. Проверьте разрешения сайта в браузере.");
    } finally {
      setRequesting(false);
    }
  };

  const label = enabled ? "Выключить уведомления о завершении генерации" : "Включить уведомления о завершении генерации";

  return (
    <>
      <div className="relative">
        <button
          type="button"
          onClick={() => void toggle()}
          disabled={requesting}
          title={label}
          aria-label={label}
          aria-pressed={enabled}
          className={cn(
            "inline-flex h-10 items-center justify-center gap-1.5 rounded-full px-2.5 text-sm transition-colors hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35 disabled:opacity-50",
            enabled ? "text-[var(--ar-sky)]" : "text-[var(--ar-stone)]"
          )}
        >
          {enabled ? <BellRing size={17} aria-hidden /> : <Bell size={17} aria-hidden />}
          <span className="hidden sm:inline">{enabled ? "Уведомления" : "Уведомлять"}</span>
        </button>
      </div>
      {typeof document !== "undefined" && (hint || notices.length > 0) ? createPortal(
        <div className="fixed right-1 top-[4.5rem] z-[70] flex max-h-[calc(100dvh-6rem)] w-[min(24rem,calc(100vw-0.5rem))] flex-col gap-2 overflow-y-auto p-2 sm:right-2 lg:right-4" aria-live="polite" aria-relevant="additions">
          {hint ? (
            <div className="relative rounded-2xl border border-black/10 bg-white p-4 pr-10 text-sm text-[var(--ar-graphite)] shadow-lg" role="status">
              {hint}
              <button type="button" onClick={() => setHint("")} aria-label="Закрыть подсказку" className="absolute right-1 top-1 rounded-full p-2 hover:bg-black/5">
                <X size={14} aria-hidden />
              </button>
            </div>
          ) : null}
          {notices.map((notice) => (
            <div key={notice.id} className="flex items-start gap-3 rounded-2xl border border-black/10 bg-white p-4 shadow-lg">
              {notice.outcome === "success"
                ? <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-emerald-600" aria-hidden />
                : <CircleAlert size={20} className="mt-0.5 shrink-0 text-amber-600" aria-hidden />}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-[var(--ar-black)]">{notice.title}</p>
                <p className="mt-1 text-sm text-[var(--ar-stone)]">{notice.body}</p>
                <Link href={generationNoticeHref(notice)} onClick={() => dismissGenerationNotice(notice.id)} className="mt-2 inline-flex text-sm font-medium text-[var(--ar-sky)] hover:underline">
                  Открыть диалог
                </Link>
              </div>
              <button type="button" onClick={() => dismissGenerationNotice(notice.id)} aria-label="Закрыть уведомление" className="-mr-2 -mt-2 shrink-0 rounded-full p-2 text-[var(--ar-stone)] hover:bg-black/5">
                <X size={16} aria-hidden />
              </button>
            </div>
          ))}
        </div>,
        document.body
      ) : null}
    </>
  );
}
