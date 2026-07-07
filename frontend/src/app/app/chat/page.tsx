"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useProjects } from "@/lib/use-projects";

export default function ChatOverviewPage() {
  const { projects, error, refresh } = useProjects();

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-[var(--ar-cloud)] sm:text-3xl">Чат</h1>
        <Button variant="ghost" size="sm" onClick={refresh}>
          Обновить
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      {projects.length === 0 ? <Card>Выберите проект, чтобы начать чат.</Card> : null}
      {projects.map((project) => (
        <Card key={project.id} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="font-medium text-[var(--ar-cloud)]">{project.name}</p>
            <p className="text-sm text-[var(--ar-stone)]">{project.type}</p>
          </div>
          <Link
            href={`/app/projects/${project.id}/chat`}
            className="text-sm text-[var(--ar-sky)] hover:underline sm:shrink-0"
          >
            Открыть чат
          </Link>
        </Card>
      ))}
    </div>
  );
}
