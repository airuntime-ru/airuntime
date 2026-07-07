"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

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

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">
            {typeLabel(project.type)}
          </p>
          <Badge>{project.status}</Badge>
        </div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
          {project.name}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-[var(--ar-mist)] sm:text-base">
          {project.description || "Описание пока не добавлено. Его можно уточнить в чате проекта."}
        </p>
      </div>
      <Tabs items={tabs} />
      {children}
    </div>
  );
}
