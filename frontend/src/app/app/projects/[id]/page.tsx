"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ExternalLink, MessageSquare, Play, Settings, Sparkles, Square } from "lucide-react";
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
  const chatHref = `/app/projects/${project.id}/chat`;

  const running = isProjectRunning(project.status);
  const needsConfig = project.status === "needs_configuration";
  const canRun = canStartProject(project.status) && !needsConfig;

  let heading = "Доведите идею до запуска через чат";
  let description =
    "Опишите сценарий в чате, приложите материалы при необходимости - AIRuntime соберёт и задеплоит проект.";
  let primaryAction: React.ReactNode = (
    <Link href={chatHref} className="w-full">
      <Button variant="accent" className="w-full">
        <MessageSquare size={16} />
        Открыть чат
      </Button>
    </Link>
  );
  let secondaryAction: React.ReactNode = null;

  if (running) {
    heading = "Проект в эфире";
    description = "Дальнейшие правки вносите через чат - платформа пересоберёт и перезапустит проект сама.";
    primaryAction = project.deployment_url ? (
      <a href={project.deployment_url} target="_blank" rel="noreferrer" className="w-full">
        <Button variant="accent" className="w-full">
          <ExternalLink size={16} />
          Открыть ссылку
        </Button>
      </a>
    ) : null;
  } else if (needsConfig) {
    heading = "Нужна настройка";
    description = "Заполните недостающие данные в настройках проекта, и запуск продолжится автоматически.";
    primaryAction = (
      <Link href={`/app/projects/${project.id}/settings`} className="w-full">
        <Button variant="accent" className="w-full">
          <Settings size={16} />
          Перейти в настройки
        </Button>
      </Link>
    );
    secondaryAction = (
      <Link href={chatHref} className="w-full">
        <Button variant="outline" className="w-full">
          <MessageSquare size={16} />
          Открыть чат
        </Button>
      </Link>
    );
  } else if (canRun) {
    heading = "Можно запускать";
    description = "Файлы собраны - запустите проект, когда будете готовы.";
    primaryAction = (
      <Button variant="accent" className="w-full" disabled={startDisabled} onClick={onStart}>
        <Play size={16} />
        Запустить
      </Button>
    );
    secondaryAction = (
      <Link href={chatHref} className="w-full">
        <Button variant="outline" className="w-full">
          <MessageSquare size={16} />
          Открыть чат
        </Button>
      </Link>
    );
  }

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

      <div className="grid gap-4 sm:grid-cols-2">
        <Card hover={false}>
          <p className="text-sm text-[var(--ar-stone)]">Статус</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge>{projectStatusLabel(project.status)}</Badge>
            {canStopProject(project.status) ? (
              <Button variant="ghost" size="sm" disabled={actionLoading} onClick={onStop}>
                <Square size={13} />
                Остановить
              </Button>
            ) : null}
          </div>
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
          <h2 className="mt-3 text-2xl font-semibold text-[var(--ar-black)]">{heading}</h2>
          <p className="mt-3 text-sm leading-7 text-[var(--ar-mist)]">{description}</p>
        </div>
        <div className="flex flex-col justify-center gap-2">
          {primaryAction}
          {secondaryAction}
        </div>
      </Card>
    </div>
  );
}
