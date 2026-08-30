"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { HeadphonesIcon, Send, X } from "lucide-react";

import {
  fetchSupportConversation,
  fetchSupportUnread,
  markSupportRead,
  sendSupportMessage,
  type SupportConversationType,
  type SupportMessageType,
} from "@/lib/api";
import { cn } from "@/lib/cn";

const POLL_MS = 4000;

export function SupportUserChat({ hidden }: { hidden?: boolean }) {
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [conversation, setConversation] = useState<SupportConversationType | null>(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refreshUnread = useCallback(async () => {
    try {
      const data = await fetchSupportUnread();
      setUnread(data.unread);
    } catch {
      // ignore when logged out
    }
  }, []);

  const loadConversation = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchSupportConversation();
      setConversation(data);
      const unreadIds = data.messages
        .filter((m) => m.sender_party === "staff" && !m.read_at)
        .map((m) => m.id);
      if (unreadIds.length) {
        await markSupportRead(unreadIds);
      }
      setUnread(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (hidden) return;
    void refreshUnread();
    const timer = window.setInterval(refreshUnread, POLL_MS);
    return () => window.clearInterval(timer);
  }, [hidden, refreshUnread]);

  useEffect(() => {
    if (!open) return;
    void loadConversation();
    const timer = window.setInterval(loadConversation, POLL_MS);
    return () => window.clearInterval(timer);
  }, [open, loadConversation]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages.length, open]);

  const onSend = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      const message = await sendSupportMessage(text);
      setDraft("");
      setConversation((prev) =>
        prev
          ? { ...prev, messages: [...prev.messages, message] }
          : { id: message.conversation_id, status: "open", messages: [message] }
      );
    } finally {
      setSending(false);
    }
  };

  if (hidden) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-24 right-4 z-[70] inline-flex h-12 w-12 items-center justify-center rounded-full bg-[var(--ar-black)] text-white shadow-lg transition hover:scale-105 lg:bottom-8"
        aria-label="Поддержка"
        title="Поддержка"
      >
        <HeadphonesIcon size={20} />
        {unread > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/40 p-3 sm:items-center">
          <div className="flex max-h-[min(640px,90dvh)] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-black/10 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-black/5 px-4 py-3">
              <div>
                <p className="font-semibold text-[var(--ar-black)]">Поддержка AIRuntime</p>
                <p className="text-xs text-[var(--ar-mist)]">Ответим в рабочее время</p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-full p-2 text-[var(--ar-stone)] hover:bg-black/5"
                aria-label="Закрыть"
              >
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
              {loading && !conversation ? (
                <p className="text-sm text-[var(--ar-mist)]">Загрузка…</p>
              ) : null}
              {(conversation?.messages ?? []).map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              <div ref={bottomRef} />
            </div>

            <div className="flex gap-2 border-t border-black/5 p-3">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                placeholder="Опишите проблему или вопрос…"
                className="min-h-[44px] flex-1 resize-none rounded-xl border border-black/10 px-3 py-2 text-sm outline-none focus:border-[var(--ar-sky)]"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void onSend();
                  }
                }}
              />
              <button
                type="button"
                disabled={sending || !draft.trim()}
                onClick={() => void onSend()}
                className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--ar-black)] text-white disabled:opacity-40"
                aria-label="Отправить"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function MessageBubble({ message }: { message: SupportMessageType }) {
  const mine = message.sender_party === "user";
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap",
          mine ? "bg-[var(--ar-black)] text-white" : "bg-black/[0.06] text-[var(--ar-black)]"
        )}
      >
        {message.body}
      </div>
    </div>
  );
}
