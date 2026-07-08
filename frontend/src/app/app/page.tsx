"use client";

import Link from "next/link";
import { useState } from "react";
import { Bot, ExternalLink, FolderKanban, MessageSquare, Plus, Rocket } from "lucide-react";

import { CreateProjectModal } from "@/components/app/create-project-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/loader";
import { useProjects } from "@/lib/use-projects";

function typeLabel(type: string) {
  if (type === "telegram_bot") return "Telegram-бот";
  if (type === "website") return "Сайт";
  return type;
}

export default function ProjectsPage() {
  const { projects, error, loading, refresh } = useProjects();
  const [createOpen, setCreateOpen] = useState(false);

  const deployed = projects.filter((project) => Boolean(project.deployment_url)).length;
  const active = projects.filter((project) => project.status === "live" || project.status === "ready").length;

  return (
    <div className="space-y-6">
      <section className="rounded-[var(--ar-radius-sm)] border border-black/10 bg-white p-5 sm:p-7">
        <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
          <div>
            <p className="inline-flex items-center rounded-full border border-black/10 bg-black/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--ar-mist)]">
              AIRuntime
            </p>
            <h1 className="mt-5 max-w-3xl text-[2.35rem] font-semibold leading-[1.04] tracking-normal text-[var(--ar-black)] sm:text-5xl xl:text-6xl">
              Создайте проект и запустите его сегодня
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
              { label: "Готовы к запуску", value: active, icon: Rocket },
              { label: "Опубликовано", value: deployed, icon: Rocket },
            ].map((item) => (
              <div
                key={item.label}
                className="min-h-20 rounded-[var(--ar-radius-sm)] border border-black/10 bg-white p-3 sm:min-h-24 sm:p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[0.62rem] font-semibold uppercase tracking-[0.12em] text-[var(--ar-stone)] sm:text-xs sm:tracking-[0.16em]">{item.label}</p>
                  <item.icon size={17} className="text-[var(--ar-black)]" />
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
          description="Создайте первый проект: после этого сразу откроется чат, где можно описать сайт или Telegram-бота."
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
                <Badge>{project.status}</Badge>
              </div>
              <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-[var(--ar-mist)]">
                {project.type === "telegram_bot" ? <Bot size={14} /> : <ExternalLink size={14} />}
                {typeLabel(project.type)}
              </p>
              {project.description ? (
                <p className="mt-3 line-clamp-2 max-w-3xl text-sm leading-7 text-[var(--ar-stone)]">{project.description}</p>
              ) : (
                <p className="mt-3 text-sm leading-7 text-[var(--ar-stone)]">Откройте чат и уточните задачу для AIRuntime.</p>
              )}
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
