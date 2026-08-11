"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  Bot,
  Globe,
  KeyRound,
  Layers,
  Loader2,
  MessageSquare,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ProjectStatusChip } from "@/components/app/project-status-chip";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Tabs } from "@/components/ui/tabs";
import { PageLoader } from "@/components/ui/loader";
import { getProject, type ProjectType } from "@/lib/api";
import {
  getActiveProjectChatStream,
  subscribeProjectStreams,
  type ChatStreamSnapshot,
} from "@/lib/chat-stream-runtime";
import { cn } from "@/lib/cn";
import { projectTypeLabel } from "@/lib/project-status";
import { usePageVisible } from "@/lib/use-page-visible";

const TYPE_ICONS: Record<string, LucideIcon> = {
  website: Globe,
  telegram_bot: Bot,
  mixed: Layers,
};

const STATUS_GUIDANCE: Record<
  string,
  (project: ProjectType) => {
    title: string;
    body: string;
    showSecrets?: boolean;
    showChat?: boolean;
    showHelp?: boolean;
  }
> = {
  needs_configuration: (project) => ({
    title: "Нужна настройка",
    body:
      project.type === "telegram_bot" || project.type === "mixed"
        ? "Код бота уже есть в проекте, но запустить его пока нельзя: не хватает токена. Откройте секреты проекта, вставьте TELEGRAM_BOT_TOKEN (его выдаёт @BotFather в Telegram после команды /newbot) и запуск продолжится автоматически."
        : "Проекту не хватает данных для запуска — откройте настройки проекта и заполните то, что запрашивается в разделе «Ключи и токены».",
    showSecrets: true,
    showChat: true,
    showHelp: project.type === "telegram_bot" || project.type === "mixed",
  }),
  blocked: (project) => ({
    title: "Заблокирован модерацией",
    body:
      "Проект остановлен автоматической проверкой безопасности" +
      (project.blocked_reason ? `: ${project.blocked_reason}.` : ".") +
      " Если считаете это ошибкой, напишите в поддержку — решение может принять только администратор.",
  }),
};

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const pathname = usePathname();
  const projectId = params.id;
  const pageVisible = usePageVisible();
  const [project, setProject] = useState<ProjectType | null>(null);
  const [statusModalOpen, setStatusModalOpen] = useState(false);
  const [chatStream, setChatStream] = useState<ChatStreamSnapshot | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void (async () => {
      if (!projectId) return;
      try {
        const row = await getProject(projectId);
        if (active) setProject(row);
      } catch {
        if (active) setProject(null);
      }
    })();
    return () => {
      active = false;
      controller.abort();
    };
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !pageVisible) return undefined;
    if (project?.status !== "needs_configuration" && project?.status !== "deploying") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void getProject(projectId).then(setProject).catch(() => {});
    }, 4000);
    return () => window.clearInterval(timer);
  }, [projectId, project?.status, pageVisible]);

  useEffect(() => {
    if (!projectId) return undefined;
    // Banner is hidden on the chat tab - no need to re-render the whole layout on every chunk.
    if (pathname?.includes("/chat")) {
      setChatStream(null);
      return undefined;
    }
    let lastKey = "";
    const refresh = () => {
      const snap = getActiveProjectChatStream(projectId);
      const key = snap
        ? `${snap.loading}:${snap.agentStatus?.phase}:${snap.agentStatus?.label}:${snap.agentStatus?.state}`
        : "";
      if (key === lastKey) return;
      lastKey = key;
      setChatStream(snap);
    };
    refresh();
    return subscribeProjectStreams(projectId, refresh);
  }, [projectId, pathname]);

  if (!project) {
    return <PageLoader />;
  }

  const base = `/app/projects/${projectId}`;
  const onChatTab = pathname?.includes("/chat") ?? false;
  const tabs = [
    { href: base, label: "Обзор" },
    { href: `${base}/chat`, label: "Чат" },
    { href: `${base}/orchestration`, label: "Оркестрация" },
    { href: `${base}/deployments`, label: "Деплои" },
    { href: `${base}/versions`, label: "Файлы" },
    { href: `${base}/logs`, label: "Логи" },
    { href: `${base}/settings`, label: "Настройки" },
  ];

  const guidance = STATUS_GUIDANCE[project.status]?.(project);
  const showStreamBanner = Boolean(chatStream?.loading && chatStream.agentStatus && !onChatTab);
  const TypeIcon = TYPE_ICONS[project.type] ?? Globe;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <header className="space-y-3 border-b border-[var(--ar-border)] pb-4">
        <Link
          href="/app"
          className="inline-flex min-h-9 items-center gap-1.5 rounded-full px-2 text-sm text-[var(--ar-stone)] transition-colors hover:bg-black/[0.04] hover:text-[var(--ar-black)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
        >
          <ArrowLeft size={15} aria-hidden />
          Все проекты
        </Link>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-3">
          <span
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[0.7rem] bg-[image:var(--ar-accent-gradient-soft)] text-[var(--ar-sky)]"
            aria-hidden
          >
            <TypeIcon size={19} />
          </span>
          <div className="min-w-0 flex-1 basis-[12rem]">
            {/* Wraps rather than truncates - a project name is the one thing you must be
                able to read on a 390px screen. */}
            <h1 className="text-xl font-semibold leading-tight tracking-[-0.025em] text-[var(--ar-black)] sm:text-2xl">
              {project.name}
            </h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              {guidance ? (
                <button type="button" onClick={() => setStatusModalOpen(true)}>
                  <ProjectStatusChip status={project.status} className="cursor-pointer" />
                </button>
              ) : (
                <ProjectStatusChip status={project.status} />
              )}
              <span className="rounded-full border border-black/[0.07] bg-black/[0.02] px-2.5 py-1 text-xs text-[var(--ar-stone)]">
                {projectTypeLabel(project.type)}
              </span>
            </div>
          </div>
          {/* Pointless while you are already looking at the chat. */}
          {onChatTab ? null : (
            <Link
              href={`${base}/chat`}
              className="btn-glow inline-flex min-h-10 items-center gap-2 rounded-[0.7rem] px-4 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/40"
            >
              <MessageSquare size={15} aria-hidden />
              Чат
            </Link>
          )}
        </div>
      </header>

      <Tabs items={tabs} sticky />

      {showStreamBanner && chatStream?.agentStatus ? (
        <button
          type="button"
          onClick={() => router.push(`${base}/chat`)}
          className="flex w-full min-h-11 items-center gap-3 rounded-[var(--ar-radius-md)] border border-sky-200 bg-sky-50 px-4 py-2.5 text-left transition hover:bg-sky-100/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ar-sky)]/35"
        >
          <Loader2 size={16} className="shrink-0 animate-spin text-[var(--ar-sky)]" aria-hidden />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-[var(--ar-black)]">
              {chatStream.agentStatus.label}
            </span>
            <span className="block text-xs text-[var(--ar-stone)]">Агент работает — открыть чат</span>
          </span>
          <MessageSquare size={16} className="shrink-0 text-[var(--ar-sky)]" aria-hidden />
        </button>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col">{children}</div>

      {guidance ? (
        <Modal open={statusModalOpen} onClose={() => setStatusModalOpen(false)} title={guidance.title}>
          <div className="space-y-5">
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)]",
                  project.status === "blocked" ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-600"
                )}
              >
                <KeyRound size={18} aria-hidden />
              </span>
              <p className="text-sm leading-7 text-[var(--ar-mist)]">{guidance.body}</p>
            </div>
            {guidance.showSecrets || guidance.showChat || guidance.showHelp ? (
              <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
                {guidance.showChat ? (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setStatusModalOpen(false);
                      router.push(`${base}/chat`);
                    }}
                  >
                    <MessageSquare size={16} />
                    В чат
                  </Button>
                ) : null}
                {guidance.showHelp ? (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setStatusModalOpen(false);
                      router.push(`/help/telegram-token?projectId=${encodeURIComponent(projectId)}`);
                    }}
                  >
                    <BookOpen size={16} />
                    Как получить токен
                  </Button>
                ) : null}
                {guidance.showSecrets ? (
                  <Button
                    variant="accent"
                    onClick={() => {
                      setStatusModalOpen(false);
                      router.push(`${base}/settings#secrets`);
                    }}
                  >
                    <Settings size={16} />
                    В секреты
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>
        </Modal>
      ) : null}
    </div>
  );
}
