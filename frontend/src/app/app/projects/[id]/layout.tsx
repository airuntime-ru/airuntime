"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { BookOpen, KeyRound, MessageSquare, Settings } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Tabs } from "@/components/ui/tabs";
import { PageLoader } from "@/components/ui/loader";
import { getProject, type ProjectType } from "@/lib/api";
import { cn } from "@/lib/cn";
import { projectStatusLabel } from "@/lib/project-status";

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
        ? "Файлы бота уже собраны, но запустить его пока нельзя: не хватает токена. Откройте секреты проекта, вставьте TELEGRAM_BOT_TOKEN (его выдаёт @BotFather в Telegram после команды /newbot) и запуск продолжится автоматически."
        : "Проекту не хватает данных для запуска - откройте настройки проекта и заполните то, что запрашивается в разделе «Ключи и токены».",
    showSecrets: true,
    showChat: true,
    showHelp: project.type === "telegram_bot" || project.type === "mixed",
  }),
  blocked: (project) => ({
    title: "Заблокирован модерацией",
    body:
      "Проект остановлен автоматической проверкой безопасности" +
      (project.blocked_reason ? `: ${project.blocked_reason}.` : ".") +
      " Если считаете это ошибкой, напишите в поддержку - решение может принять только администратор.",
  }),
};

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;
  const [project, setProject] = useState<ProjectType | null>(null);
  const [statusModalOpen, setStatusModalOpen] = useState(false);

  useEffect(() => {
    let active = true;
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
    };
  }, [projectId]);

  // Poll while status can change server-side without navigation (deploy in flight, waiting on secrets).
  useEffect(() => {
    if (!projectId) return undefined;
    if (project?.status !== "needs_configuration" && project?.status !== "deploying") {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void getProject(projectId).then(setProject).catch(() => {});
    }, 4000);
    return () => window.clearInterval(timer);
  }, [projectId, project?.status]);

  if (!project) {
    return <PageLoader />;
  }

  const base = `/app/projects/${projectId}`;
  const tabs = [
    { href: base, label: "Обзор" },
    { href: `${base}/chat`, label: "Чат" },
    { href: `${base}/deployments`, label: "Деплои" },
    { href: `${base}/versions`, label: "Файлы" },
    { href: `${base}/logs`, label: "Логи" },
    { href: `${base}/settings`, label: "Настройки" },
  ];

  const guidance = STATUS_GUIDANCE[project.status]?.(project);

  return (
    <div className="space-y-5">
      <header className="relative overflow-hidden rounded-[var(--ar-radius-lg)] border border-black/[0.06] bg-white p-5">
        <div
          className="pointer-events-none absolute -left-16 -top-20 h-56 w-56 rounded-full opacity-[0.12] blur-3xl"
          style={{ background: "var(--ar-accent-gradient)" }}
          aria-hidden
        />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ar-mist)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[image:var(--ar-accent-gradient)]" aria-hidden />
                AIRuntime project
              </span>
              {guidance ? (
                <button type="button" onClick={() => setStatusModalOpen(true)}>
                  <Badge
                    className={cn(
                      "cursor-pointer",
                      project.status === "blocked"
                        ? "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
                        : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
                    )}
                  >
                    {projectStatusLabel(project.status)}
                  </Badge>
                </button>
              ) : (
                <Badge>{projectStatusLabel(project.status)}</Badge>
              )}
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-normal text-[var(--ar-black)] sm:text-5xl">
              {project.name}
            </h1>
          </div>
        </div>
      </header>
      <Tabs items={tabs} />
      {children}

      {guidance ? (
        <Modal
          open={statusModalOpen}
          onClose={() => setStatusModalOpen(false)}
          title={guidance.title}
        >
          <div className="space-y-5">
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)]",
                  project.status === "blocked" ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-600"
                )}
              >
                <KeyRound size={18} />
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
