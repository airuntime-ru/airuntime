"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { PageLoader } from "@/components/ui/loader";
import { getProject, type ProjectType } from "@/lib/api";

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
    { href: `${base}/versions`, label: "Файлы" },
    { href: `${base}/logs`, label: "Логи" },
    { href: `${base}/settings`, label: "Настройки" },
  ];

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
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--ar-accent-gradient)]" aria-hidden />
                AIRuntime project
              </span>
              <Badge>{project.status}</Badge>
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-normal text-[var(--ar-black)] sm:text-5xl">
              {project.name}
            </h1>
          </div>
        </div>
      </header>
      <Tabs items={tabs} />
      {children}
    </div>
  );
}
