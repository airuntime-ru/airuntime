"use client";

import Link from "next/link";
import { useState } from "react";
import { Bot, FolderKanban, MessageSquare, Plus, Rocket } from "lucide-react";

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

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Проекты</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
            Ваши запуски
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--ar-mist)]">
            Создавайте проекты, ведите диалог в чате и следите за деплоями в одном месте.
          </p>
        </div>
        <Button
          variant="accent"
          data-tour="project-create-trigger"
          className="w-full sm:w-auto"
          onClick={() => setCreateOpen(true)}
        >
          <Plus size={16} />
          Новый проект
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { label: "Проекты", value: projects.length, icon: FolderKanban },
          { label: "Задеплоено", value: deployed, icon: Rocket },
        ].map((item) => (
          <Card key={item.label} hover={false}>
            <div className="flex items-center justify-between">
              <p className="text-sm text-[var(--ar-stone)]">{item.label}</p>
              <item.icon size={18} className="text-[var(--ar-sky)]" />
            </div>
            <p className="mt-3 text-3xl font-semibold tabular-nums text-[var(--ar-black)]">{item.value}</p>
          </Card>
        ))}
      </div>

      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {!loading && projects.length === 0 ? (
        <EmptyState
          title="Пока нет проектов"
          description="Создайте первый проект — сразу откроется чат и можно начать работу."
          action={
            <Button variant="accent" onClick={() => setCreateOpen(true)}>
              <Plus size={16} />
              Создать проект
            </Button>
          }
        />
      ) : null}

      <div className="grid gap-3" data-tour="project-list">
        {projects.map((project) => (
          <Card key={project.id} className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-semibold text-[var(--ar-black)]">{project.name}</p>
                <Badge>{project.status}</Badge>
              </div>
              <p className="mt-1 flex items-center gap-1.5 text-sm text-[var(--ar-mist)]">
                {project.type === "telegram_bot" ? <Bot size={14} /> : null}
                {typeLabel(project.type)}
              </p>
              {project.description ? (
                <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-[var(--ar-stone)]">{project.description}</p>
              ) : null}
            </div>
            <Link href={`/app/projects/${project.id}/chat`} className="sm:shrink-0">
              <Button variant="outline" size="sm">
                <MessageSquare size={15} />
                Открыть чат
              </Button>
            </Link>
          </Card>
        ))}
      </div>

      <CreateProjectModal open={createOpen} onClose={() => setCreateOpen(false)} onCreated={refresh} />
    </div>
  );
}
