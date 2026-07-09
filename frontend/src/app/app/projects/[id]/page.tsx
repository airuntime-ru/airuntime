"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ExternalLink, MessageSquare, Rocket, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import { getProject, type ProjectType } from "@/lib/api";

export default function ProjectOverviewPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectType | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!params.id) return;
      const row = await getProject(params.id);
      if (active) setProject(row);
    })();
    return () => {
      active = false;
    };
  }, [params.id]);

  if (!project) return <PageLoader />;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card hover={false}>
          <p className="text-sm text-[var(--ar-stone)]">Статус</p>
          <div className="mt-2">
            <Badge>{project.status}</Badge>
          </div>
        </Card>
        <Card hover={false}>
          <p className="text-sm text-[var(--ar-stone)]">Идея</p>
          <p className="mt-2 line-clamp-2 text-sm font-medium leading-6 text-[var(--ar-black)]">
            {project.description || "Опишите задачу в чате"}
          </p>
        </Card>
        <Card hover={false}>
          <p className="text-sm text-[var(--ar-stone)]">Публикация</p>
          <p className="mt-2 break-all text-sm font-medium text-[var(--ar-sky)]">
            {project.deployment_url ?? "Ссылка появится после первого запуска"}
          </p>
        </Card>
      </div>

      <Card hover={false} className="grid gap-5 md:grid-cols-[1fr_0.72fr]">
        <div>
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--ar-cyan)]">
            <Sparkles size={14} />
            Следующее действие
          </p>
          <h2 className="mt-3 text-2xl font-semibold text-[var(--ar-black)]">Доведите идею до запуска через чат</h2>
          <p className="mt-3 text-sm leading-7 text-[var(--ar-mist)]">
            Уточните сценарий, приложите материалы и попросите AIRuntime собрать проект. Деплои покажут, где сейчас находится запуск.
          </p>
        </div>
        <div className="flex flex-col justify-center gap-2">
          <Link href={`/app/projects/${project.id}/chat`} className="w-full">
            <Button variant="accent" className="w-full">
              <MessageSquare size={16} />
              Открыть чат
            </Button>
          </Link>
          <Link href={`/app/projects/${project.id}/deployments`} className="w-full">
            <Button variant="outline" className="w-full">
              <Rocket size={16} />
              Деплои
            </Button>
          </Link>
          {project.deployment_url ? (
            <a href={project.deployment_url} target="_blank" rel="noreferrer" className="w-full">
              <Button variant="outline" className="w-full">
                <ExternalLink size={16} />
                Открыть ссылку
              </Button>
            </a>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
