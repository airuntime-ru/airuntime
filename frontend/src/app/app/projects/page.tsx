"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { createProject } from "@/lib/api";
import { useProjects } from "@/lib/use-projects";

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
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-[var(--ar-cloud)] sm:text-3xl">Проекты</h1>
        <Button variant="ghost" size="sm" onClick={refresh}>
          Обновить
        </Button>
      </div>
      <Card className="space-y-3" hover={false}>
        <Input placeholder="Название проекта" value={name} onChange={(event) => setName(event.target.value)} />
        <Textarea placeholder="Описание" value={description} onChange={(event) => setDescription(event.target.value)} />
        <div className="grid grid-cols-2 gap-2 sm:flex sm:w-auto">
          <Button variant={type === "website" ? "default" : "ghost"} onClick={() => setType("website")}>
            Сайт
          </Button>
          <Button variant={type === "telegram_bot" ? "default" : "ghost"} onClick={() => setType("telegram_bot")}>
            Telegram-бот
          </Button>
        </div>
        <Button variant="accent" className="w-full sm:w-auto" onClick={onCreate}>
          Создать проект
        </Button>
      </Card>
      {error || createError ? <p className="text-sm text-rose-300">{error || createError}</p> : null}
      {!loading && projects.length === 0 ? (
        <EmptyState title="Пока нет проектов" description="Создайте первый проект выше." />
      ) : null}
      {projects.map((project) => (
        <Card key={project.id} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="font-medium text-[var(--ar-cloud)]">{project.name}</p>
            <p className="text-sm text-[var(--ar-stone)]">
              {project.type} • {project.status}
            </p>
          </div>
          <Link
            href={`/app/projects/${project.id}`}
            className="text-sm text-[var(--ar-sky)] hover:underline sm:shrink-0"
          >
            Открыть
          </Link>
        </Card>
      ))}
    </div>
  );
}
