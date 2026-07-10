"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { FolderKanban, MessageSquare, Plus, Rocket } from "lucide-react";

import { CreateProjectModal } from "@/components/app/create-project-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/loader";
import { getProjectRuntimeLimits, type ProjectRuntimeLimitsType } from "@/lib/api";
import { projectStatusLabel } from "@/lib/project-status";
import { useProjects } from "@/lib/use-projects";

export default function ProjectsPage() {
  const { projects, error, loading, refresh } = useProjects();
  const [createOpen, setCreateOpen] = useState(false);
  const [limits, setLimits] = useState<ProjectRuntimeLimitsType | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setLimits(await getProjectRuntimeLimits());
      } catch {
        setLimits(null);
      }
    })();
  }, [projects]);

  const deployed = projects.filter((project) => Boolean(project.deployment_url)).length;
  const running = projects.filter((project) => project.status === "live" || project.status === "deploying").length;

  return (
    <div className="space-y-6">
      <section className="accent-ring relative overflow-hidden rounded-[var(--ar-radius-lg)] border border-black/[0.06] bg-white p-5 sm:p-7">
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full opacity-[0.14] blur-3xl"
          style={{ background: "var(--ar-accent-gradient)" }}
          aria-hidden
        />
        <div className="relative grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
          <div>
            <p className="inline-flex items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--ar-mist)]">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--ar-accent-gradient)]" aria-hidden />
              AIRuntime
            </p>
            <h1 className="mt-5 max-w-3xl text-[2.35rem] font-semibold leading-[1.04] tracking-normal text-[var(--ar-black)] sm:text-5xl xl:text-6xl">
              Создайте <span className="accent-text">проект</span> и запустите его сегодня
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-[var(--ar-mist)]">
              Опишите идею в чате, а AIRuntime соберет и задеплоит рабочую версию.
            </p>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              <Button variant="accent" size="lg" data-tour="project-create-trigger" onClick={() => setCreateOpen(true)}>
                <Plus size={18} />
                Новый проект
              </Button>
              {projects[0] ? (
                <Link href={`/app/projects/${projects[0].id}/chat`}>
                  <Button variant="outline" size="lg" className="w-full sm:w-auto">
                    <MessageSquare size={18} />
                    Продолжить диалог
                  </Button>
                </Link>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 sm:gap-3 lg:grid-cols-1">
            {[
              { label: "Проектов", value: projects.length, icon: FolderKanban },
              {
                label: "Запущено",
                value: limits ? `${limits.running}/${limits.max_running}` : running,
                icon: Rocket,
              },
              { label: "Опубликовано", value: deployed, icon: Rocket },
            ].map((item) => (
              <div
                key={item.label}
                className="min-h-20 rounded-[var(--ar-radius-md)] border border-black/[0.06] bg-white p-3 shadow-[0_8px_22px_rgba(7,20,38,0.045)] sm:min-h-24 sm:p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-[var(--ar-stone)] sm:text-xs sm:tracking-[0.16em]">{item.label}</p>
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--ar-accent-gradient-soft)] text-[var(--ar-sky)]">
                    <item.icon size={13} />
                  </span>
                </div>
                <p className="mt-3 text-2xl font-semibold tabular-nums text-[var(--ar-black)] sm:text-3xl">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      {!loading && projects.length === 0 ? (
        <EmptyState
          title="Здесь пока тихо"
          description="Создайте первый проект: после этого сразу откроется чат, где можно описать, что нужно собрать и запустить."
          action={
            <Button variant="accent" onClick={() => setCreateOpen(true)}>
              <Plus size={16} />
              Начать создание
            </Button>
          }
        />
      ) : null}

      <div className="grid gap-3" data-tour="project-list">
        {projects.map((project) => (
          <Card
            key={project.id}
            className="group grid gap-4 p-4 sm:grid-cols-[1fr_auto] sm:items-center"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-lg font-semibold text-[var(--ar-black)]">{project.name}</p>
                <Badge>{projectStatusLabel(project.status)}</Badge>
              </div>
              <p className="mt-2 text-sm font-medium text-[var(--ar-mist)]">
                {project.deployment_url ?? (project.description || "Откройте чат и опишите задачу")}
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:w-44">
              <Link href={`/app/projects/${project.id}/chat`}>
                <Button variant="accent" size="sm" className="w-full">
                  <MessageSquare size={15} />
                  В чат
                </Button>
              </Link>
              <Link href={`/app/projects/${project.id}`}>
                <Button variant="outline" size="sm" className="w-full">
                  Обзор
                </Button>
              </Link>
            </div>
          </Card>
        ))}
      </div>

      <CreateProjectModal open={createOpen} onClose={() => setCreateOpen(false)} onCreated={refresh} />
    </div>
  );
}
