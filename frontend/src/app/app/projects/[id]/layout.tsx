"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Bot, Globe2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { PageLoader } from "@/components/ui/loader";
import { getProject, type ProjectType } from "@/lib/api";

function typeLabel(type: string) {
  if (type === "telegram_bot") return "Telegram-бот";
  if (type === "website") return "Сайт";
  return type;
}

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const [project, setProject] = useState<ProjectType | null>(null);

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

  if (!project) {
    return <PageLoader />;
  }

  const base = `/app/projects/${projectId}`;
  const tabs = [
    { href: base, label: "Обзор" },
    { href: `${base}/chat`, label: "Чат" },
    { href: `${base}/deployments`, label: "Деплои" },
    { href: `${base}/logs`, label: "Логи" },
    { href: `${base}/settings`, label: "Настройки" },
  ];
  const Icon = project.type === "telegram_bot" ? Bot : Globe2;

  return (
    <div className="space-y-5">
      <header className="rounded-[var(--ar-radius-sm)] border border-black/10 bg-white p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-black/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--ar-mist)]">
                <Icon size={14} />
                {typeLabel(project.type)}
              </span>
              <Badge>{project.status}</Badge>
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-normal text-[var(--ar-black)] sm:text-5xl">
              {project.name}
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--ar-mist)] sm:text-base">
              {project.description || "Описание пока не добавлено. Уточните идею в чате проекта, и AIRuntime соберет ее в рабочий запуск."}
            </p>
          </div>
        </div>
      </header>
      <Tabs items={tabs} />
      {children}
    </div>
  );
}
