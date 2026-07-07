"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, Paperclip, Pin, PinOff, Plus, Search, Send, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";

import { AutoTextarea } from "@/components/ui/auto-textarea";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
  const [mobilePanel, setMobilePanel] = useState<"list" | "chat">("list");
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const bootstrap = async () => {
      if (!projectId) return;
      const rows = await listChats(projectId);
      setChats(rows);
      if (rows.length > 0) {
        setChatId(rows[0].id);
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
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
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

  const currentTitle = filteredChats.find((chat) => chat.id === chatId)?.title ?? "Чат проекта";

  return (
    <div className="flex min-h-[calc(100dvh-15rem)] flex-col gap-3 lg:min-h-[calc(100vh-15rem)] lg:flex-row lg:gap-4">
      <Card
        hover={false}
        className={cn("flex w-full flex-col p-3 lg:w-72 lg:shrink-0", mobilePanel === "chat" ? "hidden lg:flex" : "flex")}
      >
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[var(--ar-black)]">Диалоги</h2>
            <p className="text-xs text-[var(--ar-stone)]">{filteredChats.length} в проекте</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onNewChat} aria-label="Новый чат">
            <Plus size={16} />
          </Button>
        </div>
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ar-stone)]" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск чатов"
            className="w-full rounded-[var(--ar-radius-sm)] border border-[var(--ar-border)] bg-white/80 py-2 pl-8 pr-3 text-sm text-[var(--ar-black)] shadow-sm shadow-sky-950/5 placeholder:text-[var(--ar-stone)] focus:outline-none focus:ring-2 focus:ring-[var(--ar-sky)]/15"
          />
        </div>
        <div className="max-h-[42dvh] flex-1 space-y-1 overflow-y-auto lg:max-h-none">
          {filteredChats.map((chat) => (
            <div
              key={chat.id}
              className={cn(
                "flex items-center gap-1 rounded-[var(--ar-radius-sm)] px-2 py-1.5",
                chatId === chat.id ? "bg-white shadow-sm shadow-sky-950/5" : "hover:bg-white/70"
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
                className="text-[var(--ar-stone)] hover:text-[var(--ar-sky)]"
                onClick={() => togglePin(chat.id)}
                aria-label={pinned.includes(chat.id) ? "Открепить чат" : "Закрепить чат"}
              >
                {pinned.includes(chat.id) ? <Pin size={14} /> : <PinOff size={14} />}
              </button>
            </div>
          ))}
        </div>
      </Card>

      <div className={cn("flex min-h-0 min-w-0 flex-1 flex-col gap-3", mobilePanel === "list" ? "hidden lg:flex" : "flex")}>
        <div className="flex items-center gap-2 lg:hidden">
          <Button variant="ghost" size="sm" onClick={() => setMobilePanel("list")} aria-label="К списку чатов">
            <ArrowLeft size={16} />
          </Button>
          <p className="truncate text-sm font-medium text-[var(--ar-black)]">{currentTitle}</p>
        </div>
        <Card hover={false} className="min-h-[42dvh] flex-1 space-y-3 overflow-y-auto bg-white/70 lg:min-h-0">
          {messages.length === 0 ? (
            <div className="rounded-[var(--ar-radius-sm)] border border-dashed border-[var(--ar-border-strong)] bg-white/70 p-5 text-center">
              <p className="font-semibold text-[var(--ar-black)]">Начните диалог</p>
              <p className="mt-2 text-sm leading-relaxed text-[var(--ar-mist)]">
                Опишите, что нужно собрать, что изменить или какие файлы учитывать.
              </p>
            </div>
          ) : null}
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={cn(
                "rounded-[var(--ar-radius-sm)] border p-3",
                message.role === "user"
                  ? "ml-auto max-w-[92%] border-sky-100 bg-sky-50 text-[var(--ar-black)]"
                  : "max-w-[94%] border-[var(--ar-border)] bg-white text-[var(--ar-black)] shadow-sm shadow-sky-950/5"
              )}
            >
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--ar-stone)]">
                {message.role === "user" ? "Вы" : "AIRuntime"}
              </p>
              {message.attachments?.length ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {message.attachments.map((file) => (
                    <a
                      key={file.id}
                      href={file.download_url ?? "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-full border border-[var(--ar-border)] bg-white px-3 py-1 text-xs text-[var(--ar-sky)] hover:underline"
                    >
                      {file.original_filename}
                    </a>
                  ))}
                </div>
              ) : null}
              <div className="prose-chat text-sm leading-relaxed text-[var(--ar-black)]">
                <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{message.content}</ReactMarkdown>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </Card>

        {pendingFiles.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {pendingFiles.map((file) => (
              <span
                key={file.id}
                className="inline-flex items-center gap-2 rounded-full border border-[var(--ar-border)] bg-white px-3 py-1 text-xs text-[var(--ar-mist)] shadow-sm shadow-sky-950/5"
              >
                {file.original_filename}
                <button type="button" onClick={() => void removePendingFile(file)} aria-label="Убрать файл">
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        ) : null}

        <form
          onSubmit={onSubmit}
          className="flex items-end gap-2 rounded-[var(--ar-radius-md)] border border-[var(--ar-border)] bg-white/90 p-2 shadow-sm shadow-sky-950/5 focus-within:border-[var(--ar-border-strong)] focus-within:ring-2 focus-within:ring-[var(--ar-sky)]/15"
        >
          <input ref={fileInputRef} type="file" className="hidden" multiple onChange={onFilesSelected} />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="mb-0.5 h-9 w-9 shrink-0 p-0"
            onClick={onPickFiles}
            disabled={uploading || !chatId}
            aria-label="Прикрепить файлы"
          >
            <Paperclip size={18} />
          </Button>
          <AutoTextarea
            className="min-h-[40px] flex-1 border-0 bg-transparent px-1 py-2 shadow-none focus:border-0 focus:bg-transparent focus:ring-0"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Опишите задачу..."
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void onSubmit(event);
              }
            }}
          />
          <Button
            type="submit"
            variant="accent"
            size="sm"
            className="mb-0.5 h-9 w-9 shrink-0 rounded-full p-0"
            disabled={loading || uploading || !chatId}
            aria-label="Отправить"
          >
            <Send size={16} />
          </Button>
        </form>
      </div>
    </div>
  );
}
