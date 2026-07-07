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
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-[var(--ar-cloud)]">Проекты</h1>
        <Button variant="ghost" onClick={refresh}>
          Обновить
        </Button>
      </div>
      <Card className="space-y-3" hover={false}>
        <Input placeholder="Название проекта" value={name} onChange={(event) => setName(event.target.value)} />
        <Textarea placeholder="Описание" value={description} onChange={(event) => setDescription(event.target.value)} />
        <div className="flex gap-2">
          <Button variant={type === "website" ? "default" : "ghost"} onClick={() => setType("website")}>
            Сайт
          </Button>
          <Button variant={type === "telegram_bot" ? "default" : "ghost"} onClick={() => setType("telegram_bot")}>
            Telegram-бот
          </Button>
        </div>
        <Button variant="accent" onClick={onCreate}>
          Создать проект
        </Button>
      </Card>
      {error || createError ? <p className="text-sm text-rose-300">{error || createError}</p> : null}
      {!loading && projects.length === 0 ? (
        <EmptyState title="Пока нет проектов" description="Создайте первый проект выше." />
      ) : null}
      {projects.map((project) => (
        <Card key={project.id} className="flex items-center justify-between">
          <div>
            <p className="font-medium text-[var(--ar-cloud)]">{project.name}</p>
            <p className="text-sm text-[var(--ar-stone)]">
              {project.type} • {project.status}
            </p>
          </div>
          <Link href={`/app/projects/${project.id}`} className="text-sm text-[var(--ar-sky)] hover:underline">
            Открыть
          </Link>
        </Card>
      ))}
    </div>
  );
}
