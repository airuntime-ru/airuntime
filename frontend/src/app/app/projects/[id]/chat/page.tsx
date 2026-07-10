"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  ArrowUp,
  CheckCircle2,
  ChevronDown,
  FileEdit,
  FilePlus,
  FileSearch,
  FileX,
  FolderSearch,
  Loader2,
  Paperclip,
  Pin,
  PinOff,
  Plus,
  Search,
  Square,
  Wrench,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";

import { AutoTextarea } from "@/components/ui/auto-textarea";
import {
  createChat,
  createMessage,
  deleteChatFile,
  getProviders,
  listChats,
  listMessages,
  streamChat,
  uploadChatFile,
  type ChatFileType,
  type ChatType,
  type MessageType,
  type ProvidersType,
} from "@/lib/api";
import { cn } from "@/lib/cn";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  attachments?: ChatFileType[];
};

type AgentStatus = {
  phase: string;
  label: string;
  state: "running" | "done" | "error" | "waiting";
};

type ToolActivityItem = {
  id: number;
  label: string;
  state: "running" | "done" | "error";
};

const PINNED_KEY = "airuntime_pinned_chats";
const PROVIDER_KEY = "airuntime_selected_provider";

const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic Claude",
  gemini: "Gemini",
  openrouter: "OpenRouter",
};

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

function readSelectedProvider(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(PROVIDER_KEY) ?? "";
}

function writeSelectedProvider(value: string) {
  if (typeof window === "undefined") return;
  if (value) localStorage.setItem(PROVIDER_KEY, value);
  else localStorage.removeItem(PROVIDER_KEY);
}

function toolIcon(label: string) {
  if (label.startsWith("Читаю")) return <FileSearch size={13} />;
  if (label.startsWith("Пишу")) return <FilePlus size={13} />;
  if (label.startsWith("Правлю")) return <FileEdit size={13} />;
  if (label.startsWith("Удаляю")) return <FileX size={13} />;
  if (label.startsWith("Изучаю")) return <FolderSearch size={13} />;
  return <Wrench size={13} />;
}

function ToolActivityFeed({ items }: { items: ToolActivityItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mb-3 max-h-40 space-y-1 overflow-y-auto rounded-xl border border-black/8 bg-[#fafafa] px-3 py-2">
      {items.map((item) => (
        <div
          key={item.id}
          className={cn(
            "flex items-center gap-2 text-xs",
            item.state === "error"
              ? "text-rose-600"
              : item.state === "done"
                ? "text-[var(--ar-mist)]"
                : "text-[var(--ar-black)]"
          )}
        >
          <span className="shrink-0 opacity-70">{toolIcon(item.label)}</span>
          <span className="truncate">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

function AiTypingIndicator() {
  return (
    <div className="flex items-center gap-2 py-1 text-sm text-[var(--ar-stone)]">
      <span className="inline-flex items-center gap-1" aria-hidden>
        <span className="h-1 w-1 animate-pulse rounded-full bg-[var(--ar-stone)]" />
        <span className="h-1 w-1 animate-pulse rounded-full bg-[var(--ar-stone)] [animation-delay:120ms]" />
        <span className="h-1 w-1 animate-pulse rounded-full bg-[var(--ar-stone)] [animation-delay:220ms]" />
      </span>
    </div>
  );
}

function AgentStatusPanel({ status }: { status: AgentStatus }) {
  const waiting = status.state === "waiting" || status.phase === "questions";
  const done = status.state === "done" && !waiting;
  const error = status.state === "error";
  const steps = ["thinking", "context", "tool", "verify", "module", "version", "deploy", "done"];
  const currentIndex = Math.max(0, steps.indexOf(status.phase));
  const helpHref =
    error && status.label.includes("TELEGRAM_BOT_TOKEN") ? "/help/telegram-token" : null;

  const panel = (
    <div
      className={cn(
        "sticky bottom-3 z-10 mb-5 overflow-hidden rounded-2xl border px-4 py-3 shadow-[0_14px_36px_rgba(70,130,180,0.10)] transition backdrop-blur-xl",
        helpHref && "cursor-pointer hover:-translate-y-0.5 hover:shadow-[0_18px_42px_rgba(244,63,94,0.16)]",
        error
          ? "border-rose-200 bg-rose-50"
          : waiting
            ? "border-amber-200 bg-amber-50"
          : "border-sky-100 bg-[linear-gradient(135deg,rgba(255,255,255,0.94),rgba(235,249,255,0.86))]"
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
              error
                ? "bg-rose-100 text-rose-600"
                : waiting
                  ? "bg-amber-100 text-amber-700"
                  : done
                    ? "bg-emerald-50 text-emerald-600"
                    : "bg-sky-50 text-[var(--ar-sky)]"
            )}
          >
            {done ? <CheckCircle2 size={18} /> : error || waiting ? <Activity size={18} /> : <Loader2 size={18} className="animate-spin" />}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[var(--ar-black)]">{status.label}</p>
            <p className="text-xs text-[var(--ar-stone)]">
              {waiting ? "Ответьте в чат, и агент продолжит сборку" : "Статус разработки обновляется в реальном времени"}
            </p>
          </div>
        </div>
        <span className="hidden rounded-full border border-white/70 bg-white/70 px-2.5 py-1 text-xs font-medium text-[var(--ar-mist)] sm:inline-flex">
          {waiting ? "waiting" : "agent live"}
        </span>
      </div>

      {!error && !waiting ? (
        <div className="mt-3 grid gap-1.5" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
          {steps.map((step, index) => (
            <span
              key={step}
              className={cn(
                "h-1.5 rounded-full transition-colors",
                index <= currentIndex ? "bg-[var(--ar-sky)]" : "bg-black/8",
                status.state === "running" && index === currentIndex && "animate-pulse"
              )}
            />
          ))}
        </div>
      ) : null}
    </div>
  );

  if (helpHref) {
    return (
      <a href={helpHref} className="block no-underline" aria-label="Открыть инструкцию по получению Telegram token">
        {panel}
      </a>
    );
  }

  return panel;
}

function MessageBody({
  message,
  isStreaming,
}: {
  message: ChatMessage;
  isStreaming: boolean;
}) {
  if (message.role === "assistant" && isStreaming && !message.content) {
    return <AiTypingIndicator />;
  }

  if (message.role === "assistant" && isStreaming) {
    return (
      <div className="cursor-chat-assistant whitespace-pre-wrap text-[15px] leading-[1.65] text-[var(--ar-black)]">
        {message.content}
      </div>
    );
  }

  if (message.role === "assistant") {
    return (
      <div className="cursor-chat-assistant prose-chat prose-chat-cursor text-[15px] text-[var(--ar-black)]">
        <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{message.content}</ReactMarkdown>
      </div>
    );
  }

  return <p className="whitespace-pre-wrap text-[15px] leading-[1.55] text-[var(--ar-black)]">{message.content}</p>;
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
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [bootstrapError, setBootstrapError] = useState("");
  const [chatError, setChatError] = useState("");
  const [mobilePanel, setMobilePanel] = useState<"list" | "chat">("list");
  const [toolActivity, setToolActivity] = useState<ToolActivityItem[]>([]);
  const [providers, setProviders] = useState<ProvidersType | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>(() => readSelectedProvider());
  const [providerMenuOpen, setProviderMenuOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const agentStatusRef = useRef<AgentStatus | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const toolActivityIdRef = useRef(0);
  const providerMenuRef = useRef<HTMLDivElement>(null);

  const updateAgentStatus = useCallback((status: AgentStatus | null) => {
    agentStatusRef.current = status;
    setAgentStatus(status);
  }, []);

  useEffect(() => {
    getProviders()
      .then(setProviders)
      .catch(() => setProviders(null));
  }, []);

  useEffect(() => {
    if (!providerMenuOpen) return;
    const onClickOutside = (event: MouseEvent) => {
      if (providerMenuRef.current && !providerMenuRef.current.contains(event.target as Node)) {
        setProviderMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [providerMenuOpen]);

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
      updateAgentStatus(null);
    };
    void loadMessages();
  }, [projectId, chatId, updateAgentStatus]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: loading ? "smooth" : "auto" });
  }, [agentStatus?.label, loading, messages]);

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
    updateAgentStatus(null);
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
    setChatError("");
    try {
      const uploaded: ChatFileType[] = [];
      for (const file of Array.from(files)) {
        uploaded.push(await uploadChatFile(projectId, chatId, file));
      }
      setPendingFiles((prev) => [...prev, ...uploaded]);
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "Не удалось загрузить файл");
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

  const onStop = () => {
    abortControllerRef.current?.abort();
  };

  const onSubmit = async (event?: { preventDefault?: () => void }) => {
    event?.preventDefault?.();
    if ((!input.trim() && pendingFiles.length === 0) || !projectId || !chatId) return;
    const userMessage = input;
    const attachmentIds = pendingFiles.map((file) => file.id);
    setInput("");
    setPendingFiles([]);
    setLoading(true);
    setChatError("");
    setToolActivity([]);
    updateAgentStatus({ phase: "thinking", label: "AIRuntime осмысляет задачу", state: "running" });
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMessage || "Прикреплены файлы", attachments: pendingFiles },
      { role: "assistant", content: "" },
    ]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await createMessage(projectId, chatId, userMessage, attachmentIds);
      const response = await streamChat(projectId, chatId, userMessage, attachmentIds, {
        provider: selectedProvider || undefined,
        signal: controller.signal,
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Stream failed: ${response.status}`);
      }
      if (!response.body) {
        throw new Error("Stream response is empty");
      }
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
          if (payload === "[DONE]") {
            const latestStatus = agentStatusRef.current;
            if (latestStatus && (latestStatus.state !== "running" || latestStatus.phase === "questions")) {
              continue;
            }
            updateAgentStatus({ phase: "done", label: "Готово: проект передан на запуск", state: "done" });
            continue;
          }
          const parsed = JSON.parse(payload) as { chunk?: string; status?: AgentStatus };
          if (parsed.status) {
            updateAgentStatus(parsed.status);
            if (parsed.status.phase === "tool") {
              toolActivityIdRef.current += 1;
              const item: ToolActivityItem = {
                id: toolActivityIdRef.current,
                label: parsed.status.label,
                state: parsed.status.state === "error" ? "error" : parsed.status.state === "done" ? "done" : "running",
              };
              setToolActivity((prev) => [...prev.slice(-49), item]);
            }
          }
          if (parsed.chunk) {
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
      }
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === "AbortError";
      if (aborted) {
        updateAgentStatus({ phase: "done", label: "Остановлено пользователем", state: "done" });
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant" && !last.content) {
            last.content = "Остановлено.";
          }
          return copy;
        });
      } else {
        setChatError(err instanceof Error ? err.message : "Не удалось получить ответ агента");
        updateAgentStatus({ phase: "error", label: "Не удалось получить ответ агента", state: "error" });
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.role === "assistant") {
            last.content = "Не удалось получить ответ. Проверьте настройки провайдера и токен авторизации.";
          }
          return copy;
        });
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
    }
  };

  const canSend = Boolean(chatId) && (input.trim().length > 0 || pendingFiles.length > 0);
  const currentTitle = filteredChats.find((chat) => chat.id === chatId)?.title ?? "Диалог";

  return (
    <div className="accent-ring grid min-h-[calc(100dvh-14rem)] gap-0 overflow-hidden rounded-[var(--ar-radius-lg)] border border-black/[0.06] bg-white lg:grid-cols-[240px_1fr]">
      <aside
        className={cn(
          "flex flex-col border-black/[0.06] bg-[#fafbfc] lg:border-r",
          mobilePanel === "chat" ? "hidden lg:flex" : "flex"
        )}
      >
        <div className="flex items-center justify-between border-b border-black/8 px-3 py-3">
          <p className="text-sm font-medium text-[var(--ar-black)]">Чаты</p>
          <button
            type="button"
            onClick={onNewChat}
            className="rounded-lg p-1.5 text-[var(--ar-stone)] hover:bg-black/5 hover:text-[var(--ar-black)]"
            aria-label="Новый чат"
          >
            <Plus size={16} />
          </button>
        </div>

        <div className="relative border-b border-black/8 px-3 py-2">
          <Search size={14} className="absolute left-6 top-1/2 -translate-y-1/2 text-[var(--ar-stone)]" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск"
            className="w-full rounded-lg border-0 bg-white py-2 pl-8 pr-3 text-sm outline-none ring-1 ring-black/10 placeholder:text-[var(--ar-stone)] focus:ring-black/20"
          />
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {filteredChats.map((chat) => (
            <div
              key={chat.id}
              className={cn(
                "mb-0.5 flex items-center gap-0.5 rounded-[var(--ar-radius-sm)] px-2 py-1.5",
                chatId === chat.id
                  ? "bg-[var(--ar-accent-gradient-soft)] shadow-[inset_0_0_0_1px_rgba(35,136,255,0.16)]"
                  : "hover:bg-black/[0.03]"
              )}
            >
              <button
                type="button"
                className={cn(
                  "flex-1 truncate text-left text-sm",
                  chatId === chat.id ? "font-medium text-[var(--ar-black)]" : "text-[var(--ar-mist)]"
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
                className="rounded p-1 text-[var(--ar-stone)] hover:text-[var(--ar-black)]"
                onClick={() => togglePin(chat.id)}
                aria-label={pinned.includes(chat.id) ? "Открепить" : "Закрепить"}
              >
                {pinned.includes(chat.id) ? <Pin size={12} /> : <PinOff size={12} />}
              </button>
            </div>
          ))}
        </div>
      </aside>

      <section className={cn("flex min-h-0 min-w-0 flex-col", mobilePanel === "list" ? "hidden lg:flex" : "flex")}>
        <div className="flex items-center gap-2 border-b border-black/8 px-4 py-2.5 lg:hidden">
          <button
            type="button"
            onClick={() => setMobilePanel("list")}
            className="rounded-lg p-1.5 hover:bg-black/5"
            aria-label="К списку"
          >
            <ArrowLeft size={16} />
          </button>
          <p className="truncate text-sm font-medium">{currentTitle}</p>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {messages.length === 0 ? (
              <div className="flex min-h-[40vh] flex-col items-center justify-center text-center">
                <p className="text-lg font-medium text-[var(--ar-black)]">Чем помочь?</p>
                <p className="mt-2 max-w-sm text-sm text-[var(--ar-stone)]">
                  Опишите сайт или бота — AIRuntime соберёт и задеплоит проект.
                </p>
              </div>
            ) : (
              <div className="space-y-8">
                {messages.map((message, index) => {
                  const isStreaming = loading && index === messages.length - 1 && message.role === "assistant";

                  if (message.role === "user") {
                    return (
                      <div key={`${message.role}-${index}`} className="flex justify-end">
                        <div className="max-w-[min(100%,42rem)] rounded-2xl bg-[#f4f4f5] px-4 py-2.5">
                          {message.attachments?.length ? (
                            <div className="mb-2 flex flex-wrap gap-1.5">
                              {message.attachments.map((file) => (
                                <a
                                  key={file.id}
                                  href={file.download_url ?? "#"}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-md bg-white/80 px-2 py-0.5 text-xs text-[var(--ar-mist)] hover:underline"
                                >
                                  {file.original_filename}
                                </a>
                              ))}
                            </div>
                          ) : null}
                          <MessageBody message={message} isStreaming={false} />
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div key={`${message.role}-${index}`} className="w-full">
                      <MessageBody message={message} isStreaming={isStreaming} />
                    </div>
                  );
                })}
              </div>
            )}
            {loading && toolActivity.length > 0 ? <ToolActivityFeed items={toolActivity} /> : null}
            {agentStatus ? <AgentStatusPanel status={agentStatus} /> : null}
            <div ref={bottomRef} className="h-4" />
          </div>
        </div>

        <div className="border-t border-black/8 bg-white/90 px-4 py-3 backdrop-blur-sm sm:px-6">
          <div className="mx-auto w-full max-w-3xl">
            {pendingFiles.length > 0 ? (
              <div className="mb-2 flex items-center justify-between rounded-t-xl border border-b-0 border-black/10 bg-[#f4f4f5] px-3 py-2 text-xs text-[var(--ar-mist)]">
                <span>
                  {pendingFiles.length} {pendingFiles.length === 1 ? "файл" : "файла"}
                </span>
                <button
                  type="button"
                  className="text-[var(--ar-stone)] hover:text-[var(--ar-black)]"
                  onClick={() => void Promise.all(pendingFiles.map((f) => removePendingFile(f)))}
                >
                  Убрать все
                </button>
              </div>
            ) : null}

            {bootstrapError ? (
              <p className="mb-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {bootstrapError}
              </p>
            ) : null}
            {chatError ? (
              <p className="mb-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {chatError}
              </p>
            ) : null}

            <form
              onSubmit={onSubmit}
              className={cn(
                "overflow-hidden rounded-2xl border border-black/12 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] transition-colors focus-within:border-[var(--ar-sky)]/35 focus-within:shadow-[0_4px_18px_rgba(35,136,255,0.1)]",
                pendingFiles.length > 0 && "rounded-t-none border-t-0"
              )}
            >
              <input ref={fileInputRef} type="file" className="hidden" multiple onChange={onFilesSelected} />

              {pendingFiles.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 border-b border-black/8 px-3 py-2">
                  {pendingFiles.map((file) => (
                    <span
                      key={file.id}
                      className="inline-flex items-center gap-1 rounded-md bg-[#f4f4f5] px-2 py-1 text-xs text-[var(--ar-mist)]"
                    >
                      {file.original_filename}
                      <button type="button" onClick={() => void removePendingFile(file)} aria-label="Убрать">
                        <X size={11} />
                      </button>
                    </span>
                  ))}
                </div>
              ) : null}

              <AutoTextarea
                className="min-h-[52px] resize-none border-0 bg-transparent px-4 py-3.5 text-[15px] shadow-none ring-0 placeholder:text-[var(--ar-stone)] focus:border-0 focus:ring-0"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={bootstrapping ? "Загрузка..." : "Опишите задачу, @ для контекста"}
                disabled={bootstrapping || !chatId}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    if (canSend && !loading) void onSubmit(event);
                  }
                }}
              />

              <div className="flex items-center justify-between px-3 pb-2.5 pt-0">
                <div className="relative flex items-center gap-1.5" ref={providerMenuRef}>
                  <button
                    type="button"
                    onClick={() => setProviderMenuOpen((prev) => !prev)}
                    className="inline-flex items-center gap-1 rounded-full border border-black/10 bg-[#fafafa] px-2.5 py-1 text-xs font-medium text-[var(--ar-mist)] hover:bg-black/5"
                  >
                    {PROVIDER_LABELS[selectedProvider] ?? PROVIDER_LABELS[providers?.active ?? ""] ?? "AIRuntime"}
                    <ChevronDown size={12} className="opacity-50" />
                  </button>
                  {providerMenuOpen ? (
                    <div className="absolute bottom-full left-0 mb-2 w-56 overflow-hidden rounded-xl border border-black/10 bg-white py-1 shadow-lg">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedProvider("");
                          writeSelectedProvider("");
                          setProviderMenuOpen(false);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-black/5",
                          !selectedProvider && "font-medium text-[var(--ar-black)]"
                        )}
                      >
                        По умолчанию платформы
                      </button>
                      {(providers?.supported ?? []).map((name) => {
                        const configured = providers?.configured?.[name];
                        return (
                          <button
                            key={name}
                            type="button"
                            disabled={!configured}
                            onClick={() => {
                              setSelectedProvider(name);
                              writeSelectedProvider(name);
                              setProviderMenuOpen(false);
                            }}
                            className={cn(
                              "flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-40",
                              selectedProvider === name && "font-medium text-[var(--ar-black)]"
                            )}
                          >
                            <span>{PROVIDER_LABELS[name] ?? name}</span>
                            {!configured ? (
                              <span className="text-[10px] text-[var(--ar-stone)]">нет ключа</span>
                            ) : null}
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={onPickFiles}
                    disabled={uploading || !chatId}
                    className="rounded-lg p-2 text-[var(--ar-stone)] hover:bg-black/5 hover:text-[var(--ar-black)] disabled:opacity-40"
                    aria-label="Прикрепить"
                  >
                    <Paperclip size={18} />
                  </button>
                  {loading ? (
                    <button
                      type="button"
                      onClick={onStop}
                      className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--ar-black)] text-white shadow-[0_6px_18px_rgba(7,20,38,0.28)] hover:bg-black/85"
                      aria-label="Остановить"
                    >
                      <Square size={13} strokeWidth={2.5} fill="currentColor" />
                    </button>
                  ) : (
                    <button
                      type="submit"
                      disabled={bootstrapping || loading || uploading || !canSend}
                      className={cn(
                        "flex h-8 w-8 items-center justify-center rounded-full transition-all",
                        canSend && !loading && !bootstrapping
                          ? "bg-[var(--ar-accent-gradient)] text-white shadow-[0_6px_18px_rgba(35,136,255,0.32)] hover:brightness-[1.06]"
                          : "bg-black/10 text-[var(--ar-stone)]"
                      )}
                      aria-label="Отправить"
                    >
                      <ArrowUp size={16} strokeWidth={2.5} />
                    </button>
                  )}
                </div>
              </div>
            </form>
          </div>
        </div>
      </section>
    </div>
  );
}
