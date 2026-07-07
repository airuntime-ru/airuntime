"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useProjects } from "@/lib/use-projects";

export default function DashboardPage() {
  const { projects, error, refresh } = useProjects();

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-[var(--ar-cloud)] sm:text-3xl">Обзор</h1>
        <Button variant="ghost" onClick={refresh}>
          Обновить
        </Button>
      </div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
        <Card>
          <p className="text-sm text-[var(--ar-stone)]">Проекты</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-[var(--ar-cloud)]">{projects.length}</p>
        </Card>
        <Card>
          <p className="text-sm text-[var(--ar-stone)]">Типы</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--ar-cloud)]">
            {new Set(projects.map((project) => project.type)).size}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-[var(--ar-stone)]">Готовы к деплою</p>
          <p className="mt-2 text-2xl font-semibold text-[var(--ar-cloud)]">
            {projects.filter((project) => project.status === "ready").length}
          </p>
        </Card>
      </div>
    </div>
  );
}
