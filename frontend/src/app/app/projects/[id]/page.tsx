"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ExternalLink, MessageSquare, Pause, Play, Rocket, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageLoader } from "@/components/ui/loader";
import {
  getProject,
  getProjectRuntimeLimits,
  startProject,
  stopProject,
  type ProjectRuntimeLimitsType,
  type ProjectType,
} from "@/lib/api";
import {
  canStartProject,
  canStopProject,
  isProjectRunning,
  projectStatusLabel,
} from "@/lib/project-status";

export default function ProjectOverviewPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectType | null>(null);
  const [limits, setLimits] = useState<ProjectRuntimeLimitsType | null>(null);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const loadProject = useCallback(async () => {
    if (!params.id) return;
    const [row, runtimeLimits] = await Promise.all([
      getProject(params.id),
      getProjectRuntimeLimits(),
    ]);
    setProject(row);
    setLimits(runtimeLimits);
    setError("");
  }, [params.id]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await loadProject();
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Не удалось загрузить проект");
      }
    })();
    return () => {
      active = false;
    };
  }, [loadProject]);

  const onStop = async () => {
    if (!project) return;
    setActionLoading(true);
    setError("");
    try {
      setProject(await stopProject(project.id));
      setLimits(await getProjectRuntimeLimits());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось остановить проект");
    } finally {
      setActionLoading(false);
    }
  };

  const onStart = async () => {
    if (!project) return;
    setActionLoading(true);
    setError("");
    try {
      setProject(await startProject(project.id));
      setLimits(await getProjectRuntimeLimits());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось запустить проект");
    } finally {
      setActionLoading(false);
    }
  };

  if (!project) return <PageLoader />;

  const atLimit = limits ? limits.running >= limits.max_running : false;
  const startDisabled = actionLoading || (atLimit && !isProjectRunning(project.status));

  return (
    <div className="space-y-4">
      {limits ? (
        <Card hover={false} className="border-[var(--ar-sky)]/20 bg-[var(--ar-sky)]/5">
          <p className="text-sm text-[var(--ar-mist)]">
            Одновременно запущено:{" "}
            <span className="font-semibold text-[var(--ar-black)]">
              {limits.running} / {limits.max_running}
            </span>
            . Остановите один из активных проектов, чтобы освободить слот.
          </p>
        </Card>
      ) : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card hover={false}>
          <p className="text-sm text-[var(--ar-stone)]">Статус</p>
          <div className="mt-2">
            <Badge>{projectStatusLabel(project.status)}</Badge>
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
            Уточните сценарий, приложите материалы и попросите AIRuntime собрать проект. Управляйте запуском и
            остановкой runtime прямо отсюда.
          </p>
        </div>
        <div className="flex flex-col justify-center gap-2">
          <Link href={`/app/projects/${project.id}/chat`} className="w-full">
            <Button variant="accent" className="w-full">
              <MessageSquare size={16} />
              Открыть чат
            </Button>
          </Link>
          {canStopProject(project.status) ? (
            <Button variant="outline" className="w-full" disabled={actionLoading} onClick={onStop}>
              <Pause size={16} />
              Остановить
            </Button>
          ) : null}
          {canStartProject(project.status) ? (
            <Button variant="outline" className="w-full" disabled={startDisabled} onClick={onStart}>
              <Play size={16} />
              Запустить
            </Button>
          ) : null}
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
