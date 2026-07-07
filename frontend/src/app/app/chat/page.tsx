"use client";

import Link from "next/link";
import { MessageSquare, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/loader";
import { useProjects } from "@/lib/use-projects";

export default function ChatOverviewPage() {
  const { projects, error, refresh } = useProjects();

  return (
    <div className="mx-auto max-w-6xl space-y-5" data-tour="chat-screen">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--ar-sky)]">Чаты</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--ar-black)] sm:text-4xl">
            Выберите проект
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--ar-mist)]">
            У каждого проекта свой контекст, файлы и история диалога.
          </p>
        </div>
        <Button variant="outline" onClick={refresh}>
          <RefreshCw size={16} />
          Обновить
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      {projects.length === 0 ? (
        <EmptyState title="Пока нет проектов" description="Создайте проект, чтобы начать разговор о его сборке." />
      ) : null}
      <div className="grid gap-3">
        {projects.map((project) => (
          <Card key={project.id} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="font-semibold text-[var(--ar-black)]">{project.name}</p>
              <p className="text-sm text-[var(--ar-mist)]">{project.type}</p>
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
