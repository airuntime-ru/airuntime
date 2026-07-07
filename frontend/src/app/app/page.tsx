"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Bot, FolderKanban, Globe2, MessageSquare, Rocket, Sparkles } from "lucide-react";

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
  const router = useRouter();
  const { projects, error, loading, refresh } = useProjects();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState<"telegram_bot" | "website">("website");
  const [createError, setCreateError] = useState("");

  const deployed = projects.filter((project) => Boolean(project.deployment_url)).length;

  const onCreate = async () => {
    if (!name.trim()) return;
    try {
      const project = await createProject({ type, name, description });
      setName("");
      setDescription("");
      setCreateError("");
      await refresh();
      router.push(`/app/projects/${project.id}/chat`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Не удалось создать проект");
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Проекты</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
          Ваши запуски
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--ar-mist)]">
          Создавайте проекты, ведите диалог в чате и следите за деплоями в одном месте.
        </p>
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

      <Card data-tour="project-create-form" className="space-y-5" hover={false}>
        <div>
          <p className="text-sm font-semibold text-[var(--ar-black)]">Новый проект</p>
          <p className="mt-1 text-sm text-[var(--ar-mist)]">Сайт или Telegram-бот — выберите формат запуска</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {projectTypes.map((item) => {
              const active = type === item.value;
              return (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setType(item.value)}
                  className={cn(
                    "flex items-start gap-3 rounded-[var(--ar-radius-sm)] border p-3 text-left transition-all",
                    active
                      ? "border-[var(--ar-sky)] bg-sky-50/80 ring-2 ring-[var(--ar-sky)]/15"
                      : "border-[var(--ar-border)] bg-white/70 hover:border-[var(--ar-border-strong)] hover:bg-white"
                  )}
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--ar-radius-sm)] bg-white text-[var(--ar-sky)] shadow-sm shadow-sky-950/5">
                    <item.icon size={17} />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-[var(--ar-black)]">{item.label}</span>
                    <span className="mt-0.5 block text-xs leading-relaxed text-[var(--ar-mist)]">
                      {item.description}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-4 border-t border-[var(--ar-border)] pt-5">
          <div className="space-y-2">
            <label htmlFor="project-name" className="text-sm font-semibold text-[var(--ar-black)]">
              Название
            </label>
            <Input
              id="project-name"
              placeholder="Например: Лендинг для консультаций"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="project-description" className="text-sm font-semibold text-[var(--ar-black)]">
              Описание
            </label>
            <Textarea
              id="project-description"
              className="min-h-[104px] resize-none"
              rows={4}
              placeholder="Кто пользователь, что должно произойти и какие детали важны"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-[var(--ar-border)] pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[var(--ar-mist)]">После создания сразу откроется чат проекта</p>
          <Button variant="accent" className="w-full sm:w-auto sm:shrink-0" onClick={onCreate} disabled={!name.trim()}>
            <Sparkles size={16} />
            Создать проект
          </Button>
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
            <Link href={`/app/projects/${project.id}/chat`} className="sm:shrink-0">
              <Button variant="outline" size="sm">
                <MessageSquare size={15} />
                Открыть чат
              </Button>
            </Link>
          </Card>
        ))}
      </div>
    </div>
  );
}
