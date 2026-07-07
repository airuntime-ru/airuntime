"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Paperclip, Pin, PinOff, Plus, Search, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AutoTextarea } from "@/components/ui/auto-textarea";
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
      { role: "user", content: userMessage || "📎 Shared attachments", attachments: pendingFiles },
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
          last.content = "Streaming failed. Check provider configuration and auth token.";
        }
        return copy;
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-14rem)] max-w-6xl gap-4">
      <Card hover={false} className="flex w-72 shrink-0 flex-col p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-[var(--ar-cloud)]">Chats</h2>
          <Button variant="ghost" size="sm" onClick={onNewChat} aria-label="New chat">
            <Plus size={16} />
          </Button>
        </div>
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--ar-stone)]" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search chats"
            className="w-full rounded-[var(--ar-radius-md)] border border-white/10 bg-white/5 py-2 pl-8 pr-3 text-sm text-[var(--ar-cloud)] placeholder:text-[var(--ar-stone)] focus:outline-none focus:ring-2 focus:ring-[var(--ar-sky)]/30"
          />
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto">
          {filteredChats.map((chat) => (
            <div
              key={chat.id}
              className={cn(
                "flex items-center gap-1 rounded-[var(--ar-radius-md)] px-2 py-1.5",
                chatId === chat.id ? "bg-white/12" : "hover:bg-white/8"
              )}
            >
              <button
                type="button"
                className="flex-1 truncate text-left text-sm text-[var(--ar-mist)]"
                onClick={() => setChatId(chat.id)}
              >
                {chat.title}
              </button>
              <button
                type="button"
                className="text-[var(--ar-stone)] hover:text-[var(--ar-sky)]"
                onClick={() => togglePin(chat.id)}
                aria-label={pinned.includes(chat.id) ? "Unpin chat" : "Pin chat"}
              >
                {pinned.includes(chat.id) ? <Pin size={14} /> : <PinOff size={14} />}
              </button>
            </div>
          ))}
        </div>
      </Card>

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <Card hover={false} className="flex-1 space-y-3 overflow-y-auto">
          {messages.length === 0 ? (
            <p className="text-sm text-[var(--ar-stone)]">Start a conversation to build or deploy your project.</p>
          ) : null}
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={cn(
                "rounded-[var(--ar-radius-lg)] border p-3",
                message.role === "user"
                  ? "border-white/10 bg-white/5"
                  : "border-[var(--ar-sky)]/20 bg-[var(--ar-sky)]/5"
              )}
            >
              <p className="mb-1 text-xs uppercase tracking-wide text-[var(--ar-stone)]">{message.role}</p>
              {message.attachments?.length ? (
                <div className="mb-2 flex flex-wrap gap-2">
                  {message.attachments.map((file) => (
                    <a
                      key={file.id}
                      href={file.download_url ?? "#"}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-full border border-[var(--ar-border)] bg-[var(--ar-surface-1)] px-3 py-1 text-xs text-[var(--ar-sky)] hover:underline"
                    >
                      {file.original_filename}
                    </a>
                  ))}
                </div>
              ) : null}
              <div className="prose-chat text-[var(--ar-cloud)]">
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
                className="inline-flex items-center gap-2 rounded-full border border-[var(--ar-border)] bg-[var(--ar-surface-1)] px-3 py-1 text-xs text-[var(--ar-mist)]"
              >
                {file.original_filename}
                <button type="button" onClick={() => void removePendingFile(file)} aria-label="Remove file">
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        ) : null}

        <form onSubmit={onSubmit} className="relative">
          <input ref={fileInputRef} type="file" className="hidden" multiple onChange={onFilesSelected} />
          <AutoTextarea
            className="pr-24"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask AIRuntime to build, test, or deploy..."
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void onSubmit(event);
              }
            }}
          />
          <div className="absolute bottom-3 right-3 flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onPickFiles}
              disabled={uploading || !chatId}
              aria-label="Attach files"
            >
              <Paperclip size={16} />
            </Button>
            <Button type="submit" variant="accent" size="sm" disabled={loading || uploading || !chatId}>
              {loading ? "..." : "Send"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
