"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

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
    { href: `${base}/logs`, label: "Логи" },
    { href: `${base}/secrets`, label: "Секреты" },
    { href: `${base}/settings`, label: "Настройки" },
    { href: `${base}/history`, label: "История" },
  ];

  return (
    <div className="space-y-4 sm:space-y-6">
      <div>
        <p className="text-xs text-[var(--ar-stone)] sm:text-sm">{project.type}</p>
        <h1 className="text-2xl font-semibold text-[var(--ar-cloud)] sm:text-3xl">{project.name}</h1>
        <p className="mt-2 text-sm text-[var(--ar-mist)] sm:text-base">
          {project.description || "Описание пока не добавлено."}
        </p>
      </div>
      <Tabs items={tabs} />
      {children}
    </div>
  );
}
