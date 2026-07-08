"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Paperclip, Pin, PinOff, Plus, Search, Send, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";

import { AutoTextarea } from "@/components/ui/auto-textarea";
import { Button } from "@/components/ui/button";
import {
  createChat,
  createMessage,
  deleteChatFile,
  listChats,
  listMessages,
  streamChat,
  uploadChatFile,
  type ChatFileType,
  type ChatType,
  type MessageType,
} from "@/lib/api";
import { cn } from "@/lib/cn";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  attachments?: ChatFileType[];
};

const PINNED_KEY = "airuntime_pinned_chats";

function readPinned(): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(localStorage.getItem(PINNED_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}

function writePinned(ids: string[]) {
  localStorage.setItem(PINNED_KEY, JSON.stringify(ids));
}

function AiTypingIndicator() {
  return (
    <div className="flex items-center gap-2 py-0.5 text-xs text-[var(--ar-mist)]">
      <span className="inline-flex items-center gap-1" aria-hidden>
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--ar-black)]/45" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--ar-black)]/45 [animation-delay:120ms]" />
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--ar-black)]/45 [animation-delay:220ms]" />
      </span>
      <span>AIRuntime отвечает</span>
    </div>
  );
}

export default function ProjectChatPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [chats, setChats] = useState<ChatType[]>([]);
  const [chatId, setChatId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [search, setSearch] = useState("");
  const [pinned, setPinned] = useState<string[]>(() => readPinned());
  const [pendingFiles, setPendingFiles] = useState<ChatFileType[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [bootstrapError, setBootstrapError] = useState("");
  const [mobilePanel, setMobilePanel] = useState<"list" | "chat">("list");
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const bootstrap = async () => {
      if (!projectId) return;
      setBootstrapping(true);
      setBootstrapError("");
      try {
        let rows = await listChats(projectId);
        if (rows.length === 0) {
          const chat = await createChat(projectId);
          rows = [chat];
        }
        setChats(rows);
        setChatId(rows[0].id);
        setMobilePanel("chat");
      } catch (err) {
        setBootstrapError(err instanceof Error ? err.message : "Не удалось открыть чат");
      } finally {
        setBootstrapping(false);
      }
    };
    void bootstrap();
  }, [projectId]);

  useEffect(() => {
    const loadMessages = async () => {
      if (!projectId || !chatId) return;
      const rows = await listMessages(projectId, chatId);
      setMessages(
        rows.map((row: MessageType) => ({
          role: row.role === "assistant" ? "assistant" : "user",
          content: row.content_markdown,
          attachments: row.attachments,
        }))
      );
      setPendingFiles([]);
    };
    void loadMessages();
  }, [projectId, chatId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "auto" });
  }, [messages.length]);

  const filteredChats = useMemo(() => {
    const query = search.trim().toLowerCase();
    const sorted = [...chats].sort((a, b) => {
      const aPinned = pinned.includes(a.id);
      const bPinned = pinned.includes(b.id);
      if (aPinned !== bPinned) return aPinned ? -1 : 1;
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
    });
    if (!query) return sorted;
    return sorted.filter((chat) => chat.title.toLowerCase().includes(query));
  }, [chats, pinned, search]);

  const onNewChat = async () => {
    if (!projectId) return;
    const chat = await createChat(projectId);
    setChats((prev) => [chat, ...prev]);
    setChatId(chat.id);
    setMessages([]);
    setPendingFiles([]);
    setMobilePanel("chat");
  };

  const togglePin = (id: string) => {
    setPinned((prev) => {
      const next = prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id];
      writePinned(next);
      return next;
    });
  };

  const onPickFiles = () => {
    fileInputRef.current?.click();
  };

  const onFilesSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files?.length || !projectId || !chatId) return;
    setUploading(true);
    try {
      const uploaded: ChatFileType[] = [];
      for (const file of Array.from(files)) {
        uploaded.push(await uploadChatFile(projectId, chatId, file));
      }
      setPendingFiles((prev) => [...prev, ...uploaded]);
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const removePendingFile = async (file: ChatFileType) => {
    if (!projectId || !chatId) return;
    await deleteChatFile(projectId, chatId, file.id);
    setPendingFiles((prev) => prev.filter((item) => item.id !== file.id));
  };

  const onSubmit = async (event?: { preventDefault?: () => void }) => {
    event?.preventDefault?.();
    if ((!input.trim() && pendingFiles.length === 0) || !projectId || !chatId) return;
    const userMessage = input;
    const attachmentIds = pendingFiles.map((file) => file.id);
    setInput("");
    setPendingFiles([]);
    setLoading(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage || "Прикреплены файлы", attachments: pendingFiles },
      { role: "assistant", content: "" },
    ]);

    try {
      await createMessage(projectId, chatId, userMessage, attachmentIds);
      const response = await streamChat(projectId, chatId, userMessage, attachmentIds);
      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let partial = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        partial += decoder.decode(value, { stream: true });
        const lines = partial.split("\n\n");
        partial = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.replace("data: ", "");
          if (payload === "[DONE]") continue;
          const parsed = JSON.parse(payload) as { chunk: string };
          setMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            if (last?.role === "assistant") {
              last.content += parsed.chunk;
            }
            return copy;
          });
        }
      }
    } catch {
      setMessages((prev) => {
        const copy = [...prev];
        const last = copy[copy.length - 1];
        if (last?.role === "assistant") {
          last.content = "Не удалось получить ответ. Проверьте настройки провайдера и токен авторизации.";
        }
        return copy;
      });
    } finally {
      setLoading(false);
    }
  };

  const canSend = Boolean(chatId) && (input.trim().length > 0 || pendingFiles.length > 0);
  const currentTitle = filteredChats.find((chat) => chat.id === chatId)?.title ?? "Диалог проекта";

  return (
    <div className="grid min-h-[calc(100dvh-16rem)] gap-3 lg:grid-cols-[19rem_1fr]">
      <aside
        className={cn(
          "flex w-full flex-col rounded-2xl border border-[#d7e3f7] bg-[linear-gradient(160deg,#ffffff_0%,#f6f9ff_100%)] p-3 shadow-[0_14px_36px_rgba(70,112,180,0.12)] lg:flex",
          mobilePanel === "chat" ? "hidden lg:flex" : "flex"
        )}
      >
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ar-stone)]">Чаты</p>
            <p className="mt-1 text-sm text-[var(--ar-stone)]">{filteredChats.length} в проекте</p>
          </div>
          <Button variant="outline" size="sm" onClick={onNewChat} aria-label="Новый чат" className="h-9 w-9 p-0">
            <Plus size={16} />
          </Button>
        </div>

        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ar-stone)]" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Найти диалог"
            className="w-full rounded-xl border border-[#d6e0f2] bg-white py-2 pl-8 pr-3 text-sm text-[var(--ar-black)] placeholder:text-[var(--ar-stone)] outline-none focus:border-[#b8cbee] focus:ring-2 focus:ring-[#d7e4ff]"
          />
        </div>

        <div className="max-h-[42dvh] flex-1 space-y-1 overflow-y-auto pr-1 lg:max-h-none">
          {filteredChats.map((chat) => (
            <div
              key={chat.id}
              className={cn(
                "flex items-center gap-1 rounded-xl border px-2 py-1.5 transition-colors",
                chatId === chat.id
                  ? "border-[#cddcf6] bg-[#edf3ff]"
                  : "border-transparent hover:border-[#dde7f8] hover:bg-[#f5f8ff]"
              )}
            >
              <button
                type="button"
                className={cn(
                  "flex-1 truncate text-left text-sm",
                  chatId === chat.id ? "font-semibold text-[var(--ar-black)]" : "text-[var(--ar-mist)]"
                )}
                onClick={() => {
                  setChatId(chat.id);
                  setMobilePanel("chat");
                }}
              >
                {chat.title}
              </button>
              <button
                type="button"
                className="text-[var(--ar-stone)] hover:text-[var(--ar-black)]"
                onClick={() => togglePin(chat.id)}
                aria-label={pinned.includes(chat.id) ? "Открепить чат" : "Закрепить чат"}
              >
                {pinned.includes(chat.id) ? <Pin size={14} /> : <PinOff size={14} />}
              </button>
            </div>
          ))}
        </div>
      </aside>

      <section className={cn("flex min-h-0 min-w-0 flex-col gap-3", mobilePanel === "list" ? "hidden lg:flex" : "flex")}>
        <div className="flex items-center gap-2 lg:hidden">
          <Button variant="ghost" size="sm" onClick={() => setMobilePanel("list")} aria-label="К списку чатов">
            <ArrowLeft size={16} />
          </Button>
          <p className="truncate text-sm font-semibold text-[var(--ar-black)]">{currentTitle}</p>
        </div>

        <div className="relative flex min-h-[46dvh] flex-1 flex-col overflow-hidden rounded-2xl border border-[#d7e3f7] bg-[linear-gradient(180deg,#fcfdff_0%,#f7faff_100%)] shadow-[0_16px_44px_rgba(70,112,180,0.14)]">
          <div className="flex items-center justify-between gap-3 border-b border-[#e2ebfa] px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-[var(--ar-black)]">{currentTitle}</p>
              <p className="text-xs text-[var(--ar-stone)]">Чат проекта</p>
            </div>
          </div>

          <div className="relative flex-1 space-y-2.5 overflow-y-auto bg-transparent px-3 py-3 sm:px-5">
            {messages.length === 0 ? (
              <div className="mx-auto flex min-h-[34vh] max-w-2xl flex-col items-center justify-center text-center">
                <p className="text-2xl font-semibold text-[var(--ar-black)]">Начните разговор</p>
                <p className="mt-3 text-sm leading-7 text-[var(--ar-mist)]">
                  Опишите, какой сайт или бот должен появиться. Можно говорить живым языком: стиль, аудитория, функции, ограничения, файлы.
                </p>
              </div>
            ) : null}

            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={cn(
                  "w-fit rounded-xl border px-3 py-2",
                  message.role === "user"
                    ? "ml-auto max-w-[78%] border-[#cadaf6] bg-[linear-gradient(165deg,#edf3ff_0%,#e6eeff_100%)] text-[var(--ar-black)] shadow-[0_6px_18px_rgba(80,120,190,0.12)]"
                    : "max-w-[82%] border-[#dde7f8] bg-white/95 text-[var(--ar-black)] shadow-[0_6px_16px_rgba(80,120,190,0.08)]"
                )}
              >
                <p className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--ar-stone)]">
                  {message.role === "user" ? "Вы" : "AIRuntime"}
                </p>
                {message.attachments?.length ? (
                  <div className="mb-3 flex flex-wrap gap-2">
                    {message.attachments.map((file) => (
                      <a
                        key={file.id}
                        href={file.download_url ?? "#"}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full border border-black/15 bg-white px-3 py-1 text-xs text-[var(--ar-black)] hover:underline"
                      >
                        {file.original_filename}
                      </a>
                    ))}
                  </div>
                ) : null}
                {message.role === "assistant" && loading && index === messages.length - 1 && !message.content ? (
                  <AiTypingIndicator />
                ) : (
                  <div className="prose-chat prose-chat-compact text-sm leading-relaxed text-[var(--ar-black)]">
                    <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{message.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {pendingFiles.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {pendingFiles.map((file) => (
              <span
                key={file.id}
                className="inline-flex items-center gap-2 rounded-full border border-black/15 bg-white px-3 py-1 text-xs text-[var(--ar-mist)]"
              >
                {file.original_filename}
                <button type="button" onClick={() => void removePendingFile(file)} aria-label="Убрать файл">
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        ) : null}

        {bootstrapError ? (
          <p className="rounded-[var(--ar-radius-sm)] border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {bootstrapError}
          </p>
        ) : null}

        <form
          onSubmit={onSubmit}
          className="relative z-10 flex items-end gap-2 rounded-2xl border border-[#cfdcf4] bg-[linear-gradient(180deg,#ffffff_0%,#f8fbff_100%)] p-2 shadow-[0_12px_28px_rgba(80,120,190,0.12)] focus-within:border-[#b8cbee] focus-within:ring-2 focus-within:ring-[#d7e4ff]"
        >
          <input ref={fileInputRef} type="file" className="hidden" multiple onChange={onFilesSelected} />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mb-0.5 h-9 w-9 shrink-0 p-0"
            onClick={onPickFiles}
            disabled={uploading || !chatId}
            aria-label="Прикрепить файлы"
          >
            <Paperclip size={18} />
          </Button>
          <AutoTextarea
            className="min-h-[38px] flex-1 border-0 bg-transparent px-1 py-1.5 shadow-none focus:border-0 focus:bg-transparent focus:ring-0"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={bootstrapping ? "Подготавливаем чат..." : "Опишите задачу, которую нужно воплотить..."}
            disabled={bootstrapping || !chatId}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (canSend && !loading) void onSubmit(event);
              }
            }}
          />
          <Button
            type="submit"
            variant="default"
            size="sm"
            className="mb-0.5 h-9 w-9 shrink-0 rounded-xl p-0"
            disabled={bootstrapping || loading || uploading || !canSend}
            aria-label="Отправить"
          >
            <Send size={16} />
          </Button>
        </form>
      </section>
    </div>
  );
}
