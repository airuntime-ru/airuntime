"use client";

import Link from "next/link";
import { useState } from "react";
import { Bot, ExternalLink, Globe2, RefreshCw, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { createProject } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useProjects } from "@/lib/use-projects";

const projectTypes = [
  { value: "website" as const, label: "Сайт", icon: Globe2, description: "Лендинг, MVP или веб-инструмент" },
  { value: "telegram_bot" as const, label: "Telegram-бот", icon: Bot, description: "Сценарии, заявки, уведомления" },
];

function typeLabel(type: string) {
  if (type === "telegram_bot") return "Telegram-бот";
  if (type === "website") return "Сайт";
  return type;
}

export default function ProjectsPage() {
  const { projects, error, loading, refresh } = useProjects();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<"telegram_bot" | "website">("website");
  const [createError, setCreateError] = useState("");

  const onCreate = async () => {
    if (!name.trim()) return;
    try {
      await createProject({ type, name, description });
      setName("");
      setDescription("");
      setCreateError("");
      await refresh();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Не удалось создать проект");
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Проекты</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
            Создайте новый запуск
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--ar-mist)]">
            Опишите, что нужно получить. После создания откроется чат проекта, секреты, деплои и история.
          </p>
        </div>
        <Button variant="outline" onClick={refresh}>
          <RefreshCw size={16} />
          Обновить
        </Button>
      </div>

      <Card data-tour="project-create-form" className="grid gap-5 lg:grid-cols-[1fr_0.85fr]" hover={false}>
        <div className="space-y-3">
          <Input placeholder="Название проекта" value={name} onChange={(event) => setName(event.target.value)} />
          <Textarea
            placeholder="Например: лендинг для записи на консультацию с формой заявки и Telegram-уведомлением"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <Button variant="accent" className="w-full sm:w-auto" onClick={onCreate}>
            <Sparkles size={16} />
            Создать проект
          </Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          {projectTypes.map((item) => {
            const active = type === item.value;
            return (
              <button
                key={item.value}
                type="button"
                onClick={() => setType(item.value)}
                className={cn(
                  "rounded-[var(--ar-radius-sm)] border p-4 text-left transition-all",
                  active
                    ? "border-[var(--ar-border-strong)] bg-white shadow-sm shadow-sky-950/5"
                    : "border-[var(--ar-border)] bg-white/55 hover:bg-white"
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-[var(--ar-radius-sm)] bg-sky-50 text-[var(--ar-sky)]">
                    <item.icon size={18} />
                  </span>
                  <span>
                    <span className="block font-semibold text-[var(--ar-black)]">{item.label}</span>
                    <span className="text-sm text-[var(--ar-mist)]">{item.description}</span>
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {error || createError ? <p className="text-sm text-rose-600">{error || createError}</p> : null}
      {!loading && projects.length === 0 ? (
        <EmptyState
          title="Пока нет проектов"
          description="Создайте первый проект выше. С него начнется рабочий чат и история запусков."
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
              <p className="mt-1 text-sm text-[var(--ar-mist)]">{typeLabel(project.type)}</p>
              {project.description ? (
                <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-[var(--ar-stone)]">{project.description}</p>
              ) : null}
            </div>
            <Link href={`/app/projects/${project.id}`} className="sm:shrink-0">
              <Button variant="outline" size="sm">
                Открыть
                <ExternalLink size={15} />
              </Button>
            </Link>
          </Card>
        ))}
      </div>
    </div>
  );
}
