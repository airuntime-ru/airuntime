"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  closeStaffConversation,
  fetchStaffConversation,
  fetchStaffConversations,
  markStaffRead,
  openStaffConversationForUser,
  sendStaffMessage,
  setAccessToken,
  type StaffConversationSummaryType,
  type SupportConversationType,
} from "@/lib/api";
import { cn } from "@/lib/cn";

const POLL_MS = 3000;

export default function SupportStaffChatPage() {
  const searchParams = useSearchParams();
  const bridgeToken = searchParams.get("bridge_token");
  const customerUserId = searchParams.get("customer_user_id");

  const [ready, setReady] = useState(false);
  const [inbox, setInbox] = useState<StaffConversationSummaryType[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [thread, setThread] = useState<SupportConversationType | null>(null);
  const [draft, setDraft] = useState("");
  const [filter, setFilter] = useState<"all" | "open" | "closed">("open");
  const [unreadOnly, setUnreadOnly] = useState(false);

  useEffect(() => {
    if (bridgeToken) {
      setAccessToken(bridgeToken);
      setReady(true);
      return;
    }
    setReady(true);
  }, [bridgeToken]);

  const loadInbox = useCallback(async () => {
    const data = await fetchStaffConversations({
      status: filter,
      unreadOnly,
    });
    setInbox(data.items);
  }, [filter, unreadOnly]);

  const loadThread = useCallback(async (conversationId: string) => {
    const data = await fetchStaffConversation(conversationId);
    setThread(data);
    const unreadIds = data.messages
      .filter((m) => m.sender_party === "user" && !m.read_at)
      .map((m) => m.id);
    if (unreadIds.length) {
      await markStaffRead(conversationId, unreadIds);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    void loadInbox();
    const timer = window.setInterval(loadInbox, POLL_MS);
    return () => window.clearInterval(timer);
  }, [ready, loadInbox]);

  useEffect(() => {
    if (!ready || !customerUserId) return;
    void (async () => {
      const data = await openStaffConversationForUser(customerUserId);
      setActiveId(data.id);
      setThread(data);
    })();
  }, [ready, customerUserId]);

  useEffect(() => {
    if (!activeId || customerUserId) return;
    void loadThread(activeId);
    const timer = window.setInterval(() => loadThread(activeId), POLL_MS);
    return () => window.clearInterval(timer);
  }, [activeId, customerUserId, loadThread]);

  const activeSummary = useMemo(
    () => inbox.find((item) => item.id === activeId) ?? null,
    [inbox, activeId]
  );

  const onSend = async () => {
    if (!activeId || !draft.trim()) return;
    const message = await sendStaffMessage(activeId, draft.trim());
    setDraft("");
    setThread((prev) =>
      prev ? { ...prev, messages: [...prev.messages, message] } : prev
    );
    void loadInbox();
  };

  if (!ready) {
    return <p className="p-6 text-sm text-[var(--ar-mist)]">Подключение…</p>;
  }

  return (
    <div className="mx-auto flex min-h-[70dvh] max-w-6xl flex-col gap-4 p-4 lg:flex-row">
      <aside className="w-full shrink-0 rounded-2xl border border-black/10 bg-white lg:w-80">
        <div className="border-b border-black/5 p-3">
          <h1 className="text-lg font-semibold">Поддержка</h1>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {(["all", "open", "closed"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={cn(
                  "rounded-full px-3 py-1",
                  filter === value ? "bg-[var(--ar-black)] text-white" : "bg-black/5"
                )}
              >
                {value === "all" ? "Все" : value === "open" ? "Открытые" : "Закрытые"}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setUnreadOnly((v) => !v)}
              className={cn(
                "rounded-full px-3 py-1",
                unreadOnly ? "bg-red-600 text-white" : "bg-black/5"
              )}
            >
              Непрочитанные
            </button>
          </div>
        </div>
        <ul className="max-h-[60dvh] overflow-y-auto">
          {inbox.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => setActiveId(item.id)}
                className={cn(
                  "w-full border-b border-black/5 px-3 py-3 text-left hover:bg-black/[0.03]",
                  activeId === item.id && "bg-black/[0.04]"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{item.user_email}</span>
                  {item.unread_from_user > 0 ? (
                    <span className="rounded-full bg-red-600 px-2 py-0.5 text-[10px] text-white">
                      {item.unread_from_user}
                    </span>
                  ) : null}
                </div>
                <p className="mt-1 truncate text-xs text-[var(--ar-mist)]">
                  {item.last_message_preview || "—"}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex min-h-[60dvh] flex-1 flex-col rounded-2xl border border-black/10 bg-white">
        {activeId && thread ? (
          <>
            <div className="flex items-center justify-between border-b border-black/5 px-4 py-3">
              <div>
                <p className="font-semibold">{activeSummary?.user_email ?? "Диалог"}</p>
                <p className="text-xs text-[var(--ar-mist)]">Статус: {thread.status}</p>
              </div>
              {thread.status === "open" ? (
                <button
                  type="button"
                  className="rounded-full border border-black/10 px-3 py-1 text-xs"
                  onClick={() => void closeStaffConversation(activeId).then(() => loadThread(activeId))}
                >
                  Закрыть тикет
                </button>
              ) : null}
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
              {thread.messages.map((message) => (
                <div
                  key={message.id}
                  className={cn("flex", message.sender_party === "staff" ? "justify-end" : "justify-start")}
                >
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap",
                      message.sender_party === "staff"
                        ? "bg-[var(--ar-black)] text-white"
                        : "bg-black/[0.06]"
                    )}
                  >
                    {message.body}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2 border-t border-black/5 p-3">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={2}
                className="min-h-[44px] flex-1 resize-none rounded-xl border border-black/10 px-3 py-2 text-sm"
                placeholder="Ответ пользователю…"
              />
              <button
                type="button"
                onClick={() => void onSend()}
                className="rounded-xl bg-[var(--ar-black)] px-4 text-sm text-white"
              >
                Отправить
              </button>
            </div>
          </>
        ) : (
          <p className="p-6 text-sm text-[var(--ar-mist)]">Выберите диалог слева</p>
        )}
      </section>
    </div>
  );
}
